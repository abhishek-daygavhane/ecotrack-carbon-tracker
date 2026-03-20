/* EcoTrack — Marathi / English Language Toggle */

const TRANSLATIONS = {
  en: {
    /* NAV */
    "nav.dashboard":   "Dashboard",
    "nav.log":         "Log Today",
    "nav.learn":       "Learn",
    "nav.tips":        "50+ Tips",
    "nav.challenge":   "30-Day Challenge",
    "nav.awareness":   "Climate Awareness",
    "nav.pledge":      "Make a Pledge",
    "nav.myimpact":    "My Impact",
    "nav.twin":        "My Carbon Twin",
    "nav.advisor":     "AI Advisor",
    "nav.simulator":   "What-If Simulator",
    "nav.leaderboard": "Leaderboard",
    "nav.logout":      "Logout",
    "nav.login":       "Login",
    "nav.getstarted":  "Get Started",

    /* HOME */
    "home.eyebrow":    "Environmental Awareness Project",
    "home.title1":     "Track Your",
    "home.title2":     "Carbon Footprint",
    "home.title3":     "Save the Planet",
    "home.sub":        "Every person's daily choices matter. Track, reduce, and compete with your community to fight global warming — one day at a time.",
    "home.cta":        "Start Tracking Free",
    "home.how":        "How It Works",
    "home.features":   "How EcoTrack Works",
    "home.f1title":    "Log Daily Activity",
    "home.f1desc":     "Enter your transport, food, energy, and shopping habits every day.",
    "home.f2title":    "Track Progress",
    "home.f2desc":     "See weekly and monthly charts showing your carbon reduction over time.",
    "home.f3title":    "50+ Green Tips",
    "home.f3desc":     "Personalised suggestions across transport, food, energy, water, waste and more.",
    "home.f4title":    "30-Day Challenge",
    "home.f4desc":     "Take one green action every day. Unlock badges and compete with your city!",
    "home.f5title":    "Leaderboard",
    "home.f5desc":     "Compare with friends and cities. See who's making the most difference.",
    "home.f6title":    "Climate Awareness",
    "home.f6desc":     "Learn key climate facts, India's context, and what you can do at every level.",
    "home.f7title":    "Earn Badges",
    "home.f7desc":     "Get rewarded for green milestones — Green Day, Week Warrior, Carbon Zero Hero!",
    "home.f8title":    "Tree Impact Meter",
    "home.f8desc":     "See how many trees' worth of CO₂ you've saved vs the India average.",
    "home.cta2title":  "Ready to make a difference?",
    "home.cta2sub":    "Join EcoTrack and take your first step towards a sustainable future.",
    "home.cta2btn":    "Join EcoTrack Now",
    "home.stat1":      "Tonnes CO₂ emitted daily",
    "home.stat2":      "Average daily carbon/person",
    "home.stat3":      "Critical warming limit",
    "home.stat4":      "Emissions reducible by lifestyle",

    /* DASHBOARD */
    "dash.welcome":    "Welcome back",
    "dash.subtitle":   "Track, reduce, and earn badges",
    "dash.logbtn":     "Log Today",
    "dash.ecoscore":   "Your EcoScore is calculated from your emission levels, tracking consistency, and badges earned.",
    "dash.mytwin":     "My Twin",
    "dash.advisor":    "AI Advisor",
    "dash.loading":    "Loading today's eco tip...",
    "dash.today":      "Today (kg CO₂)",
    "dash.weekavg":    "Weekly Avg",
    "dash.monthtotal": "Monthly Total",
    "dash.badges":     "Badges",
    "dash.trend":      "30-Day Carbon Trend",
    "dash.breakdown":  "Emission Breakdown",
    "dash.mybadges":   "Your Badges",
    "dash.keeplogging":"Keep logging to earn badges!",
    "dash.recentlogs": "Recent Logs",
    "dash.nologs":     "No data yet.",
    "dash.logfirst":   "Log your first day!",

    /* CALCULATE */
    "calc.title":      "Log Today's Carbon Footprint",
    "calc.sub":        "Fill in your daily activities to calculate your CO₂ impact",
    "calc.transport":  "Transport",
    "calc.mode":       "Mode of Transport",
    "calc.km":         "Distance Travelled (km)",
    "calc.food":       "Food & Diet",
    "calc.diettype":   "Today's diet type",
    "calc.energy":     "Home Energy",
    "calc.elec":       "Electricity Used Today (kWh)",
    "calc.lpg":        "LPG Used (kg)",
    "calc.shopping":   "Shopping & Purchases",
    "calc.spend":      "Amount Spent Today (₹)",
    "calc.savebtn":    "Save My Footprint for Today",
    "calc.preview":    "Today's Total",

    /* TIPS */
    "tips.title":      "50+ Ways to Reduce Your Carbon Footprint",
    "tips.sub":        "Your highest emission area",
    "tips.focus":      "focus here first",
    "tips.all":        "All Tips",
    "tips.highonly":   "High Impact Only",

    /* LEADERBOARD */
    "lb.title":        "Community Leaderboard",
    "lb.sub":          "Lower CO₂ = better rank! 30-day daily average.",
    "lb.individual":   "Individual Rankings",
    "lb.city":         "City Comparison",
    "lb.user":         "User",
    "lb.cityCol":      "City",
    "lb.avg":          "Avg CO₂/day",
    "lb.days":         "Days Logged",
    "lb.you":          "You",

    /* FOOTER */
    "footer.text":     "Together we can reduce our carbon footprint",
    "footer.built":    "Built for Hackathon 2025",
  },

  mr: {
    /* NAV */
    "nav.dashboard":   "डॅशबोर्ड",
    "nav.log":         "आजचा लॉग",
    "nav.learn":       "शिका",
    "nav.tips":        "५०+ टिप्स",
    "nav.challenge":   "३०-दिवस आव्हान",
    "nav.awareness":   "हवामान जागरूकता",
    "nav.pledge":      "प्रतिज्ञा करा",
    "nav.myimpact":    "माझा प्रभाव",
    "nav.twin":        "माझे कार्बन ट्विन",
    "nav.advisor":     "AI सल्लागार",
    "nav.simulator":   "काय-जर सिम्युलेटर",
    "nav.leaderboard": "लीडरबोर्ड",
    "nav.logout":      "बाहेर पडा",
    "nav.login":       "लॉगिन",
    "nav.getstarted":  "सुरुवात करा",

    /* HOME */
    "home.eyebrow":    "पर्यावरण जागरूकता प्रकल्प",
    "home.title1":     "आपला",
    "home.title2":     "कार्बन फूटप्रिंट",
    "home.title3":     "ट्रॅक करा, पृथ्वी वाचवा",
    "home.sub":        "प्रत्येक व्यक्तीच्या रोजच्या निवडी महत्त्वाच्या आहेत. ट्रॅक करा, कमी करा आणि ग्लोबल वार्मिंगशी लढा — एक दिवस एक वेळ.",
    "home.cta":        "मोफत ट्रॅकिंग सुरू करा",
    "home.how":        "कसे कार्य करते",
    "home.features":   "EcoTrack कसे कार्य करते",
    "home.f1title":    "रोजचे लॉग करा",
    "home.f1desc":     "वाहतूक, अन्न, ऊर्जा आणि खरेदीच्या सवयी रोज नोंदवा.",
    "home.f2title":    "प्रगती पहा",
    "home.f2desc":     "साप्ताहिक आणि मासिक चार्ट पहा जे तुमची कार्बन कपात दाखवतात.",
    "home.f3title":    "५०+ हरित टिप्स",
    "home.f3desc":     "वाहतूक, अन्न, ऊर्जा, पाणी आणि कचऱ्यासाठी वैयक्तिक सूचना.",
    "home.f4title":    "३०-दिवस आव्हान",
    "home.f4desc":     "रोज एक हरित कृती करा. बॅज मिळवा आणि शहराशी स्पर्धा करा!",
    "home.f5title":    "लीडरबोर्ड",
    "home.f5desc":     "मित्र आणि शहरांशी तुलना करा. कोण सर्वात जास्त फरक करत आहे ते पहा.",
    "home.f6title":    "हवामान जागरूकता",
    "home.f6desc":     "हवामानाचे मुख्य तथ्य, भारताचा संदर्भ आणि तुम्ही काय करू शकता ते शिका.",
    "home.f7title":    "बॅज मिळवा",
    "home.f7desc":     "हरित टप्प्यांसाठी बक्षिसे मिळवा — ग्रीन डे, वीक वॉरियर!",
    "home.f8title":    "झाड प्रभाव मीटर",
    "home.f8desc":     "भारताच्या सरासरीच्या तुलनेत तुम्ही किती झाडांचे CO₂ वाचवले ते पहा.",
    "home.cta2title":  "बदल घडवण्यासाठी तयार?",
    "home.cta2sub":    "EcoTrack मध्ये सामील व्हा आणि शाश्वत भविष्याकडे पहिले पाऊल टाका.",
    "home.cta2btn":    "आत्ता EcoTrack मध्ये सामील व्हा",
    "home.stat1":      "टन CO₂ दररोज उत्सर्जित",
    "home.stat2":      "सरासरी दैनिक कार्बन/व्यक्ती",
    "home.stat3":      "गंभीर तापमानवाढ मर्यादा",
    "home.stat4":      "जीवनशैलीने कमी होणारे उत्सर्जन",

    /* DASHBOARD */
    "dash.welcome":    "पुन्हा स्वागत",
    "dash.subtitle":   "ट्रॅक करा, कमी करा आणि बॅज मिळवा",
    "dash.logbtn":     "आजचा लॉग",
    "dash.ecoscore":   "तुमचा EcoScore तुमच्या उत्सर्जन पातळी, ट्रॅकिंग सातत्य आणि मिळालेल्या बॅजवर आधारित आहे.",
    "dash.mytwin":     "माझे ट्विन",
    "dash.advisor":    "AI सल्लागार",
    "dash.loading":    "आजची इको टिप लोड होत आहे...",
    "dash.today":      "आज (kg CO₂)",
    "dash.weekavg":    "साप्ताहिक सरासरी",
    "dash.monthtotal": "मासिक एकूण",
    "dash.badges":     "बॅज",
    "dash.trend":      "३०-दिवस कार्बन ट्रेंड",
    "dash.breakdown":  "उत्सर्जन विश्लेषण",
    "dash.mybadges":   "तुमचे बॅज",
    "dash.keeplogging":"बॅज मिळवण्यासाठी लॉग करत राहा!",
    "dash.recentlogs": "अलीकडील नोंदी",
    "dash.nologs":     "अजून डेटा नाही.",
    "dash.logfirst":   "पहिला दिवस लॉग करा!",

    /* CALCULATE */
    "calc.title":      "आजचा कार्बन फूटप्रिंट नोंदवा",
    "calc.sub":        "तुमच्या CO₂ प्रभावाची गणना करण्यासाठी रोजचे कार्य भरा",
    "calc.transport":  "वाहतूक",
    "calc.mode":       "वाहतुकीचे साधन",
    "calc.km":         "प्रवास केलेले अंतर (km)",
    "calc.food":       "अन्न आणि आहार",
    "calc.diettype":   "आजचा आहार प्रकार",
    "calc.energy":     "घराची ऊर्जा",
    "calc.elec":       "आज वापरलेली वीज (kWh)",
    "calc.lpg":        "वापरलेला LPG (kg)",
    "calc.shopping":   "खरेदी आणि खर्च",
    "calc.spend":      "आज खर्च केलेली रक्कम (₹)",
    "calc.savebtn":    "आजचा फूटप्रिंट जतन करा",
    "calc.preview":    "आजचा एकूण",

    /* TIPS */
    "tips.title":      "कार्बन फूटप्रिंट कमी करण्याचे ५०+ मार्ग",
    "tips.sub":        "तुमचे सर्वाधिक उत्सर्जन क्षेत्र",
    "tips.focus":      "इथे प्रथम लक्ष द्या",
    "tips.all":        "सर्व टिप्स",
    "tips.highonly":   "फक्त उच्च प्रभाव",

    /* LEADERBOARD */
    "lb.title":        "समुदाय लीडरबोर्ड",
    "lb.sub":          "कमी CO₂ = चांगला क्रमांक! ३०-दिवसांची दैनिक सरासरी.",
    "lb.individual":   "वैयक्तिक क्रमवारी",
    "lb.city":         "शहर तुलना",
    "lb.user":         "वापरकर्ता",
    "lb.cityCol":      "शहर",
    "lb.avg":          "सरासरी CO₂/दिवस",
    "lb.days":         "दिवस नोंदवले",
    "lb.you":          "तुम्ही",

    /* FOOTER */
    "footer.text":     "एकत्र आपण कार्बन फूटप्रिंट कमी करू शकतो",
    "footer.built":    "हॅकाथॉन २०२५ साठी तयार केले",
  }
};

let currentLang = localStorage.getItem('ecotrack-lang') || 'en';

function applyLang(lang) {
  currentLang = lang;
  localStorage.setItem('ecotrack-lang', lang);

  document.querySelectorAll('[data-lang-key]').forEach(el => {
    const key = el.dataset.langKey;
    if (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]) {
      el.textContent = TRANSLATIONS[lang][key];
    }
  });

  const btn = document.getElementById('lang-btn');
  if (btn) btn.textContent = lang === 'en' ? 'मराठी' : 'English';

  document.documentElement.lang = lang === 'mr' ? 'mr' : 'en';
}

function toggleLang() {
  applyLang(currentLang === 'en' ? 'mr' : 'en');
}

document.addEventListener('DOMContentLoaded', () => {
  applyLang(currentLang);
});
