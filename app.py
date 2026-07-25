from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models import db, User, CarbonLog, Badge, Pledge, CompletedAction
from datetime import datetime, timedelta
from functools import wraps
import json

from ai_engine import (ecobot, predictor, recommender,
                        anomaly_detector, streak_predictor, report_generator)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'carbon_tracker_hackathon_2024'
# Change line 12 in the main app.py file to:
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:2004@localhost:5432/carbon_tracker_db'
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
        
        user = User.query.get(session['user_id'])
        if user is None:
            session.clear()
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

    ecoscore, eco_label, eco_color = calculate_ecoscore(user.id)

    # Carbon used vs saved (vs India average 7 kg/day)
    INDIA_AVG   = 7.0
    all_logs    = CarbonLog.query.filter_by(user_id=user.id).all()
    total_days  = len(all_logs)
    overall_avg = round(sum(l.total_co2 for l in all_logs) / max(total_days, 1), 2)
    total_emitted = round(sum(l.total_co2 for l in all_logs), 1)
    total_if_avg  = round(INDIA_AVG * total_days, 1)
    
    # Calculate saved CO2 from completed daily activities
    user_actions = CompletedAction.query.filter_by(user_id=user.id).all()
    total_action_saved = sum(a.co2_saved for a in user_actions)
    today_action_saved = sum(a.co2_saved for a in user_actions if a.date == datetime.today().date())
    
    total_saved   = round(max(0, total_if_avg - total_emitted) + total_action_saved, 1)
    today_saved   = round(max(0, INDIA_AVG - (today_log.total_co2 if today_log else 0)) + today_action_saved, 2)
    today_emitted = round(today_log.total_co2 if today_log else 0, 2)
    trees_saved   = round(total_saved / 22, 1)

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
        ecoscore=ecoscore,
        eco_label=eco_label,
        eco_color=eco_color,
        total_emitted=total_emitted,
        total_saved=total_saved,
        today_saved=today_saved,
        today_emitted=today_emitted,
        trees_saved=trees_saved,
        overall_avg=overall_avg,
        india_avg=INDIA_AVG,
    )


# ─────────────────────────────────────────────
# TIPS ROUTE
# ─────────────────────────────────────────────
TIPS_DB = {
    'transport': [
        {"title": "Switch to public transport",     "desc": "Bus instead of car saves ~0.13 kg CO₂ per km. In India, Mumbai locals alone save millions of tonnes yearly.", "impact": "High"},
        {"title": "Try carpooling",                 "desc": "Share rides to halve your per-person emissions. Apps like BlaBlaCar make it easy.", "impact": "High"},
        {"title": "Cycle short distances",          "desc": "Zero emissions + better health. Cycling 5 km instead of driving saves ~1 kg CO₂.", "impact": "Medium"},
        {"title": "Work from home 1 day/week",      "desc": "One WFH day saves 20% of your weekly commute emissions — and saves time!", "impact": "Medium"},
        {"title": "Walk for trips under 1 km",      "desc": "Short car trips are the worst for emissions per km — engines are cold. Walk instead!", "impact": "Medium"},
        {"title": "Maintain your vehicle",          "desc": "Properly inflated tyres improve fuel efficiency by 3%. A tuned engine saves up to 10%.", "impact": "Low"},
        {"title": "Avoid unnecessary flights",      "desc": "One return flight Mumbai–Delhi = ~300 kg CO₂. Use trains for distances under 500 km.", "impact": "High"},
        {"title": "Switch to Electric Vehicle",     "desc": "EVs in India emit ~60% less CO₂ than petrol cars, even with current grid electricity.", "impact": "High"},
    ],
    'food': [
        {"title": "Try Meatless Monday",            "desc": "Cutting meat once a week saves ~3.4 kg CO₂ per week — that's 177 kg per year!", "impact": "High"},
        {"title": "Buy local produce",              "desc": "Local sabzi from nearby farms cuts transport emissions by up to 90% vs imported food.", "impact": "Medium"},
        {"title": "Reduce food waste",              "desc": "India wastes ~68 million tonnes of food yearly. Planning meals saves money AND emissions.", "impact": "High"},
        {"title": "Choose seasonal vegetables",     "desc": "Off-season veg needs heated greenhouses. Seasonal produce = 5x lower emissions.", "impact": "Medium"},
        {"title": "Avoid packaged & processed food","desc": "Processing and packaging food adds 30-50% more emissions than fresh ingredients.", "impact": "Medium"},
        {"title": "Grow your own herbs",            "desc": "A small kitchen garden — tulsi, mint, coriander — is zero-emission and fresh!", "impact": "Low"},
        {"title": "Use a pressure cooker",         "desc": "Pressure cookers use 70% less energy than open pots. Dal in 10 mins vs 40 mins.", "impact": "Low"},
        {"title": "Choose plant-based milk",        "desc": "Dairy milk = 3.2 kg CO₂/litre. Oat milk = 0.9 kg CO₂/litre. Try alternatives!", "impact": "Medium"},
    ],
    'energy': [
        {"title": "Switch to LED bulbs",            "desc": "LEDs use 75% less energy than incandescent bulbs and last 25x longer.", "impact": "Medium"},
        {"title": "Unplug idle devices",            "desc": "Standby power = 10% of home energy. TV, chargers, set-top boxes silently waste power.", "impact": "Low"},
        {"title": "Use a fan before AC",            "desc": "Fans use 90% less energy than AC. Set AC to 24°C minimum — each degree saves 6% energy.", "impact": "High"},
        {"title": "Install solar panels",           "desc": "A 2kW rooftop solar system in India generates ~2,400 kWh/year, offsetting 2 tonnes CO₂.", "impact": "High"},
        {"title": "Solar water heater",             "desc": "Solar heaters cut water heating emissions by 80% and are subsidised by government.", "impact": "High"},
        {"title": "Use natural light",              "desc": "Open curtains during day. Good ventilation design can eliminate daytime lighting needs.", "impact": "Low"},
        {"title": "Energy-efficient appliances",    "desc": "A 5-star rated fridge vs 3-star saves 200 kWh/year — that's ₹1,600 and 164 kg CO₂.", "impact": "Medium"},
        {"title": "Reduce hot water usage",         "desc": "Take shorter showers. Heating water accounts for 20% of home energy use.", "impact": "Medium"},
    ],
    'shopping': [
        {"title": "Buy second-hand",                "desc": "Pre-loved items produce zero manufacturing emissions. Thrift shops, OLX, Facebook Marketplace.", "impact": "High"},
        {"title": "Choose durable products",        "desc": "Buy once, buy well — fewer replacements = less manufacturing CO₂. Choose quality over cheapness.", "impact": "Medium"},
        {"title": "Avoid fast fashion",             "desc": "Fashion industry = 10% of global CO₂. One cotton T-shirt = 2.5 kg CO₂ to make.", "impact": "High"},
        {"title": "Repair before replace",          "desc": "Fixing a device or garment extends its life and avoids new manufacturing entirely.", "impact": "Medium"},
        {"title": "Use cloth bags",                 "desc": "One plastic bag = 6g CO₂. You use ~500/year. Reusable bags save 3 kg CO₂ annually.", "impact": "Low"},
        {"title": "Minimise online shopping",       "desc": "Last-mile delivery is emission-heavy. Batch your orders and choose slower delivery.", "impact": "Medium"},
        {"title": "Choose local brands",            "desc": "Imported products travel thousands of km. Supporting local reduces supply chain emissions.", "impact": "Medium"},
        {"title": "Avoid single-use plastics",      "desc": "Plastic production = 3.8% of global CO₂. Carry a water bottle, avoid disposable cutlery.", "impact": "Medium"},
    ],
    'water': [
        {"title": "Fix leaking taps",               "desc": "A dripping tap wastes 20 litres/day. Treating 1,000 litres of water emits ~0.4 kg CO₂.", "impact": "Medium"},
        {"title": "Install rainwater harvesting",   "desc": "Collect rainwater for gardening and cleaning. Mumbai gets 2,400 mm rain — huge opportunity!", "impact": "High"},
        {"title": "Take shorter showers",           "desc": "Cut shower time by 2 minutes = save 10 litres. Multiply by 365 days = 3,650 litres saved.", "impact": "Medium"},
        {"title": "Use bucket instead of pipe",     "desc": "A running hose uses 15 litres/min. A bucket for car washing uses just 15 litres total.", "impact": "High"},
        {"title": "Water plants in morning/evening","desc": "Watering in afternoon = 30% evaporation loss. Water at dawn or dusk for efficiency.", "impact": "Low"},
        {"title": "Reuse greywater",                "desc": "Water from washing vegetables or RO reject can water your plants — zero extra cost.", "impact": "Medium"},
    ],
    'waste': [
        {"title": "Start composting",               "desc": "Kitchen waste → compost = zero landfill methane. 1 kg organic waste = 0.5 kg CO₂ saved.", "impact": "High"},
        {"title": "Segregate your waste",           "desc": "Dry/wet segregation enables recycling. Recyclables in landfill = lost opportunity + more emissions.", "impact": "High"},
        {"title": "Avoid burning waste",            "desc": "Open burning releases 10x more CO₂ than landfill. Use municipal collection instead.", "impact": "High"},
        {"title": "Refuse, Reduce, Reuse, Recycle", "desc": "The 4Rs in order of importance. Refusing unnecessary items is the most powerful action.", "impact": "High"},
        {"title": "Digital over paper",             "desc": "One A4 sheet = 10g CO₂. Go paperless with bills, notes, tickets — saves trees too!", "impact": "Low"},
        {"title": "Donate unused items",            "desc": "One person's clutter is another's treasure. Donate clothes, books, electronics rather than discarding.", "impact": "Medium"},
    ],
    'green_habits': [
        {"title": "Plant a tree",                   "desc": "One tree absorbs ~22 kg CO₂/year. Plant native species like Neem, Peepal, Banyan in your area.", "impact": "High"},
        {"title": "Create a kitchen garden",        "desc": "Growing vegetables at home eliminates transport, packaging, and pesticide emissions.", "impact": "Medium"},
        {"title": "Spread awareness",               "desc": "Talk to 5 people about climate change. Behaviour change at scale > individual action alone.", "impact": "High"},
        {"title": "Support green businesses",       "desc": "Choose companies with sustainability certifications. Your spending is a vote for the future.", "impact": "Medium"},
        {"title": "Participate in tree drives",     "desc": "Join Van Mahotsav, local NGO drives. Communities planting together have higher tree survival rates.", "impact": "High"},
        {"title": "Teach children about climate",   "desc": "Climate habits formed in childhood last a lifetime. Make sustainability fun for kids.", "impact": "High"},
        {"title": "Vote for green policies",        "desc": "Government policy > individual action in scale. Support leaders with strong climate commitments.", "impact": "High"},
        {"title": "Join a local eco-group",         "desc": "Communities like Fridays for Future India, Greenpeace India amplify individual efforts 1000x.", "impact": "Medium"},
    ],
}

