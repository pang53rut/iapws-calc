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

        if input_type == 'P':  # input dalam bar
            P = value / 10  # convert bar → MPa
            water = IAPWS97(P=P, x=0)
            steam = IAPWS97(P=P, x=1)
            return jsonify({
                "Saturated Liquid": {
                    "T (°C)": round(water.T - 273.15, 2),
                    "h": round(water.h, 2),
                    "s": round(water.s, 4),
                    "u": round(water.u, 2),
                    "v": round(water.v, 6)
                },
                "Saturated Vapor": {
                    "T (°C)": round(steam.T - 273.15, 2),
                    "P (MPa)": round(steam.P, 5),
                    "h": round(steam.h, 2),
                    "s": round(steam.s, 4),
                    "u": round(steam.u, 2),
                    "v": round(steam.v, 6)
                }
            })

        elif input_type == 'T':  # input dalam °C
            T = value + 273.15
            water = IAPWS97(T=T, x=0)
            steam = IAPWS97(T=T, x=1)
            return jsonify({
                "Saturated Liquid": {
                    "P (MPa)": round(water.P, 5),
                    "h": round(water.h, 2),
                    "s": round(water.s, 4),
                    "u": round(water.u, 2),
                    "v": round(water.v, 6)
                },
                "Saturated Vapor": {
                    "P (MPa)": round(steam.P, 5),
                    "h": round(steam.h, 2),
                    "s": round(steam.s, 4),
                    "u": round(steam.u, 2),
                    "v": round(steam.v, 6)
                }
            })

        else:
            return jsonify({'error': 'Invalid input type. Use "P" or "T".'})

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
