# 🚀 מדריך Deployment ל-Render

מדריך שלב-אחר-שלב לפריסת הבוט ב-Render.com

---

## 📋 לפני שמתחילים

- [ ] חשבון GitHub (ושהקוד push שם)
- [ ] חשבון Render.com (חינם)
- [ ] Telegram Bot Token
- [ ] Gemini API Key
- [ ] ערוץ טלגרם מוכן

---

## 🎯 שתי אפשרויות Deployment

### אפשרות 1: Polling Mode (פשוט)
✅ קל להקים  
⚠️ Free tier ישן אחרי 15 דקות  
⚠️ עלול להיות 409 Conflict errors

### אפשרות 2: Webhook Mode (מומלץ!)
✅ יותר אמין  
✅ ללא 409 errors  
✅ חסכוני יותר במשאבים  
⚠️ דורש הגדרה נוספת

---

## 🔧 Deployment עם Webhook (מומלץ)

### שלב 1: הכנת הקוד

```bash
# ודא שהקבצים הבאים קיימים:
- bot_webhook.py
- requirements.txt
- Procfile
- runtime.txt
- .env (לא לעלות ל-Git!)
```

### שלב 2: Push ל-GitHub

```bash
git init
git add .
git commit -m "Initial commit - Refiner Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/refiner-bot.git
git push -u origin main
```

### שלב 3: יצירת Web Service ב-Render

