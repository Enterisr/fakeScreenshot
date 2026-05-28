import logging
import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# הגדרת לוגים כדי שתוכלי לראות שגיאות אם יהיו בריצה
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# הטוקן שלך
TOKEN = "8827651845:AAFOMHLQbGzxqPGK8sT6_nEJFTUU3KU2mqU"
BACKEND_URL = "http://localhost:8000/validate-screenshot/"

# פונקציה שתופעל כשהמשתמש כותב /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי שירה! הבוט מחובר ועובד כראוי. מוכנה לשלב הבא?")

# פונקציה שתופעל על כל הודעת טקסט רגילה ותחזיר אותה למשתמש
async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text(f"קיבלתי את ההודעה שלך: {user_text}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{photo.file_id}.jpg"
    await photo_file.download_to_drive(file_path)

    print(f"[✓] Photo saved: {file_path}")
    await update.message.reply_text("קיבלתי את התמונה! מעבד...")

    try:
        with open(file_path, "rb") as f:
            response = requests.post(BACKEND_URL, files={"file": f})
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("⚠️ שגיאה: לא ניתן להתחבר לשרת. נסי שוב מאוחר יותר.")
        return
    except Exception as e:
        await update.message.reply_text(f"⚠️ אירעה שגיאה בעיבוד: {e}")
        return

    is_real = result["is_real"]
    confidence = int(result["confidence"] * 100)

    if is_real:
        reply = f"✅ הידיעה נמצאה מהימנה!\nרמת ביטחון: {confidence}%"
    else:
        reply = f"❌ אזהרה: כנראה מדובר בפייק ניוז!\nרמת ביטחון: {confidence}%"

    await update.message.reply_text(reply)

def main():
    print("מריץ את הבוט... לחצי על Ctrl+C בשביל לעצור.")
    
    # יצירת האפליקציה וחיבור הטוקן
    application = Application.builder().token(TOKEN).build()

    # רישום הפקודות בבוט
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

    # הפעלת הבוט (הקשבה מתמדת להודעות)
    application.run_polling(drop_pending_updates=True)
    
if __name__ == '__main__':
    main()