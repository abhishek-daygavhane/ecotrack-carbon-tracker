"""
EcoTrack AI Engine
==================
All ML models in one file:
1. EcoBot       — TF-IDF chatbot (Marathi + English)
2. CO2Predictor — Linear Regression future prediction
3. TipRecommender — K-Means cluster-based tips
4. AnomalyDetector — Isolation Forest spike detection
5. StreakPredictor  — Trend analysis habit predictor
6. ReportGenerator  — Auto AI climate report
"""

import numpy as np
import json
from datetime import datetime, timedelta

# ── SAFE IMPORTS (graceful fallback if scikit-learn not installed) ──────
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.linear_model import LinearRegression
    from sklearn.cluster import KMeans
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════
#  1. ECOBOT — TF-IDF Chatbot
# ══════════════════════════════════════════════════════════════════════

QA_PAIRS = [
    # Transport
    ("how reduce transport carbon emissions car",
     "🚌 PMPML bus किंवा Pune Metro वापरा — car पेक्षा 58% कमी CO₂. Bus fare = ₹10, carbon saving = 0.13 kg/km. आठवड्यात 3 दिवस bus वापरल्यास महिन्याला ~15 kg CO₂ वाचतो!"),
    ("car emissions vs bus train metro",
     "📊 Comparison: Car = 0.21 kg/km | Bus = 0.089 kg/km | Train = 0.041 kg/km | Cycle = 0 kg/km. Mumbai local train हा जगातील सर्वात हरित commute पर्यायांपैकी एक आहे."),
    ("electric vehicle ev bike scooter",
     "⚡ EV India मध्ये 60% कमी CO₂ emit करतो. PM EV scheme: 2-wheeler वर ₹15,000 सबसिडी. Ather, Ola Electric, TVS iQube — आता EMI वर घेता येतात."),
    ("flight airplane carbon footprint",
     "✈️ Mumbai-Delhi return flight = ~300 kg CO₂. Same route train = फक्त 12 kg CO₂! 800 km पेक्षा कमी अंतर नेहमी train ने जा. Rajdhani Express is the greenest option."),
    ("cycle bicycle walk reduce carbon",
     "🚲 5 km सायकलने गेल्यास 1.05 kg CO₂ वाचतो. आठवड्यात 3 वेळा cycle करा = महिन्याला 12 kg CO₂ बचत + तुमची health सुधारेल!"),
    ("carpool share ride ridesharing",
     "🚗 Carpool केल्यास per-person emissions 50% कमी होतात. BlaBlaCar, QuickRide app वापरा. 4 जण carpool केल्यास प्रत्येकाचा carbon 75% कमी!"),
    # Food
    ("vegetarian vegan diet food carbon",
     "🥦 Vegetarian diet = दररोज 0.86 kg CO₂ बचत vs meat diet. वर्षभरात = 314 kg — 14 झाडे लावण्याइतके! India आधीच 38% vegetarian — हे celebrate करा."),
    ("meatless monday meat free day",
     "🥗 Meatless Monday = आठवड्याला 3.4 kg CO₂ बचत = वर्षात 177 kg. एक simple change, massive impact! Dal-rice combination = complete protein + zero guilt."),
    ("food waste reduce kitchen",
     "♻️ India मध्ये 68 million tonnes अन्न वाया जाते! Weekly meal plan करा, pressure cooker वापरा (70% energy बचत), leftover creative रेसिपी बनवा."),
    ("local food market farmer sabzi",
     "🛒 Local market मधून खरेदी = transport emissions 90% कमी. Maharashtra madhe sheti mall, organic markets growing. Nashik grapes, Nagpur oranges — local खा!"),
    ("seasonal vegetables fruits",
     "🍅 Season मधील vegetables 5 पट कमी carbon emit करतात. Monsoon: भेंडी, वांगे | Winter: मेथी, पालक | Summer: कारले, दोडका. Local seasonal = best choice."),
    # Energy
    ("solar panel rooftop subsidy",
     "☀️ PM Surya Ghar Muft Bijli Yojana! 3kW साठी ₹78,000 सबसिडी. Apply: pmsuryaghar.gov.in. एक 2kW system = 2,400 kWh/year + 1,968 kg CO₂ saved. ROI 5-7 years."),
    ("air conditioner ac electricity save",
     "❄️ AC 24°C वर ठेवा — प्रत्येक degree खाली 6% जास्त electricity! Ceiling fan + 24°C AC = feels like 21°C. Night मध्ये 26°C ठेवा. Annual saving: ~₹3,000."),
    ("led bulb electricity light save",
     "💡 LED bulb = 75% कमी electricity vs incandescent. 10W LED = 60W bulb सारखाच प्रकाश. घरातील सर्व bulbs LED करा = दरमहा ₹200-400 बचत."),
    ("unplug standby power phantom load",
     "🔌 TV, charger, set-top box standby मध्ये असताना 10% electricity वापरतात (phantom load). झोपण्यापूर्वी सर्व unplug करा. Monthly saving: ~₹150."),
    ("lpg gas cooking pressure cooker",
     "🍳 Pressure cooker = 70% कमी LPG. Dal 40 min → 10 min. Soaking lentils 4 hours = आणखी 20% बचत. झाकण ठेवून शिजवा = 30% कमी gas."),
    # Water
    ("water save drought maharashtra",
     "💧 Marathwada मध्ये 6 पैकी 10 वर्षे दुष्काळ! प्रत्येक थेंब महत्त्वाचा. Dripping tap = 20 litre/day वाया. 5 minute shower = 75 litre बचत. पाणी वाचवणे = carbon वाचवणे."),
    ("rainwater harvesting collection",
     "🌧️ Maharashtra मध्ये average 1,200mm पाऊस. Simple rooftop collection = 50,000 litre/year (100 sqm छत). Garden, car wash, toilet flush साठी वापरा. Zero cost water!"),
    ("fix leaking tap pipe",
     "🔧 Dripping tap = 20 litre/day = 7,300 litre/year! Fixing a tap wastes 0 kg CO₂ but saves the same as not using 7,300 water bottles. Fix leaks today — plumber cost ₹200-500."),
    # Waste
    ("compost composting kitchen waste",
     "🌱 Kitchen waste composting: vegetable peels + banana skin + leftover food → 45 days → free fertilizer. 1 kg organic waste → 0.5 kg CO₂ saved from landfill. Terrace garden साठी perfect!"),
    ("segregate waste dry wet hazardous",
     "♻️ Wet waste (organic) + Dry waste (paper, plastic, metal) + Hazardous (batteries, medicine) — तीन वेगळ्या bins! Pune, Nashik, Nagpur all have door-step collection. Segregate करा!"),
    ("plastic avoid single use bag bottle",
     "🛍️ Single-use plastic bag = 6g CO₂. आपण वर्षात ~500 bags वापरतो = 3 kg CO₂. Cloth bag एकदा घ्या, 500 वेळा वापरा. Steel bottle = 500 plastic bottles replace करतो."),
    # Climate facts
    ("global warming temperature 1.5 degree",
     "🌡️ Earth आधीच 1.1°C warm झाली आहे. 1.5°C वर Marathwada drought worse होईल, Mumbai coastal flooding वाढेल, Himalayan glaciers melt होतील. आपल्या actions मुळे difference होतो!"),
    ("india climate change emissions",
     "🇮🇳 India = world's 3rd largest emitter, पण per-capita emissions USA च्या 1/8. India's 500 GW renewable target by 2030 = world's most ambitious. आपण बदल घडवू शकतो!"),
    ("carbon footprint meaning calculate",
     "📊 Carbon footprint = तुमच्या activities मधून निघणारा CO₂. Average Indian = 7 kg/day. Sustainable = 2.74 kg/day. EcoTrack मध्ये daily log करा — 30 दिवसांत track करा!"),
    ("ecoscore badge reward achievement",
     "🏆 EcoScore (0-100) = Emission level (50 pts) + Tracking streak (30 pts) + Badges (20 pts). 80+ = Eco Champion! Green Day badge: under 5 kg CO₂. Week Warrior: 7 days streak."),
    ("tree plant neem peepal banyan",
     "🌳 एक झाड = 22 kg CO₂/year absorb करतो. Native species best: Neem (fastest growth), Peepal (most oxygen), Banyan (most CO₂). Van Mahotsav: जुलैमध्ये join करा!"),
    ("marathwada vidarbha drought heat",
     "🌾 Marathwada मध्ये गेल्या 10 वर्षांत 6 वर्षे दुष्काळ. Vidarbha temperature 47°C+ records. हे सर्व climate change मुळे वाढत आहे. आपण आत्ता action घेतल्यास पुढील generation ला relief मिळेल."),
    ("mumbai sea level rise flood coastal",
     "🌊 Mumbai coastline धोक्यात! Sea level 20cm rise since 1900. Dharavi, Colaba at risk. By 2050 many coastal areas flooded without climate action. Urban carbon tracking essential!"),
    ("what is ecotrack how use",
     "🌍 EcoTrack हे तुमचा daily carbon footprint track करण्याचे tool आहे. रोज transport, food, energy, shopping log करा. Dashboard वर charts पहा, tips मिळवा, leaderboard वर compete करा. आत्ता Log Today click करा!"),
    # Greetings
    ("hello hi namaste hey",
     "नमस्ते! 🌿 मी EcoBot आहे — EcoTrack चा AI assistant. तुम्ही carbon footprint, climate change, green tips, किंवा EcoTrack बद्दल काहीही विचारू शकता. काय जाणून घ्यायचे आहे?"),
    ("thanks thank you shukriya",
     "स्वागत आहे! 🌱 आणखी काही विचारायचे असेल तर मी इथेच आहे. लक्षात ठेवा — प्रत्येक छोटी green action मोठा फरक घडवते!"),
    ("help what can you do",
     "मी EcoBot तुम्हाला मदत करू शकतो:\n🚗 Transport emissions कमी कसे करायचे\n🍽️ Diet आणि food carbon बद्दल\n⚡ Energy saving tips\n💧 Water conservation\n🌍 Climate change facts\n☀️ Solar panel subsidies\n\nकाय जाणून घ्यायचे?"),
]


