from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models import db, User, CarbonLog, Badge
from datetime import datetime, timedelta
from functools import wraps
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'carbon_tracker_hackathon_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///carbon_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ─────────────────────────────────────────────
# EMISSION FACTORS (kg CO2 per unit)
# ─────────────────────────────────────────────
EMISSION_FACTORS = {
    "transport": {
        "car":    0.21,   # per km
        "bike":   0.0,
        "bus":    0.089,
        "train":  0.041,
        "flight": 0.255,
    },
    "food": {
        "meat_heavy": 7.19,   # per day
        "meat_medium":4.67,
        "vegetarian": 3.81,
        "vegan":      2.89,
    },
    "energy": {
        "electricity": 0.82,  # per kWh (India grid)
        "lpg":         2.98,  # per kg
    },
    "shopping": 0.5,           # per ₹100 spent
}

# ─────────────────────────────────────────────
# LOGIN REQUIRED DECORATOR
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        city     = request.form['city'].strip()

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        user = User(name=name, email=email, city=city)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash(f'Welcome, {name}! 🌱 Start tracking your carbon footprint.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ─────────────────────────────────────────────
# CALCULATOR ROUTE
# ─────────────────────────────────────────────
@app.route('/calculate', methods=['GET', 'POST'])
@login_required
def calculate():
    if request.method == 'POST':
        f = request.form

        # Transport
        transport_mode = f.get('transport_mode', 'car')
        transport_km   = float(f.get('transport_km', 0))
        transport_co2  = transport_km * EMISSION_FACTORS['transport'].get(transport_mode, 0.21)

        # Food
        food_type = f.get('food_type', 'meat_medium')
        food_co2  = EMISSION_FACTORS['food'].get(food_type, 4.67)

        # Energy
        electricity_kwh = float(f.get('electricity_kwh', 0))
        lpg_kg          = float(f.get('lpg_kg', 0))
        energy_co2      = (electricity_kwh * EMISSION_FACTORS['energy']['electricity']) + \
                          (lpg_kg * EMISSION_FACTORS['energy']['lpg'])

        # Shopping
        shopping_spend = float(f.get('shopping_spend', 0))
        shopping_co2   = (shopping_spend / 100) * EMISSION_FACTORS['shopping']

        total_co2 = round(transport_co2 + food_co2 + energy_co2 + shopping_co2, 2)

        breakdown = {
            'transport': round(transport_co2, 2),
            'food':      round(food_co2, 2),
            'energy':    round(energy_co2, 2),
            'shopping':  round(shopping_co2, 2),
        }

        # Save log
        log = CarbonLog(
            user_id=session['user_id'],
            date=datetime.today().date(),
            total_co2=total_co2,
            transport=breakdown['transport'],
            food=breakdown['food'],
            energy=breakdown['energy'],
            shopping=breakdown['shopping'],
        )
        db.session.add(log)
        db.session.commit()

        # Check & award badges
        _check_badges(session['user_id'], total_co2)

        flash(f'✅ Today\'s footprint logged: {total_co2} kg CO₂', 'success')
        return redirect(url_for('dashboard'))

    return render_template('calculate.html')


# ─────────────────────────────────────────────
# DASHBOARD (PROGRESS TRACKER)
# ─────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    last_30 = (datetime.today() - timedelta(days=30)).date()

    logs = CarbonLog.query.filter(
        CarbonLog.user_id == user.id,
        CarbonLog.date >= last_30
    ).order_by(CarbonLog.date).all()

    chart_labels  = [str(l.date) for l in logs]
    chart_data    = [l.total_co2 for l in logs]

    # Weekly average
    weekly_avg = round(sum(chart_data[-7:]) / max(len(chart_data[-7:]), 1), 2) if chart_data else 0
    monthly_total = round(sum(chart_data), 2)
    today_log = next((l for l in reversed(logs) if l.date == datetime.today().date()), None)

    badges = Badge.query.filter_by(user_id=user.id).all()

    # Breakdown totals for pie chart
    breakdown_totals = {
        'transport': round(sum(l.transport for l in logs), 2),
        'food':      round(sum(l.food      for l in logs), 2),
        'energy':    round(sum(l.energy    for l in logs), 2),
        'shopping':  round(sum(l.shopping  for l in logs), 2),
    }

    return render_template('dashboard.html',
        user=user,
        logs=logs,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
        breakdown_totals=json.dumps(breakdown_totals),
        weekly_avg=weekly_avg,
        monthly_total=monthly_total,
        today_log=today_log,
        badges=badges,
    )


# ─────────────────────────────────────────────
# TIPS ROUTE
# ─────────────────────────────────────────────
TIPS_DB = {
    'transport': [
        {"title": "Switch to public transport",   "desc": "Taking the bus instead of a car saves ~0.13 kg CO₂ per km.", "impact": "High"},
        {"title": "Try carpooling",               "desc": "Share rides to halve your per-person transport emissions.",     "impact": "High"},
        {"title": "Cycle short distances",        "desc": "Zero emissions and better health — win-win!",                  "impact": "Medium"},
        {"title": "Work from home 1 day/week",    "desc": "One WFH day per week can cut commute emissions by 20%.",       "impact": "Medium"},
    ],
    'food': [
        {"title": "Try Meatless Monday",          "desc": "Cutting meat once a week saves ~3.4 kg CO₂ per week.",        "impact": "High"},
        {"title": "Buy local produce",            "desc": "Local food has lower transport emissions.",                    "impact": "Medium"},
        {"title": "Reduce food waste",            "desc": "Wasted food = wasted emissions. Plan your meals.",             "impact": "Medium"},
        {"title": "Choose seasonal vegetables",   "desc": "Seasonal produce needs less energy to grow & ship.",           "impact": "Low"},
    ],
    'energy': [
        {"title": "Switch to LED bulbs",          "desc": "LEDs use 75% less energy than incandescent bulbs.",            "impact": "Medium"},
        {"title": "Unplug idle devices",          "desc": "Standby power accounts for up to 10% of home energy use.",    "impact": "Low"},
        {"title": "Use a fan before AC",          "desc": "Fans use 90% less energy than AC — use them first.",          "impact": "High"},
        {"title": "Solar water heater",           "desc": "Solar heaters can cut water heating emissions by 80%.",        "impact": "High"},
    ],
    'shopping': [
        {"title": "Buy second-hand",              "desc": "Pre-loved items produce zero manufacturing emissions.",        "impact": "High"},
        {"title": "Choose durable products",      "desc": "Buy once, buy well — fewer replacements = less CO₂.",         "impact": "Medium"},
        {"title": "Avoid fast fashion",           "desc": "Fashion is 10% of global CO₂. Choose wisely.",               "impact": "High"},
        {"title": "Repair before replace",        "desc": "Fixing items extends life and avoids new manufacturing.",     "impact": "Medium"},
    ],
}

@app.route('/tips')
@login_required
def tips():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).all()

    # Find highest emission category
    if logs:
        totals = {
            'transport': sum(l.transport for l in logs),
            'food':      sum(l.food      for l in logs),
            'energy':    sum(l.energy    for l in logs),
            'shopping':  sum(l.shopping  for l in logs),
        }
        top_category = max(totals, key=totals.get)
    else:
        top_category = 'transport'

    return render_template('tips.html',
        tips_db=TIPS_DB,
        top_category=top_category,
        user=user,
    )


