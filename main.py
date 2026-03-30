# ============================================================
# LAB3b - Oscilloscope through an embedded system
# main.py
# ============================================================

from time import time

import T_Display
import arial_16
import math
import gc

# ------------------------------------------------------------
# DISPLAY DIMENSIONS
# ------------------------------------------------------------
DISPLAY_W = 240         # Total display width in pixels
DISPLAY_H = 135         # Total display height in pixels
TOP_BAR   = 16          # Height of the top text bar (scales + WiFi)
GRID_H    = DISPLAY_H - TOP_BAR   # Grid height = 119 pixels
GRID_W    = DISPLAY_W              # Grid width  = 240 pixels
GRID_Y0   = 0                      # Grid starts at y=0 (bottom of grid area)

# Number of grid divisions
N_DIV_H = 10            # 10 horizontal divisions
N_DIV_V = 6             # 6 vertical divisions

# Number of ADC samples per reading
N_POINTS = 240

# ------------------------------------------------------------
# ADC CONVERSION PARAMETERS (before calibration)
# Formula: V_ADC = 0.00044028 * D + 0.091455
# These two constants are updated after calibration in the lab
# ------------------------------------------------------------
ADC_GAIN   =  0.00044028   # Volts per ADC count
ADC_OFFSET =  0.091455     # Offset in Volts

# Resistive divider factor (Q1 conducting, Q2 off -> Factor2)
# Allows reading voltages between -29.3V and +29.3V
FATOR = 1.0 / 29.3

# Reference voltage subtracted (negative terminal connected to 1V)
V_REF = 1.0

# ------------------------------------------------------------
# VERTICAL SCALES  [V/div]
# The grid has 6 vertical divisions, centre = 0V
# So full range = scale * 6, half range = scale * 3
# ------------------------------------------------------------
V_SCALES  = [1, 2, 5, 10]    # available V/div values
V_IDX     = 2                 # startup index -> 5 V/div

# ------------------------------------------------------------
# HORIZONTAL SCALES  [ms/div]
# The grid has 10 horizontal divisions
# Total time = scale * 10  (ms)
# read_adc() only accepts: 50, 100, 200, 500 ms
# We pick the closest allowed interval for each scale
# ------------------------------------------------------------
H_SCALES  = [5, 10, 20, 50]          # available ms/div values
H_INTERVALS = [50, 100, 200, 500]    # matching read_adc() intervals (ms)
H_IDX     = 1                        # startup index -> 10 ms/div

# ------------------------------------------------------------
# GLOBAL STATE
# pontos_volt  : last voltage reading (240 floats), used for DFT
# modo_fft     : True when showing frequency spectrum
# ------------------------------------------------------------
pontos_volt = [0.0] * N_POINTS
modo_fft    = False


# ============================================================
# SECTION 2 - CONVERSION AND DRAWING
# ============================================================

def adc_to_volt(d):
    """Convert a raw ADC value (0-4095) to input voltage in Volts.
    Step 1: ADC count -> V_ADC  (linear fit from calibration)
    Step 2: subtract the 1V reference
    Step 3: divide by the resistive divider factor
    """
    v_adc = ADC_GAIN * d + ADC_OFFSET   # voltage at the ADC pin
    v_in  = (v_adc - V_REF) / FATOR     # actual input voltage
    return v_in


def volt_to_pixel_y(v, v_scale):
    """Convert a voltage value to a y pixel coordinate on the grid.

    The grid has 6 vertical divisions. With centre = 0V:
      top    of grid ->  +v_scale * 3  Volts  -> y = GRID_H - 1 = 118
      centre of grid ->   0 V          -> y = GRID_H / 2 ~ 59
      bottom of grid ->  -v_scale * 3  Volts  -> y = 0

    In the TFT coordinate system y=0 is at the BOTTOM of the screen,
    so a higher voltage maps to a LARGER y value (closer to top).
    """
    v_full  = v_scale * N_DIV_V          # full vertical range in Volts
    v_half  = v_full / 2.0               # half range (= top voltage)

    # Clamp voltage to the visible range
    v = max(-v_half, min(v_half, v))

    # Map: v = +v_half -> y = GRID_H - 1 (top of grid)
    #      v = -v_half -> y = 0           (bottom of grid)
    pixel_y = int((v + v_half) / v_full * (GRID_H - 1))

    # Keep within grid bounds
    pixel_y = max(0, min(GRID_H - 1, pixel_y))
    return pixel_y


def draw_waveform(tft, volts, v_scale):
    """Draw the waveform on the grid.
    volts  : list of 240 voltage values
    v_scale: current V/div setting
    Maps each sample index (0-239) to an x pixel (0-239)
    and each voltage to a y pixel using volt_to_pixel_y().
    """
    x_list = []
    y_list = []
    for i in range(N_POINTS):
        x_list.append(i)                          # x = sample index (0-239)
        y_list.append(volt_to_pixel_y(volts[i], v_scale))

    tft.display_nline(tft.YELLOW, x_list, y_list)


