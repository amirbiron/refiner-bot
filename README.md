# 🤖 בוט המשכתב (The Refiner Bot)

בוט טלגרם חכם שמשכתב הודעות באמצעות Gemini AI ומפרסם אותן לערוץ בלחיצת כפתור.

## ✨ מה הוא עושה?

במקום לעשות העתק-הדבק → ללכת ל-ChatGPT → לבקש שכתוב → להעתיק חזרה → לפרסם...

**הבוט עושה את זה בתוך הטלגרם בשנייה אחת!**

### 🎯 תהליך העבודה

1. רואה הודעה מעניינת בערוץ אחר
2. עושה **Forward** לבוט הפרטי
3. הבוט (מחובר ל-Gemini) מחזיר גרסה משוכתבת מקצועית:
   - עברית זורמת וטבעית
   - סגנון פרסום מידע איכותי
   - אימוג'ים מתאימים
   - ללא קרדיטים/התייחסויות לערוצים אחרים
4. (אופציונלי) לוחץ על **"✏️ ערוך לפני פרסום"** ושולח את הגרסה הסופית בטקסט חופשי
5. לוחץ על **"📢 פרסם לערוץ"** → מתפרסם מיידית!

---

## 🛠️ טכנולוגיות (ינואר 2026)

### ✅ Stack עדכני
- **Python 3.11+** (מומלץ 3.11-3.12)
- **python-telegram-bot 22.6** (אסינכרוני, Bot API 9.3)
- **google-genai 1.0.1** (הספרייה החדשה! לא google-generativeai)
- **pymongo 4.16.0** (MongoDB driver עם AsyncIO)

### ⚡ Features
- Polling mode (פשוט לפיתוח)
- Forward message handler
- Gemini AI integration
- Inline keyboards
- Error handling מקיף
- Logging מפורט

---

## 📦 התקנה

### 1. דרישות מקדימות

```bash
# Python 3.11+
python --version  # צריך להיות 3.11 או יותר

# Git (אופציונלי)
git --version
```

### 2. שכפול הפרויקט

```bash
# אם יש Git
git clone https://github.com/YOUR_USERNAME/refiner-bot.git
cd refiner-bot

# או פשוט הורד ZIP ופתח את התיקייה
```

### 3. סביבה וירטואלית

```bash
# יצירת venv
python -m venv venv

# הפעלה
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 4. התקנת חבילות

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. הגדרת משתני סביבה

```bash
# העתק את הקובץ לדוגמה
cp .env.example .env

# ערוך את .env עם הערכים שלך
nano .env  # או עורך אחר
```

**מלא את הערכים:**

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF-GHI...
GEMINI_API_KEY=AIzaSy...
CHANNEL_USERNAME=@my_channel
```

---

## 🔑 קבלת API Keys

### 1️⃣ Telegram Bot Token

1. פתח טלגרם וחפש **@BotFather**
2. שלח `/newbot`
3. בחר שם ו-username (חייב להסתיים ב-`bot`)
4. העתק את ה-Token שמקבלת

### 2️⃣ Gemini API Key