# ─────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────
@app.route('/leaderboard')
@login_required
def leaderboard():
    user = User.query.get(session['user_id'])
    last_30 = (datetime.today() - timedelta(days=30)).date()

    all_users = User.query.all()
    rankings = []
    for u in all_users:
        logs = CarbonLog.query.filter(
            CarbonLog.user_id == u.id,
            CarbonLog.date >= last_30
        ).all()
        if logs:
            avg_co2 = round(sum(l.total_co2 for l in logs) / len(logs), 2)
            rankings.append({'user': u, 'avg_co2': avg_co2, 'logs_count': len(logs)})

    rankings.sort(key=lambda x: x['avg_co2'])

    city_data = {}
    for r in rankings:
        city = r['user'].city or 'Unknown'
        if city not in city_data:
            city_data[city] = []
        city_data[city].append(r['avg_co2'])

    city_avgs = {c: round(sum(v)/len(v), 2) for c, v in city_data.items()}
    city_labels = json.dumps(list(city_avgs.keys()))
    city_values = json.dumps(list(city_avgs.values()))

    return render_template('leaderboard.html',
        rankings=rankings,
        current_user=user,
        city_labels=city_labels,
        city_values=city_values,
    )


# ─────────────────────────────────────────────
# API: Quick CO2 calculation (AJAX)
# ─────────────────────────────────────────────
@app.route('/api/calculate', methods=['POST'])
@login_required
def api_calculate():
    data = request.get_json()
    transport_co2 = data.get('transport_km', 0) * EMISSION_FACTORS['transport'].get(data.get('transport_mode','car'), 0.21)
    food_co2      = EMISSION_FACTORS['food'].get(data.get('food_type','meat_medium'), 4.67)
    energy_co2    = data.get('electricity_kwh', 0) * EMISSION_FACTORS['energy']['electricity']
    shopping_co2  = (data.get('shopping_spend', 0) / 100) * EMISSION_FACTORS['shopping']
    total = round(transport_co2 + food_co2 + energy_co2 + shopping_co2, 2)
    return jsonify({'total_co2': total, 'transport': round(transport_co2,2), 'food': round(food_co2,2), 'energy': round(energy_co2,2), 'shopping': round(shopping_co2,2)})


# ─────────────────────────────────────────────
# BADGE LOGIC
# ─────────────────────────────────────────────
def _check_badges(user_id, today_co2):
    logs = CarbonLog.query.filter_by(user_id=user_id).all()
    existing = {b.name for b in Badge.query.filter_by(user_id=user_id).all()}

    def award(name, desc):
        if name not in existing:
            db.session.add(Badge(user_id=user_id, name=name, description=desc))
            db.session.commit()

    if today_co2 < 5:
        award("🌿 Green Day", "Logged a day with under 5 kg CO₂!")
    if len(logs) >= 7:
        award("🔥 Week Warrior", "Tracked for 7 days straight!")
    if len(logs) >= 30:
        award("🏆 Monthly Champion", "30 days of tracking!")
    if today_co2 < 3:
        award("⚡ Carbon Zero Hero", "Logged a day under 3 kg CO₂!")


# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
