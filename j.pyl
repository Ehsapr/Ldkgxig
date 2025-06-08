import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = "7852631688:AAEGWAIunyQeh2XfrfzCVWpB2pt5gsuSixo"
ADMIN_ID = 7030085944

bot = telebot.TeleBot(API_TOKEN)

# لینک‌ها
join_links = [
    "https://t.me/+W044nt0qUwgwOTk5",
    "https://t.me/+fdMu6Q5zzZ84ZDNh",
    "https://t.me/+BfYT-a_nu2kxYzJh",
    "https://t.me/+6ZnucYw_ZMA1ZWYx",
    "https://t.me/+BxG3vgzftUljNTZh",
    "https://t.me/+5J77jBGWRwQ3YWVh",
    "https://t.me/+biVwyWMVDkIxMmRh",
    "https://t.me/+rjAUd5yjcQFkN2Fh",
    "https://t.me/+HiljEKbcdHxmYTRh",
    "https://t.me/+4g7b78hhQj0xMzJh"
]

user_links = {}   # user_id : لینک اختصاصی
user_points = {}  # user_id : امتیاز
user_wallets = {} # user_id : آدرس کیف پول
withdraw_requests = []  # لیست درخواست برداشت: (user_id, amount, wallet)

def get_next_link():
    # دایره‌ای از لینک‌ها
    n = len(user_links)
    return join_links[n % len(join_links)]

def main_menu_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔗 لینک اختصاصی", callback_data="get_link"),
        InlineKeyboardButton("💰 امتیاز من", callback_data="get_points"),
        InlineKeyboardButton("💼 ثبت ولت USDT", callback_data="set_wallet"),
        InlineKeyboardButton("📤 درخواست برداشت", callback_data="withdraw")
    )
    if user_id == ADMIN_ID:
        keyboard.add(
            InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats"),
            InlineKeyboardButton("➕ اضافه کردن امتیاز", callback_data="admin_addpoint")
        )
    return keyboard

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    if user_id not in user_links:
        link = get_next_link()
        user_links[user_id] = link
        user_points[user_id] = 0
        bot.send_message(ADMIN_ID, f"کاربر جدید استارت زد:\nآیدی: {user_id}\nلینک اختصاصی: {link}")

    bot.send_message(user_id, "به ربات خوش آمدید! از دکمه‌ها استفاده کنید.", reply_markup=main_menu_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "get_link":
        link = user_links.get(user_id, get_next_link())
        user_links[user_id] = link
        bot.answer_callback_query(call.id, f"لینک اختصاصی شما:\n{link}", show_alert=True)

    elif data == "get_points":
        points = user_points.get(user_id, 0)
        bot.answer_callback_query(call.id, f"امتیاز شما: {points}", show_alert=True)

    elif data == "set_wallet":
        msg = bot.send_message(user_id, "آدرس کیف پول USDT خود را ارسال کنید:")
        bot.register_next_step_handler(msg, wallet_handler)

    elif data == "withdraw":
        points = user_points.get(user_id, 0)
        if points < 20:
            bot.answer_callback_query(call.id, "امتیاز کافی برای برداشت ندارید.", show_alert=True)
        elif user_id not in user_wallets:
            bot.answer_callback_query(call.id, "ابتدا کیف پول خود را ثبت کنید.", show_alert=True)
        else:
            msg = bot.send_message(user_id, "مقدار برداشت به دلار (هر ۲۰ امتیاز = ۱۵ دلار):")
            bot.register_next_step_handler(msg, withdraw_amount_handler)

    elif data == "admin_stats":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        total_users = len(user_links)
        user_list = "\n".join([f"{uid}: {link}, امتیاز: {user_points.get(uid,0)}, کیف پول: {user_wallets.get(uid,'ثبت نشده')}" for uid in user_links])
        bot.send_message(user_id, f"تعداد کاربران: {total_users}\n\nاطلاعات کاربران:\n{user_list}")
        bot.answer_callback_query(call.id)

    elif data == "admin_addpoint":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        msg = bot.send_message(user_id, "لطفا شناسه کاربری و تعداد امتیاز را با فرمت زیر ارسال کنید:\nuser_id امتیاز\nمثال: 123456789 5")
        bot.register_next_step_handler(msg, admin_add_point_handler)
        bot.answer_callback_query(call.id)

def wallet_handler(message):
    user_id = message.from_user.id
    wallet = message.text.strip()
    user_wallets[user_id] = wallet
    bot.send_message(user_id, f"کیف پول شما ثبت شد:\n{wallet}")

def withdraw_amount_handler(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text.strip())
    except:
        bot.send_message(user_id, "مقدار وارد شده معتبر نیست. دوباره تلاش کنید.")
        return
    points = user_points.get(user_id, 0)
    max_amount = (points // 20) * 15
    if amount > max_amount:
        bot.send_message(user_id, f"شما فقط می‌توانید تا {max_amount} دلار برداشت کنید.")
        return
    wallet = user_wallets.get(user_id)
    if not wallet:
        bot.send_message(user_id, "ابتدا کیف پول خود را ثبت کنید.")
        return
    # ثبت درخواست برداشت
    withdraw_requests.append((user_id, amount, wallet))
    user_points[user_id] -= int(amount / 15 * 20)  # کم کردن امتیاز متناسب
    bot.send_message(user_id, f"درخواست برداشت شما ثبت شد:\nمقدار: {amount} دلار\nکیف پول: {wallet}")
    bot.send_message(ADMIN_ID, f"درخواست برداشت جدید:\nکاربر: {user_id}\nمقدار: {amount} دلار\nکیف پول: {wallet}")

def admin_add_point_handler(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.send_message(user_id, "شما دسترسی ندارید.")
        return
    try:
        text = message.text.strip().split()
        target_id = int(text[0])
        points_to_add = int(text[1])
    except:
        bot.send_message(user_id, "فرمت اشتباه است. لطفا مانند مثال ارسال کنید:\n123456789 5")
        return
    if target_id not in user_points:
        bot.send_message(user_id, "کاربر یافت نشد.")
        return
    user_points[target_id] += points_to_add
    bot.send_message(user_id, f"امتیاز {points_to_add} به کاربر {target_id} اضافه شد.")
    bot.send_message(target_id, f"شما {points_to_add} امتیاز دریافت کردید.")

bot.infinity_polling()