1. לך ל-[Render Dashboard](https://dashboard.render.com)
2. לחץ **"New +"** → **"Web Service"**
3. חבר את חשבון GitHub שלך
4. בחר את ה-repository: `refiner-bot`

### שלב 4: הגדרות השרת

**Build & Deploy:**
```
Name: refiner-bot
Region: Oregon (או הקרוב אליך)
Branch: main
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn bot_webhook:app --bind 0.0.0.0:$PORT
```

**Instance Type:**
```
Free (מספיק להתחלה)
```

### שלב 5: Environment Variables

לחץ **"Advanced"** → **"Add Environment Variable"**

הוסף:
```
TELEGRAM_BOT_TOKEN = <הטוקן שלך>
GEMINI_API_KEY = <המפתח שלך>
CHANNEL_USERNAME = @your_channel
WEBHOOK_URL = https://refiner-bot.onrender.com
PORT = 10000
```

⚠️ **חשוב:** `WEBHOOK_URL` צריך להיות ה-URL של השרת ב-Render!

### שלב 6: Deploy!

1. לחץ **"Create Web Service"**
2. המתן כ-3-5 דקות
3. אמור לראות: ✅ "Live"

### שלב 7: הגדרת Webhook

אפשרות א' - אוטומטי:
```bash
# הבוט יגדיר webhook אוטומטית בהרצה ראשונה
# רק ודא ש-WEBHOOK_URL נכון
```

אפשרות ב' - ידני:
```bash
# גש ל:
https://refiner-bot.onrender.com/set_webhook

# אמור לראות:
{
  "status": "success",
  "webhook_url": "https://refiner-bot.onrender.com/..."
}
```

### שלב 8: בדיקה

```bash
# בדוק health:
https://refiner-bot.onrender.com/health
# תקבל: {"status": "healthy"}

# בדוק webhook info:
https://refiner-bot.onrender.com/webhook_info
```

✅ **זהו! הבוט פעיל!**

---

## 🔄 Deployment עם Polling (פשוט יותר)

### שינויים נדרשים:

1. ערוך `Procfile`:
```
web: python bot.py
```

2. **הסר** משתנה:
```
WEBHOOK_URL (לא צריך!)
```

3. Deploy כרגיל

⚠️ **שים לב:**
- Render Free יכול לנמנם אחרי 15 דקות
- עלול להיות 409 errors ב-deployments
- פחות אמין מ-Webhook

---

## 🛠️ Troubleshooting

### ❌ Build נכשל

**שגיאה:** `Could not find a version that satisfies...`

**פתרון:**
```bash
# בדוק requirements.txt
# ודא שכל הגרסאות תואמות Python 3.11
```

### ❌ "409 Conflict"

**שגיאה:** `terminated by other getUpdates request`

**פתרון:**
1. עצור את כל ה-instances הישנות
2. מחק webhook ישן:
```bash
curl https://api.telegram.org/bot<TOKEN>/deleteWebhook
```
3. Deploy מחדש

### ❌ Webhook לא עובד

**שגיאה:** הבוט לא מגיב להודעות

**בדיקה:**
```bash
# בדוק webhook info:
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# אמור להראות את ה-URL שלך
```

**פתרון:**
1. ודא ש-`WEBHOOK_URL` נכון ב-Environment Variables
2. הרץ `/set_webhook` שוב
3. בדוק logs ב-Render

### ❌ הבוט נרדם

**בעיה:** Free tier ישן אחרי 15 דקות

**פתרון:**
- שדרג ל-Paid plan ($7/חודש)
- או השתמש ב-[Cron-Job.org](https://cron-job.org) לשמור אותו ער:
  ```
  URL: https://refiner-bot.onrender.com/health
  Interval: כל 10 דקות
  ```

### ❌ "Chat not found"

**בעיה:** לא מצליח לפרסם לערוץ

**פתרון:**
1. ודא שהבוט הוא **Admin** בערוץ
2. בדוק ש-`CHANNEL_USERNAME` נכון (עם @)
3. נסה לשלוח הודעה ידנית מהבוט לערוץ

---

## 📊 ניטור ו-Logs

### צפייה ב-Logs

```bash
# ב-Render Dashboard:
Services → refiner-bot → Logs (בצד ימין)
```

### מה לחפש:
```
✅ "Webhook set to: ..."
✅ "Message refined successfully"
✅ "Published to channel"

❌ "Failed to..."
❌ "Error:"
```

### Health Checks

```bash
# בדוק שהשרת רץ:
curl https://refiner-bot.onrender.com/

# בדוק health:
curl https://refiner-bot.onrender.com/health

# מידע על webhook:
curl https://refiner-bot.onrender.com/webhook_info
```

---

## 🔐 אבטחה

### Environment Variables
- **לעולם** אל תעלה `.env` ל-Git!
- השתמש רק ב-Render Environment Variables
- סובב מפתחות אם הם דלפו

### Secrets Management
```bash
# טוב:
export TELEGRAM_BOT_TOKEN=...

# רע:
TELEGRAM_BOT_TOKEN = "123:ABC..."  # בקוד!
```

---

## 📈 שדרוגים והרחבות

### שדרוג ל-Paid Plan

**יתרונות:**
- ללא sleep mode
- יותר זיכרון וCPU
- תמיכה טובה יותר

**מחיר:**
- $7/חודש (Starter)
- $25/חודש (Standard)

### Scaling

```bash
# ב-Render:
Settings → Instance Count

# הגדר 1-2 instances
# (יותר = יותר יקר!)
```

### CI/CD אוטומטי

```bash
# ב-Render Settings:
✅ Auto-Deploy: Yes
Branch: main

# כל push ל-main = deployment אוטומטי!
```

---

## 🎓 Best Practices

1. **נסה Local תמיד לפני Deploy**
   ```bash
   python bot.py  # בדוק שעובד!
   ```

2. **השתמש ב-Staging Environment**
   - בוט נפרד לבדיקות
   - ערוץ נפרד לבדיקות

3. **Logs הם החברים שלך**
   - תמיד בדוק logs אחרי deploy
   - הוסף logging לפיצ'רים חדשים

4. **Monitor Uptime**
   - השתמש ב-UptimeRobot או Pingdom
   - קבל התראות אם הבוט נופל

5. **Backup Configuration**
   - שמור את ה-Environment Variables
   - יצא backup מהדטהבייס

---

## 📚 משאבים נוספים

- [Render Docs](https://render.com/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [Flask Docs](https://flask.palletsprojects.com/)

---

**צריך עזרה?** פתח Issue ב-GitHub או צור קשר!

Happy Deploying! 🚀
