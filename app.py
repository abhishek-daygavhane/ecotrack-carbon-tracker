from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models import db, User, CarbonLog, Badge, Pledge
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

    ecoscore, eco_label, eco_color = calculate_ecoscore(user.id)

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
                CarbonLog.date.desc()).limit(14).all()

    context = {}
    smart_tips = []

    if logs:
        avg = round(sum(l.total_co2 for l in logs)/len(logs), 2)
        breakdown = {
            'transport': round(sum(l.transport for l in logs)/len(logs), 2),
            'food':      round(sum(l.food      for l in logs)/len(logs), 2),
            'energy':    round(sum(l.energy    for l in logs)/len(logs), 2),
            'shopping':  round(sum(l.shopping  for l in logs)/len(logs), 2),
        }
        # Rank categories by emission
        ranked = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        context = {
            'avg': avg, 'breakdown': breakdown,
            'top1': ranked[0][0], 'top2': ranked[1][0],
            'days': len(logs),
        }
        # Build personalised tip list
        import random
        for cat, _ in ranked[:3]:
            tips_pool = AI_TIPS_BANK.get(cat, [])
            if tips_pool:
                smart_tips.append({'category': cat, 'tip': random.choice(tips_pool)})

        # Trend analysis
        if len(logs) >= 7:
            recent_avg = sum(l.total_co2 for l in logs[:7]) / 7
            older_avg  = sum(l.total_co2 for l in logs[7:]) / max(len(logs)-7, 1)
            context['trend'] = 'improving' if recent_avg < older_avg else 'worsening'
            context['trend_pct'] = abs(round((recent_avg - older_avg)/max(older_avg,0.01)*100, 1))
        else:
            context['trend'] = 'insufficient'
    else:
        context = {'avg': 0, 'days': 0, 'trend': 'no_data'}

    ecoscore, eco_label, eco_color = calculate_ecoscore(user.id)

    return render_template('ai_advisor.html',
        user=user, context=context,
        smart_tips=smart_tips,
        ecoscore=ecoscore, eco_label=eco_label, eco_color=eco_color,
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
        req = urllib.request.Request(url, headers={'User-Agent': 'EcoTrack/1.0'})
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
        print("[OK] Database ready - tables created/verified.")
        print("[*] EcoTrack running at http://127.0.0.1:5000")
        print("[*] DB check: http://127.0.0.1:5000/db-check")
    app.run(debug=True)
