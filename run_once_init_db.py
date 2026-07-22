"""
run_once_init_db.py
===================
Run this ONCE before starting the app for the first time:
    python run_once_init_db.py

This creates the SQLite database file and all tables.
"""

from app import app, db
from models import User, CarbonLog, Badge

with app.app_context():
    db.create_all()
    print("=" * 50)
    print("[SUCCESS] Database initialized successfully!")
    print("File: instance/carbon_tracker.db")
    print("")
    print("Tables created:")
    print("  -> users")
    print("  -> carbon_logs")
    print("  -> badges")
    print("  -> completed_actions")
    print("=" * 50)
    print("\nNow run: python app.py")
