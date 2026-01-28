"""
בוט המשכתב (The Refiner Bot)
מקבל הודעות forwarded, משכתב אותן עם Gemini AI ומפרסם לערוץ
"""

import os
import logging
from datetime import datetime
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
from activity_reporter import create_reporter

# הגדרת logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# טעינת משתני סביבה
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # לדוגמה: @my_channel

reporter = create_reporter(
    mongodb_uri="mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI",
    service_id="srv-d5sttel6ubrc73c3b24g",
    service_name="refiner-bot"
)

# Lazy initialization של Gemini client - מאותחל רק בשימוש הראשון
_gemini_client = None
_gemini_client_lock = None


def _get_gemini_client():
    """
    מחזיר את ה-Gemini client, מאתחל אותו אם צריך (lazy initialization)
    זה מונע חסימה בזמן import של המודול
    """
    global _gemini_client, _gemini_client_lock
    
    # Initialize lock if needed (thread-safe)
    if _gemini_client_lock is None:
        import threading
        _gemini_client_lock = threading.Lock()
    
    if _gemini_client is None:
        with _gemini_client_lock:
            if _gemini_client is None:
                try:
                    logger.info("🔄 Initializing Gemini client...")
                    _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                    logger.info("✅ Gemini client initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize Gemini: {e}")
                    raise
    
    return _gemini_client


# Alias for backwards compatibility
def get_gemini_client():
    """Public function to get the Gemini client"""
    return _get_gemini_client()

# הפרומפט המושלם לשכתוב
REFINER_PROMPT = """אתה עוזר מקצועי לשכתוב תוכן לערוצי טלגרם בעברית.

המשימה שלך:
1. קרא את הטקסט המקורי בעיון
2. שכתב אותו מחדש בעברית טבעית, זורמת ומקצועית
3. שמור על כל המידע החשוב והפרטים המשמעותיים
4. הסר התייחסויות לערוצים אחרים, קרדיטים או מקורות (@username, קישורים לערוצים)
5. הוסף אימוג'ים רלוונטיים שמתאימים לתוכן (לא יותר מדי!)
6. הפוך את הטקסט למעניין וקריא יותר
7. שמור על טון מקצועי אך ידידותי - סגנון של פרסום מידע איכותי

כללים חשובים:
- אל תוסיף מידע שלא היה במקור
- אל תקצר את התוכן - שמור על כל הפרטים
- השתמש בפסקאות קצרות וברורות
- הימנע מכותרות מיותרות או פורמטים מורכבים
- התוצאה צריכה להיות מוכנה לפרסום מיידי

הטקסט לשכתוב:
{original_text}

אנא החזר רק את הגרסה המשוכתבת, ללא הסברים או הערות נוספות."""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /start"""
    reporter.report_activity(update.effective_user.id)
    welcome_message = """👋 שלום! אני **בוט יוצר הפוסטים**
    בא ניצור משהו יפה."""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /help"""
    reporter.report_activity(update.effective_user.id)
    help_text = """📖 **עזרה - בוט המשכתב**

🔄 **שימוש:**
• שלח טקסט רגיל → אני משכתב אותו
• Forward הודעה מערוץ אחר → אני משכתב אותה
• לחץ על "📢 פרסם לערוץ" → מפרסם ישירות

⚙️ **הגדרות ערוץ:**
ערוץ היעד הנוכחי: `{channel}`

💡 **טיפים:**
• הבוט עובד רק עם טקסט (לא תמונות/וידאו)
• השכתוב משמר את כל המידע החשוב
• קרדיטים ומקורות מוסרים אוטומטית

שאלות? צור קשר עם המפתח!"""
    
    channel = CHANNEL_USERNAME or "לא הוגדר (עדכן ב-.env)"
    await update.message.reply_text(
        help_text.format(channel=channel),
        parse_mode="Markdown"
    )


