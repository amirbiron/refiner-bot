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

# אתחול Gemini client
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Gemini: {e}")
    raise

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
    welcome_message = """👋 שלום! אני **בוט המשכתב**

🎯 **איך אני עובד?**
1. עשה Forward להודעה שאתה רוצה לשכתב (מערוץ אחר או מכל מקום)
2. אני אשכתב אותה בעברית זורמת ומקצועית עם Gemini AI
3. תקבל את הגרסה המשוכתבת עם כפתור "📢 פרסם לערוץ"

⚡ **פשוט, מהיר, מקצועי!**

צריך עזרה? שלח /help"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /help"""
    help_text = """📖 **עזרה - בוט המשכתב**

🔄 **שימוש:**
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
        
        # קריאה ל-Gemini API
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=REFINER_PROMPT.format(original_text=original_text),
            config=types.GenerateContentConfig(
                temperature=0.7,  # קצת יצירתיות אבל לא יותר מדי
                top_p=0.9,
                top_k=40,
                max_output_tokens=2048,
            )
        )
        
        refined_text = response.text.strip()
        logger.info(f"✅ Refinement successful, output length: {len(refined_text)}")
        
        return refined_text
        
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        raise


async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בהודעות forwarded
    """
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
        
        # מחיקת הודעת ההמתנה
        await processing_msg.delete()
        
        # שליחת התוצאה
        await message.reply_text(
            f"✨ **גרסה משוכתבת:**\n\n{refined_text}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Message refined successfully for user {message.from_user.id}")
        
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ שגיאה בשכתוב ההודעה:\n{str(e)}\n\n"
            "נסה שוב מאוחר יותר."
        )
        logger.error(f"Error in handle_forwarded_message: {e}")


async def publish_to_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בלחיצה על כפתור "פרסם לערוץ"
    """
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
        # פרסום לערוץ
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=refined_text,
            parse_mode="Markdown"
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
