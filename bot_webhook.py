"""
Webhook Version - לפרודקשן ב-Render
גרסה עם Flask webhooks במקום polling
"""

import os
import logging
import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeout
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
WEBHOOK_PATH = (os.getenv("WEBHOOK_PATH") or TELEGRAM_BOT_TOKEN or "").lstrip("/")
PORT = int(os.getenv("PORT", 10000))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set!")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set!")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL not set!")
if not WEBHOOK_PATH:
    raise ValueError("❌ WEBHOOK_PATH not set!")

WEBHOOK_FULL_URL = f"{WEBHOOK_URL}/{WEBHOOK_PATH}"


def _mask_webhook_url(url: str) -> str:
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN in url:
        return url.replace(TELEGRAM_BOT_TOKEN, "<TOKEN>")
    return url

# יצירת Flask app
app = Flask(__name__)

# יצירת Telegram Application
telegram_app = None
_telegram_started = False

_loop = None
_loop_thread = None
_loop_ready = threading.Event()
_start_lock = threading.Lock()
_setup_lock = threading.Lock()
_start_event = threading.Event()
_start_in_progress = False
_start_error = None
_setup_event = threading.Event()
_setup_in_progress = False
_setup_error = None


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


def _run_coroutine(coro, timeout=None):
    future = _submit_coroutine(coro)
    return future.result(timeout=timeout)


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
    await asyncio.wait_for(
        telegram_app.bot.set_webhook(url=WEBHOOK_FULL_URL),
        timeout=10
    )
    logger.info("✅ Webhook set to: %s", _mask_webhook_url(WEBHOOK_FULL_URL))


def _start_worker():
    global _start_in_progress, _start_error
    try:
        _run_coroutine(_start_telegram_app(), timeout=15)
        _start_event.set()
        _start_error = None
    except Exception as exc:
        _start_error = str(exc)
        logger.error("Failed to start Telegram app: %s", exc, exc_info=True)
    finally:
        with _start_lock:
            _start_in_progress = False


def trigger_app_start(wait=False, timeout=0):
    if _start_event.is_set():
        return True
    global _start_in_progress
    with _start_lock:
        if _start_event.is_set():
            return True
        if not _start_in_progress:
            _start_in_progress = True
            thread = threading.Thread(target=_start_worker, daemon=True)
            thread.start()
    if wait:
        return _start_event.wait(timeout=timeout)
    return False


def _setup_worker():
    global _setup_in_progress, _setup_error
    try:
        if not trigger_app_start(wait=True, timeout=15):
            raise TimeoutError("Telegram app start timed out")
        _run_coroutine(setup_webhook(), timeout=15)
        _setup_event.set()
        _setup_error = None
    except Exception as exc:
        _setup_error = str(exc)
        logger.error("Webhook setup failed: %s", exc, exc_info=True)
    finally:
        with _setup_lock:
            _setup_in_progress = False


def trigger_webhook_setup(force=False):
    global _setup_in_progress
    if _setup_event.is_set() and not force:
        return "already_set"
    with _setup_lock:
        if _setup_in_progress:
            return "running"
        if _setup_event.is_set() and not force:
            return "already_set"
        if force:
            _setup_event.clear()
        _setup_in_progress = True
        thread = threading.Thread(target=_setup_worker, daemon=True)
        thread.start()
        return "started"


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
        if not _start_event.is_set():
            trigger_app_start()
            if not _start_event.wait(timeout=2):
                return jsonify({
                    "ok": False,
                    "error": "Bot is starting, try again shortly"
                }), 503
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        logger.info("📩 Webhook update received: %s", update.update_id)
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
    status = trigger_webhook_setup(force=True)
    response = {
        "status": status,
        "webhook_url": _mask_webhook_url(WEBHOOK_FULL_URL)
    }
    if _setup_error:
        response["last_error"] = _setup_error
    http_status = 202 if status in ("started", "running") else 200
    return jsonify(response), http_status


async def _get_webhook_info():
    return await asyncio.wait_for(
        telegram_app.bot.get_webhook_info(),
        timeout=5
    )


@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """
    מידע על ה-webhook הנוכחי
    """
    try:
        if not _start_event.is_set():
            trigger_app_start()
            response = {
                "status": "starting",
                "start_error": _start_error
            }
            if _setup_error:
                response["last_setup_error"] = _setup_error
            return jsonify(response), 202
        info = _run_coroutine(_get_webhook_info(), timeout=6)
        return jsonify({
            "url": _mask_webhook_url(info.url) if info.url else info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "setup_status": "done" if _setup_event.is_set() else "running" if _setup_in_progress else "idle"
        })
    except FutureTimeout:
        return jsonify({"error": "Timeout while contacting Telegram"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main():
    """
    הרצת השרת
    """
    logger.info("🤖 Starting Refiner Bot in WEBHOOK mode...")
    logger.info("📡 Webhook URL: %s", _mask_webhook_url(WEBHOOK_FULL_URL))

    status = trigger_webhook_setup(force=False)
    if status == "started":
        logger.info("⏳ Webhook setup started in background")
    elif status == "running":
        logger.info("⏳ Webhook setup already in progress")
    
    # הרצת Flask
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False
    )


if __name__ == "__main__":
    main()
else:
    trigger_webhook_setup(force=False)
