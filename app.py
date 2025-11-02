from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "✅ IAPWS Steam API (accurate version). Use /api/steam?input=P&value=1.5"

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input', '').upper()  # 'T' or 'P'
        value = float(request.args.get('value'))

        # konversi otomatis
        if input_type == 'P':  # user input dalam bar
            P = value / 10  # convert bar → MPa
            water = IAPWS97(P=P, x=0)
            steam = IAPWS97(P=P, x=1)
        elif input_type == 'T':  # user input dalam °C
            T = value + 273.15
            water = IAPWS97(T=T, x=0)
            steam = IAPWS97(T=T, x=1)
        else:
            return jsonify({'error': 'Gunakan input=P (bar) atau T (°C)'})

        data = {
            'Input': input_type,
            'Value': value,
            'Saturated Liquid': {
                'T (°C)': round(water.T - 273.15, 2),
                'P (bar)': round(water.P * 10, 3),
                'h (kJ/kg)': round(water.h, 2),
                's (kJ/kg·K)': round(water.s, 4),
                'u (kJ/kg)': round(water.u, 2),
                'v (m³/kg)': round(water.v, 6),
                'ρ (kg/m³)': round(1 / water.v, 2),
                'x': 0
            },
            'Saturated Vapor': {
                'T (°C)': round(steam.T - 273.15, 2),
                'P (bar)': round(steam.P * 10, 3),
                'h (kJ/kg)': round(steam.h, 2),
                's (kJ/kg·K)': round(steam.s, 4),
                'u (kJ/kg)': round(steam.u, 2),
                'v (m³/kg)': round(steam.v, 6),
                'ρ (kg/m³)': round(1 / steam.v, 2),
                'x': 1
            }
        }

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
