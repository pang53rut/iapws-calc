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
                    "Temperature (°C)": round(water.T - 273.15, 2),
                    "Pressure (MPa)": Pw_MPa,
                    "Pressure (bar abs)": Pw_bara,
                    "Pressure (bar g)": Pw_barg,
                    "Enthalpy (kJ/kg)": round(water.h, 2),
                    "Entropy (kJ/kg·K)": round(water.s, 4),
                    "Internal Energy (kJ/kg)": round(water.u, 2),
                    "Specific Volume (m³/kg)": round(water.v, 6),
                    "Density (kg/m³)": round(1 / water.v, 2),
                    "Dynamic Viscosity (Pa·s)": round(water.mu, 6),
                    "Kinematic Viscosity (m²/s)": round(water.mu * water.v, 9),
                    "X Quality (%)": 0.0
                },
                "Saturated Vapor": {
                    "Temperature (°C)": round(steam.T - 273.15, 2),
                    "Pressure (MPa)": Ps_MPa,
                    "Pressure (bar abs)": Ps_bara,
                    "Pressure (bar g)": Ps_barg,
                    "Enthalpy (kJ/kg)": round(steam.h, 2),
                    "Entropy (kJ/kg·K)": round(steam.s, 4),
                    "Internal Energy (kJ/kg)": round(steam.u, 2),
                    "Specific Volume (m³/kg)": round(steam.v, 6),
                    "Density (kg/m³)": round(1 / steam.v, 2),
                    "Dynamic Viscosity (Pa·s)": round(steam.mu, 6),
                    "Kinematic Viscosity (m²/s)": round(steam.mu * steam.v, 9),
                    "X Quality (%)": 100.0
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
                    "X Quality (%)": round(x * 100, 2),
                    "Sat. Liq. (kJ/kg)": round(hf, 2),
                    "Sat. Steam (kJ/kg)": round(hg, 2),
                    "Wet Steam (kJ/kg)": round(hf + x * (hg - hf), 2)
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
                    "X Quality (%)": round(x * 100, 2),
                    "Sat. Liq. (kJ/kg)": round(hf, 2),
                    "Sat. Steam (kJ/kg)": round(hg, 2),
                    "Wet Steam (kJ/kg)": round(hf + x * (hg - hf), 2)
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
        # --- Mode P + V (Pressure + Specific Volume) ---
        elif input_type == 'PV' and pressure and request.args.get('specificvolume'):
            P = float(pressure) / 10
            V_target = float(request.args.get('specificvolume'))

            # Cari state dengan metode bisection berdasarkan volume
            sat_liq = IAPWS97(P=P, x=0)
            sat_vap = IAPWS97(P=P, x=1)

            # Jika di dua fase
            if sat_liq.v <= V_target <= sat_vap.v:
                x = (V_target - sat_liq.v) / (sat_vap.v - sat_liq.v)
                class Mix: pass
                ms = Mix()
                ms.P = P
                ms.T = sat_liq.T
                ms.v = V_target
                ms.h = sat_liq.h + x * (sat_vap.h - sat_liq.h)
                ms.s = sat_liq.s + x * (sat_vap.s - sat_liq.s)
                ms.u = sat_liq.u + x * (sat_vap.u - sat_liq.u)
                ms.cp = sat_liq.cp + x * (sat_vap.cp - sat_liq.cp)
                ms.cv = sat_liq.cv + x * (sat_vap.cv - sat_liq.cv)
                ms.k = sat_liq.k + x * (sat_vap.k - sat_liq.k)
                ms.mu = sat_liq.mu + x * (sat_vap.mu - sat_liq.mu)
                ms.w = sat_liq.w + x * (sat_vap.w - sat_liq.w)
                st = ms
            else:
                # superheated / compressed
                T_low = sat_liq.T
                T_high = sat_vap.T + 800
                for _ in range(60):
                    T_mid = 0.5 * (T_low + T_high)
                    st_mid = IAPWS97(P=P, T=T_mid)
                    if abs(st_mid.v - V_target) < 1e-8:
                        st = st_mid
                        break
                    if st_mid.v > V_target:
                        T_low = T_mid
                    else:
                        T_high = T_mid
                st = st_mid

            results = {"Pressure & Specific Volume": format_state(st)}
        # --- Mode T + V (Temperature + Specific Volume) ---
        elif input_type == 'TV' and temperature and (request.args.get('specificvolume') or request.args.get('specific_volume') or request.args.get('v')):
            T = float(temperature) + 273.15
            v_raw = request.args.get('specificvolume') or request.args.get('specific_volume') or request.args.get('v')
            V_target = float(v_raw)

            # ambil properti saturasi pada T
            sat_liq = IAPWS97(T=T, x=0)
            sat_vap = IAPWS97(T=T, x=1)
            vf, vg = sat_liq.v, sat_vap.v
            P_sat = sat_liq.P  # MPa

            # 1) two-phase: langsung interpolate jika V_target di antara vf dan vg
            if vf - 1e-12 <= V_target <= vg + 1e-12:
                # quality
                x = (V_target - vf) / (vg - vf) if vg != vf else 0.0
                class Mix: pass
                ms = Mix()
                ms.P = P_sat
                ms.T = T
                ms.v = V_target
                ms.h = sat_liq.h + x * (sat_vap.h - sat_liq.h)
                ms.u = sat_liq.u + x * (sat_vap.u - sat_liq.u)
                ms.s = sat_liq.s + x * (sat_vap.s - sat_liq.s)
                ms.cp = sat_liq.cp + x * (sat_vap.cp - sat_liq.cp)
                ms.cv = sat_liq.cv + x * (sat_vap.cv - sat_liq.cv)
                ms.k = sat_liq.k + x * (sat_vap.k - sat_liq.k)
                ms.mu = sat_liq.mu + x * (sat_vap.mu - sat_liq.mu)
                ms.w = sat_liq.w + x * (sat_vap.w - sat_liq.w)
                st = ms
            else:
                # 2) superheated or compressed liquid: cari P yang memenuhi st.v ~= V_target
                # buat bracket P_low,P_high yang monoton sehingga st.v(P) menurun dengan P
                P_low = 1e-6   # sangat rendah
                P_high = 100.0 # cukup tinggi (MPa) - sesuaikan jika perlu

                # Pastikan fungsi memiliki tanda berlawanan pada batas - jika tidak, expand batas atau fallback
                st_low = IAPWS97(P=P_low, T=T)
                st_high = IAPWS97(P=P_high, T=T)
                # jika keduanya gagal (eksepsi) lakukan fallback scanning kecil
                for _ in range(80):
                    P_mid = 0.5 * (P_low + P_high)
                    try:
                        st_mid = IAPWS97(P=P_mid, T=T)
                    except Exception:
                        # jika library error dengan P_mid, adjust range
                        P_low = P_mid
                        continue

                    # kondisi monotonic: jika st_mid.v > V_target -> root di kanan (naikkan P_low)
                    if abs(st_mid.v - V_target) < 1e-9:
                        st = st_mid
                        break
                    if st_mid.v > V_target:
                        P_low = P_mid
                    else:
                        P_high = P_mid
                    st = st_mid

            results = {"Temperature & Specific Volume": format_state(st)}




    # --- Mode P + U (Pressure + Internal Energy) ---
        elif input_type == 'PU' and pressure and request.args.get('u'):
            P = float(pressure) / 10
            U_target = float(request.args.get('u'))

            sat_liq = IAPWS97(P=P, x=0)
            sat_vap = IAPWS97(P=P, x=1)

            # two-phase
            if sat_liq.u <= U_target <= sat_vap.u:
                x = (U_target - sat_liq.u) / (sat_vap.u - sat_liq.u)
                class Mix: pass
                ms = Mix()
                ms.P = P
                ms.T = sat_liq.T
                ms.u = U_target
                ms.h = sat_liq.h + x * (sat_vap.h - sat_liq.h)
                ms.v = sat_liq.v + x * (sat_vap.v - sat_liq.v)
                ms.s = sat_liq.s + x * (sat_vap.s - sat_liq.s)
                ms.cp = sat_liq.cp + x * (sat_vap.cp - sat_liq.cp)
                ms.cv = sat_liq.cv + x * (sat_vap.cv - sat_liq.cv)
                ms.k = sat_liq.k + x * (sat_vap.k - sat_liq.k)
                ms.mu = sat_liq.mu + x * (sat_vap.mu - sat_liq.mu)
                ms.w = sat_liq.w + x * (sat_vap.w - sat_liq.w)
                st = ms
            else:
                # superheated/compressed
                T_low = sat_liq.T
                T_high = sat_vap.T + 1000
                for _ in range(60):
                    T_mid = 0.5*(T_low+T_high)
                    st_mid = IAPWS97(P=P,T=T_mid)
                    diff = st_mid.u - U_target
                    if abs(diff)<1e-6:
                        st = st_mid
                        break
                    if diff>0:
                        T_high = T_mid
                    else:
                        T_low = T_mid
                st = st_mid

            results = {"Pressure & Internal Energy": format_state(st)}


        # --- Mode T + U (Temperature + Internal Energy) ---
        elif input_type == 'TU' and temperature and (request.args.get('internalenergy') or request.args.get('internal_energy') or request.args.get('u')):
            T = float(temperature) + 273.15
            u_raw = request.args.get('internalenergy') or request.args.get('internal_energy') or request.args.get('u')
            U_target = float(u_raw)

            # saturasi pada T
            sat_liq = IAPWS97(T=T, x=0)
            sat_vap = IAPWS97(T=T, x=1)
            uf, ug = sat_liq.u, sat_vap.u
            P_sat = sat_liq.P

            # 1) two-phase: jika U_target berada di antara uf dan ug
            if uf - 1e-9 <= U_target <= ug + 1e-9:
                x = (U_target - uf) / (ug - uf) if ug != uf else 0.0
                class Mix: pass
                ms = Mix()
                ms.P = P_sat
                ms.T = T
                ms.u = U_target
                ms.h = sat_liq.h + x * (sat_vap.h - sat_liq.h)
                ms.v = sat_liq.v + x * (sat_vap.v - sat_liq.v)
                ms.s = sat_liq.s + x * (sat_vap.s - sat_liq.s)
                ms.cp = sat_liq.cp + x * (sat_vap.cp - sat_liq.cp)
                ms.cv = sat_liq.cv + x * (sat_vap.cv - sat_liq.cv)
                ms.k = sat_liq.k + x * (sat_vap.k - sat_liq.k)
                ms.mu = sat_liq.mu + x * (sat_vap.mu - sat_liq.mu)
                ms.w = sat_liq.w + x * (sat_vap.w - sat_liq.w)
                st = ms
            else:
                # 2) cari P via bisection supaya st.u ~= U_target
                P_low = 1e-6
                P_high = 100.0
                for _ in range(80):
                    P_mid = 0.5 * (P_low + P_high)
                    try:
                        st_mid = IAPWS97(P=P_mid, T=T)
                    except Exception:
                        P_low = P_mid
                        continue

                    diff = st_mid.u - U_target
                    if abs(diff) < 1e-6:
                        st = st_mid
                        break
                    # jika st_mid.u > U_target, perlu tekan lebih tinggi (compress) -> naikkan P_low or P_high?
                    # Observasi: st.u biasanya menurun with decreasing P, so if st_mid.u > U_target -> increase P
                    if st_mid.u > U_target:
                        P_low = P_mid
                    else:
                        P_high = P_mid
                    st = st_mid

            results = {"Temperature & Internal Energy": format_state(st)}

            
        # --- Mode P + X (Steam Quality dari tekanan) ---
        elif input_type == 'PX' and pressure and (request.args.get('x') or request.args.get('steamquality') or request.args.get('steam_quality')):
            P = float(pressure) / 10
            x_raw = request.args.get('x') or request.args.get('steamquality') or request.args.get('steam_quality')
            try:
                x = float(x_raw) / 100.0
            except:
                return jsonify({'error': 'Invalid x value'}), 400
            x = max(0.0, min(1.0, x))
            water = IAPWS97(P=P, x=0)
            steam = IAPWS97(P=P, x=1)
            mix = IAPWS97(P=P, x=x)
            results = {
                "Pressure & Steam Quality": {
                    "Temperature (°C)": round(mix.T - 273.15, 2),
                    "Pressure (MPa)": round(P, 5),
                    "Enthalpy (kJ/kg)": round(mix.h, 2),
                    "Entropy (kJ/kg·K)": round(mix.s, 4),
                    "Specific Volume (m³/kg)": round(mix.v, 6),
                    "Density (kg/m³)": round(1 / mix.v, 3),
                    "Internal Energy (kJ/kg)": round(mix.u, 2),
                    "X Quality (%)": round(x * 100, 2)
                },
                "Steam Info": {
                    "Sat. Liq. (kJ/kg)": round(water.h, 2),
                    "Sat. Steam (kJ/kg)": round(steam.h, 2),
                    "Wet Steam (kJ/kg)": round(water.h + x * (steam.h - water.h), 2)
                }
            }
        # --- Mode T + X (Steam Quality dari temperatur) ---
        elif input_type == 'TX' and temperature and (request.args.get('x') or request.args.get('steamquality') or request.args.get('steam_quality')):
            T = float(temperature) + 273.15
            x_raw = request.args.get('x') or request.args.get('steamquality') or request.args.get('steam_quality')
            try:
                x = float(x_raw) / 100.0
            except:
                return jsonify({'error': 'Invalid x value'}), 400
            x = max(0.0, min(1.0, x))
            water = IAPWS97(T=T, x=0)
            steam = IAPWS97(T=T, x=1)
            mix = IAPWS97(T=T, x=x)
            results = {
                "Temperature & Steam Quality": {
                    "Temperature (°C)": round(mix.T - 273.15, 2),
                    "Pressure (MPa)": round(mix.P, 5),
                    "Enthalpy (kJ/kg)": round(mix.h, 2),
                    "Entropy (kJ/kg·K)": round(mix.s, 4),
                    "Specific Volume (m³/kg)": round(mix.v, 6),
                    "Density (kg/m³)": round(1 / mix.v, 3),
                    "Internal Energy (kJ/kg)": round(mix.u, 2),
                    "X Quality (%)": round(x * 100, 2)
                },
                "Steam Info": {
                    "Sat. Liq. (kJ/kg)": round(water.h, 2),
                    "Sat. Steam (kJ/kg)": round(steam.h, 2),
                    "Wet Steam (kJ/kg)": round(water.h + x * (steam.h - water.h), 2)
                }
            }
        else:
            return jsonify({'error': 'Invalid input. Supported: P, T, PT, PH, PS, TH, TS'})

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)})


# 🔧 Helper untuk format hasil
def format_state(state):
    return {
        "Temperature (°C)": round(state.T - 273.15, 2),
        "Pressure (MPa)": round(state.P, 5),
        "Pressure (bar abs)": round(state.P * 10, 4),
        "Pressure (bar g)": round(state.P * 10 - 1.01325, 4),
        "Spesific volume (m³/kg)": round(state.v, 6),
        "Density (kg/m³)": round(1 / state.v, 3),
        "Enthalpy (kJ/kg)": round(state.h, 2),
        "Internal energy (kJ/kg)": round(state.u, 2),
        "Entropy (kJ/kg·K)": round(state.s, 4),
        "Specific isobaric heat capacity (kJ/kg·°C)": round(state.cp, 3),
        "Specific isochoric heat capacity (kJ/kg·°C)": round(state.cv, 3),
        "Sound speed (m/s)": round(state.w, 2),
        "Dynamic viscosity (Pa·s)": round(state.mu, 8),
        "Kinematic viscosity (m²/s)": round(state.mu * state.v, 9),
        "Thermal conductivity (W/m·K)": round(state.k, 5)
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
