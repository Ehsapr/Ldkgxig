import telebot
from telebot import types

# اطلاعات ربات
BOT_TOKEN = '7852631688:AAEGWAIunyQeh2XfrfzCVWpB2pt5gsuSixo'
ADMIN_ID = 7030085944
BOT_USERNAME = 'masihfinance_orginal'

# لینک‌های جوین خصوصی
referral_links = [
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

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# دکمه‌های کاربری
def user_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📎 لینک اختصاصی", callback_data="referral_link"))
    markup.add(types.InlineKeyboardButton("🏆 امتیاز من", callback_data="my_points"))
    markup.add(types.InlineKeyboardButton("💰 برداشت", callback_data="withdraw"))
    return markup

# شروع ربات
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    full_name = message.from_user.first_name

    if user_id not in user_data:
        index = len(user_data) % len(referral_links)
        assigned_link = referral_links[index]
        user_data[user_id] = {"points": 0, "link": assigned_link}

    # اگر رفرال بود
    if len(message.text.split()) > 1:
        ref = message.text.split()[1]
        if ref.startswith("ref_"):
            referrer_id = int(ref[4:])
            if referrer_id != user_id and referrer_id in user_data:
                user_data[referrer_id]["points"] += 1
                bot.send_message(referrer_id, "🎉 یک عضو جدید از طریق لینک شما عضو شد!")

    bot.send_message(user_id, f"سلام {full_name} 🌟 به ربات خوش اومدی.", reply_markup=user_keyboard())

# دکمه‌ها
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    if call.data == "referral_link":
        link = user_data[user_id]["link"]
        bot.send_message(user_id, f"📎 لینک اختصاصی شما:\n{link}")

    elif call.data == "my_points":
        points = user_data[user_id]["points"]
        bot.send_message(user_id, f"🏆 امتیاز فعلی شما: {points}\nهر ۲۰ امتیاز = ۱۵ دلار USDT")

    elif call.data == "withdraw":
        points = user_data[user_id]["points"]
        if points >= 20:
            bot.send_message(user_id, "لطفاً آدرس کیف پول USDT خود را ارسال کنید:")
            bot.register_next_step_handler(call.message, handle_wallet)
        else:
            bot.send_message(user_id, "❌ امتیاز کافی ندارید. حداقل ۲۰ امتیاز لازم است.")

# دریافت ولت
def handle_wallet(message):
    user_id = message.from_user.id
    wallet = message.text
    bot.send_message(ADMIN_ID, f"💸 درخواست برداشت از {user_id}\n🪙 ولت: {wallet}")
    bot.send_message(user_id, "✅ ولت ثبت شد. در حال بررسی توسط مدیریت...")

# افزودن امتیاز فقط توسط ادمین
@bot.message_handler(commands=['addpoints'])
def handle_addpoints(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id_str, points_str = message.text.split()
        user_id = int(user_id_str)
        points = int(points_str)

        if user_id in user_data:
            user_data[user_id]["points"] += points
            bot.send_message(message.chat.id, f"✅ {points} امتیاز به کاربر {user_id} اضافه شد.")
            bot.send_message(user_id, f"🏅 {points} امتیاز جدید برای شما ثبت شد!")
        else:
            bot.send_message(message.chat.id, "❌ کاربر پیدا نشد.")
    except:
        bot.send_message(message.chat.id, "❗ فرمت درست دستور:\n/addpoints <user_id> <points>")

print("✅ ربات فعال است...")
bot.infinity_polling()