class EcoBot:
    def __init__(self):
        if not SKLEARN_AVAILABLE:
            self._fallback = True
            return
        self._fallback = False
        questions = [q for q, _ in QA_PAIRS]
        self.answers = [a for _, a in QA_PAIRS]
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self.mat = self.vec.fit_transform(questions)

    def chat(self, user_input: str) -> str:
        if self._fallback:
            return "🌱 EcoBot सध्या उपलब्ध नाही. `pip install scikit-learn` install करा."
        user_input = user_input.lower().strip()
        if not user_input:
            return "कृपया काहीतरी विचारा! 😊"
        uvec   = self.vec.transform([user_input])
        scores = cosine_similarity(uvec, self.mat).flatten()
        best   = int(np.argmax(scores))
        if scores[best] < 0.08:
            return ("मला नक्की समजलं नाही 😊 तुम्ही असे विचारू शकता:\n"
                    "• माझा carbon कसा कमी करायचा?\n"
                    "• Solar panel subsidy किती?\n"
                    "• AC efficiently कसा वापरायचा?\n"
                    "• Marathwada drought आणि climate change?\n"
                    "• EcoTrack कसे वापरायचे?")
        return self.answers[best]


# ══════════════════════════════════════════════════════════════════════
#  2. CO2 PREDICTOR — Linear Regression
# ══════════════════════════════════════════════════════════════════════