def read_and_convert(tft):
    """Read 240 ADC samples, convert to volts, store in pontos_volt.
    Returns the filled list.
    Uses the current horizontal scale to pick the read_adc() interval.
    """
    global pontos_volt
    interval = H_INTERVALS[H_IDX]                      # e.g. 100 ms
    raw = tft.read_adc(N_POINTS, interval)             # list of 240 ints

    for i in range(N_POINTS):
        pontos_volt[i] = adc_to_volt(raw[i])

    gc.collect()   # free memory on the IoT module
    return pontos_volt


# ============================================================
# SECTION 3 - DISPLAY SETUP
# ============================================================

def draw_screen(tft, fft_mode=False):
    """Clear the display, draw grid, scale text and WiFi icon.
    fft_mode=False -> time domain grid (with centre lines)
    fft_mode=True  -> frequency domain grid (no centre lines)
    """
    # Step 1: clear entire display to black
    tft.display_set(tft.BLACK, 0, 0, DISPLAY_W, DISPLAY_H)

    # Step 2: draw the grid
    # Grid occupies x=0..239, y=0..118 (119 pixels tall, bottom of display)
    # Top bar (text + WiFi) occupies y=119..134
    # Centre lines shown only in time domain mode
    tft.display_write_grid(0, 0, GRID_W, GRID_H,
                           N_DIV_H, N_DIV_V,
                           not fft_mode,       # centre lines on/off
                           tft.GREY1, tft.GREY2)

    # Step 3: write scale information in the top bar
    draw_scales_text(tft, fft_mode)

    # Step 4: WiFi icon - top right corner (16x16 pixels)
    tft.set_wifi_icon(DISPLAY_W - 16, DISPLAY_H - 16)


def str_pixel_width(text):
    """Return the total pixel width of a string using the Arial16 font."""
    total = 0
    for ch in text:
        _, _, w = arial_16.get_ch(ch)
        total += w
    return total


def draw_scales_text(tft, fft_mode=False):
    """Write current scale values in the 16-pixel top bar.
    Layout: V text at left | ms (or Hz) text centred | WiFi icon at right
    """
    # Clear only the top bar area (leave 16px on right for WiFi icon)
    tft.display_set(tft.BLACK, 0, DISPLAY_H - TOP_BAR, DISPLAY_W - 16, TOP_BAR)

    v_scale = V_SCALES[V_IDX]
    h_scale = H_SCALES[H_IDX]

    if not fft_mode:
        v_str = "%dV/" % v_scale
        h_str = "%dms/" % h_scale
    else:
        fs = N_POINTS / (H_INTERVALS[H_IDX] / 1000.0)
        hz_per_div = (fs / 2.0) / N_DIV_H
        v_fft = v_scale / 2.0
        if v_fft == int(v_fft):
            v_str = "%dV/" % int(v_fft)
        else:
            v_str = "%.1fV/" % v_fft
        if hz_per_div == int(hz_per_div):
            h_str = "%dHz/" % int(hz_per_div)
        else:
            h_str = "%.0fHz/" % hz_per_div

    bar_y = DISPLAY_H - TOP_BAR   # top y of the bar in display coords

    # Left: V text
    tft.display_write_str(tft.Arial16, v_str, 2, bar_y)

    # Centre: ms/Hz text  (centred in the area left of the WiFi icon)
    usable_w = DISPLAY_W - 16          # pixels available (excluding WiFi)
    h_w = str_pixel_width(h_str)
    h_x = (usable_w - h_w) // 2
    tft.display_write_str(tft.Arial16, h_str, h_x, bar_y)


# ============================================================
# SECTION 4 - DFT AND EMAIL
# ============================================================

def compute_dft(signal):
    """Compute the single-sided normalised DFT spectrum (Xss).

    The lab guide defines:
      Xk = sum_{n=0}^{N-1} x_n * [cos(2pi*k*n/N) - j*sin(2pi*k*n/N)]

    Then the single-sided spectrum Xss:
      Xss[0]       = |X0| / N               (DC)
      Xss[k]       = 2*|Xk| / N   0 < k < N/2
      Xss[N/2]     = |X_{N/2}| / N          (Nyquist)

    Returns a list of N/2+1 values (121 values for N=240).
    No numpy allowed - computed manually using math module.
    """
    N = len(signal)
    half = N // 2
    xss = [0.0] * (half + 1)

    for k in range(half + 1):
        re = 0.0
        im = 0.0
        for n in range(N):
            angle = 2.0 * math.pi * k * n / N
            re += signal[n] * math.cos(angle)
            im -= signal[n] * math.sin(angle)
        mag = math.sqrt(re * re + im * im)
        if k == 0 or k == half:
            xss[k] = mag / N
        else:
            xss[k] = 2.0 * mag / N

    gc.collect()
    return xss   # 121 values


