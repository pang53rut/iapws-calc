from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input')  # 'T' atau 'P'
        value = float(request.args.get('value'))
        unit = request.args.get('unit', 'bara').lower()  # default: bar(a)

        if input_type == 'P':
            # ---- Konversi satuan tekanan ke MPa (absolut) ----
            if unit in ['barg', 'gauge']:
                P = (value + 1.01325) * 0.1   # konversi bar(g) → MPa
            elif unit in ['bara', 'bar']:
                P = value * 0.1               # bar(a) → MPa
            elif unit == 'mpa':
                P = value
            elif unit == 'kpa':
                P = value / 1000
            else:
                return jsonify({'error': f'Satuan tekanan "{unit}" tidak dikenal'})

            # ---- Hitung properti uap jenuh ----
            water = IAPWS97(P=P, x=0)  # cair jenuh
            steam = IAPWS97(P=P, x=1)  # uap jenuh

        elif input_type == 'T':
            T = value + 273.15  # konversi °C → K
            water = IAPWS97(T=T, x=0)
            steam = IAPWS97(T=T, x=1)
        else:
            return jsonify({'error': 'Input harus "P" atau "T"'})

        return jsonify({
            'Input': input_type,
            'Value': value,
            'Unit': unit,
            'Saturated Liquid': {
                'T (°C)': round(water.T - 273.15, 2),
                'P (MPa)': round(water.P, 5),
                'h (kJ/kg)': round(water.h, 2),
                's (kJ/kg·K)': round(water.s, 4),
                'u (kJ/kg)': round(water.u, 2),
                'v (m³/kg)': round(water.v, 6),
                'x': 0
            },
            'Saturated Vapor': {
                'T (°C)': round(steam.T - 273.15, 2),
                'P (MPa)': round(steam.P, 5),
                'h (kJ/kg)': round(steam.h, 2),
                's (kJ/kg·K)': round(steam.s, 4),
                'u (kJ/kg)': round(steam.u, 2),
                'v (m³/kg)': round(steam.v, 6),
                'x': 1
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
