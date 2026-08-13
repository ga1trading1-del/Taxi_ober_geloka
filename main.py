import sqlite3
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8806683255:AAFQR0g5dfbnf8vaEDPm8MvFzCse06z6fvs"

# جلسات الزبائن (ID الزبون -> ID السائق)
active_sessions = {}
# جلسات السائقين للرد (ID السائق -> ID الزبون)
driver_reply_sessions = {}

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            traccar_id TEXT PRIMARY KEY,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            driver_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_driver(traccar_id, telegram_id, username, driver_name="تكسي1"):
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO drivers (traccar_id, telegram_id, username, driver_name)
        VALUES (?, ?, ?, ?)
    """, (traccar_id, telegram_id, username, driver_name))
    conn.commit()
    conn.close()

def get_all_drivers():
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, driver_name, traccar_id FROM drivers")
    results = cursor.fetchall()
    conn.close()
    return results

def is_driver(telegram_id):
    drivers = get_all_drivers()
    for d in drivers:
        if d[0] == telegram_id:
            return True
    return False

# --- الأوامر والرسائل ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 **أهلاً بك في خدمة التاكسي!**\n\n"
        "• **للزبائن:** اكتب اسم التاكسي (مثال: `تكسي1`) لربط المحادثة بالسائق.\n"
        "• **للسائقين:** لتسجيل نفسك أرسل:\n"
        "`/register_driver [رقم_جهاز_Traccar] [اسم_التاكسي]`",
        parse_mode="Markdown"
    )

async def register_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "بدون اسم مستخدم"
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ يرجى استخدام الأمر: `/register_driver 79259172 تكسي1`", parse_mode="Markdown")
        return

    traccar_id = args[0]
    driver_name = args[1] if len(args) > 1 else "تكسي1"
    
    add_driver(traccar_id, user_id, username, driver_name)

    await update.message.reply_text(
        f"✅ **تم تسجيلك كسائق بنجاح!**\n\n"
        f"🚕 اسم التاكسي: `{driver_name}`\n"
        f"🆔 معرف Traccar: `{traccar_id}`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    driver_ids = [d[0] for d in drivers]

    # --- 1. إذا كان المراسِل هو "سائق" ويريد الرد على الزبون ---
    if user_id in driver_ids:
        # إذا كان السائق مرتبكاً بزبون حالي
        if user_id in driver_reply_sessions:
            target_customer_id = driver_reply_sessions[user_id]
            try:
                await context.bot.send_message(
                    chat_id=target_customer_id,
                    text=f"🚖 **رسالة من السائق:**\n{user_text}"
                )
                await update.message.reply_text("✅ تم إرسال ردك للزبون بنجاح!")
            except Exception as e:
                await update.message.reply_text("⚠️ تعذر إرسال الرسالة للزبون (ربما قام بإيقاف البوت).")
        else:
            await update.message.reply_text("ℹ️ أنت مسجل كسائق. بانتظار استقبال طلبات جديدة من الزبائن.")
        return

    # --- 2. إذا كان المراسِل هو "زبون" ---
    if not drivers:
        await update.message.reply_text("⚠️ لا يوجد سائقون مسجلون حالياً.")
        return

    selected_driver_id = None
    selected_driver_name = None

    # البحث عن اسم السائق في رسالة الزبون (مثال: تكسي1 أو تكسي2)
    for telegram_id, driver_name, traccar_id in drivers:
        if driver_name in user_text:
            active_sessions[user_id] = (telegram_id, driver_name)
            selected_driver_id = telegram_id
            selected_driver_name = driver_name
            break

    # إذا لم يذكر اسم سائق، استخدام الجلسة السابقة
    if not selected_driver_id and user_id in active_sessions:
        selected_driver_id, selected_driver_name = active_sessions[user_id]

    if selected_driver_id:
        # ربط السائق بالزبون لكي يستطيع الرد عليه مباشرة
        driver_reply_sessions[selected_driver_id] = user_id

        try:
            await context.bot.send_message(
                chat_id=selected_driver_id,
                text=f"🚨 **طلب/رسالة من الزبون ({customer_name})!**\n\n"
                     f"💬 النص: {user_text}\n"
                     f"👤 الحساب: {customer_username}\n\n"
                     f"💡 *أكتب أي رسالة هنا للرد المباشر على هذا الزبون.*",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم توجيه رسالتك إلى ({selected_driver_name}) بنجاح!")
        except Exception as e:
            await update.message.reply_text("⚠️ تعذر الوصول للسائق.")
    else:
        await update.message.reply_text("⚠️ يرجى كتابة اسم التاكسي المطلوب (مثال: `تكسي1`) للتواصل معه.", parse_mode="Markdown")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"

    if user_id in active_sessions:
        driver_id, driver_name = active_sessions[user_id]
        driver_reply_sessions[driver_id] = user_id
        try:
            await context.bot.send_message(
                chat_id=driver_id,
                text=f"📍 **وصل موقع جغرافي من الزبون ({customer_name})!**",
                parse_mode="Markdown"
            )
            await context.bot.send_location(
                chat_id=driver_id,
                latitude=location.latitude,
                longitude=location.longitude
            )
            await update.message.reply_text(f"✅ تم إرسال موقعك للسائق ({driver_name}) بنجاح!")
        except Exception as e:
            logging.error(f"خطأ: {e}")

def main():
    init_db()
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register_driver", register_driver))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 البوت يعمل وقاعدة البيانات جاهزة...")
    app.run_polling()

if __name__ == "__main__":
    main()