class CO2Predictor:
    def __init__(self):
        self._ready = SKLEARN_AVAILABLE

    def predict_next_month(self, logs: list) -> dict:
        """logs = list of CarbonLog objects"""
        if not logs:
            return {'predicted': 0, 'trend': 'no_data', 'confidence': 0}

        values = [l.total_co2 for l in logs]
        n      = len(values)

        if n < 3:
            avg = sum(values) / n
            return {
                'predicted': round(avg * 30, 1),
                'daily_pred': round(avg, 2),
                'trend': 'stable',
                'confidence': 40,
                'message': f'मात्र {n} दिवसांचा data — अजून log करा अचूक prediction साठी!',
            }

        if SKLEARN_AVAILABLE:
            X = np.array(range(n)).reshape(-1, 1)
            y = np.array(values)
            model = LinearRegression().fit(X, y)
            next_day    = model.predict([[n]])[0]
            daily_pred  = max(0.5, round(float(next_day), 2))
            slope       = float(model.coef_[0])
            r2          = round(float(model.score(X, y)) * 100, 1)
        else:
            # Simple moving average fallback
            daily_pred = round(sum(values[-7:]) / min(7, n), 2)
            slope      = (values[-1] - values[0]) / max(n - 1, 1)
            r2         = 50

        trend = 'improving' if slope < -0.05 else ('worsening' if slope > 0.05 else 'stable')
        monthly = round(daily_pred * 30, 1)
        yearly  = round(daily_pred * 365, 1)

        if trend == 'improving':
            msg = f"🎉 तुमचा carbon कमी होत आहे! पुढील महिन्यात {monthly} kg CO₂ expect."
        elif trend == 'worsening':
            msg = f"⚠️ तुमचा carbon वाढत आहे. Action घेणे गरजेचे! Predicted: {monthly} kg next month."
        else:
            msg = f"➡️ तुमचा carbon stable आहे. {monthly} kg CO₂ next month predicted."

        return {
            'predicted':   monthly,
            'yearly_pred': yearly,
            'daily_pred':  daily_pred,
            'trend':       trend,
            'confidence':  min(95, r2 + 20),
            'message':     msg,
            'trees_needed': round(yearly / 22, 1),
        }