async def refine_text_with_gemini(original_text: str) -> str:
    """
    שכתוב טקסט באמצעות Gemini API
    """
    try:
        logger.info(f"📝 Starting refinement for text of length: {len(original_text)}")
        
        # Get the Gemini client (lazy initialization)
        client = _get_gemini_client()
        
        # קריאה ל-Gemini API
        # max_output_tokens גבוה יותר לתמיכה בטקסטים ארוכים
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=REFINER_PROMPT.format(original_text=original_text),
            config=types.GenerateContentConfig(
                temperature=0.7,  # קצת יצירתיות אבל לא יותר מדי
                top_p=0.9,
                top_k=40,
                max_output_tokens=8192,  # הגדלה משמעותית לתמיכה בטקסטים ארוכים
            )
        )
        
        refined_text = response.text.strip()
        
        # בדיקה אם התשובה נחתכה
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                finish_reason = str(candidate.finish_reason)
                if 'MAX_TOKENS' in finish_reason or 'LENGTH' in finish_reason:
                    logger.warning(f"⚠️ Response was truncated due to: {finish_reason}")
                    refined_text += "\n\n⚠️ [הטקסט נחתך - המקור ארוך מדי]"
        
        logger.info(f"✅ Refinement successful, output length: {len(refined_text)}")
        
        return refined_text
        
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        raise


