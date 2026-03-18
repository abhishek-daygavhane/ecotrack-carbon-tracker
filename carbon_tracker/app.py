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
    {"day": 29, "emoji": "🤲", "title": "Community action",      "task": "Invite neighbours/friends to join EcoTrack. Collective action multiplies impact.", "saving": "Multiplied"},
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
    total_saved = 0
    if logs:
        avg = sum(l.total_co2 for l in logs) / len(logs)
        india_avg = 7.0
        if avg < india_avg:
            total_saved = round((india_avg - avg) * len(logs), 1)
    trees_equiv = round(total_saved / 22, 1) if total_saved > 0 else 0
    return render_template('awareness.html',
        facts=CLIMATE_FACTS,
        user=user,
        total_saved=total_saved,
        trees_equiv=trees_equiv,
        logs_count=len(logs),
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
        status = {
            "status":      "✅ Connected",
            "database":    app.config['SQLALCHEMY_DATABASE_URI'],
            "tables": {
                "users":       user_count,
                "carbon_logs": log_count,
                "badges":      badge_count,
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
        print("✅  Database ready — tables created/verified.")
        print("🌍  EcoTrack running at http://127.0.0.1:5000")
        print("🔍  DB check: http://127.0.0.1:5000/db-check")
    app.run(debug=True)