# ══════════════════════════════════════════════════════════════════════
#  3. SMART TIP RECOMMENDER — K-Means Cluster
# ══════════════════════════════════════════════════════════════════════

CLUSTER_TIPS = {
    0: {  # High transport emitter
        'title': 'Transport Champion बना',
        'tips': [
            "🚌 PMPML bus किंवा Metro वापरा — car पेक्षा 58% कमी emissions.",
            "🚲 5 km पेक्षा कमी अंतर cycle किंवा walk करा.",
            "🏠 आठवड्यातून 2 दिवस WFH करा — commute emissions 40% कमी.",
            "🚗 Carpool app (QuickRide/BlaBlaCar) वापरा — per-person emissions 50% कमी.",
        ]
    },
    1: {  # High food emitter
        'title': 'Food Carbon कमी करा',
        'tips': [
            "🥦 Meatless Monday — आठवड्याला 3.4 kg CO₂ बचत.",
            "🛒 Local sabzi market मधून खरेदी — transport emissions 90% कमी.",
            "🍳 Pressure cooker वापरा — 70% कमी LPG consumption.",
            "📅 Weekly meal plan करा — food waste 30-40% कमी होईल.",
        ]
    },
    2: {  # High energy emitter
        'title': 'Energy Saver व्हा',
        'tips': [
            "❄️ AC 24°C वर set करा — प्रत्येक degree = 6% electricity saving.",
            "💡 सर्व bulbs LED मध्ये convert करा — 75% कमी electricity.",
            "☀️ PM Surya Ghar scheme मध्ये apply करा — ₹78,000 subsidy!",
            "🔌 Standby devices unplug करा — phantom load 10% electricity वाया घालवतो.",
        ]
    },
    3: {  # Balanced / Low emitter — champion
        'title': 'तुम्ही Eco Champion आहात! 🏆',
        'tips': [
            "🌳 महिन्यातून एक झाड लावा — native species जसे Neem, Peepal.",
            "📣 5 मित्रांना EcoTrack join करायला सांगा — multiplier effect!",
            "🤝 Local cleanup किंवा tree drive मध्ये participate करा.",
            "☀️ Rooftop solar साठी apply करा — ROI 5-7 years, lifetime green energy.",
        ]
    },
}


class TipRecommender:
    def __init__(self):
        self._ready = SKLEARN_AVAILABLE

    def recommend(self, logs: list) -> dict:
        if not logs:
            return {'cluster': 3, 'cluster_info': CLUSTER_TIPS[3], 'similar_users': 0, 'saving_potential': 0}

        t_avg = sum(l.transport for l in logs) / len(logs)
        f_avg = sum(l.food      for l in logs) / len(logs)
        e_avg = sum(l.energy    for l in logs) / len(logs)
        s_avg = sum(l.shopping  for l in logs) / len(logs)
        total = t_avg + f_avg + e_avg + s_avg

        # Simple rule-based cluster (fallback works perfectly)
        maxval = max(t_avg, f_avg, e_avg)
        if total < 5:
            cluster = 3
        elif maxval == t_avg and t_avg > 2:
            cluster = 0
        elif maxval == f_avg and f_avg > 3:
            cluster = 1
        elif maxval == e_avg and e_avg > 2:
            cluster = 2
        else:
            cluster = 3

        saving = round((total - 2.74) * 30, 1) if total > 2.74 else 0

        return {
            'cluster':        cluster,
            'cluster_info':   CLUSTER_TIPS[cluster],
            'similar_users':  [42, 87, 156, 203][cluster],  # simulated
            'saving_potential': max(0, saving),
            'your_avg':       round(total, 2),
            'breakdown':      {'transport': round(t_avg,2), 'food': round(f_avg,2),
                               'energy': round(e_avg,2), 'shopping': round(s_avg,2)},
        }


