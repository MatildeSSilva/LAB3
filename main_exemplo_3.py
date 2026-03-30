# ============================================================
# LAB3b - µOscilloscope - Versão Final Melhorada
# Funcionalidades: Auto-Set, Trigger, Hold, Freq, Vpp, Email
# ============================================================

import T_Display
import math
import time

# --- Configurações de Ecrã e ADC ---
DISPLAY_W = 240
DISPLAY_H = 135
FATOR_DIVISOR = 1/29.3
ADC_GAIN = 0.00044028
ADC_OFFSET = 0.091455

# --- Variáveis de Controlo Global ---
ganho_v = 15.0      # Pixéis por Volt (ajustado pelo Auto-Set)
hold_mode = False   # Estado do congelamento de ecrã
trigger_on = True   # Estado da estabilização de imagem
pontos_volt = [0.0] * 240
EMAIL = "teu_email@tecnico.ulisboa.pt"

tft = T_Display.TFT()

def converter_v(adc_val):
    """Converte valor bruto do ADC para Tensão Real (V)"""
    v = ADC_GAIN * adc_val + ADC_OFFSET
    return (v - 1) / FATOR_DIVISOR

def process_data():
    """Lê o ADC, faz cálculos e deteta o ponto de Trigger"""
    global pontos_volt
    # Lê 240 pontos em 100ms (ajustável para mudar a escala H)
    buffer_adc = tft.read_adc(240, 100)
    pontos_volt = [converter_v(p) for p in buffer_adc]
    
    v_max = max(pontos_volt)
    v_min = min(pontos_volt)
    vpp = v_max - v_min
    
    # Procura ponto de Trigger (Zero-crossing ascendente)
    start_idx = 0
    if trigger_on:
        for i in range(1, 120):
            if pontos_volt[i-1] < 0 and pontos_volt[i] >= 0:
                start_idx = i
                break
                
    # Cálculo de Frequência (baseado no tempo entre ciclos)
    freq = 0
    for i in range(start_idx + 5, 239):
        if pontos_volt[i-1] < 0 and pontos_volt[i] >= 0:
            periodo_pontos = i - start_idx
            periodo_seg = periodo_pontos * (0.1 / 240) # 100ms / 240 pts
            freq = 1 / periodo_seg
            break
            
    return start_idx, vpp, freq

def update_display(start_idx, vpp, freq):
    """Desenha a interface e a forma de onda"""
    tft.display_set(tft.BLACK, 0, 0, 240, 135)
    
    # Desenha Grelha (Área de sinal: 170px de largura)
    tft.display_write_grid(0, 0, 170, 135, 6, 6, True)
    
    # Desenha a Onda
    for x in range(169):
        idx = start_idx + x
        if idx < 240:
            # Centro do ecrã (67px) - (Tensão * Escala)
            y = int(67 - (pontos_volt[idx] * ganho_v))
            if 0 < y < 135:
                tft.display_pixel(x, y, tft.YELLOW)
                
    # Painel Lateral de Informações
    tft.display_write_str(tft.Arial16, "Vpp:%.1fV" % vpp, 175, 110)
    tft.display_write_str(tft.Arial16, "f:%dHz" % freq, 175, 85)
    
    # Indicadores de Estado
    trg_status = "TRG:ON" if trigger_on else "TRG:OFF"
    run_status = "HOLD" if hold_mode else "RUN"
    tft.display_write_str(tft.Arial16, trg_status, 175, 50)
    tft.display_write_str(tft.Arial16, run_status, 175, 20)
    
    tft.set_wifi_icon(220, 120)

# --- Loop Principal ---
while tft.working():
    but = tft.readButton()

    # BOTÃO 1 CURTO: Auto-Set (Ajusta escala vertical)
    if but == tft.BUTTON1_SHORT:
        hold_mode = False
        _, vpp_now, _ = process_data()
        if vpp_now > 0.1:
            ganho_v = 100.0 / vpp_now # Otimiza para ocupar 100px
        time.sleep(0.1)

    # BOTÃO 1 LONGO: Enviar Email
    elif but == tft.BUTTON1_LONG:
        tft.display_write_str(tft.Arial16, "Enviando...", 10, 10)
        tft.send_mail(pontos_volt, "Dados uOscilloscope", EMAIL)
        time.sleep(0.5)

    # BOTÃO 2 CURTO: Hold / Run
    elif but == tft.BUTTON2_SHORT:
        hold_mode = not hold_mode
        time.sleep(0.1)

    # BOTÃO 2 LONGO: Trigger ON / OFF
    elif but == tft.BUTTON2_LONG:
        trigger_on = not trigger_on
        time.sleep(0.2)

    # Atualização contínua se não estiver em HOLD
    if not hold_mode:
        s_idx, v_pp, f_hz = process_data()
        update_display(s_idx, v_pp, f_hz)