def draw_fft(tft, xss, v_scale):
    """Draw the FFT spectrum on the grid.

    The spectrum has N/2+1 = 121 values but the display is 240 pixels wide.
    Per the lab guide, pixels are paired: P0=P1=Xss0, P2=P3=Xss1 ...
    The last point (k=N/2, Nyquist) is ignored.

    Vertical mapping: spectrum is always >= 0.
      top    of grid -> v_scale * 3  (double the time-domain half-range)
      bottom of grid -> 0 V
    """
    N     = N_POINTS
    half  = N // 2
    v_fft_max = v_scale * N_DIV_V / 2.0   # top of FFT vertical range

    x_list = []
    y_list = []

    for k in range(half):                  # 0..119, ignore last (Nyquist)
        val = xss[k]
        # Clamp to visible range
        val = min(val, v_fft_max)

        # Map amplitude to pixel y: 0 at bottom (y=0), max at top (y=GRID_H-1)
        pixel_y = int(val / v_fft_max * (GRID_H - 1))
        pixel_y = max(0, min(GRID_H - 1, pixel_y))

        # Each spectrum value maps to 2 pixels (pixel doubling)
        x_list.append(2 * k)
        y_list.append(pixel_y)
        x_list.append(2 * k + 1)
        y_list.append(pixel_y)

    tft.display_nline(tft.CYAN, x_list, y_list)
    gc.collect()


def send_email(tft, volts, h_idx, address):
    """Send voltage data by email as CSV with statistics.
    Two columns: time (s) and voltage (V).
    Body includes Vmax, Vmin, Vav, Vrms.
    """
    interval_s = H_INTERVALS[h_idx] / 1000.0    # total interval in seconds
    delta_t    = interval_s / N_POINTS           # time between samples

    # Compute statistics
    vmax = volts[0]
    vmin = volts[0]
    vsum = 0.0
    vsum2 = 0.0
    for v in volts:
        if v > vmax: vmax = v
        if v < vmin: vmin = v
        vsum  += v
        vsum2 += v * v
    vav  = vsum  / N_POINTS
    vrms = math.sqrt(vsum2 / N_POINTS)

    body = "Vmax=%.3fV Vmin=%.3fV Vav=%.3fV Vrms=%.3fV" % (vmax, vmin, vav, vrms)

    tft.send_mail(delta_t, volts, body, address)
    gc.collect()

# ============================================================
# SECTION 5 - EXTRAS: AUTO-SCALE AND FULL REFRESH
# ============================================================

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
# ============================================================
# SECTION 6 - MAIN PROGRAM
# ============================================================

# --- Your email address for sending data from the IoT module ---
EMAIL = "margarida.sebastiao@tecnico.ulisboa.pt"

# Instantiate the TFT object (connects to display + buttons)
tft = T_Display.TFT()

# Global scale indices (modified by buttons)
V_IDX = 2    # 5 V/div at startup
H_IDX = 1    # 10 ms/div at startup

def full_refresh():
    """Full cycle: draw screen, read ADC, draw waveform."""
    global pontos_volt, modo_fft
    modo_fft = False
    draw_screen(tft, fft_mode=False)
    read_and_convert(tft)
    draw_waveform(tft, pontos_volt, V_SCALES[V_IDX])

# --- Initial reading on startup ---
full_refresh()

# --- Main loop ---
while tft.working():
    but = tft.readButton()

    if but == tft.NOTHING:
        continue

    # Button 1 short -> new waveform reading
    if but == tft.BUTTON1_SHORT:
        read_and_convert(tft)
        limite = V_SCALES[V_IDX] * 3
        if max(pontos_volt) > limite or min(pontos_volt) < -limite:
            full_refresh("Scale", tft.RED) # Abreviação para caber melhor
        else:
            full_refresh()

    # Button 1 long -> send email with current data
    elif but == tft.BUTTON1_LONG:
        send_email(tft, pontos_volt, H_IDX, EMAIL)

    # Button 2 short -> cycle vertical scale up (circular)
    elif but == tft.BUTTON2_SHORT:
        V_IDX = (V_IDX + 1) % len(V_SCALES)
        full_refresh()

    # Button 2 long -> cycle horizontal scale up (circular)
    elif but == tft.BUTTON2_LONG:
        H_IDX = (H_IDX + 1) % len(H_SCALES)
        full_refresh()

    # Button 2 double click -> show FFT spectrum of last reading
    elif but == tft.BUTTON2_DCLICK:
        modo_fft = True
        draw_screen(tft, fft_mode=True)
        xss = compute_dft(pontos_volt)
        draw_fft(tft, xss, V_SCALES[V_IDX])
        del xss
        gc.collect()

    elif but == tft.BUTTON1_TCLICK:
        full_refresh("AUTO ON", tft.GREEN)
        time.sleep(0.4)
        
        read_and_convert(tft)
        vpp, freq = get_signal_info()
        
        auto_scale_v()
        auto_scale_h(freq)
        
        read_and_convert(tft)
        full_refresh()