# ─────────────────────────────────────────────
# DAILY CHALLENGES DATA
# ─────────────────────────────────────────────
CHALLENGES = [
    {"day": 1,  "emoji": "🚶", "title": "Walk it out",           "task": "Walk or cycle for at least one trip today instead of using a vehicle.",       "saving": "~1.5 kg CO₂"},
    {"day": 2,  "emoji": "🥦", "title": "Go meat-free today",    "task": "Eat a fully vegetarian or vegan diet for today.",                              "saving": "~3.5 kg CO₂"},
    {"day": 3,  "emoji": "💡", "title": "Unplug everything",     "task": "Unplug all devices not in use for 24 hours — TV, chargers, set-top box.",     "saving": "~0.5 kg CO₂"},
    {"day": 4,  "emoji": "🛍️", "title": "Zero-plastic day",      "task": "Refuse all single-use plastic today — carry your own bag and bottle.",        "saving": "~0.3 kg CO₂"},
    {"day": 5,  "emoji": "🚰", "title": "Save water today",      "task": "Take a 5-min shower and fix any dripping taps you notice.",                   "saving": "~0.2 kg CO₂"},
    {"day": 6,  "emoji": "📱", "title": "Digital detox hour",    "task": "Power off all screens for 1 hour. Streaming 1 hr HD video = 36g CO₂.",        "saving": "~0.1 kg CO₂"},
    {"day": 7,  "emoji": "🌱", "title": "Plant something",       "task": "Plant a seed, sapling, or tend to a plant. Every tree absorbs 22 kg CO₂/yr.", "saving": "22 kg/year"},
    {"day": 8,  "emoji": "♻️", "title": "Waste audit",           "task": "Segregate your household waste into wet, dry, and hazardous today.",          "saving": "~1 kg CO₂"},
    {"day": 9,  "emoji": "☀️", "title": "Solar day",             "task": "Do 2 major tasks using daylight only — no artificial lights before 6pm.",     "saving": "~0.3 kg CO₂"},
    {"day": 10, "emoji": "🤝", "title": "Spread the word",       "task": "Share 1 climate fact with a friend or family member today.",                   "saving": "Priceless"},
    {"day": 11, "emoji": "🍳", "title": "Cook from scratch",     "task": "Avoid packaged/processed food. Cook a fresh meal from raw ingredients.",      "saving": "~1.2 kg CO₂"},
    {"day": 12, "emoji": "🚌", "title": "Public transport day",  "task": "Use only public transport today — no private vehicles at all.",               "saving": "~2.5 kg CO₂"},
    {"day": 13, "emoji": "💧", "title": "Collect rainwater",     "task": "Set up a bucket to collect water for plants or cleaning use.",                "saving": "~0.4 kg CO₂"},
    {"day": 14, "emoji": "🧺", "title": "Air-dry clothes",       "task": "Skip the dryer (if used). Air-dry all laundry today.",                        "saving": "~2 kg CO₂"},
    {"day": 15, "emoji": "🛒", "title": "Buy local only",        "task": "Source all food and necessities from local markets or nearby farms today.",   "saving": "~1 kg CO₂"},
    {"day": 16, "emoji": "🔧", "title": "Repair something",      "task": "Fix a broken item instead of throwing it away — clothes, electronics, shoes.", "saving": "~3 kg CO₂"},
    {"day": 17, "emoji": "🌿", "title": "Compost kitchen waste", "task": "Start or contribute to a compost bin with today's kitchen scraps.",           "saving": "~0.5 kg CO₂"},
    {"day": 18, "emoji": "❄️", "title": "AC-free day",           "task": "Get through the day without air conditioning. Use fans, cross-ventilation.",  "saving": "~3 kg CO₂"},
    {"day": 19, "emoji": "🎁", "title": "Donate or swap",        "task": "Find one item you no longer need and donate, sell or swap it.",               "saving": "~2 kg CO₂"},
    {"day": 20, "emoji": "📚", "title": "Learn & share",         "task": "Read one article on climate change and share the key fact with someone.",     "saving": "Awareness"},
    {"day": 21, "emoji": "🏃", "title": "Active commute week",   "task": "Commit to walking or cycling every day this week.",                           "saving": "~10 kg CO₂"},
    {"day": 22, "emoji": "🌍", "title": "Earth Day action",      "task": "Join or organise a local cleanup, tree planting, or awareness event.",        "saving": "Community impact"},
    {"day": 23, "emoji": "🍱", "title": "Zero food waste day",   "task": "Use every ingredient in your kitchen. No food goes in the bin today.",        "saving": "~1.5 kg CO₂"},
    {"day": 24, "emoji": "🌞", "title": "Natural light day",     "task": "Rely only on natural light all day. Plan your tasks around daylight.",        "saving": "~0.4 kg CO₂"},
    {"day": 25, "emoji": "📦", "title": "No online shopping",    "task": "Resist online purchases for 24 hours. Delay = often don't buy at all.",       "saving": "~1 kg CO₂"},
    {"day": 26, "emoji": "🫙", "title": "Refill, don't rebuy",   "task": "Refill a container — water bottle, tiffin, masala dabba — instead of buying new.", "saving": "~0.2 kg CO₂"},
    {"day": 27, "emoji": "🚿", "title": "3-minute shower",       "task": "Challenge yourself to shower in under 3 minutes today.",                      "saving": "~0.3 kg CO₂"},
    {"day": 28, "emoji": "🌳", "title": "Adopt a tree",          "task": "Find a tree near your home/campus and commit to caring for it.",              "saving": "22 kg CO₂/year"},
    {"day": 29, "emoji": "🤲", "title": "Community action",      "task": "Invite neighbours/friends to join GreenSaathi. Collective action multiplies impact.", "saving": "Multiplied"},
    {"day": 30, "emoji": "🏆", "title": "Reflect & recommit",    "task": "Review your 30-day journey. Calculate how much CO₂ you saved. Share your badge!", "saving": "Your total!"},
]

# ─────────────────────────────────────────────
# CLIMATE FACTS
# ─────────────────────────────────────────────
CLIMATE_FACTS = [
    {"icon": "🌡️", "stat": "1.1°C",    "label": "Global warming since 1850",     "detail": "The Earth has already warmed 1.1°C above pre-industrial levels. The target is to stay below 1.5°C."},
    {"icon": "🧊", "stat": "25%",       "label": "Arctic ice lost since 1980",    "detail": "Arctic sea ice has declined by about 25% since satellite monitoring began in 1979."},
    {"icon": "🌊", "stat": "20 cm",     "label": "Sea level rise since 1900",     "detail": "Global sea levels have risen ~20 cm since 1900. Mumbai's coastline is already affected."},
    {"icon": "🌿", "stat": "15B",       "label": "Trees cut down every year",     "detail": "15 billion trees are felled every year. Earth has lost 46% of its trees since human civilisation began."},
    {"icon": "🏭", "stat": "37B tonnes","label": "CO₂ emitted in 2023",           "detail": "Global CO₂ emissions hit a record 37.4 billion tonnes in 2023 — higher than ever before."},
    {"icon": "🐾", "stat": "69%",       "label": "Wildlife declined since 1970",  "detail": "WWF's Living Planet Report shows average wildlife population sizes have fallen by 69% since 1970."},
    {"icon": "☀️", "stat": "10x",       "label": "Cost of solar fell in 10 years","detail": "Solar energy cost dropped 90% between 2010 and 2020. Renewables are now cheaper than coal in India."},
    {"icon": "🇮🇳", "stat": "3rd",      "label": "India's global CO₂ rank",       "detail": "India is the 3rd largest emitter. But per-capita emissions are still much lower than the USA or EU."},
    {"icon": "🌾", "stat": "33%",       "label": "Emissions from food systems",   "detail": "One-third of all greenhouse gas emissions come from how we produce, transport, and waste food."},
    {"icon": "🔋", "stat": "500GW",     "label": "India's renewable target 2030", "detail": "India has pledged 500 GW of renewable energy by 2030 — one of the world's most ambitious targets."},
    {"icon": "💧", "stat": "2B people", "label": "Face water scarcity today",     "detail": "Over 2 billion people already live in water-scarce regions. Climate change will intensify this crisis."},
    {"icon": "🌱", "stat": "40%",       "label": "Emissions reducible by lifestyle","detail": "Studies show individuals can reduce their carbon footprint by up to 40% through daily choices."},
]

@app.route('/tips')
@login_required
def tips():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).all()
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
# 30-DAY CHALLENGE
# ─────────────────────────────────────────────
@app.route('/challenges')
@login_required
def challenges():
    user = User.query.get(session['user_id'])
    logs_count = CarbonLog.query.filter_by(user_id=user.id).count()
    return render_template('challenges.html',
        challenges=CHALLENGES,
        logs_count=logs_count,
        user=user,
    )


# ─────────────────────────────────────────────
# CLIMATE AWARENESS PAGE
# ─────────────────────────────────────────────
@app.route('/awareness')
@login_required
def awareness():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).all()
    
    # Calculate saved CO2 from completed daily activities
    user_actions = CompletedAction.query.filter_by(user_id=user.id).all()
    total_action_saved = sum(a.co2_saved for a in user_actions)
    
    total_saved = 0
    if logs:
        avg = sum(l.total_co2 for l in logs) / len(logs)
        india_avg = 7.0
        if avg < india_avg:
            total_saved = round((india_avg - avg) * len(logs), 1)
            
    total_saved = round(total_saved + total_action_saved, 1)
    trees_equiv = round(total_saved / 22, 1) if total_saved > 0 else 0
    return render_template('awareness.html',
        facts=CLIMATE_FACTS,
        user=user,
        total_saved=total_saved,
        trees_equiv=trees_equiv,
        logs_count=len(logs),
    )


