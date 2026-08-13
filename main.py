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

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # استبدل هذا بتوكن البوت الخاص بك من BotFather

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

def get_driver_by_traccar_id(traccar_id):
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, driver_name FROM drivers WHERE traccar_id = ?", (traccar_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# --- الأوامر والتعامل مع الرسائل ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 أهلاً بك في خدمة التاكسي!\n\n"
        "• **للزبائن:** يرجى إرسال موقعك المباشر وكتابة اسم التاكسي المطلوب (مثال: تكسي1).\n"
        "• **للائقيين:** لتسجيل حسابك، أرسل الأمر:\n"
        "`/register_driver [رقم_جهاز_Traccar]`",
        parse_mode="Markdown"
    )

async def register_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "بدون اسم مستخدم"
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚠️ **طريقة التسجيل خاطئة!**\n"
            "يرجى كتابة الأمر متبوعاً برقم معرف جهاز Traccar الخاص بك:\n"
            "مثال: `/register_driver 79259172`",
            parse_mode="Markdown"
        )
        return

    traccar_id = args[0]
    
    # حفظ البيانات في قاعدة البيانات SQLite
    add_driver(traccar_id, user_id, username)

    await update.message.reply_text(
        f"✅ **تم تسجيلك كسائق بنجاح!**\n\n"
        f"🆔 معرف Traccar: `{traccar_id}`\n"
        f"📱 Telegram ID: `{user_id}`\n\n"
        f"أنت الآن متصل بالنظام وجاهز لاستقبال الطلبات القريبة.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # هنا يمكنك إضافة منطق البحث والربط التلقائي بين طلب الزبون ومعرفات Traccar
    if text and "تكسي" in text:
        await update.message.reply_text("جاري البحث عن السائق وتحويل طلبك...")

def main():
    init_db()  # إنشاء قاعدة البيانات عند بدء التشغيل
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register_driver", register_driver))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 البوت يعمل وقاعدة البيانات جاهزة...")
    app.run_polling()

if __name__ == "__main__":
    main()
