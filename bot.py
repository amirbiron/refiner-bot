"""
בוט המשכתב (The Refiner Bot)
מקבל הודעות forwarded, משכתב אותן עם Gemini AI ומפרסם לערוץ
"""

import asyncio
import os
import re
import html
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
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

# Common trailing punctuation that often sticks to pasted URLs in text
_URL_TRAILING_PUNCT = '.,!?:;)]}>\'"'


def extract_last_url_and_clean_text(text: str) -> tuple[str, str | None]:
    """
    Extract only the last URL in the text and remove it from the returned text.
    Keeps any trailing punctuation (e.g. ')' or '.') in the text.
    """
    matches = list(re.finditer(r"https?://\S+", text))
    if not matches:
        return text, None

    m = matches[-1]
    raw = m.group(0)
    url = raw.rstrip(_URL_TRAILING_PUNCT)
    if not url:
        return text, None

    trailing = raw[len(url):]  # punctuation stripped from the URL
    cleaned = text[:m.start()] + trailing + text[m.end():]

    # light cleanup without changing the content structure
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()
    # Avoid returning empty text (Telegram doesn't allow empty messages)
    if not cleaned:
        return text, None
    return cleaned, url


def source_button_label(url: str) -> str:
    u = url.lower()

    # Code repositories
    if any(d in u for d in ("github.com", "gitlab.com", "bitbucket.org")):
        return "💻 לקוד המקור"

    # Video platforms
    if any(d in u for d in ("youtube.com", "youtu.be", "vimeo.com")):
        return "📺 לצפייה בסרטון"

    # AI tools & products
    if any(d in u for d in (
        "huggingface.co", "chat.openai.com", "chatgpt.com",
        "gemini.google.com", "claude.ai", "bard.google.com",
        "midjourney.com", "replicate.com",
    )) or re.search(r"https?://[^/]*\.ai(?:/|$)", u):
        return "🤖 להתנסות בכלי"

    # App stores
    if any(d in u for d in ("play.google.com", "apps.apple.com")):
        return "📱 להורדת האפליקציה"

    # Social media / forums
    if any(d in u for d in (
        "twitter.com", "x.com", "linkedin.com", "reddit.com",
        "facebook.com", "instagram.com", "threads.net",
    )):
        return "📝 לפוסט המקורי"

    # Neutral default
    return "🔗 למעבר לקישור"


def build_source_keyboard(url: str | None) -> InlineKeyboardMarkup | None:
    """Keyboard for a single external source URL (no callbacks)."""
    if not url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(source_button_label(url), url=url)]])


def compose_draft_for_copy(text: str, source_url: str | None) -> str:
    """Draft text for copy/paste, optionally appending the source URL at the end."""
    if not source_url:
        return text
    if not text.strip():
        return source_url
    return f"{text.rstrip()}\n\n{source_url}"


# טעינת משתני סביבה
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # לדוגמה: @my_channel

# OpenAI fallback - משמש רק אם Gemini נכשל
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "8192"))

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


# Lazy initialization של OpenAI client (fallback) - מאותחל רק בשימוש הראשון
_openai_client = None
_openai_client_lock = None


def _get_openai_client():
    """
    מחזיר את ה-OpenAI client, מאתחל אותו אם צריך (lazy initialization).
    מחזיר None אם OPENAI_API_KEY לא מוגדר או שה-SDK לא מותקן.
    """
    global _openai_client, _openai_client_lock

    if not OPENAI_API_KEY:
        return None

    if _openai_client_lock is None:
        import threading
        _openai_client_lock = threading.Lock()

    if _openai_client is None:
        with _openai_client_lock:
            if _openai_client is None:
                try:
                    from openai import OpenAI
                    logger.info("🔄 Initializing OpenAI fallback client...")
                    _openai_client = OpenAI(api_key=OPENAI_API_KEY)
                    logger.info("✅ OpenAI fallback client initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize OpenAI fallback: {e}")
                    return None

    return _openai_client