# ─────────────────────────────────────────────
# 🎯 DAILY ACTION  (CoolTheGlobe inspired)
# ─────────────────────────────────────────────
DAILY_ACTIONS = [
    {"id":"t1","cat":"transport","icon":"🚌","title":"Bus/Metro Day",    "desc":"आज कमीत कमी एक trip public transport ने करा","co2_saved":1.5,"points":50,"easy":True},
    {"id":"t2","cat":"transport","icon":"🚲","title":"Cycle 5km",        "desc":"5 km सायकल किंवा walk करा","co2_saved":1.05,"points":60,"easy":True},
    {"id":"t3","cat":"transport","icon":"🤝","title":"Carpool Today",    "desc":"एका colleague सोबत ride share करा","co2_saved":2.1,"points":70,"easy":False},
    {"id":"t4","cat":"transport","icon":"🏠","title":"Work From Home",   "desc":"आज WFH करा — commute emissions zero!","co2_saved":2.5,"points":80,"easy":False},
    {"id":"t5","cat":"transport","icon":"🚶","title":"Zero Engine Day",  "desc":"कोणताही engine चालवू नका आज","co2_saved":3.2,"points":100,"easy":False},
    {"id":"f1","cat":"food","icon":"🥦","title":"Meatless Day",          "desc":"आज पूर्ण vegetarian जेवण","co2_saved":3.4,"points":70,"easy":True},
    {"id":"f2","cat":"food","icon":"🌱","title":"Vegan Day",             "desc":"आज पूर्ण vegan — dairy पण नाही","co2_saved":4.3,"points":90,"easy":False},
    {"id":"f3","cat":"food","icon":"🛒","title":"Local Market Only",     "desc":"Local sabzi market मधून खरेदी","co2_saved":0.8,"points":40,"easy":True},
    {"id":"f4","cat":"food","icon":"♻️","title":"Zero Food Waste",      "desc":"आज कोणताही अन्न वाया घालवू नका","co2_saved":0.9,"points":50,"easy":True},
    {"id":"f5","cat":"food","icon":"🍳","title":"Pressure Cooker Day",   "desc":"सगळं शिजवणे pressure cooker मध्येच","co2_saved":0.5,"points":30,"easy":True},
    {"id":"e1","cat":"energy","icon":"💡","title":"LED Switch",          "desc":"एक incandescent bulb → LED ने replace करा","co2_saved":0.3,"points":40,"easy":True},
    {"id":"e2","cat":"energy","icon":"🔌","title":"Unplug Everything",   "desc":"झोपण्यापूर्वी सर्व devices unplug करा","co2_saved":0.5,"points":30,"easy":True},
    {"id":"e3","cat":"energy","icon":"🌞","title":"Natural Light Only",  "desc":"दिवसभर artificial lights वापरू नका","co2_saved":0.4,"points":40,"easy":True},
    {"id":"e4","cat":"energy","icon":"❄️","title":"AC-Free Day",        "desc":"AC बंद — fan + cross ventilation वापरा","co2_saved":3.0,"points":80,"easy":False},
    {"id":"e5","cat":"energy","icon":"☀️","title":"Solar Research",     "desc":"PM Surya Ghar scheme apply करा","co2_saved":900.0,"points":150,"easy":False},
    {"id":"w1","cat":"waste","icon":"🛍️","title":"No Plastic Day",     "desc":"आज एकही single-use plastic वापरू नका","co2_saved":0.3,"points":50,"easy":True},
    {"id":"w2","cat":"waste","icon":"🌿","title":"Start Composting",     "desc":"Kitchen waste compost bin मध्ये टाका","co2_saved":0.5,"points":60,"easy":True},
    {"id":"w3","cat":"waste","icon":"📦","title":"Recycle Drive",        "desc":"घरचा सुका कचरा kabadiwala ला द्या","co2_saved":0.8,"points":50,"easy":True},
    {"id":"w4","cat":"waste","icon":"🔧","title":"Repair Not Replace",   "desc":"एखादी broken item fix करा today","co2_saved":2.0,"points":70,"easy":False},
    {"id":"c1","cat":"community","icon":"📢","title":"Spread the Word",  "desc":"GreenSaathi बद्दल 3 मित्रांना सांगा","co2_saved":50.0,"points":100,"easy":True},
    {"id":"c2","cat":"community","icon":"🌳","title":"Plant a Tree",     "desc":"एक native tree (Neem/Peepal) लावा","co2_saved":22.0,"points":200,"easy":False},
    {"id":"c3","cat":"community","icon":"🧹","title":"Community Cleanup","desc":"Nearby area cleanup मध्ये participate करा","co2_saved":5.0,"points":150,"easy":False},
    {"id":"c4","cat":"community","icon":"📱","title":"Report Burning",   "desc":"Open burning दिसल्यास MPCB ला report करा","co2_saved":10.0,"points":100,"easy":True},
]

@app.route('/daily-action')
@login_required
def daily_action():
    import random
    user  = User.query.get(session['user_id'])
    logs  = CarbonLog.query.filter_by(user_id=user.id).all()
    top_cat = 'transport'
    if logs:
        totals = {'transport':sum(l.transport for l in logs),'food':sum(l.food for l in logs),
                  'energy':sum(l.energy for l in logs),'waste':sum(l.shopping for l in logs)}
        top_cat = max(totals, key=totals.get)
    random.seed(int(datetime.today().strftime('%Y%m%d')))
    cat_actions = [a for a in DAILY_ACTIONS if a['cat'] == top_cat]
    other       = [a for a in DAILY_ACTIONS if a['cat'] != top_cat]
    todays_pick = random.choice(cat_actions) if cat_actions else DAILY_ACTIONS[0]
    easy_picks  = random.sample([a for a in other if a['easy']], min(3, len([a for a in other if a['easy']])))
    random.seed()
    all_by_cat  = {}
    for a in DAILY_ACTIONS:
        all_by_cat.setdefault(a['cat'], []).append(a)

    completed_today = CompletedAction.query.filter_by(
        user_id=user.id,
        date=datetime.today().date()
    ).all()
    completed_ids = [a.action_id for a in completed_today]

    return render_template('daily_action.html',
        user=user, todays_pick=todays_pick, easy_picks=easy_picks,
        all_actions=DAILY_ACTIONS, all_by_cat=all_by_cat,
        top_cat=top_cat, total_actions=len(DAILY_ACTIONS), logs_count=len(logs),
        completed_ids=completed_ids)


# ─────────────────────────────────────────────
# 🌍 GLOBAL IMPACT  (CoolTheGlobe community dashboard)
# ─────────────────────────────────────────────
@app.route('/global-impact')
@login_required
def global_impact():
    from collections import defaultdict
    user      = User.query.get(session['user_id'])
    all_logs  = CarbonLog.query.all()
    all_users = User.query.count()
    india_avg = 7.0

    total_logged  = round(sum(l.total_co2 for l in all_logs), 1)
    total_days    = len(all_logs)
    avg_community = round(total_logged / max(total_days, 1), 2)
    saved         = round(max(0, (india_avg - avg_community) * total_days), 1)
    trees         = round(saved / 22, 1)
    flights       = round(saved / 255, 1)

    city_data = defaultdict(list)
    for l in all_logs:
        city_data[l.user.city or 'Unknown'].append(l.total_co2)
    city_avgs  = {c: round(sum(v)/len(v),2) for c,v in city_data.items() if len(v)>=1}
    city_sorted= sorted(city_avgs.items(), key=lambda x: x[1])[:8]

    week_totals = defaultdict(list)
    for l in all_logs:
        week_totals[l.date.strftime('%Y-W%V')].append(l.total_co2)
    sorted_wks = sorted(week_totals.items())[-8:]
    w_labels   = [w[0] for w in sorted_wks]
    w_avgs     = [round(sum(w[1])/len(w[1]),2) for w in sorted_wks]

    user_logs = CarbonLog.query.filter_by(user_id=user.id).all()
    user_avg  = round(sum(l.total_co2 for l in user_logs)/max(len(user_logs),1), 2)
    users_below = sum(1 for u in User.query.all()
        if u.id != user.id and u.logs and
        sum(l.total_co2 for l in u.logs)/len(u.logs) > user_avg)
    rank_pct = int(round(users_below/max(all_users-1,1)*100, 0))

    return render_template('global_impact.html',
        user=user, all_users=all_users, total_days=total_days,
        total_logged=total_logged, saved=saved, trees=trees, flights=flights,
        avg_community=avg_community, city_sorted=city_sorted,
        city_labels=json.dumps([c[0] for c in city_sorted]),
        city_vals=json.dumps([c[1] for c in city_sorted]),
        w_labels=json.dumps(w_labels), w_avgs=json.dumps(w_avgs),
        user_avg=user_avg, rank_pct=rank_pct)


# ─────────────────────────────────────────────
# WHAT-IF SIMULATOR (inspired by Earth-2 scenario modeling)
# ─────────────────────────────────────────────
@app.route('/simulator')
@login_required
def simulator():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date.desc()).limit(30).all()

    avg_transport = round(sum(l.transport for l in logs) / max(len(logs), 1), 2)
    avg_food      = round(sum(l.food      for l in logs) / max(len(logs), 1), 2)
    avg_energy    = round(sum(l.energy    for l in logs) / max(len(logs), 1), 2)
    avg_shopping  = round(sum(l.shopping  for l in logs) / max(len(logs), 1), 2)
    avg_total     = round(avg_transport + avg_food + avg_energy + avg_shopping, 2)

    # Future projection: 1 year at current rate
    yearly_current   = round(avg_total * 365, 1)
    yearly_if_bus    = round((avg_transport * 0.42 + avg_food + avg_energy + avg_shopping) * 365, 1)
    yearly_if_veg    = round((avg_transport + 3.81 + avg_energy + avg_shopping) * 365, 1)
    yearly_if_solar  = round((avg_transport + avg_food + avg_energy * 0.2 + avg_shopping) * 365, 1)
    yearly_if_all    = round((avg_transport * 0.42 + 3.81 + avg_energy * 0.2 + avg_shopping * 0.5) * 365, 1)

    scenarios = [
        {"name": "🚌 Switch to Bus/Train",      "yearly": yearly_if_bus,   "saving": round(yearly_current - yearly_if_bus, 1),   "trees": round((yearly_current - yearly_if_bus) / 22, 1)},
        {"name": "🥦 Go Vegetarian",             "yearly": yearly_if_veg,   "saving": round(yearly_current - yearly_if_veg, 1),   "trees": round((yearly_current - yearly_if_veg) / 22, 1)},
        {"name": "☀️ Switch to Solar Energy",    "yearly": yearly_if_solar, "saving": round(yearly_current - yearly_if_solar, 1), "trees": round((yearly_current - yearly_if_solar) / 22, 1)},
        {"name": "🌟 All Changes Combined",      "yearly": yearly_if_all,   "saving": round(yearly_current - yearly_if_all, 1),   "trees": round((yearly_current - yearly_if_all) / 22, 1)},
    ]

    return render_template('simulator.html',
        user=user,
        avg_total=avg_total,
        avg_transport=avg_transport,
        avg_food=avg_food,
        avg_energy=avg_energy,
        avg_shopping=avg_shopping,
        yearly_current=yearly_current,
        scenarios=json.dumps(scenarios),
        scenarios_list=scenarios,
        has_data=len(logs) > 0,
    )


