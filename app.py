from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "✅ IAPWS Steam API — Supports P–T, P–H, P–S, P–V, P–U, P–X, T–H, T–S, T–V, T–U, T–X"

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input', '').upper()
        value = request.args.get('value')
        pressure = request.args.get('pressure')
        temperature = request.args.get('temperature')
        enthalpy = request.args.get('enthalpy')
        entropy = request.args.get('entropy')
        v = request.args.get('v')
        u = request.args.get('u')
        x = request.args.get('x')

        # --- Mode Saturasi (P atau T) ---
        if input_type in ['P', 'T']:
            value = float(value)
            if input_type == 'P':  # Pressure input (bar)
                P = value / 10
                water = IAPWS97(P=P, x=0)
                steam = IAPWS97(P=P, x=1)
            elif input_type == 'T':  # Temperature input (°C)
                T = value + 273.15
                water = IAPWS97(T=T, x=0)
                steam = IAPWS97(T=T, x=1)

            def add_pressures(state):
                P_MPa = round(state.P, 5)
                P_bara = round(P_MPa * 10, 4)
                P_barg = round(P_bara - 1.01325, 4)
                return P_MPa, P_bara, P_barg

            Pw_MPa, Pw_bara, Pw_barg = add_pressures(water)
            Ps_MPa, Ps_bara, Ps_barg = add_pressures(steam)

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

               # --- Mode Superheated/Subcooled atau kombinasi dua properti ---
        elif input_type.startswith('P') and input_type != 'PT':
            P = float(pressure) / 10
            prop = get_prop_name(input_type)
            target = get_target_value(input_type, enthalpy, entropy, v, u)
            state = find_state_by_property(prop, P, target)

        elif input_type.startswith('T') and input_type != 'PT':
            T = float(temperature) + 273.15
            prop = get_prop_name(input_type)
            target = get_target_value(input_type, enthalpy, entropy, v, u)
            state = find_state_by_property_T(prop, T, target)

        # --- Pressure + Temperature (langsung) ---
        elif input_type == 'PT':
            P = float(pressure) / 10
            T = float(temperature) + 273.15
            state = IAPWS97(P=P, T=T)

        else:
            return jsonify({'error': f'Invalid input combination: {input_type}'})

            return jsonify({'error': 'Invalid input combination.'})

        # --- Format hasil umum ---
        if input_type not in ['P', 'T']:
            results = {
                "Pressure & Temperature": {
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
                    "k (W/m·K)": round(state.k, 5),
                    "x (quality)": getattr(state, "x", "-")
                }
            }

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)})


# --- Helper untuk ambil nama properti dari input_type ---
def get_prop_name(input_type):
    return {
        'PH': 'h',
        'PS': 's',
        'PV': 'v',
        'PU': 'u',
        'TH': 'h',
        'TS': 's',
        'TV': 'v',
        'TU': 'u'
    }.get(input_type, 'h')

# --- Ambil target value sesuai jenis input ---
def get_target_value(input_type, enthalpy, entropy, v, u):
    if 'H' in input_type and enthalpy: return float(enthalpy)
    if 'S' in input_type and entropy: return float(entropy)
    if 'V' in input_type and v: return float(v)
    if 'U' in input_type and u: return float(u)
    raise ValueError("Missing target property value")

# --- Format hasil state ---
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

# --- Fungsi iteratif cari state dari P + properti ---
def find_state_by_property(prop, P, target):
    best_state, best_diff = None, 1e9
    for T in range(50, 800):
        try:
            st = IAPWS97(P=P, T=T + 273.15)
            diff = abs(getattr(st, prop) - target)
            if diff < best_diff:
                best_diff = diff
                best_state = st
        except:
            pass
    return best_state

# --- Fungsi iteratif cari state dari T + properti ---
def find_state_by_property_T(prop, T, target):
    best_state, best_diff = None, 1e9
    for P in [x / 10 for x in range(1, 221)]:
        try:
            st = IAPWS97(P=P, T=T)
            diff = abs(getattr(st, prop) - target)
            if diff < best_diff:
                best_diff = diff
                best_state = st
        except:
            pass
    return best_state

if __name__ == '__main__':
    app.run(debug=True)
