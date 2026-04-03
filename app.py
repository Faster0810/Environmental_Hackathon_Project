from flask import Flask, jsonify, request
from flask_cors import CORS
import requests  # NEW — for weather API calls
import os

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
CORS(app)

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')


# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
WEATHER_API_KEY = "71401e50d24a67fb0169c1e0a579bc4b"
WEATHER_CITY    = "Delhi"

# --- SCORING WEIGHTS ---
DEBT_WEIGHTS = {
    "college_fest":     18,
    "concert":          15,
    "traffic_high":     10,
    "traffic_medium":    5,
    "generator_use":    12,
    "food_stalls":       8,
    "construction":      9,
    "holiday_weekend":   6,
}

base_score = 38

# ─────────────────────────────────────────
# NEW HELPER — fetch weather + AQI
# ─────────────────────────────────────────
def get_weather_data():
    """
    Fetches current weather + Air Quality Index from OpenWeatherMap using your key.
    """
    try:
        # Step A: get coordinates for the city
        geo_url = (
            f"http://api.openweathermap.org/geo/1.0/direct"
            f"?q={WEATHER_CITY}&limit=1&appid={WEATHER_API_KEY}"
        )
        geo_res  = requests.get(geo_url, timeout=5).json()
        lat      = geo_res[0]["lat"]
        lon      = geo_res[0]["lon"]

        # Step B: current weather
        weather_url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        )
        w = requests.get(weather_url, timeout=5).json()
        temp        = round(w["main"]["temp"])
        description = w["weather"][0]["description"].title()
        humidity    = w["main"]["humidity"]
        wind_speed  = w["wind"]["speed"]

        # Step C: Air Quality Index
        aqi_url = (
            f"http://api.openweathermap.org/data/2.5/air_pollution"
            f"?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
        )
        aqi_res   = requests.get(aqi_url, timeout=5).json()
        aqi_value = aqi_res["list"][0]["main"]["aqi"]   # 1–5 scale
        components = aqi_res["list"][0]["components"]   

        # Map AQI 1–5 to label + extra debt points
        aqi_map = {
            1: ("Good",       0),
            2: ("Fair",       5),
            3: ("Moderate",  10),
            4: ("Poor",      18),
            5: ("Very Poor", 25),
        }
        aqi_label, weather_debt = aqi_map.get(aqi_value, ("Unknown", 0))

        if temp > 38:
            weather_debt += 5

        return {
            "city":         WEATHER_CITY,
            "temp":         temp,
            "description":  description,
            "humidity":     humidity,
            "wind_speed":   wind_speed,
            "aqi":          aqi_value,
            "aqi_label":    aqi_label,
            "pm2_5":        round(components.get("pm2_5", 0), 1),
            "no2":          round(components.get("no2", 0), 1),
            "weather_debt": weather_debt,
            "status":       "ok"
        }

    except Exception as e:
        return {
            "city":         WEATHER_CITY,
            "temp":         "--",
            "description":  "Unavailable",
            "humidity":     "--",
            "wind_speed":   "--",
            "aqi":          0,
            "aqi_label":    "Unavailable",
            "pm2_5":        0,
            "no2":          0,
            "weather_debt": 0,
            "status":       "error",
            "error":        str(e)
        }


# ─────────────────────────────────────────
# NEW ROUTE — GET /api/weather
# Frontend calls this on page load
# ─────────────────────────────────────────
@app.route('/api/weather', methods=['GET'])
def weather():
    data = get_weather_data()
    return jsonify(data)


def calculate_debt(events: list, include_weather: bool = False) -> dict:
    total_added  = 0
    breakdown    = []

    for event in events:
        weight = DEBT_WEIGHTS.get(event, 0)
        total_added += weight
        breakdown.append({"event": event.replace('_', ' ').title(), "impact": weight})

    # NEW — optionally bake weather debt into score
    weather_bonus = 0
    if include_weather:
        w = get_weather_data()
        weather_bonus = w["weather_debt"]
        if weather_bonus > 0:
            breakdown.append({"event": f"Air Quality ({w['aqi_label']})", "impact": weather_bonus})
            total_added += weather_bonus

    new_score    = min(base_score + total_added, 100)
    trees_needed = round(new_score * 0.5)
    offset_cost  = new_score * 8

    if new_score < 45:
        apt_living = ["Campus Green Hostels", "Eco-Village"]
    elif new_score < 70:
        apt_living = ["Suburban Apartments", "City Outskirts"]
    else:
        apt_living = ["Remote Countryside", "Far Suburbs"]

    return {
        "base_score":     base_score,
        "added":          total_added,
        "new_score":      new_score,
        "breakdown":      breakdown,
        "offset_trees":   trees_needed,
        "offset_cost":    offset_cost,
        "weather_bonus":  weather_bonus,
        "apt_living":     apt_living,
    }


# --- ROUTE 1: Get current base score ---
@app.route('/api/score', methods=['GET'])
def get_score():
    base_score = 38
    return jsonify({
        "location":      "College Campus",
        "current_score": base_score,
        "status":        "moderate"
    })


# --- ROUTE 2: Calculate debt for given events ---
# NEW param: pass "include_weather": true in body to add AQI to score
@app.route('/api/calculate', methods=['POST'])
def calculate():
    data            = request.get_json()
    events          = data.get('events', [])
    include_weather = data.get('include_weather', False)   # NEW

    if not events:
        return jsonify({"error": "No events provided"}), 400

    result = calculate_debt(events, include_weather=include_weather)
    return jsonify(result)


# --- ROUTE 3: What-If simulator ---
@app.route('/api/whatif', methods=['POST'])
def whatif():
    data    = request.get_json()
    events  = data.get('events', [])
    bikes   = data.get('bikes', 0)
    cars    = data.get('cars', 0)
    solar   = data.get('solar', False)
    waste   = data.get('waste', False)

    result    = calculate_debt(events, include_weather=True)   # always bake weather in
    reduction = 0

    if bikes > 0: reduction += round((bikes / 100) * 10)
    if cars  > 0: reduction += round((cars  /  50) *  5)
    if solar:     reduction += 8
    if waste:     reduction += 6

    final_score = max(result['new_score'] - reduction, 0)

    return jsonify({
        "before":    result['new_score'],
        "reduction": reduction,
        "after":     final_score,
        "new_trees": round(final_score * 0.5),
        "new_cost":  final_score * 8,
        "message":   f"Green actions reduced debt by {reduction} points!"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8080)