# ─────────────────────────────────────────────
# INDIA CLIMATE RISK MAP (inspired by Earth-2 geospatial)
# ─────────────────────────────────────────────
INDIA_CLIMATE_RISKS = {
    "Maharashtra": {
        "drought":     "Very High",
        "heat_stress": "High",
        "flood":       "Medium",
        "regions": ["Marathwada (severe drought)", "Vidarbha (extreme heat)", "Konkan (flooding)"],
        "fact": "Marathwada has faced drought for 6 of last 10 years. Groundwater depleted by 40%.",
        "co2_contribution": 12.4,
    },
    "Rajasthan": {
        "drought": "Extreme", "heat_stress": "Extreme", "flood": "Low",
        "regions": ["Thar Desert expansion", "Barmer (45°C+ heat waves)"],
        "fact": "Jaisalmer recorded 51°C in 2023. Desert is expanding eastward at 0.5 km/year.",
        "co2_contribution": 8.1,
    },
    "Kerala": {
        "drought": "Low", "heat_stress": "Medium", "flood": "Very High",
        "regions": ["Wayanad (landslides)", "Alappuzha (coastal flooding)"],
        "fact": "2018 Kerala floods: worst in 100 years. 483 deaths, ₹31,000 crore damage.",
        "co2_contribution": 3.2,
    },
    "Uttarakhand": {
        "drought": "Medium", "heat_stress": "Low", "flood": "Very High",
        "regions": ["Chamoli (glacial lake outbursts)", "Kedarnath zone"],
        "fact": "Glaciers retreating 20m/year. Himalayan glaciers feed 600 million people downstream.",
        "co2_contribution": 1.8,
    },
    "West Bengal": {
        "drought": "Medium", "heat_stress": "High", "flood": "Very High",
        "regions": ["Sundarbans (sea level rise)", "Kolkata (urban heat island)"],
        "fact": "Sundarbans losing 8 sq km of land yearly to rising seas. 4 million people at risk.",
        "co2_contribution": 9.7,
    },
    "Gujarat": {
        "drought": "High", "heat_stress": "Very High", "flood": "Medium",
        "regions": ["Kutch (cyclone zone)", "Saurashtra (water scarcity)"],
        "fact": "Gujarat coastline faces 6 major cyclones/decade. 2020 cyclone Amphan = ₹1 lakh crore damage.",
        "co2_contribution": 14.2,
    },
}


@app.route('/climate-risk')
@login_required
def climate_risk():
    user = User.query.get(session['user_id'])
    return render_template('climate_risk.html',
        user=user,
        risks=INDIA_CLIMATE_RISKS,
        risks_json=json.dumps(INDIA_CLIMATE_RISKS),
    )


# ─────────────────────────────────────────────
# COMMUNITY PLEDGE WALL (inspired by Earth-2 collaboration)
# ─────────────────────────────────────────────
PLEDGE_OPTIONS = [
    {"id": "p1", "icon": "🚲", "text": "I will cycle/walk for trips under 2 km",       "co2_saving": 1.5},
    {"id": "p2", "icon": "🥦", "text": "I will go meat-free at least 3 days/week",     "co2_saving": 10.2},
    {"id": "p3", "icon": "💡", "text": "I will switch all lights to LED",               "co2_saving": 2.4},
    {"id": "p4", "icon": "🛍️", "text": "I will carry a reusable bag always",           "co2_saving": 0.5},
    {"id": "p5", "icon": "🌱", "text": "I will plant at least 1 tree this month",      "co2_saving": 22.0},
    {"id": "p6", "icon": "🚿", "text": "I will shower in under 5 minutes",             "co2_saving": 0.8},
    {"id": "p7", "icon": "♻️", "text": "I will segregate wet/dry waste daily",         "co2_saving": 1.2},
    {"id": "p8", "icon": "🚌", "text": "I will use public transport 5 days/week",      "co2_saving": 18.5},
    {"id": "p9", "icon": "☀️", "text": "I will explore solar panels for my home",      "co2_saving": 900.0},
    {"id":"p10", "icon": "📱", "text": "I will spread awareness to 5 friends",          "co2_saving": 50.0},
]

@app.route('/pledge', methods=['GET', 'POST'])
@login_required
def pledge():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        pledge_id   = request.form.get('pledge_id')
        pledge_text = next((p['text'] for p in PLEDGE_OPTIONS if p['id'] == pledge_id), '')
        pledge_co2  = next((p['co2_saving'] for p in PLEDGE_OPTIONS if p['id'] == pledge_id), 0)
        existing = Pledge.query.filter_by(user_id=user.id, pledge_id=pledge_id).first()
        if not existing:
            db.session.add(Pledge(user_id=user.id, pledge_id=pledge_id, text=pledge_text, co2_saving=pledge_co2))
            db.session.commit()
        return redirect(url_for('pledge'))

    all_pledges = Pledge.query.order_by(Pledge.created_at.desc()).all()
    user_pledge_ids = {p.pledge_id for p in Pledge.query.filter_by(user_id=user.id).all()}
    total_community_co2 = round(sum(p.co2_saving for p in all_pledges), 1)
    pledgers_count = db.session.query(Pledge.user_id).distinct().count()

    return render_template('pledge.html',
        user=user,
        pledge_options=PLEDGE_OPTIONS,
        all_pledges=all_pledges,
        user_pledge_ids=user_pledge_ids,
        total_community_co2=total_community_co2,
        pledgers_count=pledgers_count,
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
# API: Record completed daily action
# ─────────────────────────────────────────────
@app.route('/api/complete-action', methods=['POST'])
@login_required
def complete_action():
    data = request.get_json() or {}
    action_id = data.get('action_id')
    title = data.get('title')
    co2_saved = float(data.get('co2_saved', 0.0))
    
    if not action_id or not title:
        return jsonify({'success': False, 'error': 'Missing action details'}), 400
    
    today = datetime.today().date()
    existing = CompletedAction.query.filter_by(
        user_id=session['user_id'],
        action_id=action_id,
        date=today
    ).first()
    
    if not existing:
        completed = CompletedAction(
            user_id=session['user_id'],
            action_id=action_id,
            title=title,
            co2_saved=co2_saved,
            date=today
        )
        db.session.add(completed)
        db.session.commit()
        
    return jsonify({'success': True})


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
# ECOSCORE HELPER
# ─────────────────────────────────────────────
def calculate_ecoscore(user_id):
    logs  = CarbonLog.query.filter_by(user_id=user_id).all()
    if not logs:
        return 0, "Beginner", "#888"
    avg        = sum(l.total_co2 for l in logs) / len(logs)
    consistency= min(len(logs) / 30 * 30, 30)
    emit_score = max(0, min(50, (10 - avg) * 5 + 20))
    badge_pts  = min(Badge.query.filter_by(user_id=user_id).count() * 4, 20)
    score      = int(min(100, consistency + emit_score + badge_pts))
    if score >= 80:  label, color = "Eco Champion 🏆", "#1a7a45"
    elif score >= 60:label, color = "Green Warrior 🌿", "#2d9e5f"
    elif score >= 40:label, color = "Eco Learner 🌱",  "#f4a261"
    else:            label, color = "Just Starting 🌍", "#e76f51"
    return score, label, color


# ─────────────────────────────────────────────
# CARBON DIGITAL TWIN  (Earth-2 inspired)
# ─────────────────────────────────────────────
@app.route('/my-twin')
@login_required
def carbon_twin():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).all()
    if not logs:
        flash("Log at least one day first to see your Carbon Twin!", "warning")
        return redirect(url_for('calculate'))

    avg_daily = sum(l.total_co2 for l in logs) / len(logs)
    india_avg  = 7.0
    world_avg  = 13.0

    # Breakdown averages
    avg_t = round(sum(l.transport for l in logs)/len(logs), 2)
    avg_f = round(sum(l.food      for l in logs)/len(logs), 2)
    avg_e = round(sum(l.energy    for l in logs)/len(logs), 2)
    avg_s = round(sum(l.shopping  for l in logs)/len(logs), 2)

    proj = {
        'daily':       round(avg_daily, 2),
        'monthly':     round(avg_daily * 30, 1),
        'yearly':      round(avg_daily * 365, 1),
        'five_years':  round(avg_daily * 365 * 5, 1),
        'trees_yearly':round(avg_daily * 365 / 22, 1),
        'flights_eq':  round(avg_daily * 365 / 255, 1),
        'vs_india_pct':round(((avg_daily - india_avg) / india_avg) * 100, 1),
        'vs_world_pct':round(((avg_daily - world_avg) / world_avg) * 100, 1),
    }

    # What-if sliders default values
    what_if = {
        'transport_reduce': 50,
        'food_switch':      'vegetarian',
        'energy_reduce':    30,
    }

    ecoscore, eco_label, eco_color = calculate_ecoscore(user.id)
    breakdown_json = json.dumps({'transport': avg_t, 'food': avg_f,
                                  'energy': avg_e, 'shopping': avg_s})

    return render_template('carbon_twin.html',
        user=user, proj=proj, ecoscore=ecoscore,
        eco_label=eco_label, eco_color=eco_color,
        avg_t=avg_t, avg_f=avg_f, avg_e=avg_e, avg_s=avg_s,
        breakdown_json=breakdown_json,
        india_avg=india_avg, world_avg=world_avg,
    )


# ─────────────────────────────────────────────
# AI SMART ADVISOR  (Earth-2 AI insight inspired)
# ─────────────────────────────────────────────
AI_TIPS_BANK = {
    'transport': [
        "Switch from car to bus/train for your daily commute — saves up to 0.13 kg CO₂ per km.",
        "Consider cycling short distances under 5 km — zero emissions and great for health!",
        "Try carpooling with colleagues — halves your per-person transport emissions instantly.",
        "Work from home even 1 day/week cuts your commute footprint by 20%.",
    ],
    'food': [
        "Try Meatless Monday — cutting meat once a week saves ~3.4 kg CO₂ per week.",
        "Buy vegetables from your local market instead of supermarket — lower transport emissions.",
        "Plan your weekly meals to reduce food waste — 40% of Indian food is wasted.",
        "Switch to a fully vegetarian diet — saves ~0.86 kg CO₂ per day vs average.",
    ],
    'energy': [
        "Set your AC to 24°C minimum — every degree lower uses 6% more electricity.",
        "Unplug phone chargers, TV, and set-top box when not in use — saves 10% standby power.",
        "Replace remaining incandescent bulbs with LED — uses 75% less energy.",
        "Explore the PM Surya Ghar scheme for rooftop solar — up to ₹78,000 subsidy available!",
    ],
    'shopping': [
        "Buy one item second-hand this week instead of new — zero manufacturing emissions.",
        "Carry a reusable bag and bottle daily — saves ~500 plastic bags per year.",
        "Avoid fast fashion — choose quality over quantity, one durable item over three cheap ones.",
        "Repair before replace — fixing a garment or device avoids ~3 kg CO₂ of new manufacturing.",
    ],
}