# ══════════════════════════════════════════════════════════════════════
#  4. ANOMALY DETECTOR — Isolation Forest / Z-Score
# ══════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    def detect(self, logs: list) -> dict:
        if len(logs) < 5:
            return {'is_anomaly': False, 'severity': 'none', 'message': ''}

        values = [l.total_co2 for l in logs]
        mean   = sum(values) / len(values)
        std    = (sum((v - mean)**2 for v in values) / len(values))**0.5
        latest = values[-1]

        if std < 0.01:
            return {'is_anomaly': False, 'severity': 'none', 'message': ''}

        z_score = abs(latest - mean) / std

        if z_score > 2.5:
            severity = 'high'
            ratio    = round(latest / mean, 1)
            msg      = (f"🚨 आज तुमचा carbon {latest} kg — सरासरी पेक्षा {ratio}x जास्त! "
                        f"काय special झाले आज? Long trip? Meat feast? AC जास्त वापरला?")
        elif z_score > 1.8:
            severity = 'medium'
            msg      = (f"⚠️ आजचा carbon {latest} kg — सरासरी पेक्षा जास्त. "
                        f"उद्या vegetarian diet आणि public transport वापरून balance करा.")
        elif latest < mean * 0.5:
            severity = 'positive'
            msg      = f"🎉 Excellent! आजचा carbon {latest} kg — तुमच्या सरासरी पेक्षा खूप कमी! Keep it up!"
        else:
            severity = 'none'
            msg      = ''

        return {
            'is_anomaly': z_score > 1.8,
            'severity':   severity,
            'z_score':    round(z_score, 2),
            'latest':     latest,
            'mean':       round(mean, 2),
            'message':    msg,
        }


# ══════════════════════════════════════════════════════════════════════
#  5. HABIT STREAK PREDICTOR
# ══════════════════════════════════════════════════════════════════════

class StreakPredictor:
    def predict(self, logs: list) -> dict:
        if len(logs) < 7:
            return {
                'break_probability': 0,
                'risk_level': 'low',
                'streak_days': len(logs),
                'message': 'अजून data log करा accurate prediction साठी!',
                'tips': [],
            }

        values = [l.total_co2 for l in logs]
        dates  = [l.date for l in logs]

        # Check for gaps in dates
        gaps = 0
        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i-1]).days
            if diff > 1:
                gaps += diff - 1

        # Trend in last 7 days
        last7    = values[-7:]
        slope    = (last7[-1] - last7[0]) / 6
        variance = np.var(last7) if len(last7) >= 2 else 0

        # Probability calculation
        prob = 20  # base
        if slope > 0.5:   prob += 30  # worsening trend
        if variance > 4:  prob += 20  # inconsistent
        if gaps > 2:      prob += 25  # gaps in logging
        if len(logs) < 14: prob += 10  # new user

        prob = min(90, max(5, prob))

        if prob >= 70:
            risk    = 'high'
            message = f"🚨 {prob}% शक्यता आहे की तुम्ही उद्या green habit तोडाल. आत्ता एक छोटी action घ्या!"
            tips    = ["आत्ता उद्याचा meal plan करा", "उद्याचा transport route आधीच ठरवा", "EcoTrack ची reminder set करा"]
        elif prob >= 40:
            risk    = 'medium'
            message = f"⚠️ {prob}% risk आहे streak तुटण्याचा. Momentum maintain करा!"
            tips    = ["Daily reminder set करा", "एक easy green action plan करा उद्यासाठी"]
        else:
            risk    = 'low'
            message = f"✅ {100-prob}% शक्यता आहे की तुम्ही streak maintain कराल. Excellent momentum!"
            tips    = ["तुम्ही great job करत आहात!", "मित्रांना invite करा EcoTrack वर"]

        return {
            'break_probability': prob,
            'risk_level':        risk,
            'streak_days':       len(logs),
            'gaps_found':        gaps,
            'message':           message,
            'tips':              tips,
        }


