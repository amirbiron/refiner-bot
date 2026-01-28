"""
Webhook Version - לפרודקשן ב-Render
גרסה עם Flask webhooks במקום polling
"""

import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters
)
from google import genai
from google.genai import types

# Import מקובץ הבוט הרגיל
from bot import (
    REFINER_PROMPT,
    start_command,
    help_command,
    refine_text_with_gemini,
    handle_forwarded_message,
    publish_to_channel_callback,
    error_handler
)

# הגדרת logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# טעינת משתני סביבה
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com
PORT = int(os.getenv("PORT", 10000))

# יצירת Flask app
app = Flask(__name__)

# יצירת Telegram Application
telegram_app = None


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "bot": "Refiner Bot",
        "mode": "webhook",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/health')
def health():
    """Health check לRender"""
    return jsonify({"status": "healthy"}), 200


@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
async def webhook():
    """
    Webhook endpoint לקבלת עדכונים מטלגרם
    """
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        
        await telegram_app.process_update(update)
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


async def setup_webhook():
    """
    הגדרת webhook ב-Telegram
    """
    global telegram_app
    
    # יצירת Application
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # הוספת handlers (זהה לגרסת polling)
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(
        filters.FORWARDED & filters.TEXT & ~filters.COMMAND,
        handle_forwarded_message
    ))
    telegram_app.add_handler(CallbackQueryHandler(
        publish_to_channel_callback,
        pattern="^publish$"
    ))
    telegram_app.add_error_handler(error_handler)
    
    # אתחול הבוט
    await telegram_app.initialize()
    await telegram_app.start()
    
    # הגדרת webhook
    webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    await telegram_app.bot.set_webhook(url=webhook_url)
    
    logger.info(f"✅ Webhook set to: {webhook_url}")


@app.route('/set_webhook', methods=['GET'])
async def set_webhook_route():
    """
    Route להגדרת webhook ידנית
    """
    try:
        await setup_webhook()
        return jsonify({
            "status": "success",
            "webhook_url": f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
        })
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/webhook_info', methods=['GET'])
async def webhook_info():
    """
    מידע על ה-webhook הנוכחי
    """
    try:
        info = await telegram_app.bot.get_webhook_info()
        return jsonify({
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main():
    """
    הרצת השרת
    """
    # בדיקת משתני סביבה
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set!")
    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY not set!")
    if not WEBHOOK_URL:
        raise ValueError("❌ WEBHOOK_URL not set!")
    
    logger.info("🤖 Starting Refiner Bot in WEBHOOK mode...")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}")
    
    # הרצת Flask
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False
    )


if __name__ == "__main__":
    import asyncio
    
    # הגדרת webhook לפני הרצת השרת
    asyncio.run(setup_webhook())
    
    # הרצת השרת
    main()
