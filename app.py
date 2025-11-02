from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "✅ IAPWS Steam API — Now with viscosity & quality!"

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input', '').upper()
        value = float(request.args.get('value'))

        if input_type == 'P':  # Pressure input (bar)
            P = value / 10  # convert bar → MPa
            water = IAPWS97(P=P, x=0)
            steam = IAPWS97(P=P, x=1)

        elif input_type == 'T':  # Temperature input (°C)
            T = value + 273.15
            water = IAPWS97(T=T, x=0)
            steam = IAPWS97(T=T, x=1)

        else:
            return jsonify({'error': 'Invalid input type. Use "P" or "T".'})

        # Calculate derived properties
        results = {
            "Saturated Liquid": {
                "T (°C)": round(water.T - 273.15, 2),
                "P (MPa)": round(water.P, 5),
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
                "P (MPa)": round(steam.P, 5),
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

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
