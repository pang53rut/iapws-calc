from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "✅ IAPWS Steam API — with viscosity, density, quality & PT mode!"

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input', '').upper()
        value = request.args.get('value')
        pressure = request.args.get('pressure')
        temperature = request.args.get('temperature')

        # --- Mode P atau T (saturasi) ---
        if input_type in ['P', 'T']:
            value = float(value)

            if input_type == 'P':  # Pressure input (bar)
                P = value / 10  # bar → MPa
                water = IAPWS97(P=P, x=0)
                steam = IAPWS97(P=P, x=1)

            elif input_type == 'T':  # Temperature input (°C)
                T = value + 273.15
                water = IAPWS97(T=T, x=0)
                steam = IAPWS97(T=T, x=1)

            # Konversi tekanan
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

        # --- Mode Pressure + Temperature (superheated/subcooled) ---
        elif input_type == 'PT' and pressure and temperature:
            P = float(pressure) / 10       # bar → MPa
            T = float(temperature) + 273.15  # °C → K
            state = IAPWS97(P=P, T=T)

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
                    "x (quality)": "-"
                }
            }

        else:
            return jsonify({'error': 'Invalid input. Use ?input=P, T, or PT with proper parameters.'})

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