@app.route('/ai-advisor')
@login_required
def ai_advisor():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(
                CarbonLog.date.desc()).limit(30).all()

    import random

    # Always-safe defaults
    context = {
        'avg': 0, 'days': 0, 'trend': 'no_data', 'trend_pct': 0,
        'top1': 'transport', 'top2': 'food',
        'breakdown': {'transport': 0, 'food': 0, 'energy': 0, 'shopping': 0},
    }
    smart_tips  = []
    benchmarks  = []
    week_labels = []
    week_data   = []

    if logs:
        avg = round(sum(l.total_co2 for l in logs) / len(logs), 2)
        breakdown = {
            'transport': round(sum(l.transport for l in logs) / len(logs), 2),
            'food':      round(sum(l.food      for l in logs) / len(logs), 2),
            'energy':    round(sum(l.energy    for l in logs) / len(logs), 2),
            'shopping':  round(sum(l.shopping  for l in logs) / len(logs), 2),
        }
        ranked = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        top1   = ranked[0][0]
        top2   = ranked[1][0] if len(ranked) > 1 else 'food'

        trend     = 'insufficient'
        trend_pct = 0
        if len(logs) >= 7:
            recent_avg = sum(l.total_co2 for l in logs[:7]) / 7
            older_avg  = sum(l.total_co2 for l in logs[7:]) / max(len(logs)-7, 1)
            trend      = 'improving' if recent_avg < older_avg else 'worsening'
            trend_pct  = abs(round((recent_avg - older_avg) / max(older_avg, 0.01) * 100, 1))

        context = {
            'avg': avg, 'days': len(logs), 'trend': trend, 'trend_pct': trend_pct,
            'top1': top1, 'top2': top2, 'breakdown': breakdown,
        }

        for cat, _ in ranked[:3]:
            pool = AI_TIPS_BANK.get(cat, [])
            if pool:
                smart_tips.append({'category': cat, 'tip': random.choice(pool)})

        # Benchmark comparison data
        benchmarks = [
            {'label': '🌱 Sustainable target', 'val': 2.74,
             'below': avg <= 2.74, 'pct': min(200, round(avg/2.74*100))},
            {'label': '🇮🇳 India average',      'val': 7.0,
             'below': avg <= 7.0,  'pct': min(200, round(avg/7.0*100))},
            {'label': '🌍 World average',       'val': 13.0,
             'below': avg <= 13.0, 'pct': min(200, round(avg/13.0*100))},
            {'label': '🇺🇸 USA average',        'val': 43.0,
             'below': avg <= 43.0, 'pct': min(200, round(avg/43.0*100))},
        ]

        # Weekly chart (last 14 days, grouped by week)
        week_labels = [str(l.date) for l in reversed(logs[:14])]
        week_data   = [l.total_co2 for l in reversed(logs[:14])]

    ecoscore, eco_label, eco_color = calculate_ecoscore(user.id)

    # Checklist actions mapped to top category
    CHECKLISTS = {
        'transport': [
            ('Mon', 'आज bus/metro वापरा — car नको'),
            ('Tue', 'एक trip walk किंवा cycle करा'),
            ('Wed', 'Carpool arrange करा colleague सोबत'),
            ('Thu', 'WFH request करा manager ला'),
            ('Fri', 'पुढील आठवड्याचा travel plan करा'),
        ],
        'food': [
            ('Mon', 'आज पूर्ण vegetarian जेवण'),
            ('Tue', 'Local sabzi market मधून खरेदी'),
            ('Wed', 'Meal plan करा — waste कमी होईल'),
            ('Thu', 'Pressure cooker वापरा — 70% gas बचत'),
            ('Fri', 'Food waste check करा — काय शिल्लक?'),
        ],
        'energy': [
            ('Mon', 'AC 24°C वर set करा — खाली नको'),
            ('Tue', 'झोपण्यापूर्वी सर्व plug काढा'),
            ('Wed', 'Natural light वापरा दिवसभर'),
            ('Thu', 'PM Surya Ghar site visit करा'),
            ('Fri', 'Monthly electricity bill review करा'),
        ],
        'shopping': [
            ('Mon', 'Cloth bag वापरा — plastic नको'),
            ('Tue', 'एक online order delay करा 48 hrs'),
            ('Wed', 'एखादी broken item fix करा'),
            ('Thu', 'OLX/Facebook वर second-hand पहा'),
            ('Fri', 'आठवड्यात कमी plastic वापरला का?'),
        ],
    }
    checklist = CHECKLISTS.get(context['top1'], CHECKLISTS['transport'])

    return render_template('ai_advisor.html',
        user=user,
        context=context,
        smart_tips=smart_tips,
        benchmarks=json.dumps(benchmarks),
        benchmarks_list=benchmarks,
        checklist=checklist,
        week_labels=json.dumps(week_labels),
        week_data=json.dumps(week_data),
        ecoscore=ecoscore,
        eco_label=eco_label,
        eco_color=eco_color,
    )


# ─────────────────────────────────────────────
# WEATHER TIP API  (no API key needed — wttr.in)
# ─────────────────────────────────────────────
@app.route('/api/weather')
@login_required
def weather_tip():
    import urllib.request
    user = User.query.get(session['user_id'])
    city = user.city or 'Pune'
    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'GreenSaathi/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        temp_c    = int(data['current_condition'][0]['temp_C'])
        condition = data['current_condition'][0]['weatherDesc'][0]['value']

        if temp_c > 38:
            tip = f"🌡️ {temp_c}°C in {city}! Use fan instead of AC — saves 90% energy."
            icon = "🔥"
        elif temp_c > 30:
            tip = f"☀️ {temp_c}°C — hot day! Set AC to 24°C, not lower. Saves 6% per degree."
            icon = "☀️"
        elif 'Rain' in condition or 'Drizzle' in condition:
            tip = f"🌧️ Raining in {city}! Collect rainwater for plants and cleaning today."
            icon = "🌧️"
        elif temp_c < 15:
            tip = f"🧊 Only {temp_c}°C! Wear warm clothes instead of an electric heater."
            icon = "❄️"
        else:
            tip = f"🌤️ {temp_c}°C — perfect weather for cycling or walking today!"
            icon = "🌿"

        return jsonify({'temp': temp_c, 'condition': condition,
                        'city': city, 'tip': tip, 'icon': icon})
    except Exception:
        return jsonify({'temp': '--', 'condition': 'Unavailable',
                        'city': city,
                        'tip': '🌱 Every day is a good day to reduce your carbon footprint!',
                        'icon': '🌍'})


# ─────────────────────────────────────────────
# 🤖 ECOBOT CHATBOT
# ─────────────────────────────────────────────
@app.route('/chatbot')
@login_required
def chatbot():
    user = User.query.get(session['user_id'])
    return render_template('chatbot.html', user=user)

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data    = request.get_json()
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'reply': 'कृपया काहीतरी विचारा! 😊'})
    reply = ecobot.chat(message)
    return jsonify({'reply': reply, 'timestamp': datetime.now().strftime('%H:%M')})


# ─────────────────────────────────────────────
# 📈 CO2 PREDICTION ENGINE
# ─────────────────────────────────────────────
@app.route('/predict')
@login_required
def predict():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date).all()
    result = predictor.predict_next_month(logs)

    # Chart data for last 30 days + prediction line
    last30 = logs[-30:] if len(logs) >= 30 else logs
    chart_labels = [str(l.date) for l in last30]
    chart_actual = [l.total_co2 for l in last30]

    # Extend with 7-day prediction
    if last30:
        last_date = last30[-1].date
        pred_labels = [(last_date + timedelta(days=i+1)).strftime('%m/%d') for i in range(7)]
        pred_values = [result.get('daily_pred', 0)] * 7
    else:
        pred_labels, pred_values = [], []

    return render_template('predict.html',
        user=user,
        result=result,
        chart_labels=json.dumps(chart_labels + pred_labels),
        chart_actual=json.dumps(chart_actual),
        pred_values=json.dumps([None]*len(chart_actual) + pred_values),
        has_data=len(logs) > 0,
    )


# ─────────────────────────────────────────────
# 💡 SMART TIP RECOMMENDER
# ─────────────────────────────────────────────
@app.route('/smart-tips')
@login_required
def smart_tips():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date.desc()).limit(30).all()
    result = recommender.recommend(logs)
    return render_template('smart_tips.html', user=user, result=result)


# ─────────────────────────────────────────────
# 🚨 ANOMALY DETECTOR
# ─────────────────────────────────────────────
@app.route('/anomaly')
@login_required
def anomaly():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date).all()
    result = anomaly_detector.detect(logs)

    # Historical for chart
    last20 = logs[-20:] if len(logs) > 20 else logs
    values = [l.total_co2 for l in last20]
    mean   = round(sum(values)/len(values), 2) if values else 0
    labels = [str(l.date) for l in last20]
    colors = []
    for v in values:
        if mean > 0 and abs(v - mean) / max(mean, 0.01) > 0.5:
            colors.append('#e8604a')
        else:
            colors.append('#2d8a56')

    return render_template('anomaly.html',
        user=user,
        result=result,
        chart_labels=json.dumps(labels),
        chart_values=json.dumps(values),
        chart_colors=json.dumps(colors),
        mean=mean,
        has_data=len(logs) >= 5,
    )


# ─────────────────────────────────────────────
# 🔮 HABIT STREAK PREDICTOR
# ─────────────────────────────────────────────
@app.route('/streak')
@login_required
def streak():
    user = User.query.get(session['user_id'])
    logs = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date).all()
    result = streak_predictor.predict(logs)

    # Calendar heatmap data (last 30 days)
    today    = datetime.today().date()
    cal_data = {}
    for l in logs[-30:]:
        cal_data[str(l.date)] = l.total_co2
    cal_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(29, -1, -1)]

    return render_template('streak.html',
        user=user,
        result=result,
        cal_dates=json.dumps(cal_dates),
        cal_data=json.dumps(cal_data),
        has_data=len(logs) >= 3,
    )


# ─────────────────────────────────────────────
# 📸 PHOTO CARBON SCANNER
# ─────────────────────────────────────────────
FOOD_CARBON_MAP = {
    'beef':       7.19, 'chicken':    4.67, 'fish':     3.5,
    'egg':        1.5,  'milk':       1.3,  'cheese':   6.1,
    'rice':       2.7,  'bread':      1.1,  'dal':      0.9,
    'vegetable':  0.4,  'fruit':      0.3,  'salad':    0.2,
    'pizza':      2.8,  'burger':     5.5,  'biryani':  3.2,
    'roti':       0.5,  'paratha':    0.8,  'idli':     0.3,
    'dosa':       0.5,  'thali':      2.1,  'vada':     0.6,
    'paneer':     2.9,  'tofu':       1.1,  'noodles':  1.8,
    'pasta':      1.6,  'soup':       0.5,  'samosa':   0.8,
}

@app.route('/photo-scanner')
@login_required
def photo_scanner():
    user = User.query.get(session['user_id'])
    return render_template('photo_scanner.html', user=user)