def markdown_to_html(text: str) -> str:
    """
    המרת Markdown בסיסי ל-HTML לשליחה בטלגרם
    תומך ב: **bold**, *italic*, `code`
    """
    # Escape HTML special characters first (but not our formatting)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # המרת **bold** ל-<b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # המרת *italic* ל-<i>italic</i> (רק כוכבית בודדת)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # המרת `code` ל-<code>code</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    return text


def text_to_pre_html(text: str) -> str:
    """Wrap text as a Telegram HTML <pre> code block (safe escaping)."""
    return f"<pre>{html.escape(text)}</pre>"


def build_publish_keyboard(is_edit_mode: bool = False) -> InlineKeyboardMarkup:
    """
    מקלדת אינליין עבור תצוגת פוסט לפני פרסום.
    - מצב רגיל: מאפשר עריכה לפני פרסום + פרסום
    - מצב עריכה: מאפשר לפרסם בלי עריכה או לבטל את מצב העריכה
    """
    if is_edit_mode:
        keyboard = [
            [InlineKeyboardButton("📢 פרסם בלי עריכה", callback_data="publish")],
            [InlineKeyboardButton("❌ בטל עריכה", callback_data="cancel_manual_edit")],
            [InlineKeyboardButton("📋 שלח טיוטה להעתקה", callback_data="send_draft_copy")],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("✏️ ערוך לפני פרסום", callback_data="edit_before_publish"),
                InlineKeyboardButton("📢 פרסם לערוץ", callback_data="publish"),
            ],
            [InlineKeyboardButton("📋 שלח טיוטה להעתקה", callback_data="send_draft_copy")],
        ]
    return InlineKeyboardMarkup(keyboard)


def build_preview_keyboard(
    *,
    is_edit_mode: bool = False,
    source_url: str | None = None,
) -> InlineKeyboardMarkup:
    """Preview keyboard: optional source link button + existing publish controls."""
    rows = []
    if source_url:
        rows.append([InlineKeyboardButton(source_button_label(source_url), url=source_url)])

    publish_rows = build_publish_keyboard(is_edit_mode=is_edit_mode).inline_keyboard
    rows.extend(publish_rows)
    return InlineKeyboardMarkup(rows)


def get_message_text_or_caption(message) -> str | None:
    """Return text from message or caption (for media)."""
    if message is None:
        return None
    return message.text or message.caption


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
- אל תהיה שיווקי
- אל תהיה מתלהב מידי
- שמור על ניסוח מקצועי
- זכור: הקהל מעוניין במידע עצמו, ובסגנון קריאה הכי נוח שאפשרי

הטקסט לשכתוב:
{original_text}

אנא החזר רק את הגרסה המשוכתבת, ללא הסברים או הערות נוספות."""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /start"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    if chat is None or message is None or user is None:
        logger.debug("Ignoring /start update without user/message (likely channel_post)")
        return
    if chat.type == "channel":
        logger.debug(f"Ignoring /start in channel chat_id={chat.id}")
        return
    
    reporter.report_activity(user.id)
    welcome_message = """👋 שלום! אני **בוט יוצר הפוסטים**
    בא ניצור משהו יפה."""
    
    await message.reply_text(
        welcome_message,
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /help"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    if chat is None or message is None or user is None:
        logger.debug("Ignoring /help update without user/message (likely channel_post)")
        return
    if chat.type == "channel":
        logger.debug(f"Ignoring /help in channel chat_id={chat.id}")
        return
    
    reporter.report_activity(user.id)
    help_text = """📖 **עזרה - בוט המשכתב**

🔄 **שימוש:**
• שלח טקסט רגיל → אני משכתב אותו
• Forward הודעה מערוץ אחר → אני משכתב אותה
• לחץ על "📢 פרסם לערוץ" → מפרסם ישירות

