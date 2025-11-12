from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/')
def home():
    return "✅ IAPWS Steam API — now supports P–T, P–H, P–S, T–H, and T–S modes!"


@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input', '').upper()
        value = request.args.get('value')
        pressure = request.args.get('pressure')
        temperature = request.args.get('temperature')
        enthalpy = request.args.get('enthalpy')
        entropy = request.args.get('entropy')

        # --- Mode Saturasi (P atau T) ---
        if input_type in ['P', 'T']:
            value = float(value)
            if input_type == 'P':
                P = value / 10
                water = IAPWS97(P=P, x=0)
                steam = IAPWS97(P=P, x=1)
            elif input_type == 'T':
                T = value + 273.15
                water = IAPWS97(T=T, x=0)
                steam = IAPWS97(T=T, x=1)

            def press(state):
                P_MPa = round(state.P, 5)
                P_bara = round(P_MPa * 10, 4)
                P_barg = round(P_bara - 1.01325, 4)
                return P_MPa, P_bara, P_barg

            Pw_MPa, Pw_bara, Pw_barg = press(water)
            Ps_MPa, Ps_bara, Ps_barg = press(steam)

            results = {
                "Saturated Liquid": {
                    "T (°C)": round(water.T - 273.15, 2),
                    "P (MPa)": Pw_MPa,
                    "P (bar abs)": Pw_bara,
                    "P (bar g)": Pw_barg,
                    "h (kJ/kg)": round(water.h, 2),
                    "s (kJ/kg·K)": round(water.s, 4),
                    "u (kJ/kg)": round(water.u, 2),
                    "v (m³/kg)": round(water.v, 6),
                    "rho (kg/m³)": round(1 / water.v, 2),
                    "mu (Pa·s)": round(water.mu, 6),
                    "nu (m²/s)": round(water.mu * water.v, 9),
                    "x (quality)": 0.0
                },
                "Saturated Vapor": {
                    "T (°C)": round(steam.T - 273.15, 2),
                    "P (MPa)": Ps_MPa,
                    "P (bar abs)": Ps_bara,
                    "P (bar g)": Ps_barg,
                    "h (kJ/kg)": round(steam.h, 2),
                    "s (kJ/kg·K)": round(steam.s, 4),
                    "u (kJ/kg)": round(steam.u, 2),
                    "v (m³/kg)": round(steam.v, 6),
                    "rho (kg/m³)": round(1 / steam.v, 2),
                    "mu (Pa·s)": round(steam.mu, 6),
                    "nu (m²/s)": round(steam.mu * steam.v, 9),
                    "x (quality)": 1.0
                }
            }

        # --- Mode P + T ---
        elif input_type == 'PT' and pressure and temperature:
            P = float(pressure) / 10
            T = float(temperature) + 273.15
            st = IAPWS97(P=P, T=T)
            results = {"Pressure & Temperature": format_state(st)}

        # --- Mode P + H ---
        elif input_type == 'PH' and pressure and enthalpy:
            P = float(pressure) / 10
            H = float(enthalpy)
            st = find_state_by_property("h", P, H)

            # Hitung data saturasi
            sat_liq = IAPWS97(P=P, x=0)
            sat_vap = IAPWS97(P=P, x=1)
            hf, hg = sat_liq.h, sat_vap.h

            # Hitung steam quality (%)
            if hf <= H <= hg:
                x = (H - hf) / (hg - hf)
            elif H < hf:
                x = 0
            else:
                x = 1

            results = {
                "Pressure & Enthalpy": format_state(st),
                "Steam Info": {
                    "x (quality %)": round(x * 100, 2),
                    "h_sat_liq (kJ/kg)": round(hf, 2),
                    "h_sat_vap (kJ/kg)": round(hg, 2),
                    "h_mix (wet steam, kJ/kg)": round(hf + x * (hg - hf), 2)
                }
            }

        # --- Mode P + S ---
        elif input_type == 'PS' and pressure and entropy:
            P = float(pressure) / 10
            S = float(entropy)
            st = find_state_by_property("s", P, S)

            # Hitung data saturasi
            sat_liq = IAPWS97(P=P, x=0)
            sat_vap = IAPWS97(P=P, x=1)
            sf, sg = sat_liq.s, sat_vap.s
            hf, hg = sat_liq.h, sat_vap.h

            # Hitung steam quality (%)
            if sf <= S <= sg:
                x = (S - sf) / (sg - sf)
            elif S < sf:
                x = 0
            else:
                x = 1

            results = {
                "Pressure & Entropy": format_state(st),
                "Steam Info": {
                    "x (quality %)": round(x * 100, 2),
                    "h_sat_liq (kJ/kg)": round(hf, 2),
                    "h_sat_vap (kJ/kg)": round(hg, 2),
                    "h_mix (wet steam, kJ/kg)": round(hf + x * (hg - hf), 2)
                }
            }

        # --- Mode T + H ---
        elif input_type == 'TH' and temperature and enthalpy:
            T = float(temperature) + 273.15
            H = float(enthalpy)
            st = find_state_by_property_T("h", T, H)
            results = {"Temperature & Enthalpy": format_state(st)}

        # --- Mode T + S ---
        elif input_type == 'TS' and temperature and entropy:
            T = float(temperature) + 273.15
            S = float(entropy)
            st = find_state_by_property_T("s", T, S)
            results = {"Temperature & Entropy": format_state(st)}

        else:
            return jsonify({'error': 'Invalid input. Supported: P, T, PT, PH, PS, TH, TS'})

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)})


