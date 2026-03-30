# ============================================================
# LAB3b - Oscilloscope - Final Version (Messages Top-Right)
# ============================================================

import T_Display
import math
import gc
import time

# --- Configurações do Display e ADC ---
DISPLAY_W = 240
DISPLAY_H = 135
TOP_BAR   = 16
GRID_H    = DISPLAY_H - TOP_BAR
N_POINTS  = 240

ADC_GAIN   = 0.00044028
ADC_OFFSET = 0.091455
FATOR      = 1.0 / 29.3
V_REF      = 1.0

# Escalas
V_SCALES    = [1, 2, 5, 10]
V_IDX       = 2 
H_SCALES    = [5, 10, 20, 50]
H_INTERVALS = [50, 100, 200, 500] 
H_IDX       = 1 

# Estado Global
pontos_volt = [0.0] * N_POINTS
tft = T_Display.TFT()

# --- Funções de Conversão e Cálculos ---

def adc_to_volt(d):
    v_adc = ADC_GAIN * d + ADC_OFFSET
    return (v_adc - V_REF) / FATOR

def read_and_convert(tft):
    global pontos_volt
    interval = H_INTERVALS[H_IDX]
    raw = tft.read_adc(N_POINTS, interval)
    for i in range(N_POINTS):
        pontos_volt[i] = adc_to_volt(raw[i])
    gc.collect()
    return pontos_volt

def get_signal_info():
    """Calcula Vpp e Frequência baseada no valor médio."""
    v_max = max(pontos_volt)
    v_min = min(pontos_volt)
    vpp = v_max - v_min
    v_media = (v_max + v_min) / 2
    
    crossings = []
    for i in range(1, len(pontos_volt)):
        if pontos_volt[i-1] < v_media and pontos_volt[i] >= v_media:
            crossings.append(i)
    
    freq = 0
    if len(crossings) >= 2:
        pts_per_cycle = crossings[1] - crossings[0]
        t_total_sec = H_INTERVALS[H_IDX] / 1000.0
        periodo = pts_per_cycle * (t_total_sec / N_POINTS)
        if periodo > 0: freq = 1.0 / periodo
                
    return vpp, freq

# --- Funções de Auto-Escala ---

def auto_scale_v():
    global V_IDX
    v_max_abs = max([abs(v) for v in pontos_volt])
    for i in range(len(V_SCALES)):
        if v_max_abs < (V_SCALES[i] * 3):
            V_IDX = i
            break
    else: V_IDX = len(V_SCALES) - 1

def auto_scale_h(freq):
    global H_IDX
    if freq <= 0: return
    periodo_ms = (1.0 / freq) * 1000
    tempo_ideal_total = periodo_ms * 2 
    escala_ideal_div = tempo_ideal_total / 10 
    
    best_idx = 0
    min_diff = 9999
    for i, scale in enumerate(H_SCALES):
        diff = abs(scale - escala_ideal_div)
        if diff < min_diff:
            min_diff = diff
            best_idx = i
    H_IDX = best_idx

# --- Funções de Desenho ---

def volt_to_pixel_y(v, v_scale):
    v_full = v_scale * 6.0
    v_half = v_full / 2.0
    v = max(-v_half, min(v_half, v))
    return int((v + v_half) / v_full * (GRID_H - 1))

def draw_screen_base():
    tft.display_set(tft.BLACK, 0, 0, DISPLAY_W, DISPLAY_H)
    tft.display_write_grid(0, 0, DISPLAY_W, GRID_H, 10, 6, True, tft.GREY1, tft.GREY2)
    
    # Escalas no topo (esquerda)
    info = "%dV/div  %dms/div" % (V_SCALES[V_IDX], H_SCALES[H_IDX])
    tft.display_write_str(tft.Arial16, info, 5, DISPLAY_H - TOP_BAR)
    tft.set_wifi_icon(DISPLAY_W - 16, DISPLAY_H - 16)

def full_refresh(msg="", color=0):
    draw_screen_base()
    
    # Desenhar Onda Amarela
    x_list = list(range(N_POINTS))
    y_list = [volt_to_pixel_y(v, V_SCALES[V_IDX]) for v in pontos_volt]
    tft.display_nline(tft.YELLOW, x_list, y_list)
    
    # MENSAGENS NO CANTO SUPERIOR DIREITO (x=140, y=119)
    # y=119 é a base da barra de topo (TOP_BAR)
    if msg:
        tft.display_write_str(tft.Arial16, msg, 120, DISPLAY_H - TOP_BAR, color)
    
    gc.collect()

# --- Execução Inicial ---
read_and_convert(tft)
full_refresh()

# --- Loop Principal ---
while tft.working():
    but = tft.readButton()

    if but == tft.NOTHING:
        continue

    # BOTÃO 1 LONGO: AUTO-SCALE V e H
    if but == tft.BUTTON1_LONG:
        full_refresh("AUTO ON", tft.GREEN)
        time.sleep(0.4)
        
        read_and_convert(tft)
        vpp, freq = get_signal_info()
        
        auto_scale_v()
        auto_scale_h(freq)
        
        read_and_convert(tft)
        full_refresh()

    # BOTÃO 1 CURTO: Refresh + Alerta
    elif but == tft.BUTTON1_SHORT:
        read_and_convert(tft)
        limite = V_SCALES[V_IDX] * 3
        if max(pontos_volt) > limite or min(pontos_volt) < -limite:
            full_refresh("Scale", tft.RED) # Abreviação para caber melhor
        else:
            full_refresh()

    # BOTÃO 2 CURTO: Manual V_IDX
    elif but == tft.BUTTON2_SHORT:
        V_IDX = (V_IDX + 1) % len(V_SCALES)
        full_refresh()

    # BOTÃO 2 LONGO: Manual H_IDX
    elif but == tft.BUTTON2_LONG:
        H_IDX = (H_IDX + 1) % len(H_SCALES)
        read_and_convert(tft) 
        full_refresh()