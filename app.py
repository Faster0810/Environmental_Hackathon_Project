from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

def calculate_debt(events: list) -> dict:
    total_added = 0
    breakdown = []
    for event in events:
        weight = DEBT_WEIGHTS.get(event, 0)
        total_added += weight
        breakdown.append({"event": event, "impact": weight})
    new_score = min(base_score + total_added, 100)
    return {
        "base_score": base_score,
        "added": total_added,
        "new_score": new_score,
        "breakdown": breakdown
    }


# --- ROUTE 1: Get current base score ---
@app.route('/api/score', methods=['GET'])
def get_score():
    return jsonify({
        "location": "College Campus",
        "current_score": base_score,
        "status": "moderate"
    })


# --- ROUTE 2: Calculate debt for given events ---
@app.route('/api/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    events = data.get('events', [])
    if not events:
        return jsonify({"error": "No events provided"}), 400
    result = calculate_debt(events)
    return jsonify(result)


# --- ROUTE 3: What-If simulator ---
@app.route('/api/whatif', methods=['POST'])
def whatif():
    data = request.get_json()
    events = data.get('events', [])
    bikes = data.get('bikes', 0)        # number of students using bikes
    solar = data.get('solar', False)    # solar panels in use?

    result = calculate_debt(events)
    reduction = 0

    if bikes > 0:
        reduction += round((bikes / 100) * 10)  # every 100 bikes = -10 debt
    if solar:
        reduction += 8

    final_score = max(result['new_score'] - reduction, 0)

    return jsonify({
        "before": result['new_score'],
        "reduction": reduction,
        "after": final_score,
        "message": f"Green actions reduced debt by {reduction} points"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
    
app.py