# 🔧 Helper untuk format hasil
def format_state(state):
    return {
        "T (°C)": round(state.T - 273.15, 2),
        "P (MPa)": round(state.P, 5),
        "P (bar abs)": round(state.P * 10, 4),
        "P (bar g)": round(state.P * 10 - 1.01325, 4),
        "v (m³/kg)": round(state.v, 6),
        "rho (kg/m³)": round(1 / state.v, 3),
        "h (kJ/kg)": round(state.h, 2),
        "u (kJ/kg)": round(state.u, 2),
        "s (kJ/kg·K)": round(state.s, 4),
        "Cp (kJ/kg·°C)": round(state.cp, 3),
        "Cv (kJ/kg·°C)": round(state.cv, 3),
        "w (m/s)": round(state.w, 2),
        "mu (Pa·s)": round(state.mu, 8),
        "nu (m²/s)": round(state.mu * state.v, 9),
        "k (W/m·K)": round(state.k, 5)
    }


# ganti fungsi find_state_by_property lama dengan ini
def find_state_by_property(prop, P, target, tol=1e-6, tmax=1000.0):
    sat_liq = IAPWS97(P=P, x=0)
    sat_vap = IAPWS97(P=P, x=1)
    hf, hg = sat_liq.h, sat_vap.h
    sf, sg = sat_liq.s, sat_vap.s
    vf, vg = sat_liq.v, sat_vap.v
    uf, ug = sat_liq.u, sat_vap.u

    # jika mencari berdasarkan enthalpy
    if prop == "h":
        # 1) two-phase: langsung interpolate
        if hf <= target <= hg:
            x = (target - hf) / (hg - hf) if hg != hf else 0.0
            class Mix: pass
            ms = Mix()
            ms.P = P
            ms.T = sat_liq.T
            ms.h = target
            ms.s = sf + x * (sg - sf)
            ms.v = vf + x * (vg - vf)
            ms.u = uf + x * (ug - uf)
            # set atribut lain supaya format_state bisa akses (boleh None)
            ms.cp = getattr(sat_liq, "cp", None)
            ms.cv = getattr(sat_liq, "cv", None)
            ms.k = getattr(sat_liq, "k", None)
            ms.mu = getattr(sat_liq, "mu", None)
            ms.w = getattr(sat_liq, "w", None)
            return ms

        # 2) superheated: bisection cari T sehingga st.h ~= target
        if target > hg:
            T_low = sat_vap.T
            T_high = tmax + 273.15
            for _ in range(60):
                T_mid = 0.5 * (T_low + T_high)
                st_mid = IAPWS97(P=P, T=T_mid)
                diff = st_mid.h - target
                if abs(diff) < tol:
                    return st_mid
                if diff > 0:
                    T_high = T_mid
                else:
                    T_low = T_mid
            return st_mid

        # 3) compressed liquid: kembalikan saturated liquid sebagai aproks.
        if target < hf:
            return sat_liq

    # jika mencari berdasarkan entropy, lakukan analog (cek sf/sg lalu interpolate, dll.)
    if prop == "s":
        if sf <= target <= sg:
            x = (target - sf) / (sg - sf) if sg != sf else 0.0
            class Mix: pass
            ms = Mix()
            ms.P = P
            ms.T = sat_liq.T
            ms.s = target
            ms.h = hf + x * (hg - hf)
            ms.v = vf + x * (vg - vf)
            ms.u = uf + x * (ug - uf)
            ms.cp = getattr(sat_liq, "cp", None)
            ms.cv = getattr(sat_liq, "cv", None)
            ms.k = getattr(sat_liq, "k", None)
            ms.mu = getattr(sat_liq, "mu", None)
            ms.w = getattr(sat_liq, "w", None)
            return ms

        if target > sg:
            T_low = sat_vap.T
            T_high = tmax + 273.15
            for _ in range(60):
                T_mid = 0.5 * (T_low + T_high)
                st_mid = IAPWS97(P=P, T=T_mid)
                diff = st_mid.s - target
                if abs(diff) < tol:
                    return st_mid
                if diff > 0:
                    T_high = T_mid
                else:
                    T_low = T_mid
            return st_mid

        if target < sf:
            return sat_liq

    return None



# 🔧 Fungsi cari kondisi dari T + (H atau S)
def find_state_by_property_T(prop, T, target):
    best_state, best_diff = None, 1e9
    for P in [x / 10 for x in range(1, 221)]:
        st = IAPWS97(P=P, T=T)
        diff = abs(getattr(st, prop) - target)
        if diff < best_diff:
            best_diff = diff
            best_state = st
    return best_state


if __name__ == '__main__':
    app.run(debug=True)