@app.route('/api/scan-food', methods=['POST'])
@login_required
def api_scan_food():
    """Analyze food name/description text for carbon estimate"""
    data       = request.get_json()
    food_text  = (data.get('food_text') or '').lower().strip()
    portions   = int(data.get('portions', 1))

    if not food_text:
        return jsonify({'error': 'कृपया food describe करा'}), 400

    # Match keywords
    matched  = []
    total_co2 = 0.0
    for food, co2 in FOOD_CARBON_MAP.items():
        if food in food_text:
            matched.append({'food': food, 'co2': co2})
            total_co2 += co2

    if not matched:
        # Default estimate
        total_co2 = 2.5
        matched   = [{'food': 'mixed meal', 'co2': 2.5}]

    total_co2 = round(total_co2 * portions, 2)
    vs_vegan  = round(total_co2 - 0.5 * portions, 2)
    tip = "🥦 Vegetarian option choose केल्यास आणखी carbon वाचला असता!" if total_co2 > 3 else "✅ Low-carbon meal choice — great job!"

    return jsonify({
        'total_co2': total_co2,
        'matched':   matched,
        'portions':  portions,
        'vs_vegan':  max(0, vs_vegan),
        'tip':       tip,
    })


# ─────────────────────────────────────────────
# ♻️ WASTE ANALYZER — Photo + Description
# ─────────────────────────────────────────────
WASTE_KNOWLEDGE = {
    # Plastic
    'plastic': {
        'emoji': '🧴', 'marathi': 'प्लास्टिक',
        'type': 'Dry Waste — Recyclable',
        'danger': 'high',
        'co2_if_burned': 2.9,   # kg CO2 per kg plastic burned
        'steps': [
            '🚫 कधीही जाळू नका! Burning plastic = 2.9 kg CO₂/kg + toxic dioxins released',
            '🧹 स्वच्छ करा आणि dry waste bin मध्ये टाका',
            '♻️ HDPE (#2), PET (#1) bottles scrap dealers ला विका — ₹5-15/kg मिळतात',
            '🏪 Safaai Sena, SWaCH, local kabadiwala यांना द्या',
            '📱 घरापासून collection साठी: Saahas Zero Waste, Recykal app वापरा',
        ],
        'carbon_saved': 'Recycling करण्यापेक्षा burning 10x जास्त CO₂ emit करते',
        'alternatives': 'कापडी पिशव्या, steel containers, बाटली refilling वापरा',
    },
    'bottle': {
        'emoji': '🍶', 'marathi': 'बाटली/कंटेनर',
        'type': 'Dry Waste — Recyclable',
        'danger': 'high',
        'co2_if_burned': 2.5,
        'steps': [
            '🚫 जाळू नका — plastic bottles जळताना benzene आणि styrene निघतात',
            '💧 रिकामी करा, स्वच्छ धुवा, dry waste bin मध्ये ठेवा',
            '♻️ Glass bottles: ₹2-5 each depot वर; Plastic: kabadiwala',
            '🔄 Steel/glass bottles reuse करा — single-use टाळा',
        ],
        'carbon_saved': 'Glass recycling = 20% कमी energy; Plastic recycling = 70% कमी',
        'alternatives': 'Steel water bottle, glass jar — एकदा घ्या, कायम वापरा',
    },
    # Paper
    'paper': {
        'emoji': '📄', 'marathi': 'कागद',
        'type': 'Dry Waste — Recyclable',
        'danger': 'medium',
        'co2_if_burned': 1.5,
        'steps': [
            '⚠️ Burning paper = CO₂ + ash particles — health risk',
            '📦 Cardboard boxes flatten करून dry waste मध्ये द्या',
            '📰 Newspapers kabadiwala ला विका — ₹8-12/kg',
            '🖨️ Office paper: shredder वापरून compost मध्ये टाका किंवा recycle करा',
            '📚 Books: donate to libraries, schools, NGOs',
        ],
        'carbon_saved': 'Paper recycling = 60% कमी energy + trees वाचवतो',
        'alternatives': 'Digital bills, notes; newspaper bags instead of plastic',
    },
    # Construction
    'brick': {
        'emoji': '🧱', 'marathi': 'विटा/बांधकाम कचरा',
        'type': 'Construction & Demolition Waste (C&D)',
        'danger': 'low',
        'co2_if_burned': 0,
        'steps': [
            '🏗️ बांधकाम कचरा (C&D waste) municipal sites वर न्या — जाळू नका',
            '♻️ Bricks, tiles, concrete crush करून road base मध्ये reuse होतो',
            '📞 Pune: PCMC C&D waste facility | Nashik: NMC yard | Mumbai: MCGM',
            '🏠 Small quantities: ओसाड जागेत fill करण्यासाठी द्या (legally)',
            '💰 Construction waste recyclers directly collect करतात — free या paid',
        ],
        'carbon_saved': 'C&D recycling = new material manufacturing 40% कमी',
        'alternatives': 'Building planning नीट करा — waste कमी होईल',
    },
    'concrete': {
        'emoji': '🪨', 'marathi': 'सिमेंट/काँक्रीट',
        'type': 'Construction & Demolition Waste',
        'danger': 'low',
        'co2_if_burned': 0,
        'steps': [
            '♻️ Concrete crush करून road sub-base, parking foundation मध्ये वापरतात',
            '🚛 Contractor किंवा municipality ला कळवा — ते collect करतात',
            '🌱 Small pieces: garden drainage layer म्हणून वापरा',
        ],
        'carbon_saved': 'Recycled concrete = 50% कमी CO₂ vs new production',
        'alternatives': 'Fly ash bricks, AAC blocks — lightweight आणि eco-friendly',
    },
    # Food/Organic
    'food': {
        'emoji': '🍌', 'marathi': 'ओला कचरा/अन्न',
        'type': 'Wet Waste — Compostable',
        'danger': 'low',
        'co2_if_burned': 0.5,
        'steps': [
            '🌱 Composting सर्वात best! Kitchen waste → 45 दिवसांत खत',
            '🪣 Green/wet waste bin वेगळा ठेवा — dry waste मिसळू नका',
            '🏘️ Society level composting: apartment composters available — ₹2,000-5,000',
            '🌿 Banana peels, vegetable scraps → directly garden मध्ये bury करा',
            '🚗 Municipal wet waste collection: daily pickup in most cities',
        ],
        'carbon_saved': 'Composting = landfill methane 100% कमी + free fertilizer',
        'alternatives': 'Meal planning करा — food waste कमी करा',
    },
    # Electronic
    'electronic': {
        'emoji': '📱', 'marathi': 'इलेक्ट्रॉनिक कचरा',
        'type': 'E-Waste — Hazardous',
        'danger': 'critical',
        'co2_if_burned': 5.0,
        'steps': [
            '🚨 कधीही जाळू नका! E-waste burning = lead, mercury, cadmium — serious health risk',
            '🏪 Authorized E-waste collector ला द्या: Attero, Ecoreco, E-Parisaraa',
            '📞 Manufacturers take-back: Samsung, LG, Apple India — free collection',
            '🏛️ PCB (Pollution Control Board) authorized facilities only',
            '💰 Working devices: donate, sell OLX/Quikr',
            '📱 Maharashtra: 1800-233-5500 (E-waste helpline)',
        ],
        'carbon_saved': 'E-waste recycling = 95% कमी energy vs mining new metals',
        'alternatives': 'Repair before replace, buy certified refurbished devices',
    },
    # Medical
    'medical': {
        'emoji': '💊', 'marathi': 'वैद्यकीय कचरा',
        'type': 'Biomedical Waste — Hazardous',
        'danger': 'critical',
        'co2_if_burned': 3.5,
        'steps': [
            '🚨 कधीही जाळू नका! घरच्या कचऱ्यात टाकू नका',
            '💉 Needles, syringes: sharps container मध्ये close करून hospital ला द्या',
            '💊 Expired medicines: pharmacy take-back program किंवा hospital',
            '🏥 Nearest PHC (Primary Health Center) — biomedical waste collection',
            '📞 MPCB helpline: 022-26871080',
        ],
        'carbon_saved': 'Proper disposal = community health + groundwater protection',
        'alternatives': 'Medicines: जेवढं हवं तेवढंच घ्या, expiry check करा',
    },
    # Burning / Open fire (direct detection)
    'burning': {
        'emoji': '🔥', 'marathi': 'कचरा जाळणे',
        'type': '🚨 OPEN BURNING — ILLEGAL + MOST HARMFUL',
        'danger': 'critical',
        'co2_if_burned': 10.0,
        'steps': [
            '🚨 Open waste burning ILLEGAL आहे — MPCB Rule 2016 नुसार ₹25,000 दंड',
            '☎️ तत्काळ municipal helpline वर कळवा: Pune 020-25506800 | Mumbai 1916',
            '📱 SwachSurvekshan App वर तक्रार नोंदवा — anonymously',
            '🌬️ Burning 1 kg plastic = 2,000 litres toxic air pollutes',
            '♻️ Alternative: segregate करा → dry waste kabadiwala ला द्या',
            '🏘️ Society level awareness: RWA meeting मध्ये dustbin system propose करा',
            '📢 दिसल्यास: MPCB complaint: 1800-233-5500 (toll-free)',
        ],
        'carbon_saved': 'Burning थांबवल्यास प्रति kg = 3-10 kg CO₂ वाचतो + toxic gases नाहीत',
        'alternatives': 'Segregate: Wet bin (green) + Dry bin (blue) + Hazardous (red)',
    },
    'fire': {
        'emoji': '🔥', 'marathi': 'आग/जळत आहे',
        'type': '🚨 OPEN BURNING — ILLEGAL + MOST HARMFUL',
        'danger': 'critical',
        'co2_if_burned': 10.0,
        'steps': [
            '🚨 Open waste burning ILLEGAL आहे — MPCB Rule 2016 नुसार ₹25,000 दंड',
            '☎️ तत्काळ municipal helpline: Pune 020-25506800 | Mumbai 1916 | Nashik 1800-233-4678',
            '📱 SwachSurvekshan App वर complaint करा — photo सहित evidence द्या',
            '🌬️ 1 kg plastic जाळणे = 2,000 litre toxic air + cancer-causing dioxins',
            '♻️ Proper solution: Segregate करा → kabadiwala / municipal collection',
            '📢 MPCB complaint: 1800-233-5500 (toll-free, 24x7)',
        ],
        'carbon_saved': 'Open burning बंद केल्यास = 10 kg CO₂/kg waste वाचतो',
        'alternatives': 'Municipal solid waste (MSW) management system वापरा',
    },
    'smoke': {
        'emoji': '💨', 'marathi': 'धूर/जळालेला कचरा',
        'type': '🚨 OPEN BURNING DETECTED',
        'danger': 'critical',
        'co2_if_burned': 8.0,
        'steps': [
            '🚨 हे ILLEGAL आहे — MPCB ला तत्काळ कळवा: 1800-233-5500',
            '📱 Photo काढा आणि SwachSurvekshan App वर report करा',
            '🏘️ Nearest municipal ward office ला complaint द्या',
            '♻️ Alternative: Safaai Sena, SWaCH यांना collection साठी call करा',
        ],
        'carbon_saved': 'Smoke means burning — stop it = massive CO₂ saving',
        'alternatives': 'Call kabadiwala or municipal waste collection',
    },
    # General mixed
    'mixed': {
        'emoji': '🗑️', 'marathi': 'मिश्र कचरा',
        'type': 'Mixed Waste — Needs Segregation',
        'danger': 'medium',
        'co2_if_burned': 3.5,
        'steps': [
            '🔴 Wet Waste (ओला): भाजीपाला peels, food scraps → Green bin → Compost',
            '🔵 Dry Waste (सुका): Paper, plastic, metal, glass → Blue bin → Kabadiwala',
            '⚫ Hazardous: Batteries, medicines, e-waste → Red/Black bin → Special collection',
            '⚪ Sanitary: Napkins, diapers → wrap in paper → general waste',
            '🏪 Kabadiwala: dry recyclables ला ₹3-15/kg मिळतात — waste to cash!',
            '📱 Recykal app, Kabadiwala.com, Junk Daddy वापरा घरपोच collection साठी',
        ],
        'carbon_saved': 'Proper segregation = landfill 70% कमी + 60% recyclables recover',
        'alternatives': 'तीन bins घरी ठेवा — एकच bin नको',
    },
    # Tyres / Rubber
    'tyre': {
        'emoji': '🔧', 'marathi': 'टायर/रबर',
        'type': 'Special Waste — Hazardous if burned',
        'danger': 'critical',
        'co2_if_burned': 3.0,
        'steps': [
            '🚨 टायर जाळणे = 3 kg CO₂ + PAH (cancer-causing chemicals)',
            '🔄 Old tyres: retreading shops ला द्या — नवीन tyre खरेदी वाचते',
            '🏗️ Road construction, playground surfaces मध्ये crumb rubber वापरतात',
            '🚗 Tyre manufacturers take-back: CEAT, MRF collection programs',
            '📞 MPCB authorized waste processors: tyresrecycling.in',
        ],
        'carbon_saved': 'Tyre recycling = 75% कमी energy vs burning',
        'alternatives': 'Electric bikes/cars = tyre wear कमी; carpool करा',
    },
}

