# قاموس مؤقت لحفظ السائق المختار لكل زبون داخل الجلسة
active_sessions = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    if not drivers:
        await update.message.reply_text("⚠️ لا يوجد سائقون مسجلون في النظام حالياً.")
        return

    # 1. إذا كتب الزبون اسم سائق معين (مثل "تكسي1") نثبته في جلسة الزبون
    selected_driver_id = None
    for telegram_id, driver_name, traccar_id in drivers:
        if driver_name in user_text:
            active_sessions[user_id] = telegram_id  # حفظ السائق المختار للزبون
            selected_driver_id = telegram_id
            break

    # 2. إذا لم يذكر اسم السائق ولكن لديه سائق اختاره سابقاً في المحادثة
    if not selected_driver_id and user_id in active_sessions:
        selected_driver_id = active_sessions[user_id]

    # 3. إرسال الرسالة للسائق المنسوب للزبون
    if selected_driver_id:
        try:
            await context.bot.send_message(
                chat_id=selected_driver_id,
                text=f"🚨 **رسالة جديدة من الزبون ({customer_name})!**\n\n"
                     f"💬 النص: {user_text}\n"
                     f"👤 الحساب: {customer_username}",
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ تم توجيه طلبك للسائق بنجاح!")
        except Exception as e:
            logging.error(f"خطأ في التوجيه: {e}")
    else:
        # إذا كانت أول رسالة للزبون ولم يحدد اسم السائق
        await update.message.reply_text(
            "⚠️ يرجى كتابة اسم التاكسي أولاً (مثال: `تكسي1`) لربط محادثتك بالسائق المباشر.",
            parse_mode="Markdown"
        )
