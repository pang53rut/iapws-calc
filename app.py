# app.py
from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS
import math
from flasgger import Swagger

app = Flask(__name__)
CORS(app)
Swagger(app)

# ------------------ Helpers / Safety wrappers ------------------

def safe_iapws(P=None, T=None, x=None):
    """
    Try to call IAPWS97 with given arguments. Return instance or None if out of range.
    Prefer explicit argument combinations: (P,T), (P,x), (T,x).
    """ 
    # 1. Tentukan kombinasi argumen yang valid
    if P is not None and T is not None:
        kwargs = {"P":P, "T":T,}    
    elif P is not None and x is not None:
        kwargs = {"P":P, "x":x,}
    elif T is not None and x is not None:
        kwargs = {"T":T, "x":x,}
    elif P is not None:
        kwargs = {"P":P,"x":0}
    elif T is not None:
        kwargs = {"T":T,"x":0}
    else:
        return None #input tidak cukup

    #2. lindungi pemanggilan library
    try:
        return IAPWS97(**kwargs)
    except Exception:
        return None

def jsonify_error(msg, code=400):
    payload = {"error": msg}
    return jsonify(payload), code


def parse_float(s):
    try:
        return float(s)
    except Exception:
        return None


# Format state for output
def format_state(state):
    # state is IAPWS97 or mixed pseudo object (with attributes)
    def safe(attr, fmt=lambda x: x):
        v = getattr(state, attr, None)
        try:
            return fmt(v) if v is not None else "—"
        except Exception:
            return "—"

    # convert to human-friendly
    return {
        "Temperature (°C)": round(state.T - 273.15, 2) if getattr(state, "T", None) is not None else "—",
        "Pressure (MPa)": round(state.P, 5) if getattr(state, "P", None) is not None else "—",
        "Pressure (bar abs)": round(state.P * 10, 4) if getattr(state, "P", None) is not None else "—",
        "Pressure (bar g)": round(state.P * 10 - 1.01325, 4) if getattr(state, "P", None) is not None else "—",
        "Specific Volume (m³/kg)": round(getattr(state, "v", None), 6) if getattr(state, "v", None) is not None else "—",
        "Density (kg/m³)": round(1 / state.v, 3) if getattr(state, "v", None) else "—",
        "Enthalpy (kJ/kg)": round(getattr(state, "h", None), 2) if getattr(state, "h", None) is not None else "—",
        "Internal energy (kJ/kg)": round(getattr(state, "u", None), 2) if getattr(state, "u", None) is not None else "—",
        "Entropy (kJ/kg·K)": round(getattr(state, "s", None), 4) if getattr(state, "s", None) is not None else "—",
        "Cp (kJ/kg·°C)": round(getattr(state, "cp", None), 3) if getattr(state, "cp", None) is not None else "—",
        "Cv (kJ/kg·°C)": round(getattr(state, "cv", None), 3) if getattr(state, "cv", None) is not None else "—",
        "Sound speed (m/s)": round(getattr(state, "w", None), 2) if getattr(state, "w", None) is not None else "—",
        "Dynamic viscosity (Pa·s)": round(getattr(state, "mu", None), 8) if getattr(state, "mu", None) is not None else "—",
        "Kinematic viscosity (m²/s)": round(getattr(state, "mu", None) * getattr(state, "v", 1), 9) if getattr(state, "mu", None) is not None and getattr(state, "v", None) is not None else "—",
        "Thermal conductivity (W/m·K)": round(getattr(state, "k", None), 5) if getattr(state, "k", None) is not None else "—"
    }