# Map common Marathi words to English keys
MARATHI_TO_KEY = {
    'प्लास्टिक': 'plastic', 'पिशवी': 'plastic', 'कागद': 'paper',
    'विटा': 'brick', 'वीट': 'brick', 'सिमेंट': 'concrete',
    'आग': 'fire', 'जाळत': 'burning', 'धूर': 'smoke',
    'कचरा': 'mixed', 'बाटली': 'bottle', 'खाणे': 'food',
    'टायर': 'tyre', 'मोबाईल': 'electronic', 'औषध': 'medical',
}

@app.route('/waste-analyzer')
@login_required
def waste_analyzer():
    user = User.query.get(session['user_id'])
    return render_template('waste_analyzer.html', user=user)

@app.route('/api/analyze-waste', methods=['POST'])
@login_required
def api_analyze_waste():
    data       = request.get_json()
    waste_text = (data.get('waste_text') or '').lower().strip()

    if not waste_text:
        return jsonify({'error': 'कचऱ्याचे वर्णन करा'}), 400

    # Translate Marathi words first
    for mr, en in MARATHI_TO_KEY.items():
        if mr in waste_text:
            waste_text += ' ' + en

    # Priority: burning/fire/smoke first (most urgent)
    detected_types = []
    priority_keys  = ['burning', 'fire', 'smoke']
    for pk in priority_keys:
        if pk in waste_text:
            detected_types.append(pk)

    if not detected_types:
        for key in WASTE_KNOWLEDGE:
            if key in waste_text and key not in ['burning', 'fire', 'smoke']:
                detected_types.append(key)

    if not detected_types:
        detected_types = ['mixed']

    results = []
    for wtype in detected_types[:3]:
        info = WASTE_KNOWLEDGE.get(wtype, WASTE_KNOWLEDGE['mixed'])
        results.append({
            'type':          info['type'],
            'emoji':         info['emoji'],
            'marathi':       info['marathi'],
            'danger':        info['danger'],
            'steps':         info['steps'],
            'carbon_impact': info['co2_if_burned'],
            'carbon_saved':  info['carbon_saved'],
            'alternatives':  info.get('alternatives', ''),
        })

    # Overall urgency
    urgency = 'critical' if any(r['danger'] == 'critical' for r in results) else \
              'high'     if any(r['danger'] == 'high'     for r in results) else 'medium'

    return jsonify({'results': results, 'urgency': urgency, 'detected': detected_types})


# ─────────────────────────────────────────────
# 📝 AI CLIMATE REPORT
# ─────────────────────────────────────────────
@app.route('/ai-report')
@login_required
def ai_report():
    user   = User.query.get(session['user_id'])
    logs   = CarbonLog.query.filter_by(user_id=user.id).order_by(CarbonLog.date).all()
    badges = Badge.query.filter_by(user_id=user.id).all()

    report = report_generator.generate(user, logs, badges)

    # Monthly trend for chart
    monthly = {}
    for l in logs:
        key = l.date.strftime('%b %Y')
        if key not in monthly:
            monthly[key] = []
        monthly[key].append(l.total_co2)
    month_labels = list(monthly.keys())[-6:]
    month_avgs   = [round(sum(monthly[k])/len(monthly[k]), 2) for k in month_labels]

    return render_template('ai_report.html',
        user=user,
        report=report,
        month_labels=json.dumps(month_labels),
        month_avgs=json.dumps(month_avgs),
    )


# ─────────────────────────────────────────────
# 🎙️ VOICE LOG (Web Speech API — browser-side)
# ─────────────────────────────────────────────
@app.route('/voice-log')
@login_required
def voice_log():
    user = User.query.get(session['user_id'])
    return render_template('voice_log.html', user=user)

@app.route('/api/voice-parse', methods=['POST'])
@login_required
def api_voice_parse():
    """Parse voice transcript to extract carbon log data"""
    data       = request.get_json()
    transcript = (data.get('transcript') or '').lower()

    result = {
        'transport_mode': 'car', 'transport_km': 0,
        'food_type':      'meat_medium',
        'electricity_kwh': 0, 'lpg_kg': 0, 'shopping_spend': 0,
        'detected':       [],
    }

    # Transport detection
    km_words = {'km': 1, 'किलोमीटर': 1, 'kilometre': 1}
    import re
    numbers = re.findall(r'\d+\.?\d*', transcript)
    nums    = [float(n) for n in numbers]

    if any(w in transcript for w in ['bus', 'बस', 'pmpml', 'metro', 'मेट्रो']):
        result['transport_mode'] = 'bus'
        result['detected'].append('🚌 Bus detected')
    elif any(w in transcript for w in ['train', 'रेल्वे', 'railway', 'local']):
        result['transport_mode'] = 'train'
        result['detected'].append('🚆 Train detected')
    elif any(w in transcript for w in ['cycle', 'सायकल', 'bicycle', 'walk', 'चालत']):
        result['transport_mode'] = 'bike'
        result['detected'].append('🚲 Cycle/Walk detected')
    elif any(w in transcript for w in ['car', 'गाडी', 'scooter', 'bike', 'taxi']):
        result['transport_mode'] = 'car'
        result['detected'].append('🚗 Car detected')

    if nums:
        result['transport_km'] = nums[0]
        result['detected'].append(f'📏 {nums[0]} km detected')

    # Food detection
    if any(w in transcript for w in ['vegan', 'व्हेगन']):
        result['food_type'] = 'vegan'
        result['detected'].append('🌱 Vegan diet')
    elif any(w in transcript for w in ['vegetarian', 'शाकाहारी', 'veg']):
        result['food_type'] = 'vegetarian'
        result['detected'].append('🥦 Vegetarian diet')
    elif any(w in transcript for w in ['chicken', 'meat', 'mutton', 'fish', 'मांस', 'non-veg']):
        result['food_type'] = 'meat_medium'
        result['detected'].append('🍗 Non-veg meal')

    # Energy
    if 'kwh' in transcript or 'unit' in transcript:
        if len(nums) > 1:
            result['electricity_kwh'] = nums[1]
            result['detected'].append(f'⚡ {nums[1]} kWh electricity')

    if not result['detected']:
        result['detected'].append('❓ काही detect झाले नाही — clearly बोला')

    return jsonify(result)


