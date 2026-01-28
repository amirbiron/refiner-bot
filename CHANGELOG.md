# 📝 Changelog

כל השינויים החשובים בפרויקט מתועדים כאן.

הפורמט מבוסס על [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] - 2026-01-28

### 🎉 Initial Release

#### ✨ Added
- **בוט טלגרם מלא** עם תמיכה ב-forwarded messages
- **אינטגרציה עם Gemini AI** (google-genai החדש!)
- **שכתוב חכם** של טקסט לעברית זורמת ומקצועית
- **פרסום לערוץ** בלחיצת כפתור
- **שני מצבי הרצה:**
  - Polling (לפיתוח)
  - Webhooks (לפרודקשן)
- **Inline keyboards** עם אפשרות פרסום
- **Error handling** מקיף
- **Logging** מפורט לניפוי באגים

#### 🛠️ Technical Stack
- Python 3.11+
- python-telegram-bot 22.6
- google-genai 1.0.1 (ספרייה חדשה!)
- pymongo 4.16.0 (אופציונלי)
- Flask 3.1.0 (למצב webhook)

#### 📚 Documentation
- README.md מפורט בעברית
- QUICKSTART.md להתחלה מהירה
- DEPLOYMENT.md לפריסה ב-Render
- TEST_PROMPTS.md לבדיקת הבוט
- דוגמאות קוד ותבניות

#### 🔧 Configuration
- ניהול משתנים עם .env
- config.py מרכזי
- תמיכה ב-MongoDB Atlas (אופציונלי)
- Render deployment מוכן

#### 🎯 Features
- Forward message → Auto-refine → Publish
- הסרת קרדיטים ואזכורים אוטומטית
- אימוג'ים חכמים
- טון מקצועי ומאוזן
- שמירה על כל המידע החשוב

---

## [Unreleased]

### 🔮 Planned Features

#### בשיקולים לגרסאות עתידיות:

- [ ] **בחירת סגנון שכתוב** (פורמלי/קז'ואל/טכני)
- [ ] **היסטוריית שכתובים** ב-MongoDB
- [ ] **תמיכה בתמונות** (OCR + תיאור)
- [ ] **תמיכה בוידאו** (transcription)
- [ ] **כפתור "שכתב מחדש"** עם פרומפט שונה
- [ ] **Analytics ודאשבורד**
- [ ] **Multi-channel support**
- [ ] **A/B testing** של prompts
- [ ] **Rate limiting** חכם
- [ ] **Caching** של שכתובים נפוצים
- [ ] **Admin panel** ניהול
- [ ] **Webhook logs** וסטטיסטיקות

---

## Version Guidelines

### סוגי שינויים:

- **Added** - פיצ'רים חדשים
- **Changed** - שינויים בפיצ'רים קיימים
- **Deprecated** - פיצ'רים שיוסרו בעתיד
- **Removed** - פיצ'רים שהוסרו
- **Fixed** - תיקוני באגים
- **Security** - תיקוני אבטחה

### גרסאות:

```
[MAJOR.MINOR.PATCH]

MAJOR: שינויים breaking
MINOR: פיצ'רים חדשים (backwards compatible)
PATCH: תיקוני באגים
```

---

## כיצד לתרום

1. Fork את הפרויקט
2. צור branch: `git checkout -b feature/AmazingFeature`
3. Commit: `git commit -m 'Add some AmazingFeature'`
4. Push: `git push origin feature/AmazingFeature`
5. פתח Pull Request

---

**Last Updated:** 28 ינואר 2026
