import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# التوكين الخاص بك من BotFather
TOKEN = "8806683255:AAHDhW4l_zzSYOEYl_lREzIBrQ7k_JYmtoQ"

# رابط جدول بيانات جوجل الخاص بك
GOOGLE_SHEET_URL = "https://opensheet.elk.sh/1eSH2Kxj6K6DTcg0CrOqe30H4Fque4ozO67TZ8V6P_YQ/1"

active_sessions = {}

logging.basicConfig(level=logging.INFO)

def get_drivers():
    try:
        response = requests.get(GOOGLE_SHEET_URL)
        if response.status_code == 200:
            data = response.json()
            drivers = {}
            for row in data:
                taxi_name = str(row.get("اسم التاكسي", "")).strip()
                driver_id = str(row.get("ID السائق", "")).strip()
                if taxi_name and driver_id.isdigit():
                    drivers[taxi_name.lower()] = int(driver_id)
            return drivers
    except Exception as e:
        logging.error(f"Error fetching sheet: {e}")
    return {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 أهلاً بك في خدمة التاكسي!\n\n"
        "يرجى إرسال **موقعك المباشر** وكتابة **اسم التاكسي** المطلوب (مثال: تكسي 1) لبدء الاتفاق."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""
    
    if user_id in active_sessions:
        target_id = active_sessions[user_id]
        if update.message.location:
            await context.bot.send_location(chat_id=target_id, location=update.message.location)
        elif text:
            await context.bot.send_message(chat_id=target_id, text=f"💬 رسالة: {text}")
        return

    drivers = get_drivers()

    for taxi_name, driver_id in drivers.items():
        if taxi_name in text.lower():
            active_sessions[user_id] = driver_id
            active_sessions[driver_id] = user_id
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إنهاء الرحلة", callback_data="end_ride")]
            ])
            
            await context.bot.send_message(
                chat_id=driver_id,
                text=f"🚖 **طلب جديد!**\nالزبون يناديك [{taxi_name}]. تم فتح الشات المباشر بينكما الآن.",
                reply_markup=keyboard
            )
            
            await update.message.reply_text(
                f"✅ تم توصيلك بـ [{taxi_name}]. يمكنك الآن الاتفاق على السعر والوجهة مباشرة هنا.",
                reply_markup=keyboard
            )
            
            if update.message.location:
                await context.bot.send_location(chat_id=driver_id, location=update.message.location)
            return

    await update.message.reply_text("❓ لم نتمكن من التعرف على اسم التاكسي، أو ربما غير مسجل حالياً. يرجى التأكد من الاسم.")

async def end_ride(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if user_id in active_sessions:
        partner_id = active_sessions.pop(user_id, None)
        if partner_id in active_sessions:
            del active_sessions[partner_id]
            
        await context.bot.send_message(chat_id=user_id, text="🔴 تم إنهاء الرحلة وإغلاق الشات.")
        if partner_id:
            await context.bot.send_message(chat_id=partner_id, text="🔴 تم إنهاء الرحلة من قبل الطرف الآخر.")
    else:
        await query.edit_message_text("لا توجد رحلة نشطة حالياً.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(end_ride, pattern="^end_ride$"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    app.run_polling()