# ─────────────────────────────────────────────
# ⚡ ACTION LIBRARY — CoolTheGlobe inspired
# ─────────────────────────────────────────────
ACTIONS_LIBRARY = [
    # Travel
    {"id":"t1","cat":"travel","icon":"🚌","title":"Take the bus today","marathi":"आज bus वापरा","co2_avoided":2.1,"difficulty":"Easy","impact":"High","brief":"Car ऐवजी bus = 58% कमी CO₂/km. Mumbai PMT, Pune PMPML मुळे लाखो टन CO₂ वाचतो."},
    {"id":"t2","cat":"travel","icon":"🚲","title":"Cycle for trips under 5km","marathi":"5km खाली सायकल वापरा","co2_avoided":1.05,"difficulty":"Easy","impact":"High","brief":"Zero emissions + health फायदा. 5km cycle = 1 kg CO₂ avoided + 150 calories burned."},
    {"id":"t3","cat":"travel","icon":"🚶","title":"Walk instead of drive","marathi":"गाडी सोडा, चालत जा","co2_avoided":0.8,"difficulty":"Easy","impact":"Medium","brief":"Short car trips are worst per km (cold engine). Walk = 0 CO₂ + better air quality."},
    {"id":"t4","cat":"travel","icon":"🚆","title":"Choose train over flight","marathi":"विमानाऐवजी ट्रेन घ्या","co2_avoided":25.0,"difficulty":"Medium","impact":"High","brief":"Mumbai-Delhi flight = 300 kg CO₂. Same train = 12 kg. Train is 25x greener."},
    {"id":"t5","cat":"travel","icon":"🤝","title":"Carpool with colleagues","marathi":"साथीदारांसोबत carpool करा","co2_avoided":2.5,"difficulty":"Easy","impact":"High","brief":"4 people carpooling = each person emits 75% less. QuickRide, BlaBlaCar apps मदत करतात."},
    {"id":"t6","cat":"travel","icon":"🏠","title":"Work from home today","marathi":"आज घरून काम करा","co2_avoided":3.0,"difficulty":"Easy","impact":"High","brief":"1 WFH day/week = 20% annual commute CO₂ savings + less traffic + more family time."},
    {"id":"t7","cat":"travel","icon":"⚡","title":"Ride an electric vehicle","marathi":"इलेक्ट्रिक वाहन वापरा","co2_avoided":1.5,"difficulty":"Medium","impact":"High","brief":"EVs emit 60% less than petrol in India even with coal grid. PM EV scheme gives ₹15K subsidy."},
    # Food
    {"id":"f1","cat":"food","icon":"🥦","title":"Eat vegetarian today","marathi":"आज शाकाहारी जेवण खा","co2_avoided":3.5,"difficulty":"Easy","impact":"High","brief":"Meat production uses 20x more water and land. One vegetarian day = 3.5 kg CO₂ saved = driving 17 km less."},
    {"id":"f2","cat":"food","icon":"🌱","title":"Try a vegan meal","marathi":"एक vegan जेवण करून पहा","co2_avoided":4.3,"difficulty":"Easy","impact":"High","brief":"Vegan meal = lowest food carbon. Dal-rice-sabzi combo is both nutritious and planet-friendly."},
    {"id":"f3","cat":"food","icon":"🛒","title":"Buy from local market","marathi":"स्थानिक बाजारातून खरेदी करा","co2_avoided":0.8,"difficulty":"Easy","impact":"Medium","brief":"Local sabzi = 90% less transport emissions than supermarket imports. Fresher + cheaper too."},
    {"id":"f4","cat":"food","icon":"🍱","title":"Zero food waste today","marathi":"आज अन्न वाया जाऊ देऊ नका","co2_avoided":1.2,"difficulty":"Medium","impact":"Medium","brief":"India wastes 68 million tonnes food/year. Wasted food = wasted water, land, emissions. Plan meals!"},
    {"id":"f5","cat":"food","icon":"🍳","title":"Use pressure cooker","marathi":"प्रेशर कुकर वापरा","co2_avoided":0.4,"difficulty":"Easy","impact":"Low","brief":"Dal in 10 min vs 40 min = 70% less LPG. Simple change that saves ₹200+/month on gas bills."},
    {"id":"f6","cat":"food","icon":"🌾","title":"Choose seasonal produce","marathi":"हंगामी भाज्या-फळे खा","co2_avoided":0.6,"difficulty":"Easy","impact":"Medium","brief":"Off-season veg needs heated greenhouses. Seasonal = 5x lower emissions + better nutrition."},
    {"id":"f7","cat":"food","icon":"🌿","title":"Grow your own herbs","marathi":"घरी हर्ब्स लावा","co2_avoided":0.3,"difficulty":"Medium","impact":"Low","brief":"Tulsi, mint, coriander in pots = zero food miles. Connects you to nature + improves air quality."},
    # Energy
    {"id":"e1","cat":"energy","icon":"❄️","title":"Set AC to 24°C","marathi":"AC 24°C वर ठेवा","co2_avoided":1.8,"difficulty":"Easy","impact":"High","brief":"Each degree below 24°C = 6% more electricity. 24°C + ceiling fan feels like 21°C. Annual saving: ₹3,000+."},
    {"id":"e2","cat":"energy","icon":"💡","title":"Switch to LED bulbs","marathi":"LED bulbs लावा","co2_avoided":0.5,"difficulty":"Easy","impact":"Medium","brief":"LED uses 75% less electricity than old bulbs and lasts 25x longer. Pay ₹100 once, save ₹2,000 over life."},
    {"id":"e3","cat":"energy","icon":"🔌","title":"Unplug idle devices","marathi":"बंद उपकरणे unplug करा","co2_avoided":0.3,"difficulty":"Easy","impact":"Low","brief":"TV, charger, set-top box on standby = 10% of your electricity bill wasted. Unplug before sleep."},
    {"id":"e4","cat":"energy","icon":"☀️","title":"Use solar energy","marathi":"सौरऊर्जा वापरा","co2_avoided":4.0,"difficulty":"Hard","impact":"High","brief":"PM Surya Ghar scheme: ₹78,000 subsidy for 3kW rooftop solar. Saves ₹1,500/month on electricity."},
    {"id":"e5","cat":"energy","icon":"🪟","title":"Use natural light today","marathi":"आज नैसर्गिक प्रकाश वापरा","co2_avoided":0.4,"difficulty":"Easy","impact":"Low","brief":"Open curtains, rearrange workspace near windows. Natural light also improves mood and productivity."},
    {"id":"e6","cat":"energy","icon":"🚿","title":"5-minute shower only","marathi":"फक्त 5 मिनिट shower घ्या","co2_avoided":0.3,"difficulty":"Easy","impact":"Low","brief":"Hot water heating = 20% of home energy. 5-min shower saves 40 litres. In Marathwada, water is precious."},
    {"id":"e7","cat":"energy","icon":"🌡️","title":"Air dry clothes","marathi":"कपडे उन्हात वाळवा","co2_avoided":0.6,"difficulty":"Easy","impact":"Medium","brief":"Dryers use 5 kWh per load = ₹40 + 4 kg CO₂. India's sun does it free. Use drying rack or clothesline."},
    # Waste
    {"id":"w1","cat":"waste","icon":"♻️","title":"Segregate waste today","marathi":"आज कचरा वेगळा करा","co2_avoided":0.5,"difficulty":"Easy","impact":"Medium"},
    {"id":"w2","cat":"waste","icon":"🌱","title":"Start composting","marathi":"composting सुरू करा","co2_avoided":0.8,"difficulty":"Medium","impact":"High"},
    {"id":"w3","cat":"waste","icon":"🛍️","title":"Use cloth bags only","marathi":"कापडी पिशव्या वापरा","co2_avoided":0.3,"difficulty":"Easy","impact":"Medium"},
    {"id":"w4","cat":"waste","icon":"💧","title":"Refill water bottle","marathi":"बाटली refill करा","co2_avoided":0.2,"difficulty":"Easy","impact":"Low"},
    {"id":"w5","cat":"waste","icon":"🔧","title":"Repair instead of replace","marathi":"नवीन घेण्यापेक्षा दुरुस्त करा","co2_avoided":3.0,"difficulty":"Medium","impact":"High"},
    # Nature
    {"id":"n1","cat":"nature","icon":"🌳","title":"Plant a tree","marathi":"एक झाड लावा","co2_avoided":22.0,"difficulty":"Medium","impact":"High"},
    {"id":"n2","cat":"nature","icon":"💧","title":"Harvest rainwater","marathi":"पावसाचे पाणी जमा करा","co2_avoided":0.4,"difficulty":"Medium","impact":"Medium"},
    {"id":"n3","cat":"nature","icon":"📣","title":"Spread awareness","marathi":"5 जणांना सांगा","co2_avoided":50.0,"difficulty":"Easy","impact":"High"},
    {"id":"n4","cat":"nature","icon":"🤝","title":"Join a cleanup drive","marathi":"cleanup drive मध्ये सामील व्हा","co2_avoided":2.0,"difficulty":"Medium","impact":"High"},
    {"id":"n5","cat":"nature","icon":"📱","title":"Report open burning","marathi":"कचरा जाळणे report करा","co2_avoided":10.0,"difficulty":"Easy","impact":"High"},
]

@app.route('/actions')
@login_required
def action_library():
    user  = User.query.get(session['user_id'])
    logs  = CarbonLog.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    total_users   = User.query.count()
    total_logs    = CarbonLog.query.count()
    global_avoided = round(total_logs * 1.8, 0)  # estimated avoided per log
    return render_template('action_library.html',
        user=user,
        actions=ACTIONS_LIBRARY,
        logs_count=len(logs),
        badges_count=len(badges),
        total_users=total_users,
        global_avoided=global_avoided,
    )

@app.route('/api/log-action', methods=['POST'])
@login_required
def api_log_action():
    """Log a completed climate action — give bonus badge"""
    data     = request.get_json()
    action_id = data.get('action_id')
    action   = next((a for a in ACTIONS_LIBRARY if a['id'] == action_id), None)
    if not action:
        return jsonify({'error': 'Action not found'}), 404
    user_id = session['user_id']
    existing = Badge.query.filter_by(user_id=user_id, name=f"Action:{action_id}").first()
    if not existing:
        db.session.add(Badge(
            user_id=user_id,
            name=f"Action:{action_id}",
            description=f"Completed: {action['title']} — saved {action['co2_avoided']} kg CO₂"
        ))
        db.session.commit()
    return jsonify({'success': True, 'co2_avoided': action['co2_avoided'], 'title': action['title']})


# ─────────────────────────────────────────────
# 🎬 CLIMATE VIDEOS
# ─────────────────────────────────────────────
CLIMATE_VIDEOS = [
    {"id":"dkh375PZRAM","title":"What is Climate Change?","source":"NASA","duration":"3:28","lang":"English","desc":"NASA explains climate change in simple terms — causes, effects, what we can do."},
    {"id":"G4H1N_yXBiA","title":"Greta Thunberg: Our House is on Fire","source":"TED","duration":"11:11","lang":"English","desc":"Powerful climate speech at Davos — the urgency of now."},
    {"id":"EzgFRFBP7GE","title":"India's Climate Crisis","source":"DW","duration":"12:43","lang":"English","desc":"How climate change is affecting India — droughts, floods, heatwaves."},
    {"id":"ipVR0W_jHUQ","title":"How Trees Fight Climate Change","source":"BBC","duration":"4:22","lang":"English","desc":"How planting trees can help fight global warming globally and locally."},
    {"id":"3NkpKR93HrA","title":"Individual vs Systemic Change","source":"TED","duration":"8:55","lang":"English","desc":"Can individual actions really stop climate change? The honest answer."},
    {"id":"d5TGT7ebl_Q","title":"Reduce Your Carbon Footprint","source":"UN","duration":"2:14","lang":"English","desc":"Simple daily actions from the UN to reduce personal emissions."},
]

@app.route('/videos')
@login_required
def videos():
    user = User.query.get(session['user_id'])
    return render_template('videos.html', user=user, videos=CLIMATE_VIDEOS)





# ─────────────────────────────────────────────
# DB CONNECTION CHECK ROUTE
# ─────────────────────────────────────────────
@app.route('/db-check')
def db_check():
    """Visit http://127.0.0.1:5000/db-check to verify DB connection."""
    from sqlalchemy import text
    try:
        db.session.execute(text('SELECT 1'))
        user_count = User.query.count()
        log_count  = CarbonLog.query.count()
        badge_count = Badge.query.count()
        action_count = CompletedAction.query.count()
        status = {
            "status":      "✅ Connected",
            "database":    app.config['SQLALCHEMY_DATABASE_URI'],
            "tables": {
                "users":             user_count,
                "carbon_logs":       log_count,
                "badges":            badge_count,
                "completed_actions": action_count,
            }
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "❌ Error", "message": str(e)}), 500


# ─────────────────────────────────────────────
# INIT DB & RUN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # Creates tables if they don't exist (safe to run every time)
        print("[DATABASE] ready - tables created/verified.")
        print("[SERVER] GreenSaathi running at http://127.0.0.1:5000")
        print("[CHECK] DB check: http://127.0.0.1:5000/db-check")
    app.run(debug=True)
