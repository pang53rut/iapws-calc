# app.py
from flask import Flask, request, jsonify
from iapws import IAPWS97
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/steam', methods=['GET'])
def steam_properties():
    try:
        input_type = request.args.get('input')  # 'T' or 'P'
        value = float(request.args.get('value'))

        if input_type == 'P':
            water = IAPWS97(P=value, x=0)  # Saturated liquid
            steam = IAPWS97(P=value, x=1)  # Saturated vapor
        elif input_type == 'T':
            water = IAPWS97(T=value + 273.15, x=0)
            steam = IAPWS97(T=value + 273.15, x=1)
        else:
            return jsonify({'error': 'Input harus P atau T'})

        return jsonify({
            'Input': input_type,
            'Value': value,
            'Saturated Liquid': {
                'T (C)': round(water.T - 273.15, 2),
                'P (MPa)': round(water.P, 5),
                'h': round(water.h, 2),
                's': round(water.s, 4),
                'u': round(water.u, 2),
                'v': round(water.v, 6),
                'x': 0
            },
            'Saturated Vapor': {
                'T (C)': round(steam.T - 273.15, 2),
                'P (MPa)': round(steam.P, 5),
                'h': round(steam.h, 2),
                's': round(steam.s, 4),
                'u': round(steam.u, 2),
                'v': round(steam.v, 6),
                'x': 1
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