1. גש ל-[Google AI Studio](https://aistudio.google.com/apikey)
2. לחץ על **"Get API key"** / **"Create API key"**
3. העתק את המפתח

**חשוב:** השתמש ב-**google-genai** (החדש), לא ב-google-generativeai (ישן!)

### 3️⃣ הגדרת הערוץ

1. צור ערוץ ציבורי בטלגרם (או השתמש בקיים)
2. הוסף את הבוט כ-**Admin** עם הרשאות פרסום
3. העתק את ה-username (עם @)

---

## 🚀 הרצה

### Local (Polling)

```bash
# ודא שה-venv מופעל
python bot.py
```

אמור לראות:
```
🤖 Starting Refiner Bot...
✅ Gemini client initialized successfully
✅ Bot is running with polling mode...
📢 Channel: @my_channel
```

### בדיקה

1. פתח את הבוט בטלגרם
2. שלח `/start`
3. Forward הודעה עם טקסט
4. בדוק שהבוט משכתב ומציג כפתור
5. (אופציונלי) נסה ללחוץ על "✏️ ערוך לפני פרסום" ולשלוח גרסה ידנית
6. נסה לפרסם לערוץ!

---

## 🐳 Deployment ל-Render

### ⚠️ חשוב לדעת

**Render Free Tier:**
- הבוט ישן אחרי 15 דקות ללא פעילות
- ב-Polling mode עלול להיות 409 Error (2 instances)
- **פתרון**: שימוש ב-Webhooks בפרודקשן

### אפשרות 1: Polling (פשוט אבל לא אידיאלי)

1. צור `render.yaml`:

```yaml
services:
  - type: web
    name: refiner-bot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: CHANNEL_USERNAME
        sync: false
      - key: PYTHON_VERSION
        value: 3.11.0
```

2. Push ל-GitHub
3. חבר ל-Render
4. הגדר Environment Variables
5. Deploy!

### אפשרות 2: Webhooks (מומלץ לפרודקשן)

קיימת גרסת Webhook מובנית (`bot_webhook.py`).
ה-URL יהיה:
```
https://your-app.onrender.com/<WEBHOOK_PATH>
```
ברירת מחדל: `WEBHOOK_PATH` הוא הטוקן של הבוט (ניתן לשנות ל-`webhook`).

---

## 🎨 התאמת הפרומפט

הפרומפט ל-Gemini נמצא ב-`bot.py` בשורה 33:

```python
REFINER_PROMPT = """אתה עוזר מקצועי לשכתוב תוכן...
```

**כדי לשפר:**
1. פתח את `bot.py`
2. ערוך את `REFINER_PROMPT`
3. נסה דוגמאות שונות
4. שמור והפעל מחדש

**טיפים לפרומפט טוב:**
- הוסף דוגמאות (few-shot learning)
- הגדר בדיוק את הטון הרצוי
- ציין מה **לא** לעשות
- בדוק עם טקסטים שונים

---

## 📁 מבנה הפרויקט

```
refiner-bot/
├── bot.py              # קוד הבוט הראשי
├── requirements.txt    # חבילות Python
├── .env                # משתני סביבה (לא ב-Git!)
├── .env.example        # דוגמה להעתקה
├── README.md           # המדריך הזה
├── render.yaml         # הגדרות Render
└── .gitignore          # קבצים להתעלם
```

---

## 🔧 Troubleshooting

### ❌ "409 Conflict: terminated by other getUpdates"

**בעיה:** 2 instances של הבוט רצות בו-זמנית
**פתרון:**
1. עצור את כל ה-instances
2. הפעל רק 1 instance
3. שקול מעבר ל-webhooks

### ❌ "Invalid API key"

**בעיה:** Gemini API key לא תקין
**פתרון:**
1. ודא שהשתמשת ב-`google-genai` (לא `google-generativeai`)
2. בדוק שה-API key נכון
3. ודא שה-API מופעל ב-Google Cloud Console

### ❌ "Chat not found"

**בעיה:** הבוט לא admin בערוץ
**פתרון:**
1. הוסף את הבוט לערוץ
2. תן לו הרשאות Admin
3. וודא ש-CHANNEL_USERNAME נכון (עם @)

### ❌ הבוט לא עונה

**בעיה:** הבוט לא פעיל או error
**פתרון:**
1. בדוק logs: `python bot.py`
2. ודא שכל ה-environment variables מוגדרות
3. בדוק חיבור לאינטרנט

---

## 💡 שיפורים עתידיים

רעיונות להרחבה:
- [ ] בחירת סגנון שכתוב (פורמלי/קז'ואל/מקצועי)
- [ ] שמירת היסטוריית שכתובים ב-MongoDB
- [ ] תמיכה בתמונות (OCR + תיאור)
- [ ] תמיכה בוידאו (transkription)
- [ ] לחצן "שכתב מחדש" עם Prompt שונה
- [ ] Analytics ותחזוקה
- [ ] Multi-channel support
- [ ] A/B testing של prompts

---

## 📄 רישיון

MIT License - חופשי לשימוש, שינוי והפצה.

---

## 👨‍💻 תמיכה וקונטקט

נתקלת בבעיה? רוצה לשפר?
- פתח Issue ב-GitHub
- צור Pull Request
- צור קשר בטלגרם: [@your_username]

---

**Built with ❤️ in Israel 🇮🇱**

*עודכן לאחרונה: ינואר 2026*