⚙️ **הגדרות ערוץ:**
ערוץ היעד הנוכחי: `{channel}`

💡 **טיפים:**
• הבוט עובד עם טקסט וגם עם כיתוב של תמונה/וידאו
• השכתוב משמר את כל המידע החשוב
• קרדיטים ומקורות מוסרים אוטומטית

שאלות? צור קשר עם המפתח!"""
    
    channel = CHANNEL_USERNAME or "לא הוגדר (עדכן ב-.env)"
    await message.reply_text(
        help_text.format(channel=channel),
        parse_mode="Markdown"
    )


async def refine_text_with_gpt(original_text: str) -> str:
    """
    שכתוב טקסט באמצעות OpenAI GPT - משמש כ-fallback אם Gemini נכשל.
    """
    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI fallback is not configured (OPENAI_API_KEY missing).")

    logger.info(
        f"🔁 Using GPT fallback ({OPENAI_MODEL}) for text of length: {len(original_text)}"
    )

    prompt = REFINER_PROMPT.format(original_text=original_text)

    def _call_openai():
        return client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )

    # ה-SDK של OpenAI סינכרוני - מריצים ב-thread כדי לא לחסום את ה-event loop
    response = await asyncio.to_thread(_call_openai)

    choice = response.choices[0]
    refined_text = (choice.message.content or "").strip()

    if not refined_text:
        raise RuntimeError("OpenAI returned an empty response.")

    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        logger.warning("⚠️ GPT response was truncated due to length limit")
        refined_text += "\n\n⚠️ [הטקסט נחתך - המקור ארוך מדי]"

    logger.info(f"✅ GPT fallback refinement successful, output length: {len(refined_text)}")
    return refined_text


async def refine_text_with_gemini(original_text: str) -> str:
    """
    שכתוב טקסט באמצעות Gemini API.
    אם Gemini נכשל (למשל תקלה בצד גוגל), ננסה אוטומטית fallback ל-GPT
    - רק אם OPENAI_API_KEY מוגדר. אחרת נעיף את השגיאה המקורית.
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

        refined_text = (response.text or "").strip()

        if not refined_text:
            # Gemini מחזיר לפעמים תשובה ריקה כשיש בעיה בצד שלו - נחשיב כשגיאה
            raise RuntimeError("Gemini returned an empty response.")

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

    except Exception as gemini_error:
        logger.error(f"❌ Gemini API error: {gemini_error}")

        if not OPENAI_API_KEY:
            raise

        try:
            return await refine_text_with_gpt(original_text)
        except Exception as gpt_error:
            logger.error(f"❌ GPT fallback also failed: {gpt_error}")
            # מחזירים את שגיאת Gemini המקורית כדי לא להסתיר את הסיבה האמיתית
            raise gemini_error


