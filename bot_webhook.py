"""
Webhook Version - לפרודקשן ב-Render
גרסה עם Flask webhooks במקום polling
"""

import os
import logging
import asyncio
import threading
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
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").rstrip("/")  # https://your-app.onrender.com
PORT = int(os.getenv("PORT", 10000))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set!")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set!")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL not set!")

WEBHOOK_PATH = TELEGRAM_BOT_TOKEN
WEBHOOK_FULL_URL = f"{WEBHOOK_URL}/{WEBHOOK_PATH}"

# יצירת Flask app
app = Flask(__name__)

# יצירת Telegram Application
telegram_app = None
_telegram_started = False

_loop = None
_loop_thread = None
_loop_ready = threading.Event()
_setup_lock = threading.Lock()
_setup_done = False


def _loop_runner():
    asyncio.set_event_loop(_loop)
    _loop_ready.set()
    _loop.run_forever()


def _ensure_loop():
    global _loop, _loop_thread
    if _loop_thread is None:
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop_runner, daemon=True)
        _loop_thread.start()
        _loop_ready.wait()


def _submit_coroutine(coro):
    _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, _loop)


def _run_coroutine(coro):
    future = _submit_coroutine(coro)
    return future.result()


def _build_telegram_app():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(
        filters.FORWARDED & filters.TEXT & ~filters.COMMAND,
        handle_forwarded_message
    ))
    app.add_handler(CallbackQueryHandler(
        publish_to_channel_callback,
        pattern="^publish$"
    ))
    app.add_error_handler(error_handler)
    return app


async def _start_telegram_app():
    global telegram_app, _telegram_started
    if telegram_app is None:
        telegram_app = _build_telegram_app()
    if not _telegram_started:
        await telegram_app.initialize()
        await telegram_app.start()
        _telegram_started = True


async def setup_webhook():
    """
    הגדרת webhook ב-Telegram
    """
    await _start_telegram_app()
    await telegram_app.bot.set_webhook(url=WEBHOOK_FULL_URL)
    logger.info("✅ Webhook set to: %s", WEBHOOK_FULL_URL)


def ensure_webhook():
    global _setup_done
    if _setup_done:
        return
    with _setup_lock:
        if _setup_done:
            return
        _run_coroutine(setup_webhook())
        _setup_done = True


def _log_future_error(future):
    try:
        future.result()
    except Exception as exc:
        logger.error("Update processing failed: %s", exc, exc_info=True)


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


@app.route(f'/{WEBHOOK_PATH}', methods=['POST'])
def webhook():
    """
    Webhook endpoint לקבלת עדכונים מטלגרם
    """
    try:
        ensure_webhook()
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        future = _submit_coroutine(telegram_app.process_update(update))
        future.add_done_callback(_log_future_error)
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error("Webhook error: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """
    Route להגדרת webhook ידנית
    """
    global _setup_done
    try:
        with _setup_lock:
            _run_coroutine(setup_webhook())
            _setup_done = True
        return jsonify({
            "status": "success",
            "webhook_url": WEBHOOK_FULL_URL
        })
    except Exception as e:
        logger.error("Failed to set webhook: %s", e, exc_info=True)
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """
    מידע על ה-webhook הנוכחי
    """
    try:
        ensure_webhook()
        info = _run_coroutine(telegram_app.bot.get_webhook_info())
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
    logger.info("🤖 Starting Refiner Bot in WEBHOOK mode...")
    logger.info("📡 Webhook URL: %s", WEBHOOK_FULL_URL)

    ensure_webhook()
    
    # הרצת Flask
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False
    )


def _auto_setup_webhook():
    try:
        ensure_webhook()
    except Exception:
        logger.exception("Auto webhook setup failed")


def _schedule_webhook_setup():
    thread = threading.Thread(target=_auto_setup_webhook, daemon=True)
    thread.start()


if __name__ == "__main__":
    main()
else:
    _schedule_webhook_setup()
