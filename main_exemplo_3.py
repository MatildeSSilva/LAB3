# ============================================================
# LAB3b - Oscilloscope - Versão Simplificada (Sem FFT)
# ============================================================

import T_Display
import math
import gc
import time

# --- Configurações do Display e ADC (Mantidas do teu original) ---
DISPLAY_W = 240
DISPLAY_H = 135
TOP_BAR   = 16
GRID_H    = DISPLAY_H - TOP_BAR
N_POINTS  = 240

ADC_GAIN   = 0.00044028
ADC_OFFSET = 0.091455
FATOR      = 1.0 / 29.3
V_REF      = 1.0

# Escalas Verticais
V_SCALES = [1, 2, 5, 10]
V_IDX    = 2  # Começa em 5V/div

H_INTERVALS = [50, 100, 200, 500]    # matching read_adc() intervals (ms)
H_IDX = 1  # Começa em 100ms/div
# Estado Global
pontos_volt = [0.0] * N_POINTS
tft = T_Display.TFT()

# --- Funções de Conversão e Desenho ---
def read_and_convert(tft):
    global pontos_volt
    interval = H_INTERVALS[H_IDX]
    raw = tft.read_adc(N_POINTS, interval)
    for i in range(N_POINTS):
        pontos_volt[i] = adc_to_volt(raw[i])
    gc.collect()
    return pontos_volt

def adc_to_volt(d):
    v_adc = ADC_GAIN * d + ADC_OFFSET
    return (v_adc - V_REF) / FATOR

def volt_to_pixel_y(v, v_scale):
    v_full = v_scale * 6.0  # 6 divisões verticais
    v_half = v_full / 2.0
    v = max(-v_half, min(v_half, v))
    # Mapeia para a área da grelha (GRID_H = 119)
    return int((v + v_half) / v_full * (GRID_H - 1))

def draw_screen_base():
    """Desenha a base: Fundo, Grelha e Texto de Escala"""
    tft.display_set(tft.BLACK, 0, 0, DISPLAY_W, DISPLAY_H)
    tft.display_write_grid(0, 0, DISPLAY_W, GRID_H, 10, 6, True, tft.GREY1, tft.GREY2)
    
    # Texto da Escala no Topo
    v_text = "%dV/div" % V_SCALES[V_IDX]
    tft.display_write_str(tft.Arial16, v_text, 5, DISPLAY_H - TOP_BAR)
    tft.set_wifi_icon(DISPLAY_W - 16, DISPLAY_H - 16)

def auto_scale():
    """Escolhe a melhor escala V/div (V_IDX) para o sinal atual."""
    global V_IDX
    # Encontra o maior valor (pico) para saber quanto espaço a onda ocupa
    v_max_abs = 0
    for v in pontos_volt:
        if abs(v) > v_max_abs:
            v_max_abs = abs(v)
    
    # O ecrã tem 6 divisões (+3 e -3). 
    # Testamos qual escala (1, 2, 5, 10) acomoda o v_max_abs
    for i in range(len(V_SCALES)):
        if v_max_abs < (V_SCALES[i] * 3):
            V_IDX = i
            break
    else:
        V_IDX = len(V_SCALES) - 1 # Se for muito grande, usa a escala máxima

def full_refresh():
    """Lê ADC e atualiza todo o ecrã"""
    global pontos_volt
    draw_screen_base()
    
    # Leitura (Intervalo fixo de 100ms para estabilidade)
    raw = tft.read_adc(N_POINTS, 100)
    for i in range(N_POINTS):
        pontos_volt[i] = adc_to_volt(raw[i])
    
    # Desenho da Onda
    x_list = list(range(N_POINTS))
    y_list = [volt_to_pixel_y(v, V_SCALES[V_IDX]) for v in pontos_volt]
    tft.display_nline(tft.YELLOW, x_list, y_list)
    
    gc.collect()

# --- Execução Inicial ---
full_refresh()

# --- Loop Principal ---
while tft.working():
    but = tft.readButton()

    if but == tft.NOTHING:
        # Se quiseres que ele atualize continuamente, retira o 'continue' 
        # e coloca o full_refresh() aqui.
        continue

    # BOTÃO 1: Nova Leitura (Refresh manual)
    if but == tft.BUTTON1_SHORT:
        full_refresh()
    
    # Button 1 long -> Nova leitura COM Auto-Set
    if but == tft.BUTTON1_LONG:
        read_and_convert(tft)  # 1. Lê os dados novos
        auto_scale()           # 2. Calcula a melhor escala para esses dados
        full_refresh()         # 3. Desenha tudo com a nova escala
        
    # Button 2 short -> Mantém a mudança manual (opcional)
    elif but == tft.BUTTON2_SHORT:
        V_IDX = (V_IDX + 1) % len(V_SCALES)
        full_refresh()

    # BOTÃO 2: Muda Escala Vertical (Cíclico: 1, 2, 5, 10)
    elif but == tft.BUTTON2_LONG:
        V_IDX = (V_IDX + 1) % len(V_SCALES)
        full_refresh()
        time.sleep(0.1) # Debounce



    