"""
Configuration file for Refiner Bot
מרכז את כל ההגדרות במקום אחד
"""

import os
from dotenv import load_dotenv

# טעינת משתני סביבה מ-.env
load_dotenv()

# ======================
# Telegram Configuration
# ======================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

# ======================
# Gemini AI Configuration
# ======================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # ברירת מחדל

# פרמטרים ל-Gemini
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
GEMINI_TOP_P = float(os.getenv("GEMINI_TOP_P", "0.9"))
GEMINI_TOP_K = int(os.getenv("GEMINI_TOP_K", "40"))
GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))

# ======================
# MongoDB Configuration (Optional)
# ======================
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "refiner_bot")

# ======================
# Logging Configuration
# ======================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ======================
# Bot Behavior
# ======================
# זמן תפוגה לטקסט משוכתב (בשניות) - אחרי זה לא אפשר לפרסם
REFINED_TEXT_EXPIRY = int(os.getenv("REFINED_TEXT_EXPIRY", "3600"))  # שעה

# האם לשמור היסטוריה ב-MongoDB
SAVE_HISTORY = os.getenv("SAVE_HISTORY", "false").lower() == "true"


def validate_config():
    """
    בדיקה שכל המשתנים החיוניים מוגדרים
    """
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("❌ TELEGRAM_BOT_TOKEN is not set!")
    
    if not GEMINI_API_KEY:
        errors.append("❌ GEMINI_API_KEY is not set!")
    
    if not CHANNEL_USERNAME:
        errors.append("⚠️ CHANNEL_USERNAME is not set - publish to channel will not work!")
    
    if errors:
        for error in errors:
            print(error)
        if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
            raise ValueError("Critical configuration missing! Check .env file.")
    
    return True


# בדיקה אוטומטית בעת import
if __name__ != "__main__":
    validate_config()
