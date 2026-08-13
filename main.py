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

# التوكن الخاص بالبوت
TOKEN = "8806683255:AAFQR0g5dfbnf8vaEDPm8MvFzCse06z6fvs"

# قاموس مؤقت لحفظ الجلسة النشطة لكل زبون (ID الزبون -> ID السائق)
active_sessions = {}

# --- إدارة قاعدة البيانات (SQLite) ---
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

# --- الأوامر والتعامل مع الرسائل ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 **أهلاً بك في خدمة التاكسي!**\n\n"
        "• **للزبائن:** اكتب اسم التاكسي (مثال: `تكسي1` أو `تكسي2`) لربط محادثتك به مباشرة، وسيتم تحويل جميع رسائلك وموقعك إليه تلقائياً.\n"
        "• **للسائقين:** لتسجيل حسابك والتأكيد على اسم التاكسي، أرسل:\n"
        "`/register_driver [رقم_جهاز_Traccar] [اسم_التاكسي]`\n"
        "مثال: `/register_driver 79259172 تكسي1`",
        parse_mode="Markdown"
    )

async def register_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "بدون اسم مستخدم"
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚠️ **طريقة التسجيل خاطئة!**\n"
            "يرجى كتابة الأمر متبوعاً برقم معرف Traccar واسم التاكسي:\n"
            "مثال: `/register_driver 79259172 تكسي1`",
            parse_mode="Markdown"
        )
        return

    traccar_id = args[0]
    driver_name = args[1] if len(args) > 1 else "تكسي1"
    
    add_driver(traccar_id, user_id, username, driver_name)

    await update.message.reply_text(
        f"✅ **تم تسجيلك كسائق بنجاح!**\n\n"
        f"🚕 اسم التاكسي: `{driver_name}`\n"
        f"🆔 معرف Traccar: `{traccar_id}`\n"
        f"📱 Telegram ID: `{user_id}`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    if not drivers:
        await update.message.reply_text("⚠️ لا يوجد سائقون مسجلون في النظام حالياً.")
        return

    # 1. التحقق مما إذا كان النص يحتوي على اسم سائق جديد للتحويل إليه
    selected_driver_id = None
    selected_driver_name = None

    for telegram_id, driver_name, traccar_id in drivers:
        if driver_name in user_text:
            active_sessions[user_id] = (telegram_id, driver_name)  # تحديث/تبديل السائق للزبون
            selected_driver_id = telegram_id
            selected_driver_name = driver_name
            break

    # 2. إذا لم يذكر اسم سائق جديد، استخدام السائق المحفوظ في الجلسة السابقة
    if not selected_driver_id and user_id in active_sessions:
        selected_driver_id, selected_driver_name = active_sessions[user_id]

    # 3. إرسال الرسالة للسائق المحدد
    if selected_driver_id:
        try:
            await context.bot.send_message(
                chat_id=selected_driver_id,
                text=f"🚨 **رسالة جديدة من الزبون ({customer_name})!**\n\n"
                     f"💬 النص: {user_text}\n"
                     f"👤 الحساب: {customer_username}",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم توجيه رسالتك إلى ({selected_driver_name}) بنجاح!")
        except Exception as e:
            logging.error(f"خطأ في توجيه الرسالة: {e}")
            await update.message.reply_text("⚠️ تعذر الوصول للسائق حالياً.")
    else:
        await update.message.reply_text(
            "⚠️ يرجى كتابة اسم التاكسي المطلوب أولاً (مثال: `تكسي1` أو `تكسي2`) لتوجيه المحادثة إليه.",
            parse_mode="Markdown"
        )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"

    # إرسال الموقع للسائق المرتبط بالزبون في الجلسة، أو لجميع السائقين إن لم يحدد سائقاً
    if user_id in active_sessions:
        driver_id, driver_name = active_sessions[user_id]
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
            logging.error(f"خطأ في إرسال الموقع: {e}")
    else:
        drivers = get_all_drivers()
        if drivers:
            for telegram_id, driver_name, traccar_id in drivers:
                try:
                    await context.bot.send_location(chat_id=telegram_id, latitude=location.latitude, longitude=location.longitude)
                except Exception as e:
                    pass
            await update.message.reply_text("✅ تم إرسال موقعك لجميع السائقين المتاحين!")

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