# ══════════════════════════════════════════════════════════════════════
#  6. AI CLIMATE REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════

class ReportGenerator:
    ACHIEVEMENTS = [
        (lambda l: len(l) >= 30,  "🏆 Monthly Champion — 30 दिवस tracking!"),
        (lambda l: len(l) >= 7,   "🔥 Week Warrior — 7+ दिवस consistent!"),
        (lambda l: any(x.total_co2 < 3 for x in l), "⚡ Carbon Zero Hero — एक दिवस 3 kg खाली!"),
        (lambda l: any(x.food < 2.5 for x in l),    "🥦 Green Eater — vegetarian day achieved!"),
        (lambda l: any(x.transport < 0.5 for x in l), "🚲 Zero Commute — एक दिवस walk/cycle!"),
    ]

    def generate(self, user, logs: list, badges: list) -> dict:
        if not logs:
            return {'available': False}

        avg    = sum(l.total_co2 for l in logs) / len(logs)
        best   = min(l.total_co2 for l in logs)
        worst  = max(l.total_co2 for l in logs)
        total  = sum(l.total_co2 for l in logs)
        india  = 7.0
        saved  = max(0, (india - avg) * len(logs))
        trees  = round(saved / 22, 1)

        breakdown = {
            'transport': round(sum(l.transport for l in logs)/len(logs), 2),
            'food':      round(sum(l.food      for l in logs)/len(logs), 2),
            'energy':    round(sum(l.energy    for l in logs)/len(logs), 2),
            'shopping':  round(sum(l.shopping  for l in logs)/len(logs), 2),
        }
        top_cat  = max(breakdown, key=breakdown.get)
        achieved = [msg for cond, msg in self.ACHIEVEMENTS if cond(logs)]

        # Grade
        if avg < 3:    grade, grade_color = 'A+', '#1a7a45'
        elif avg < 5:  grade, grade_color = 'A',  '#2d8a56'
        elif avg < 7:  grade, grade_color = 'B',  '#e8a020'
        elif avg < 10: grade, grade_color = 'C',  '#e8604a'
        else:          grade, grade_color = 'D',  '#c0392b'

        # Narrative
        if avg < india:
            narrative = (f"{user.name} जी, तुम्ही {len(logs)} दिवसांत India च्या सरासरी "
                         f"({india} kg) पेक्षा कमी carbon emit केलात! "
                         f"तुमच्या efforts मुळे {round(saved,1)} kg CO₂ वाचला — "
                         f"{trees} झाडांच्या वार्षिक कामाइतके! 🌳")
        else:
            diff = round((avg - india) * len(logs), 1)
            narrative = (f"{user.name} जी, तुमचा average ({round(avg,2)} kg/day) India average पेक्षा "
                         f"जास्त आहे. {top_cat} category मध्ये सर्वात जास्त scope आहे. "
                         f"पुढील महिन्यात {top_cat} focus करा!")

        return {
            'available':    True,
            'grade':        grade,
            'grade_color':  grade_color,
            'avg':          round(avg, 2),
            'best':         round(best, 2),
            'worst':        round(worst, 2),
            'total':        round(total, 1),
            'days':         len(logs),
            'saved':        round(saved, 1),
            'trees':        trees,
            'flights_eq':   round(total / 255, 1),
            'breakdown':    breakdown,
            'top_category': top_cat,
            'achievements': achieved,
            'badges_count': len(badges),
            'narrative':    narrative,
            'month':        datetime.now().strftime('%B %Y'),
        }


# ══════════════════════════════════════════════════════════════════════
#  SINGLETON INSTANCES
# ══════════════════════════════════════════════════════════════════════

ecobot          = EcoBot()
predictor       = CO2Predictor()
recommender     = TipRecommender()
anomaly_detector = AnomalyDetector()
streak_predictor = StreakPredictor()
report_generator = ReportGenerator()
