"""
Webhook Version - לפרודקשן ב-Render
גרסה עם Flask webhooks במקום polling
"""

import os
import logging
import asyncio
import threading
import time
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

# הגדרת logging מוקדם
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


# Import מקובץ הבוט הרגיל - אחרי הגדרת logging
# הimport מבוצע כאן כי bot.py מאתחל את Gemini client
from bot import (
    REFINER_PROMPT,
    start_command,
    help_command,
    refine_text_with_gemini,
    handle_forwarded_message,
    publish_to_channel_callback,
    error_handler
)

# יצירת Flask app
app = Flask(__name__)

# יצירת Telegram Application
telegram_app = None
_telegram_started = False

_loop = None
_loop_thread = None
_loop_ready = threading.Event()
_start_lock = threading.Lock()
_setup_lock = threading.RLock()  # RLock allows same thread to acquire multiple times
_setup_done = False
_setup_in_progress = False  # Flag to track if setup is running


def _loop_runner():
    """רץ ב-thread נפרד ומריץ את ה-event loop"""
    asyncio.set_event_loop(_loop)
    _loop_ready.set()
    _loop.run_forever()


def _ensure_loop():
    """מוודא שיש event loop פעיל"""
    global _loop, _loop_thread
    if _loop_thread is None or not _loop_thread.is_alive():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop_runner, daemon=True)
        _loop_thread.start()
        # Wait with timeout to avoid hanging
        if not _loop_ready.wait(timeout=10):
            logger.error("Event loop failed to start within timeout")
            raise RuntimeError("Event loop initialization timeout")


def _submit_coroutine(coro):
    """מגיש coroutine להרצה ב-event loop"""
    _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, _loop)


def _run_coroutine(coro, timeout=None):
    """מריץ coroutine וממתין לתוצאה"""
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
    
    # First, delete any existing webhook
    try:
        await asyncio.wait_for(
            telegram_app.bot.delete_webhook(drop_pending_updates=False),
            timeout=15
        )
        logger.info("🔄 Deleted existing webhook")
    except asyncio.TimeoutError:
        logger.warning("Timeout deleting existing webhook, continuing...")
    except Exception as e:
        logger.warning(f"Could not delete existing webhook: {e}")
    
    # Set the new webhook
    await asyncio.wait_for(
        telegram_app.bot.set_webhook(url=WEBHOOK_FULL_URL),
        timeout=20
    )
    logger.info("✅ Webhook set to: %s", _mask_webhook_url(WEBHOOK_FULL_URL))


def ensure_app_started():
    """מוודא שה-Telegram app מאותחל ורץ"""
    if _telegram_started:
        return True
    
    # Try to acquire lock with timeout to avoid deadlock
    acquired = _start_lock.acquire(timeout=30)
    if not acquired:
        logger.warning("Could not acquire start lock - another thread is initializing")
        return _telegram_started
    
    try:
        if _telegram_started:
            return True
        _run_coroutine(_start_telegram_app(), timeout=30)
        return True
    except Exception as e:
        logger.error(f"Failed to start Telegram app: {e}")
        return False
    finally:
        _start_lock.release()


def ensure_webhook():
    """מוודא שה-webhook מוגדר - thread-safe"""
    global _setup_done, _setup_in_progress
    
    if _setup_done:
        return True
    
    # Try to acquire lock with timeout
    acquired = _setup_lock.acquire(timeout=5)
    if not acquired:
        logger.info("Webhook setup already in progress by another thread")
        # Wait for the other thread to finish
        for _ in range(30):
            time.sleep(1)
            if _setup_done:
                return True
        return False
    
    try:
        if _setup_done:
            return True
        
        _setup_in_progress = True
        logger.info("Starting webhook setup...")
        
        if not ensure_app_started():
            logger.error("Failed to start Telegram app")
            return False
        
        _run_coroutine(setup_webhook(), timeout=30)
        _setup_done = True
        logger.info("✅ Webhook setup completed successfully")
        return True
        
    except FutureTimeout:
        logger.error("Webhook setup timed out")
        return False
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}", exc_info=True)
        return False
    finally:
        _setup_in_progress = False
        _setup_lock.release()


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
        ensure_app_started()
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
    global _setup_done
    
    # If already done, just return success
    if _setup_done:
        return jsonify({
            "status": "success",
            "message": "Webhook already configured",
            "webhook_url": _mask_webhook_url(WEBHOOK_FULL_URL)
        })
    
    # If setup is in progress, wait for it
    if _setup_in_progress:
        logger.info("Webhook setup in progress, waiting...")
        for _ in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            if _setup_done:
                return jsonify({
                    "status": "success",
                    "message": "Webhook configured by background thread",
                    "webhook_url": _mask_webhook_url(WEBHOOK_FULL_URL)
                })
        return jsonify({
            "status": "error",
            "error": "Webhook setup still in progress, try again later"
        }), 503
    
    try:
        success = ensure_webhook()
        if success:
            return jsonify({
                "status": "success",
                "webhook_url": _mask_webhook_url(WEBHOOK_FULL_URL)
            })
        else:
            return jsonify({
                "status": "error",
                "error": "Webhook setup failed"
            }), 500
    except FutureTimeout:
        logger.error("Webhook setup timed out")
        return jsonify({
            "status": "error",
            "error": "Timeout while setting webhook"
        }), 504
    except Exception as e:
        logger.error("Failed to set webhook: %s", e, exc_info=True)
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


async def _get_webhook_info():
    await _start_telegram_app()
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
        ensure_app_started()
        info = _run_coroutine(_get_webhook_info(), timeout=10)
        return jsonify({
            "url": _mask_webhook_url(info.url) if info.url else info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message
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

    ensure_webhook()
    
    # הרצת Flask
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False
    )


def _auto_setup_webhook():
    """
    Setup webhook automatically with retry logic
    """
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Auto webhook setup attempt {attempt + 1}/{max_retries}")
            
            # Small delay to let the app fully initialize
            if attempt == 0:
                time.sleep(2)
            
            success = ensure_webhook()
            if success:
                logger.info("✅ Auto webhook setup successful")
                return
            else:
                logger.warning(f"Webhook setup returned False, attempt {attempt + 1}")
                
        except Exception as e:
            logger.error(f"Auto webhook setup attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
    
    logger.error("❌ All auto webhook setup attempts failed")


def _schedule_webhook_setup():
    """
    Schedule webhook setup in a background thread
    """
    thread = threading.Thread(target=_auto_setup_webhook, daemon=True, name="WebhookSetup")
    thread.start()
    logger.info("📡 Webhook setup scheduled in background thread")


if __name__ == "__main__":
    main()
else:
    # Only schedule webhook setup when imported by gunicorn
    _schedule_webhook_setup()