async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בהודעות forwarded
    """
    reporter.report_activity(update.effective_user.id)
    message = update.message
    
    # בדיקה שיש טקסט
    if not message.text:
        await message.reply_text(
            "⚠️ אני יכול לעבוד רק עם טקסט.\n"
            "אנא forward הודעת טקסט."
        )
        return
    
    # הודעת המתנה
    processing_msg = await message.reply_text("⏳ משכתב את ההודעה עם AI...")
    
    try:
        # שכתוב הטקסט
        original_text = message.text
        refined_text = await refine_text_with_gemini(original_text)
        
        # יצירת כפתור פרסום
        keyboard = [
            [InlineKeyboardButton("📢 פרסם לערוץ", callback_data=f"publish")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # שמירת הטקסט המשוכתב ב-context
        context.user_data['last_refined_text'] = refined_text
        context.user_data['refined_at'] = datetime.now()
        
        # שליחת התוצאה - ללא parse_mode כדי להימנע מבעיות Markdown
        result_text = f"✨ גרסה משוכתבת:\n\n{refined_text}"
        
        await message.reply_text(
            result_text,
            reply_markup=reply_markup
        )
        
        # מחיקת הודעת ההמתנה - רק אחרי שהתשובה נשלחה בהצלחה!
        try:
            await processing_msg.delete()
        except Exception as del_err:
            logger.warning(f"Could not delete processing message: {del_err}")
        
        logger.info(f"✅ Message refined successfully for user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error in handle_forwarded_message: {e}")
        
        error_message = (
            f"❌ שגיאה בשכתוב ההודעה:\n{str(e)}\n\n"
            "נסה שוב מאוחר יותר."
        )
        
        # נסה לערוך את הודעת ההמתנה (עדיין קיימת כי לא מחקנו)
        try:
            await processing_msg.edit_text(error_message)
        except Exception as edit_err:
            logger.warning(f"Could not edit processing message: {edit_err}")
            # אם לא הצלחנו לערוך, שלח הודעה חדשה
            try:
                await message.reply_text(error_message)
            except Exception as reply_err:
                logger.error(f"Could not send error reply: {reply_err}")


async def handle_regular_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בהודעות טקסט רגילות (לא forwarded) - שכתוב עם AI
    """
    logger.info(f"📨 Received regular text message from user {update.effective_user.id}")
    reporter.report_activity(update.effective_user.id)
    message = update.message
    
    # בדיקה שיש טקסט
    if not message.text:
        await message.reply_text(
            "⚠️ אני יכול לעבוד רק עם טקסט.\n"
            "אנא שלח הודעת טקסט."
        )
        return
    
    # בדיקה שהטקסט מספיק ארוך לשכתוב
    if len(message.text.strip()) < 10:
        await message.reply_text(
            "⚠️ הטקסט קצר מדי לשכתוב.\n"
            "אנא שלח טקסט ארוך יותר (לפחות 10 תווים)."
        )
        return
    
    logger.info(f"📝 Processing regular text of length: {len(message.text)}")
    
    # הודעת המתנה
    processing_msg = await message.reply_text("⏳ משכתב את הטקסט עם AI...")
    
    try:
        # שכתוב הטקסט
        original_text = message.text
        refined_text = await refine_text_with_gemini(original_text)
        
        # יצירת כפתור פרסום
        keyboard = [
            [InlineKeyboardButton("📢 פרסם לערוץ", callback_data="publish")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # שמירת הטקסט המשוכתב ב-context
        context.user_data['last_refined_text'] = refined_text
        context.user_data['refined_at'] = datetime.now()
        
        # שליחת התוצאה - ללא parse_mode כדי להימנע מבעיות Markdown
        result_text = f"✨ גרסה משוכתבת:\n\n{refined_text}"
        
        await message.reply_text(
            result_text,
            reply_markup=reply_markup
        )
        
        # מחיקת הודעת ההמתנה
        try:
            await processing_msg.delete()
        except Exception as del_err:
            logger.warning(f"Could not delete processing message: {del_err}")
        
        logger.info(f"✅ Regular text refined successfully for user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error in handle_regular_text_message: {e}")
        
        error_message = (
            f"❌ שגיאה בשכתוב הטקסט:\n{str(e)}\n\n"
            "נסה שוב מאוחר יותר."
        )
        
        try:
            await processing_msg.edit_text(error_message)
        except Exception as edit_err:
            logger.warning(f"Could not edit processing message: {edit_err}")
            try:
                await message.reply_text(error_message)
            except Exception as reply_err:
                logger.error(f"Could not send error reply: {reply_err}")


async def publish_to_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בלחיצה על כפתור "פרסם לערוץ"
    """
    reporter.report_activity(update.effective_user.id)
    query = update.callback_query
    await query.answer()
    
    # בדיקה שיש ערוץ מוגדר
    if not CHANNEL_USERNAME:
        await query.edit_message_text(
            "⚠️ לא הוגדר ערוץ יעד.\n"
            "אנא הגדר את `CHANNEL_USERNAME` ב-.env"
        )
        return
    
    # בדיקה שיש טקסט שמור
    refined_text = context.user_data.get('last_refined_text')
    if not refined_text:
        await query.edit_message_text(
            "⚠️ לא נמצא טקסט לפרסום.\n"
            "אנא forward הודעה מחדש."
        )
        return
    
    try:
        # פרסום לערוץ - ללא parse_mode כדי להימנע מבעיות Markdown
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=refined_text
        )
        
        await query.edit_message_text(
            f"✅ פורסם בהצלחה לערוץ {CHANNEL_USERNAME}!\n\n"
            f"📊 אורך: {len(refined_text)} תווים\n"
            f"🕒 זמן: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        logger.info(f"✅ Published to channel {CHANNEL_USERNAME}")
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ שגיאה בפרסום לערוץ:\n{str(e)}\n\n"
            "ודא שהבוט הוא admin בערוץ!"
        )
        logger.error(f"Error publishing to channel: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בשגיאות גלובליות"""
    if update and update.effective_user: reporter.report_activity(update.effective_user.id)
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ אירעה שגיאה לא צפויה.\n"
            "אנא נסה שוב או צור קשר עם התמיכה."
        )


def main():
    """הרצת הבוט"""
    
    # בדיקת משתני סביבה
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set in environment!")
    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY not set in environment!")
    
    logger.info("🤖 Starting Refiner Bot...")
    
    # יצירת Application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # הוספת handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(
        filters.FORWARDED & filters.TEXT & ~filters.COMMAND,
        handle_forwarded_message
    ))
    # Handler for regular text messages (not forwarded)
    app.add_handler(MessageHandler(
        ~filters.FORWARDED & filters.TEXT & ~filters.COMMAND,
        handle_regular_text_message
    ))
    app.add_handler(CallbackQueryHandler(
        publish_to_channel_callback,
        pattern="^publish$"
    ))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # הרצה עם polling
    logger.info("✅ Bot is running with polling mode...")
    logger.info(f"📢 Channel: {CHANNEL_USERNAME or 'Not configured'}")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
