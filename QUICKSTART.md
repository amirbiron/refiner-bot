# ⚡ Quick Start - התחלה מהירה

מדריך מהיר להפעלת הבוט תוך 5 דקות!

## 📋 צ'קליסט לפני שמתחילים

- [ ] Python 3.11+ מותקן
- [ ] יש לך Telegram Bot Token (מ-@BotFather)
- [ ] יש לך Gemini API Key (מ-Google AI Studio)
- [ ] יש לך ערוץ טלגרם (והבוט הוא admin)

---

## 🚀 4 צעדים פשוטים

### 1️⃣ התקנה (דקה אחת)

```bash
# הורד את הפרויקט
cd refiner_bot

# צור סביבה וירטואלית
python -m venv venv

# הפעל את הסביבה
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# התקן חבילות
pip install -r requirements.txt
```

### 2️⃣ הגדרת משתנים (2 דקות)

```bash
# העתק את הקובץ לדוגמה
cp .env.example .env
```

**ערוך את `.env`** והכנס:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
GEMINI_API_KEY=AIzaSyA1B2C3D4E5F6G7H8I9J0
CHANNEL_USERNAME=@my_channel
```

### 3️⃣ הרצה (שנייה אחת)

```bash
python bot.py
```

אמור לראות:
```
🤖 Starting Refiner Bot...
✅ Gemini client initialized successfully
✅ Bot is running with polling mode...
```

### 4️⃣ בדיקה (דקה אחת)

1. פתח את הבוט בטלגרם
2. שלח `/start`
3. Forward הודעה מערוץ אחר
4. קבל את הגרסה המשוכתבת!
5. לחץ "📢 פרסם לערוץ"

✅ **זהו! הבוט עובד!**

---

## 🔑 איך להשיג API Keys?

### Telegram Bot Token

1. פתח [@BotFather](https://t.me/botfather)
2. שלח `/newbot`
3. תן שם לבוט: `My Refiner Bot`
4. תן username: `my_refiner_bot` (חייב להסתיים ב-`bot`)
5. **העתק את ה-Token** ← זה מה שצריך!

### Gemini API Key

1. גש ל-[Google AI Studio](https://aistudio.google.com/apikey)
2. לחץ **"Get API key"**
3. **העתק את המפתח** ← זה מה שצריך!

חינם: 60 requests לדקה, 1500 ליום

### הגדרת הערוץ

1. צור ערוץ חדש (או השתמש בקיים)
2. הוסף את הבוט כ-**Admin** בערוץ:
   - ⚙️ Manage Channel
   - 👥 Administrators
   - ➕ Add Administrator
   - חפש את הבוט
   - ✅ **Post Messages** - חשוב!
3. העתק את ה-username של הערוץ (עם @)

---

## ⚠️ בעיות נפוצות

### "TELEGRAM_BOT_TOKEN not set"
→ לא יצרת `.env` או לא מילאת אותו כראוי

### "Invalid API key"
→ הגמיני API key לא נכון, או לא הפעלת את ה-API

### "Chat not found"
→ הבוט לא admin בערוץ, או ה-username לא נכון

### הבוט לא עונה
→ בדוק שהוא רץ (`python bot.py`) וראה את ה-logs

---

## 💡 טיפים

- **פיתוח**: השתמש בבוט אחד
- **פרודקשן**: צור בוט נפרד לפרודקשן
- **בדיקות**: תמיד בדוק לפני לפרסם לערוץ הראשי!

---

## 📚 למידע נוסף

- [README.md](./README.md) - מדריך מלא
- [bot.py](./bot.py) - הקוד עם הערות
- [config.py](./config.py) - הגדרות מתקדמות

---

**זקוק לעזרה?** פתח Issue ב-GitHub!

Happy Refining! 🚀✨
