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

# التوكن الجديد المحدث
TOKEN = "8806683255:AAFQR0g5dfbnf8vaEDPm8MvFzCse06z6fvs"

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

def add_driver(traccar_id, telegram_id, username, driver_name="سائق"):
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
        "• **للزبائن:** اكتب اسم التاكسي المطلوبة (مثال: `تكسي1`) أو أرسل موقعك الجغرافي لطلب أقرب سائق.\n"
        "• **للسائقين:** لتسجيل حسابك وتحديد اسم التاكسي، أرسل:\n"
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
    
    # حفظ البيانات في قاعدة البيانات SQLite
    add_driver(traccar_id, user_id, username, driver_name)

    await update.message.reply_text(
        f"✅ **تم تسجيلك كسائق بنجاح!**\n\n"
        f"🚕 اسم التاكسي: `{driver_name}`\n"
        f"🆔 معرف Traccar: `{traccar_id}`\n"
        f"📱 Telegram ID: `{user_id}`\n\n"
        f"أنت الآن جاهز واستقبال الطلبات الموجهة لك مباشرة!",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    if user_text and "تكسي" in user_text:
        drivers = get_all_drivers()
        if not drivers:
            await update.message.reply_text("⚠️ لا يوجد سائقون مسجلون في النظام حالياً.")
            return

        # البحث عن السائق المطابق أو إرسال الطلب لجميع السائقين
        sent = False
        for telegram_id, driver_name, traccar_id in drivers:
            if driver_name in user_text or user_text == "تكسي":
                try:
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text=f"🚨 **طلب جديد من زبون!**\n\n"
                             f"👤 الزبون: {customer_name} ({customer_username})\n"
                             f"💬 نص الطلب: {user_text}\n\n"
                             f"يرجى التواصل مع الزبون لخدمته.",
                        parse_mode="Markdown"
                    )
                    sent = True
                except Exception as e:
                    logging.error(f"فشل إرسال الرسالة للسائق: {e}")

        if sent:
            await update.message.reply_text("✅ تم توجيه طلبك للسائق بنجاح! سيتم التواصل معك الآن.")
        else:
            await update.message.reply_text("جاري البحث عن السائق وتوجيه طلبك...")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    if drivers:
        for telegram_id, driver_name, traccar_id in drivers:
            try:
                # إرسال موقع الزبون للسائق مباشرة
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=f"📍 **وصل موقع جديد من زبون ({customer_name})!**",
                    parse_mode="Markdown"
                )
                await context.bot.send_location(
                    chat_id=telegram_id,
                    latitude=location.latitude,
                    longitude=location.longitude
                )
            except Exception as e:
                logging.error(f"خطأ في إرسال الموقع: {e}")
        await update.message.reply_text("✅ تم إرسال موقعك لجميع السائقين القريبين بنجاح!")

def main():
    init_db()  # إنشاء/تحديث قاعدة البيانات
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register_driver", register_driver))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 البوت يعمل وقاعدة البيانات جاهزة...")
    app.run_polling()

if __name__ == "__main__":
    main()