# Interpolate mix properties for two-phase
def make_mixture_from_quality(P, vf, vg, hf, hg, sf, sg, uf, ug, x):
    class Mix: pass
    ms = Mix()
    ms.P = P
    ms.T = IAPWS97(P=P, x=0).T  # saturated temperature (K) - use saturated liquid's T
    ms.v = vf + x * (vg - vf)
    ms.h = hf + x * (hg - hf)
    ms.s = sf + x * (sg - sf)
    ms.u = uf + x * (ug - uf)
    # best-effort fill others (use saturated liquid attributes where available)
    sat_liq = IAPWS97(P=P, x=0)
    ms.cp = getattr(sat_liq, "cp", None)
    ms.cv = getattr(sat_liq, "cv", None)
    ms.k = getattr(sat_liq, "k", None)
    ms.mu = getattr(sat_liq, "mu", None)
    ms.w = getattr(sat_liq, "w", None)
    return ms


# ------------------ Main API ------------------

@app.route('/')
def home():
    return "✅ IAPWS Steam API — extended, safe modes: P, T, PT, PH, PS, TH, TS, PV, TV, PU, TU, PX, TX"


@app.route('/api/steam', methods=['GET'])
def steam_properties():
    """
    Steam Properties API (IAPWS IF97)
    ---
    tags:
      - Steam Tables

    parameters:
      - name: input
        in: query
        type: string
        required: true
        description: |
          Calculation mode:
          
          **Saturation**
          - P  : Saturation by Pressure
          - T  : Saturation by Temperature
          
          **Two-Property**
          - PT : Pressure & Temperature
          - PH : Pressure & Enthalpy
          - PS : Pressure & Entropy
          - PV : Pressure & Specific Volume
          - PU : Pressure & Internal Energy
          
          **Quality-based**
          - PX : Pressure & Steam Quality
          - TX : Temperature & Steam Quality

      - name: pressure
        in: query
        type: number
        description: |
          Pressure **(bar abs)**  
          Required for: P, PT, PH, PS, PV, PU, PX

      - name: temperature
        in: query
        type: number
        description: |
          Temperature **(°C)**  
          Required for: T, PT, TX

      - name: enthalpy
        in: query
        type: number
        description: |
          Enthalpy **(kJ/kg)**  
          Required for: PH

      - name: entropy
        in: query
        type: number
        description: |
          Entropy **(kJ/kg·K)**  
          Required for: PS

      - name: v
        in: query
        type: number
        description: |
          Specific volume **(m³/kg)**  
          Required for: PV

      - name: u
        in: query
        type: number
        description: |
          Internal energy **(kJ/kg)**  
          Required for: PU

      - name: x
        in: query
        type: number
        description: |
          Steam quality **(%)**  
          Range: 0–100  
          Required for: PX, TX

    responses:
      200:
        description: |
          Successful response.  
          Returns steam thermodynamic properties based on selected mode.

        examples:
          application/json:
            Pressure & Temperature:
              Temperature (°C): 350
              Pressure (MPa): 1.0
              Pressure (bar abs): 10
              Enthalpy (kJ/kg): 3158.16
              Entropy (kJ/kg·K): 7.3028
              Specific Volume (m³/kg): 0.2825

      400:
        description: Invalid or missing parameters

      500:
        description: Internal server error
    """
    input_type = request.args.get('input', '').upper()
    value = request.args.get('value')
    pressure = request.args.get('pressure')
    temperature = request.args.get('temperature')
    enthalpy = request.args.get('enthalpy')
    entropy = request.args.get('entropy')

    # --- Saturation mode: P ---
    if input_type == 'P':
        # ambil pressure (utama), fallback ke value (legacy)
        val_raw = pressure or request.args.get('value')
        if not val_raw:
            return jsonify_error("Missing pressure for P mode")

        val = parse_float(val_raw)
        if val is None:
            return jsonify_error("Invalid numeric pressure")

        # pressure dalam bar abs → MPa
        P = val / 10.0

        sat_liq = safe_iapws(P=P, x=0)
        sat_vap = safe_iapws(P=P, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Pressure out of valid IAPWS97 range")

        return jsonify({
            "Saturated Liquid": {
                "Temperature (°C)": round(sat_liq.T - 273.15, 2),
                "Pressure (MPa)": round(sat_liq.P, 5),
                "Pressure (bar abs)": round(sat_liq.P * 10, 4),
                "Pressure (bar g)": round(sat_liq.P * 10 - 1.01325, 4),
                "Enthalpy (kJ/kg)": round(sat_liq.h, 2),
                "Entropy (kJ/kg·K)": round(sat_liq.s, 4),
                "Internal Energy (kJ/kg)": round(sat_liq.u, 2),
                "Specific Volume (m³/kg)": round(sat_liq.v, 6),
                "Density (kg/m³)": round(1 / sat_liq.v, 2),
                "Dynamic Viscosity (Pa·s)": round(sat_liq.mu, 6),
                "Kinematic Viscosity (m²/s)": round(sat_liq.mu * sat_liq.v, 9),
                "X Quality (%)": 0.0
            },
            "Saturated Vapor": {
                "Temperature (°C)": round(sat_vap.T - 273.15, 2),
                "Pressure (MPa)": round(sat_vap.P, 5),
                "Pressure (bar abs)": round(sat_vap.P * 10, 4),
                "Pressure (bar g)": round(sat_vap.P * 10 - 1.01325, 4),
                "Enthalpy (kJ/kg)": round(sat_vap.h, 2),
                "Entropy (kJ/kg·K)": round(sat_vap.s, 4),
                "Internal Energy (kJ/kg)": round(sat_vap.u, 2),
                "Specific Volume (m³/kg)": round(sat_vap.v, 6),
                "Density (kg/m³)": round(1 / sat_vap.v, 2),
                "Dynamic Viscosity (Pa·s)": round(sat_vap.mu, 6),
                "Kinematic Viscosity (m²/s)": round(sat_vap.mu * sat_vap.v, 9),
                "X Quality (%)": 100.0
            }
        })
    # --- Saturation mode: T ---
    if input_type == 'T':
        # ambil temperature (utama), fallback ke value (legacy)
        val_raw = temperature or request.args.get('value')
        if not val_raw:
            return jsonify_error("Missing temperature for T mode")

        val = parse_float(val_raw)
        if val is None:
            return jsonify_error("Invalid numeric temperature")

        T_C = val
        if T_C < -273.15 or T_C > 2000:
            return jsonify_error("Temperature out of expected bounds")

        T = T_C + 273.15

        sat_liq = safe_iapws(T=T, x=0)
        sat_vap = safe_iapws(T=T, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Temperature out of valid IAPWS97 range")

        return jsonify({
            "Saturated Liquid": {
                "Temperature (°C)": round(sat_liq.T - 273.15, 2),
                "Pressure (MPa)": round(sat_liq.P, 5),
                "Pressure (bar abs)": round(sat_liq.P * 10, 4),
                "Pressure (bar g)": round(sat_liq.P * 10 - 1.01325, 4),
                "Enthalpy (kJ/kg)": round(sat_liq.h, 2),
                "Entropy (kJ/kg·K)": round(sat_liq.s, 4),
                "Internal Energy (kJ/kg)": round(sat_liq.u, 2),
                "Specific Volume (m³/kg)": round(sat_liq.v, 6),
                "Density (kg/m³)": round(1 / sat_liq.v, 2),
                "Dynamic Viscosity (Pa·s)": round(sat_liq.mu, 6),
                "Kinematic Viscosity (m²/s)": round(sat_liq.mu * sat_liq.v, 9),
                "X Quality (%)": 0.0
            },
            "Saturated Vapor": {
                "Temperature (°C)": round(sat_vap.T - 273.15, 2),
                "Pressure (MPa)": round(sat_vap.P, 5),
                "Pressure (bar abs)": round(sat_vap.P * 10, 4),
                "Pressure (bar g)": round(sat_vap.P * 10 - 1.01325, 4),
                "Enthalpy (kJ/kg)": round(sat_vap.h, 2),
                "Entropy (kJ/kg·K)": round(sat_vap.s, 4),
                "Internal Energy (kJ/kg)": round(sat_vap.u, 2),
                "Specific Volume (m³/kg)": round(sat_vap.v, 6),
                "Density (kg/m³)": round(1 / sat_vap.v, 2),
                "Dynamic Viscosity (Pa·s)": round(sat_vap.mu, 6),
                "Kinematic Viscosity (m²/s)": round(sat_vap.mu * sat_vap.v, 9),
                "X Quality (%)": 100.0
            }
        })

    # --- Two-property mode: P + T ---
    if input_type == 'PT':
        if not pressure or not temperature:
            return jsonify_error("Missing pressure or temperature for PT mode")

        P_bar = parse_float(pressure)
        T_C = parse_float(temperature)

        if P_bar is None or T_C is None:
            return jsonify_error("Invalid numeric pressure or temperature")

        # convert units
        P = P_bar / 10.0        # bar abs → MPa
        T = T_C + 273.15        # °C → K

        st = safe_iapws(P=P, T=T)
        if st is None:
            return jsonify_error("PT state out of IAPWS97 valid range")

        return jsonify({
            "Pressure & Temperature": format_state(st)
        })

    # --- Two-property mode: P + H ---
    if input_type == 'PH':
        if not pressure or not enthalpy:
            return jsonify_error("Missing pressure or enthalpy for PH mode")

        P_bar = parse_float(pressure)
        H = parse_float(enthalpy)

        if P_bar is None or H is None:
            return jsonify_error("Invalid numeric pressure or enthalpy")

        # convert units
        P = P_bar / 10.0  # bar abs → MPa

        # cari state berdasarkan P & h
        st = find_state_by_property("h", P, H)
        if st is None:
            return jsonify_error("PH: cannot find state for given P & h (out of range)")

        # info steam (quality & sat values)
        sat_liq = safe_iapws(P=P, x=0)
        sat_vap = safe_iapws(P=P, x=1)

        hf, hg = sat_liq.h, sat_vap.h
        if hf <= H <= hg:
            x = (H - hf) / (hg - hf) if hg != hf else 0.0
        elif H < hf:
            x = 0.0
        else:
            x = 1.0

        return jsonify({
            "Pressure & Enthalpy": format_state(st),
            "Steam Info": {
                "X Quality (%)": round(x * 100, 4),
                "Sat. Liq. (kJ/kg)": round(hf, 4),
                "Sat. Steam (kJ/kg)": round(hg, 4),
                "Wet Steam (kJ/kg)": round(hf + x * (hg - hf), 4)
            }
        })

    # --- Two-property mode: P + S ---
    if input_type == 'PS':
        if not pressure or not entropy:
            return jsonify_error("Missing pressure or entropy for PS mode")

        P_bar = parse_float(pressure)
        S = parse_float(entropy)

        if P_bar is None or S is None:
            return jsonify_error("Invalid numeric pressure or entropy")

        # convert units
        P = P_bar / 10.0  # bar abs → MPa

        # cari state berdasarkan P & s
        st = find_state_by_property("s", P, S)
        if st is None:
            return jsonify_error("PS: cannot find state for given P & s (out of range)")

        # info steam (quality & sat values)
        sat_liq = safe_iapws(P=P, x=0)
        sat_vap = safe_iapws(P=P, x=1)

        sf, sg = sat_liq.s, sat_vap.s
        hf, hg = sat_liq.h, sat_vap.h

        if sf <= S <= sg:
            x = (S - sf) / (sg - sf) if sg != sf else 0.0
        elif S < sf:
            x = 0.0
        else:
            x = 1.0

        return jsonify({
            "Pressure & Entropy": format_state(st),
            "Steam Info": {
                "X Quality (%)": round(x * 100, 4),
                "Sat. Liq. (kJ/kg)": round(hf, 4),
                "Sat. Steam (kJ/kg)": round(hg, 4),
                "Wet Steam (kJ/kg)": round(hf + x * (hg - hf), 4)
            }
        })

    # --- Two-property mode: P + V ---
    if input_type == 'PV':
        # ambil specific volume (v)
        v_raw = (
            request.args.get('v')
            or request.args.get('specificvolume')
            or request.args.get('specific_volume')
        )

        if not pressure or v_raw is None:
            return jsonify_error("Missing pressure or specific volume for PV mode")

        P_bar = parse_float(pressure)
        V_target = parse_float(v_raw)

        if P_bar is None or V_target is None:
            return jsonify_error("Invalid numeric pressure or specific volume")

        if V_target <= 0:
            return jsonify_error("Specific volume must be > 0")
        if V_target > 1000:
            return jsonify_error("Specific volume too large for practical engineering range")

        # convert units
        P = P_bar / 10.0  # bar abs → MPa

        # ambil kondisi saturasi
        sat_liq = safe_iapws(P=P, x=0)
        sat_vap = safe_iapws(P=P, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Pressure out of valid IAPWS97 range (PV)")

        vf, vg = sat_liq.v, sat_vap.v
        hf, hg = sat_liq.h, sat_vap.h
        sf, sg = sat_liq.s, sat_vap.s
        uf, ug = sat_liq.u, sat_vap.u

        # --- Dua-fasa (wet steam) ---
        if vf <= V_target <= vg:
            x = (V_target - vf) / (vg - vf) if vg != vf else 0.0

            st = make_mixture_from_quality(
                P, vf, vg,
                hf, hg,
                sf, sg,
                uf, ug,
                x
            )

            return jsonify({
                "Pressure & Specific Volume": format_state(st),
                "Steam Info": {
                    "X Quality (%)": round(x * 100, 4),
                    "Sat. Liq. (m³/kg)": round(vf, 6),
                    "Sat. Steam (m³/kg)": round(vg, 6)
                }
            })

        # --- Bukan dua-fasa: cari T ---
        T_low = sat_vap.T
        T_high = sat_vap.T + 1500  # batas atas aman

        st_mid = None
        for _ in range(80):
            T_mid = 0.5 * (T_low + T_high)
            st_try = safe_iapws(P=P, T=T_mid)

            if st_try is None:
                T_high = T_mid
                continue

            if abs(st_try.v - V_target) < 1e-8:
                st_mid = st_try
                break

            if st_try.v < V_target:
                T_low = T_mid
            else:
                T_high = T_mid

            st_mid = st_try

        if st_mid is None:
            return jsonify_error("PV: cannot find state matching specific volume at this pressure")

        return jsonify({
            "Pressure & Specific Volume": format_state(st_mid)
        })

    # --- T + V ---
    # --- T + V (Temperature & Specific Volume) ---
    if input_type == 'TV':

        # 1️⃣ Ambil input
        v_raw = request.args.get('v') \
            or request.args.get('specificvolume') \
            or request.args.get('specific_volume')

        if not temperature or v_raw is None:
            return jsonify_error("Missing temperature or specific volume for TV mode")

        # 2️⃣ Parse & validasi
        T_C = parse_float(temperature)
        V_target = parse_float(v_raw)

        if T_C is None or V_target is None:
            return jsonify_error("Invalid numeric temperature or specific volume")

        if V_target <= 0:
            return jsonify_error("Specific volume must be > 0")

        # 3️⃣ Konversi satuan
        T_K = T_C + 273.15

        # 4️⃣ Ambil kondisi saturasi
        sat_liq = safe_iapws(T=T_K, x=0)
        sat_vap = safe_iapws(T=T_K, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Temperature out of valid IAPWS97 range")

        vf, vg = sat_liq.v, sat_vap.v

        # 5️⃣ TWO-PHASE CHECK
        if vf <= V_target <= vg:
            x = (V_target - vf) / (vg - vf) if vg != vf else 0.0

            mix = make_mixture_from_quality(
                sat_liq.P,
                vf, vg,
                sat_liq.h, sat_vap.h,
                sat_liq.s, sat_vap.s,
                sat_liq.u, sat_vap.u,
                x
            )

            return jsonify({
                "Temperature & Specific Volume": format_state(mix),
                "Steam Info": {
                    "X Quality (%)": round(x * 100, 4)
                }
            })

        # 6️⃣ SINGLE-PHASE → cari P
        P_low, P_high = 1e-6, 100.0
        state = None

        for _ in range(80):
            P_mid = 0.5 * (P_low + P_high)
            st_try = safe_iapws(P=P_mid, T=T_K)

            if st_try is None:
                P_high = P_mid
                continue

            if abs(st_try.v - V_target) < 1e-8:
                state = st_try
                break

            if st_try.v > V_target:
                P_low = P_mid
            else:
                P_high = P_mid

            state = st_try

        if state is None:
            return jsonify_error("TV: cannot find state for given T & v")

        return jsonify({
            "Temperature & Specific Volume": format_state(state)
        })

    # --- P + U (Pressure & Internal Energy) ---
    if input_type == 'PU':

        # 1️⃣ Ambil input
        u_raw = request.args.get('u') \
            or request.args.get('internalenergy') \
            or request.args.get('internal_energy')

        if not pressure or u_raw is None:
            return jsonify_error("Missing pressure or internal energy for PU mode")

        # 2️⃣ Parse & validasi
        P_bar = parse_float(pressure)
        U_target = parse_float(u_raw)

        if P_bar is None or U_target is None:
            return jsonify_error("Invalid numeric pressure or internal energy")

        # 3️⃣ Konversi satuan
        P_MPa = P_bar / 10.0

        # 4️⃣ Ambil kondisi saturasi
        sat_liq = safe_iapws(P=P_MPa, x=0)
        sat_vap = safe_iapws(P=P_MPa, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Pressure out of valid IAPWS97 range")

        uf, ug = sat_liq.u, sat_vap.u

        # 5️⃣ TWO-PHASE CHECK
        if uf <= U_target <= ug:
            x = (U_target - uf) / (ug - uf) if ug != uf else 0.0

            mix = make_mixture_from_quality(
                P_MPa,
                sat_liq.v, sat_vap.v,
                sat_liq.h, sat_vap.h,
                sat_liq.s, sat_vap.s,
                uf, ug,
                x
            )

            return jsonify({
                "Pressure & Internal Energy": format_state(mix),
                "Steam Info": {
                    "X Quality (%)": round(x * 100, 4)
                }
            })

        # 6️⃣ SINGLE-PHASE → cari T
        T_low = sat_liq.T
        T_high = sat_vap.T + 1500
        state = None

        for _ in range(80):
            T_mid = 0.5 * (T_low + T_high)
            st_try = safe_iapws(P=P_MPa, T=T_mid)

            if st_try is None:
                T_high = T_mid
                continue

            if abs(st_try.u - U_target) < 1e-6:
                state = st_try
                break

            if st_try.u < U_target:
                T_low = T_mid
            else:
                T_high = T_mid

            state = st_try

        if state is None:
            return jsonify_error("PU: cannot find state for given P & u")

        return jsonify({
            "Pressure & Internal Energy": format_state(state)
        })

    # --- T + U (Temperature & Internal Energy) ---
    if input_type == 'TU':

        # 1️⃣ Ambil input
        u_raw = request.args.get('u') \
            or request.args.get('internalenergy') \
            or request.args.get('internal_energy')

        if not temperature or u_raw is None:
            return jsonify_error("Missing temperature or internal energy for TU mode")

        # 2️⃣ Parse & validasi
        T_C = parse_float(temperature)
        U_target = parse_float(u_raw)

        if T_C is None or U_target is None:
            return jsonify_error("Invalid numeric temperature or internal energy")

        # 3️⃣ Konversi satuan
        T_K = T_C + 273.15

        # 4️⃣ Ambil kondisi saturasi
        sat_liq = safe_iapws(T=T_K, x=0)
        sat_vap = safe_iapws(T=T_K, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Temperature out of valid IAPWS97 range")

        uf, ug = sat_liq.u, sat_vap.u

        # 5️⃣ TWO-PHASE CHECK
        if uf <= U_target <= ug:
            x = (U_target - uf) / (ug - uf) if ug != uf else 0.0

            mix = make_mixture_from_quality(
                sat_liq.P,
                sat_liq.v, sat_vap.v,
                sat_liq.h, sat_vap.h,
                sat_liq.s, sat_vap.s,
                uf, ug,
                x
            )

            return jsonify({
                "Temperature & Internal Energy": format_state(mix),
                "Steam Info": {
                    "X Quality (%)": round(x * 100, 4)
                }
            })

        # 6️⃣ SINGLE-PHASE → cari P
        P_low, P_high = 1e-6, 100.0
        state = None

        for _ in range(80):
            P_mid = 0.5 * (P_low + P_high)
            st_try = safe_iapws(P=P_mid, T=T_K)

            if st_try is None:
                P_high = P_mid
                continue

            if abs(st_try.u - U_target) < 1e-6:
                state = st_try
                break

            if st_try.u < U_target:
                P_low = P_mid
            else:
                P_high = P_mid

            state = st_try

        if state is None:
            return jsonify_error("TU: cannot find state for given T & u")

        return jsonify({
            "Temperature & Internal Energy": format_state(state)
        })

    # --- P + X (Pressure & Steam Quality) ---
    if input_type == 'PX':

        # 1️⃣ Ambil input
        x_raw = request.args.get('x') \
            or request.args.get('steamquality') \
            or request.args.get('steam_quality')

        if not pressure or x_raw is None:
            return jsonify_error("Missing pressure or steam quality for PX mode")

        # 2️⃣ Parse & validasi
        P_bar = parse_float(pressure)
        x_pct = parse_float(x_raw)

        if P_bar is None or x_pct is None:
            return jsonify_error("Invalid numeric pressure or steam quality")

        if x_pct < 0 or x_pct > 100:
            return jsonify_error("Steam quality (x) must be between 0 and 100 (%)")

        # 3️⃣ Konversi satuan
        P_MPa = P_bar / 10.0
        x = x_pct / 100.0

        # 4️⃣ Ambil kondisi saturasi
        sat_liq = safe_iapws(P=P_MPa, x=0)
        sat_vap = safe_iapws(P=P_MPa, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Pressure out of valid IAPWS97 range")

        # 5️⃣ Bangun mixture
        mix = make_mixture_from_quality(
            P_MPa,
            sat_liq.v, sat_vap.v,
            sat_liq.h, sat_vap.h,
            sat_liq.s, sat_vap.s,
            sat_liq.u, sat_vap.u,
            x
        )

        # 6️⃣ Return
        return jsonify({
            "Pressure & Steam Quality": format_state(mix),
            "Steam Info": {
                "X Quality (%)": round(x_pct, 4)
            }
        })

    # --- T + X (Temperature & Steam Quality) ---
    if input_type == 'TX':

        # 1️⃣ Ambil input
        x_raw = request.args.get('x') \
            or request.args.get('steamquality') \
            or request.args.get('steam_quality')

        if not temperature or x_raw is None:
            return jsonify_error("Missing temperature or steam quality for TX mode")

        # 2️⃣ Parse & validasi
        T_C = parse_float(temperature)
        x_pct = parse_float(x_raw)

        if T_C is None or x_pct is None:
            return jsonify_error("Invalid numeric temperature or steam quality")

        if x_pct < 0 or x_pct > 100:
            return jsonify_error("Steam quality (x) must be between 0 and 100 (%)")

        # 3️⃣ Konversi satuan
        T_K = T_C + 273.15
        x = x_pct / 100.0

        # 4️⃣ Ambil kondisi saturasi
        sat_liq = safe_iapws(T=T_K, x=0)
        sat_vap = safe_iapws(T=T_K, x=1)

        if sat_liq is None or sat_vap is None:
            return jsonify_error("Temperature out of valid IAPWS97 range")

        # 5️⃣ Bangun mixture
        mix = make_mixture_from_quality(
            sat_liq.P,
            sat_liq.v, sat_vap.v,
            sat_liq.h, sat_vap.h,
            sat_liq.s, sat_vap.s,
            sat_liq.u, sat_vap.u,
            x
        )

        # 6️⃣ Return
        return jsonify({
            "Temperature & Steam Quality": format_state(mix),
            "Steam Info": {
                "X Quality (%)": round(x_pct, 4)
            }
        })

    # If not matched
    return jsonify_error("Invalid input. Supported: P, T, PT, PH, PS, TH, TS, PV, TV, PU, TU, PX, TX")




# ------------------ find_state helpers (unchanged logic but safer) ------------------

def find_state_by_property(prop, P, target, tol=1e-6, tmax=1300.0):
    """
    Find state given pressure (MPa) and property (h or s).
    - Returns mixture-like object for two-phase
    - Returns IAPWS97 object for superheated/compressed
    - Returns None if cannot find
    """
    # Validate P
    sat_liq = safe_iapws(P=P, x=0)
    sat_vap = safe_iapws(P=P, x=1)
    if sat_liq is None or sat_vap is None:
        return None

    hf, hg = sat_liq.h, sat_vap.h
    sf, sg = sat_liq.s, sat_vap.s
    vf, vg = sat_liq.v, sat_vap.v
    uf, ug = sat_liq.u, sat_vap.u

    if prop == "h":
        # two-phase
        if hf - 1e-12 <= target <= hg + 1e-12:
            x = (target - hf) / (hg - hf) if hg != hf else 0.0
            return make_mixture_from_quality(P, vf, vg, hf, hg, sf, sg, uf, ug, x)
        # superheated
        if target > hg:
            T_low = sat_vap.T
            T_high = sat_vap.T + tmax
            st_mid = None
            for _ in range(80):
                T_mid = 0.5 * (T_low + T_high)
                st_try = safe_iapws(P=P, T=T_mid)
                if st_try is None:
                    T_high = T_mid
                    continue
                diff = st_try.h - target
                if abs(diff) < tol:
                    return st_try
                if diff > 0:
                    T_high = T_mid
                else:
                    T_low = T_mid
                st_mid = st_try
            return st_mid
        # compressed liquid
        if target < hf:
            return sat_liq

    if prop == "s":
        if sf - 1e-12 <= target <= sg + 1e-12:
            x = (target - sf) / (sg - sf) if sg != sf else 0.0
            return make_mixture_from_quality(P, vf, vg, hf, hg, sf, sg, uf, ug, x)
        if target > sg:
            T_low = sat_vap.T
            T_high = sat_vap.T + tmax
            st_mid = None
            for _ in range(80):
                T_mid = 0.5 * (T_low + T_high)
                st_try = safe_iapws(P=P, T=T_mid)
                if st_try is None:
                    T_high = T_mid
                    continue
                diff = st_try.s - target
                if abs(diff) < tol:
                    return st_try
                if diff > 0:
                    T_high = T_mid
                else:
                    T_low = T_mid
                st_mid = st_try
            return st_mid
        if target < sf:
            return sat_liq

    return None


def find_state_by_property_T(prop, T_K, target):
    """
    Given T (K) and property (h or s), scan pressure grid to find best match.
    """
    best_state = None
    best_diff = 1e9
    for Px in [x / 10.0 for x in range(1, 2001)]:  # 0.1 MPa steps up to 200 MPa -> wide coverage
        st = safe_iapws(P=Px, T=T_K)
        if st is None:
            continue
        try:
            val = getattr(st, prop)
        except Exception:
            continue
        diff = abs(val - target)
        if diff < best_diff:
            best_diff = diff
            best_state = st
            if diff < 1e-6:
                break
    return best_state


if __name__ == '__main__':
    app.run(debug=True)
