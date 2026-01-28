# Render Procfile
# בחר את השורה המתאימה:

# אופציה 1: Polling mode (פשוט, אבל עלול להיות 409 errors)
# web: python bot.py

# אופציה 2: Webhook mode (מומלץ לפרודקשן!)
# --timeout 120: מספיק זמן לאתחול webhook
# --workers 1: עובד אחד מספיק לבוט (מונע race conditions)
# --preload: טוען את האפליקציה לפני fork של workers
web: gunicorn bot_webhook:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --preload
