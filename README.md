# 🌍 EcoTrack — Carbon Footprint Tracker
### Hackathon Project | Flask + SQLite + Chart.js

## 🎯 Problem Statement
Global warming is a growing crisis. Individual daily choices — transport, food, energy, shopping — contribute significantly to carbon emissions. Most people don't even know their carbon footprint. EcoTrack helps users **track, understand, and reduce** their daily CO₂ emissions through awareness, tips, and community motivation.

## ✨ Features
| Feature | Description |
|---|---|
| 🧮 Daily Calculator | Log transport, food, energy, shopping with live CO₂ preview |
| 📊 Progress Tracker | Line + Doughnut charts showing 30-day trends |
| 💡 Smart Tips | Personalised tips based on your highest emission category |
| 🏆 Leaderboard | Rank users by daily average, compare cities |
| 🏅 Badge System | Earn badges for green milestones |
| 🔐 Auth | Register/Login with password hashing |

## 🛠️ Tech Stack
- **Backend:** Python, Flask, SQLAlchemy
- **Database:** SQLite
- **Frontend:** Jinja2, Bootstrap 5, Chart.js
- **Security:** Werkzeug password hashing, Flask sessions

## 🚀 Setup & Run

```bash
# 1. Clone / extract project
cd carbon_tracker

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# 5. Open browser at:
#    http://127.0.0.1:5000
```

## 📁 Project Structure
```
carbon_tracker/
├── app.py              # Flask routes & logic
├── models.py           # SQLAlchemy DB models
├── requirements.txt
├── templates/
│   ├── base.html       # Navbar, footer
│   ├── index.html      # Landing page
│   ├── calculate.html  # Carbon calculator
│   ├── dashboard.html  # Charts & progress
│   ├── tips.html       # Reduction tips
│   ├── leaderboard.html# Community ranking
│   ├── login.html
│   └── register.html
└── static/
    ├── css/style.css   # Custom eco theme
    └── js/calculator.js# Live CO2 preview
```

## 🌱 Emission Factors Used
- **Car:** 0.21 kg CO₂/km | **Bus:** 0.089 | **Train:** 0.041
- **Diet:** Heavy meat 7.19 kg/day → Vegan 2.89 kg/day
- **Electricity:** 0.82 kg CO₂/kWh (India grid factor)
- **Shopping:** 0.5 kg CO₂ per ₹100 spent

## 👥 Team
 TechPravah