async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בהודעות forwarded
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    # Channel posts don't have an effective user and shouldn't be processed
    if chat is None or message is None or user is None:
        logger.debug("Ignoring forwarded update without user/message (likely channel_post)")
        return
    if chat.type == "channel":
        logger.debug(f"Ignoring forwarded message from channel chat_id={chat.id}")
        return

    # אם המשתמש היה במצב עריכה ושלח forward חדש - נבטל מצב עריכה ונמשיך כרגיל
    if context.user_data.get("awaiting_manual_edit"):
        context.user_data["awaiting_manual_edit"] = False
        context.user_data.pop("last_refined_text_before_edit", None)
        context.user_data.pop("last_source_url_before_edit", None)
    
    reporter.report_activity(user.id)
    
    original_text = get_message_text_or_caption(message)
    # בדיקה שיש טקסט
    if not original_text:
        await message.reply_text(
            "⚠️ אני יכול לעבוד רק עם טקסט.\n"
            "אנא forward הודעת טקסט או הודעת תמונה עם כיתוב."
        )
        return
    
    # הודעת המתנה
    processing_msg = await message.reply_text("⏳ משכתב את ההודעה עם AI...")
    
    try:
        # שכתוב הטקסט
        refined_text = await refine_text_with_gemini(original_text)
        refined_text, source_url = extract_last_url_and_clean_text(refined_text)
        reply_markup = build_preview_keyboard(is_edit_mode=False, source_url=source_url)
        
        # שמירת הטקסט המשוכתב ב-context
        context.user_data['last_refined_text'] = refined_text
        context.user_data['last_source_url'] = source_url
        context.user_data['refined_at'] = datetime.now()
        
        # שליחת התוצאה עם HTML formatting (המרה מ-Markdown)
        # נסה לשלוח עם HTML, אם נכשל - שלח בלי פורמט
        try:
            html_text = f"✨ גרסה משוכתבת:\n\n{markdown_to_html(refined_text)}"
            await message.reply_text(
                html_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as html_err:
            logger.debug(f"HTML parsing failed, sending plain text: {html_err}")
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
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    # Channel posts don't have an effective user and shouldn't be processed
    if chat is None or message is None or user is None:
        logger.debug("Ignoring regular text update without user/message (likely channel_post)")
        return
    if chat.type == "channel":
        logger.debug(f"Ignoring regular text message from channel chat_id={chat.id}")
        return
    
    logger.info(f"📨 Received regular text message from user {user.id}")
    reporter.report_activity(user.id)

    # אם אנחנו במצב "עריכה לפני פרסום" - ההודעה הזו נחשבת כטקסט הסופי לפרסום
    if context.user_data.get("awaiting_manual_edit"):
        edited_text = (get_message_text_or_caption(message) or "").strip()
        if not edited_text:
            await message.reply_text("⚠️ לא התקבל טקסט לעריכה. נסה לשלוח שוב.")
            return
        edited_text, source_url = extract_last_url_and_clean_text(edited_text)
        context.user_data["last_refined_text"] = edited_text
        context.user_data["last_source_url"] = source_url
        context.user_data["edited_at"] = datetime.now()
        context.user_data["awaiting_manual_edit"] = False
        context.user_data.pop("last_refined_text_before_edit", None)
        context.user_data.pop("last_source_url_before_edit", None)

        reply_markup = build_preview_keyboard(is_edit_mode=False, source_url=source_url)
        try:
            html_text = f"✅ עודכן הטקסט לפרסום:\n\n{markdown_to_html(edited_text)}"
            await message.reply_text(html_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception as html_err:
            logger.debug(f"HTML parsing failed for edited text, sending plain: {html_err}")
            await message.reply_text(
                f"✅ עודכן הטקסט לפרסום:\n\n{edited_text}",
                reply_markup=reply_markup
            )
        return
    
    original_text = get_message_text_or_caption(message)
    # בדיקה שיש טקסט
    if not original_text:
        await message.reply_text(
            "⚠️ אני יכול לעבוד רק עם טקסט.\n"
            "אנא שלח הודעת טקסט או הודעת תמונה עם כיתוב."
        )
        return
    
    # בדיקה שהטקסט מספיק ארוך לשכתוב
    if len(original_text.strip()) < 10:
        await message.reply_text(
            "⚠️ הטקסט קצר מדי לשכתוב.\n"
            "אנא שלח טקסט ארוך יותר (לפחות 10 תווים)."
        )
        return
    
    logger.info(f"📝 Processing regular text of length: {len(original_text)}")
    
    # הודעת המתנה
    processing_msg = await message.reply_text("⏳ משכתב את הטקסט עם AI...")
    
    try:
        # שכתוב הטקסט
        refined_text = await refine_text_with_gemini(original_text)
        refined_text, source_url = extract_last_url_and_clean_text(refined_text)
        reply_markup = build_preview_keyboard(is_edit_mode=False, source_url=source_url)
        
        # שמירת הטקסט המשוכתב ב-context
        context.user_data['last_refined_text'] = refined_text
        context.user_data['last_source_url'] = source_url
        context.user_data['refined_at'] = datetime.now()
        
        # שליחת התוצאה עם HTML formatting (המרה מ-Markdown)
        # נסה לשלוח עם HTML, אם נכשל - שלח בלי פורמט
        try:
            html_text = f"✨ גרסה משוכתבת:\n\n{markdown_to_html(refined_text)}"
            await message.reply_text(
                html_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as html_err:
            logger.debug(f"HTML parsing failed, sending plain text: {html_err}")
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


async def _safe_answer_callback(query) -> None:
    """Answer a callback query, ignoring 'query too old' errors."""
    try:
        await query.answer()
    except BadRequest as e:
        if "query is too old" in str(e).lower() or "query id is invalid" in str(e).lower():
            logger.debug(f"Callback query expired, continuing: {e}")
        else:
            raise


async def publish_to_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    טיפול בלחיצה על כפתור "פרסם לערוץ"
    """
    query = update.callback_query
    await _safe_answer_callback(query)
    asyncio.get_event_loop().run_in_executor(None, reporter.report_activity, update.effective_user.id)

    # בכל פרסום נוודא שאנחנו לא נשארים "תקועים" במצב עריכה
    if context.user_data.get("awaiting_manual_edit"):
        context.user_data["awaiting_manual_edit"] = False
        context.user_data.pop("last_refined_text_before_edit", None)
        context.user_data.pop("last_source_url_before_edit", None)
    
    # בדיקה שיש ערוץ מוגדר
    if not CHANNEL_USERNAME:
        await query.edit_message_text(
            "⚠️ לא הוגדר ערוץ יעד.\n"
            "אנא הגדר את `CHANNEL_USERNAME` ב-.env"
        )
        return
    
    # בדיקה שיש טקסט שמור
    refined_text = context.user_data.get('last_refined_text')
    source_url = context.user_data.get('last_source_url')
    if not refined_text:
        await query.edit_message_text(
            "⚠️ לא נמצא טקסט לפרסום.\n"
            "אנא forward הודעה מחדש."
        )
        return
    
    try:
        # פרסום לערוץ עם HTML formatting
        # נסה לשלוח עם HTML, אם נכשל - שלח בלי פורמט
        try:
            html_text = markdown_to_html(refined_text)
            await context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=html_text,
                reply_markup=build_source_keyboard(source_url),
                parse_mode="HTML"
            )
        except Exception as html_err:
            logger.debug(f"HTML parsing failed for channel, sending plain: {html_err}")
            await context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=refined_text,
                reply_markup=build_source_keyboard(source_url),
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


async def edit_before_publish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    כניסה למצב "עריכה לפני פרסום" - המשתמש ישלח הודעת טקסט חדשה שתשמש כגרסה הסופית לפרסום.
    """
    query = update.callback_query
    await _safe_answer_callback(query)
    asyncio.get_event_loop().run_in_executor(None, reporter.report_activity, update.effective_user.id)

    refined_text = context.user_data.get("last_refined_text")
    if not refined_text:
        await query.edit_message_text(
            "⚠️ לא נמצא טקסט לעריכה.\n"
            "אנא שלח/forward הודעה כדי ליצור גרסה משוכתבת."
        )
        return

    context.user_data["last_refined_text_before_edit"] = refined_text
    context.user_data["last_source_url_before_edit"] = context.user_data.get("last_source_url")
    context.user_data["awaiting_manual_edit"] = True
    context.user_data["manual_edit_started_at"] = datetime.now()

    # עדכון המקלדת על גבי הודעת התצוגה כדי להציע ביטול/פרסום בלי עריכה
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_preview_keyboard(
                is_edit_mode=True,
                source_url=context.user_data.get("last_source_url"),
            )
        )
    except Exception as e:
        logger.debug(f"Could not edit reply markup for edit mode: {e}")

    # הודעה נפרדת שמסבירה מה לעשות (לא מוחקת את התצוגה הקודמת)
    await query.message.reply_text(
        "✏️ מצב עריכה הופעל.\n\n"
        "שלחתי לך עכשיו את הטיוטה להעתקה.\n"
        "העתק/י, ערוך/י בהודעה חדשה, ושלח/י לבוט את **הגרסה הסופית** לפרסום.\n"
        "כדי לבטל את מצב העריכה, לחץ על \"❌ בטל עריכה\".",
        parse_mode="Markdown"
    )

    # שליחת הטיוטה עצמה להעתקה בתוך בלוק קוד
    # כך copy-paste שומר על הסימונים כמו **bold** ולא “נבלע” ע״י טלגרם
    await query.message.reply_text(
        text_to_pre_html(
            compose_draft_for_copy(refined_text, context.user_data.get("last_source_url"))
        ),
        parse_mode="HTML",
    )


async def send_draft_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שליחת הטיוטה הנוכחית להעתקה (כדי להקל על עריכה ידנית)."""
    query = update.callback_query
    await _safe_answer_callback(query)
    asyncio.get_event_loop().run_in_executor(None, reporter.report_activity, update.effective_user.id)

    refined_text = context.user_data.get("last_refined_text")
    if not refined_text:
        await query.message.reply_text(
            "⚠️ לא נמצאה טיוטה לשליחה. אנא שלח/forward הודעה כדי ליצור גרסה משוכתבת."
        )
        return
    await query.message.reply_text(
        text_to_pre_html(
            compose_draft_for_copy(refined_text, context.user_data.get("last_source_url"))
        ),
        parse_mode="HTML",
    )


async def cancel_manual_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ביטול מצב עריכה והחזרה לגרסה לפני העריכה (אם קיימת)."""
    query = update.callback_query
    await _safe_answer_callback(query)
    asyncio.get_event_loop().run_in_executor(None, reporter.report_activity, update.effective_user.id)

    context.user_data["awaiting_manual_edit"] = False
    before = context.user_data.pop("last_refined_text_before_edit", None)
    before_url = context.user_data.pop("last_source_url_before_edit", None)
    if before:
        context.user_data["last_refined_text"] = before
        context.user_data["last_source_url"] = before_url

    # חזרה למקלדת הרגילה על הודעת התצוגה
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_preview_keyboard(
                is_edit_mode=False,
                source_url=context.user_data.get("last_source_url"),
            )
        )
    except Exception as e:
        logger.debug(f"Could not restore reply markup after cancel: {e}")

    # הודעת אישור קצרה
    await query.message.reply_text("✅ מצב עריכה בוטל. אפשר לפרסם כרגיל.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בשגיאות גלובליות"""
    chat = update.effective_chat if update else None
    user = update.effective_user if update else None
    
    # Channel posts often don't have an effective_user and shouldn't get bot replies
    if user:
        reporter.report_activity(user.id)
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        if chat and chat.type == "channel":
            # Avoid spamming channels with generic "unexpected error" replies
            return
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
    message_text_filter = (filters.TEXT | filters.CAPTION) & ~filters.COMMAND
    app.add_handler(MessageHandler(
        filters.FORWARDED & message_text_filter,
        handle_forwarded_message
    ))
    # Handler for regular text messages (not forwarded)
    app.add_handler(MessageHandler(
        ~filters.FORWARDED & message_text_filter,
        handle_regular_text_message
    ))
    app.add_handler(CallbackQueryHandler(
        edit_before_publish_callback,
        pattern="^edit_before_publish$"
    ))
    app.add_handler(CallbackQueryHandler(
        send_draft_copy_callback,
        pattern="^send_draft_copy$"
    ))
    app.add_handler(CallbackQueryHandler(
        cancel_manual_edit_callback,
        pattern="^cancel_manual_edit$"
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
