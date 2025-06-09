import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
import json
import os
import time
import threading 
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List 

# --- تنظیمات ضروری ربات ---
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 7030085944  # Set this to your actual Telegram user ID
REQUIRED_CHANNEL_ID = int(os.getenv("REQUIRED_CHANNEL_ID", "0"))
REQUIRED_CHANNEL_LINK = os.getenv("REQUIRED_CHANNEL_LINK", "https://t.me/your_channel")

# --- تنظیمات امتیازدهی و زمان‌بندی ---
REF_POINTS = 1  # امتیاز هر دعوت
LEAVE_DEDUCT = 1 # کسر امتیاز در صورت خروج
DAILY_BONUS = 5 # جایزه روزانه
MIN_WITHDRAW = 20 # حداقل امتیاز برای برداشت
CHECK_INTERVAL_SEC = 3600 * 6 # فاصله بررسی خروج از کانال (6 ساعت)



# --- ساختار داده و فایل ذخیره‌سازی ---
DATA_FILE = 'bot_data.json'
# user_db: {user_id: {'p': points, 'w': wallet, 'l': invite_link, 'r': referrer_id, 't': transactions, 'db': last_daily_bonus, 's': state, 'lvl': level}}
user_db: Dict[int, Dict[str, Any]] = {} 
withdraw_reqs: List[Any] = [] 

# --- سطوح (level: {p: points_needed, b: bonus_points}) ---
LEVELS: Dict[int, Dict[str, int]] = { 
    1: {'p': 0, 'b': 0},
    2: {'p': 10, 'b': 5},
    3: {'p': 30, 'b': 10},
    4: {'p': 60, 'b': 15},
    5: {'p': 100, 'b': 20},
    6: {'p': 150, 'b': 25},
    7: {'p': 200, 'b': 30},
    8: {'p': 300, 'b': 40},
    9: {'p': 400, 'b': 50},
    10: {'p': 500, 'b': 60}
}

bot = telebot.TeleBot(API_TOKEN)

# --- توابع مدیریت داده (Load/Save) ---
def load_data():
    """Load all user and withdrawal data from JSON file."""
    global user_db, withdraw_reqs
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                user_db.clear() 
                for k, v in loaded.get('users', {}).items():
                    try:
                        uid = int(k)
                        v.setdefault('p', 0) 
                        v.setdefault('w', None) 
                        v.setdefault('l', None) 
                        v.setdefault('r', None) 
                        v.setdefault('t', []) 
                        v.setdefault('db', None) 
                        v.setdefault('s', None) 
                        v.setdefault('lvl', 1) 
                        user_db[uid] = v
                    except ValueError:
                        print(f"WARNING: Invalid user_id key in JSON: {k}")
                withdraw_reqs.clear() 
                withdraw_reqs.extend(loaded.get('withdraws', [])) 
                print("LOG: Data loaded successfully.")
        except Exception as e: 
            print(f"ERROR loading data: {e}. Starting with empty data.")
            user_db = {}
            withdraw_reqs = []
    else: 
        print(f"LOG: {DATA_FILE} not found. Creating new data file.")
        save_data()

def save_data():
    """Save all user and withdrawal data to JSON file."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({'users': user_db, 'withdraws': withdraw_reqs}, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"ERROR saving data: {e}")

# --- کلاس UserAccount برای مدیریت اطلاعات هر کاربر ---
class UserAccount:
    def __init__(self, uid: int):
        self.id = uid
        if uid not in user_db:
            user_db[uid] = {'p': 0, 'w': None, 'l': None, 'r': None, 't': [], 'db': None, 's': None, 'lvl': 1}
            save_data()
        self._data = user_db[uid]

    @property
    def points(self): 
        return self._data['p']
    
    @points.setter
    def points(self, value):
        self._data['p'] = max(0, value)  # Ensure points never go negative
        self._check_level_up() 
        save_data() 

    @property
    def wallet(self): 
        return self._data['w']
    
    @wallet.setter
    def wallet(self, value): 
        self._data['w'] = value
        save_data()

    @property
    def invite_link(self): 
        return self._data['l']
    
    @invite_link.setter
    def invite_link(self, value): 
        self._data['l'] = value
        save_data()

    @property
    def referrer_id(self): 
        return self._data['r']
    
    @referrer_id.setter
    def referrer_id(self, value): 
        self._data['r'] = value
        save_data()
        
    @property
    def last_daily_bonus(self): 
        return self._data['db']
    
    @last_daily_bonus.setter
    def last_daily_bonus(self, value): 
        self._data['db'] = value
        save_data()

    @property
    def state(self): 
        return self._data['s']
    
    @state.setter
    def state(self, value): 
        self._data['s'] = value
        save_data()
    
    @property
    def level(self): 
        return self._data['lvl']
    
    @level.setter
    def level(self, value): 
        self._data['lvl'] = value
        save_data()



    def add_transaction(self, t_type: str, amt, status: str = "ok", details: str = ""):
        """Add a transaction to user's history."""
        self._data['t'].append({
            'type': t_type, 
            'amount': amt, 
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            'status': status, 
            'details': details
        })
        save_data()

    def get_transactions(self) -> List[Dict[str, Any]]: 
        return self._data['t']
    
    def delete_account(self) -> bool:
        """Delete user account from database."""
        if self.id in user_db:
            del user_db[self.id]
            save_data()
            print(f"LOG: User {self.id} account deleted.")
            return True
        return False

    def _check_level_up(self):
        """Check if user should level up and apply bonus."""
        curr_lvl = self.level
        next_lvl = curr_lvl + 1
        next_lvl_info = LEVELS.get(next_lvl)
        
        if next_lvl_info and self.points >= next_lvl_info['p']:
            self.level = next_lvl
            bonus = next_lvl_info['b']
            self.points += bonus 
            self.add_transaction('level_up', bonus, details=f"سطح {next_lvl}")
            try: 
                bot.send_message(self.id, f"🌟 تبریک! شما به **سطح {next_lvl}** رسیدید!\n**{bonus} امتیاز جایزه** دریافت کردید.\nامتیاز کل: `{self.points}`", parse_mode='Markdown')
            except Exception as e:
                print(f"ERROR sending level up message to {self.id}: {e}")

# --- تابع اصلی برای دسترسی به UserAccount ---
def get_user_account(uid: int) -> UserAccount: 
    return UserAccount(uid)

# --- Core Bot Utilities ---
def is_member(uid: int, cid: int) -> bool:
    """Checks if user is a member of the required channel."""
    try: 
        status = bot.get_chat_member(chat_id=cid, user_id=uid).status
        return status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiTelegramException as e:
        print(f"ERROR: Checking member for {uid} in {cid}: {e}")
        if ("Forbidden: bot is not a member of the chat" in str(e) or 
            "Bad Request: chat not found" in str(e)):
            try:
                bot.send_message(ADMIN_ID, f"⚠️ ربات در کانال `{cid}` مشکل دسترسی دارد.\n`{e}`\n\n**اطمینان حاصل کنید ربات ادمین کامل کانال `{REQUIRED_CHANNEL_LINK}` است و ID صحیح است.**", parse_mode='Markdown')
            except:
                pass
        return False
    except Exception as e: 
        print(f"ERROR checking member: {e}")
        return False

def create_main_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    """Creates the main menu keyboard based on user role."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔗 لینک اختصاصی", callback_data="get_link"),
        InlineKeyboardButton("💰 امتیاز من", callback_data="get_points")
    )
    kb.add(
        InlineKeyboardButton("💼 ثبت ولت USDT", callback_data="set_wallet"),
        InlineKeyboardButton("📤 درخواست برداشت", callback_data="withdraw")
    )
    kb.add(
        InlineKeyboardButton("📜 تاریخچه تراکنش‌ها", callback_data="trans_hist"),
        InlineKeyboardButton("🎁 جایزه روزانه", callback_data="daily_bonus")
    )
    kb.add(
        InlineKeyboardButton("📈 سطح من", callback_data="my_level"),
        InlineKeyboardButton("❓ راهنما", callback_data="help_menu")
    )
    
    if uid == ADMIN_ID:
        kb.add(InlineKeyboardButton("📊 پنل مدیریت", callback_data="admin_panel"))
    
    return kb

def create_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Creates the admin panel keyboard."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats"),
        InlineKeyboardButton("➕ اضافه کردن امتیاز", callback_data="admin_add_p")
    )
    kb.add(
        InlineKeyboardButton("📤 مدیریت برداشت‌ها", callback_data="admin_man_wd"),
        InlineKeyboardButton("📣 ارسال پیام همگانی", callback_data="admin_bcast")
    )
    kb.add(
        InlineKeyboardButton("🔍 بررسی عضویت", callback_data="admin_check_mem"),
        InlineKeyboardButton("🗑️ حذف کاربر", callback_data="admin_del_user")
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main"))
    return kb

# --- Periodic check for channel leavers ---
def periodic_check():
    """Periodically checks channel membership and deducts points/removes users who left."""
    print("LOG: Member check thread started.")
    while True:
        try:
            time.sleep(30)  # Initial delay to let bot start properly
            user_ids = list(user_db.keys())  # Create a copy to avoid RuntimeError
            
            for uid in user_ids:
                if uid == ADMIN_ID or uid not in user_db: 
                    continue 

                user_acc = get_user_account(uid)
                if not is_member(uid, REQUIRED_CHANNEL_ID):
                    print(f"LOG: User {uid} left channel. Processing deduction.")
                    
                    # Notify user about leaving
                    try: 
                        bot.send_message(uid, f"😔 شما از کانال خارج شدید. دسترسی محدود و امتیاز صفر شد.\nبه کانال {REQUIRED_CHANNEL_LINK} بپیوندید و /start کنید.", parse_mode='Markdown')
                    except: 
                        pass 
                    
                    # Deduct points from referrer
                    if user_acc.referrer_id and user_acc.referrer_id in user_db:
                        referrer_acc = get_user_account(user_acc.referrer_id)
                        deduct = LEAVE_DEDUCT
                        referrer_acc.points = max(0, referrer_acc.points - deduct)
                        referrer_acc.add_transaction('ref_deduct', -deduct, details=f"خروج {uid}")
                        
                        try:
                            bot.send_message(referrer_acc.id, f"⚠️ کاربر `{uid}` خارج شد. `{deduct}` امتیاز کسر شد.\nامتیاز شما: `{referrer_acc.points}`", parse_mode='Markdown')
                        except:
                            pass
                        
                        try:
                            bot.send_message(ADMIN_ID, f"🚨 کاربر `{uid}` خارج شد.\nارجاع دهنده: `{user_acc.referrer_id}` - `{deduct}` امتیاز کسر شد.", parse_mode='Markdown')
                        except:
                            pass
                    else: 
                        try:
                            bot.send_message(ADMIN_ID, f"🚨 کاربر `{uid}` (بدون ارجاع دهنده) از کانال خارج شد.", parse_mode='Markdown')
                        except:
                            pass
                    
                    # Delete user account
                    user_acc.delete_account() 
                
                time.sleep(0.1)  # Small delay between checks
                
        except Exception as e: 
            print(f"ERROR in periodic check: {e}")
            try:
                bot.send_message(ADMIN_ID, f"⚠️ خطا در بررسی دوره‌ای: `{e}`", parse_mode='Markdown')
            except:
                pass
        
        time.sleep(CHECK_INTERVAL_SEC)

# --- Message Handlers ---
@bot.message_handler(commands=['start', 'help'])
def start_help_handler(message: Message):
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    
    # Check channel membership
    if not is_member(uid, REQUIRED_CHANNEL_ID):
        kb = InlineKeyboardMarkup()
        # Convert username to proper URL if needed
        channel_url = REQUIRED_CHANNEL_LINK
        if channel_url.startswith('@'):
            channel_url = f"https://t.me/{channel_url[1:]}"
        elif not channel_url.startswith('https://'):
            channel_url = f"https://t.me/{channel_url}"
        
        kb.add(InlineKeyboardButton("🔗 عضویت در کانال", url=channel_url))
        kb.add(InlineKeyboardButton("✅ عضو شدم", callback_data="check_mem"))
        bot.send_message(uid, f"👋 سلام و خوش آمدید!\n\nبرای استفاده از ربات، ابتدا باید عضو کانال شوید:\n\nپس از عضویت در کانال، دکمه «✅ عضو شدم» را بزنید.", parse_mode='Markdown', reply_markup=kb)
        return

    # Initialize new user
    if not user_acc.invite_link: 
        bot_username = bot.get_me().username
        user_acc.invite_link = f"https://t.me/{bot_username}?start=user_{uid}"
        user_acc.level = 1 
        
        # Handle referral
        if len(message.text.split()) > 1 and message.text.split()[1].startswith('user_'):
            try:
                referrer_id = int(message.text.split()[1].replace('user_', ''))
                if referrer_id in user_db and referrer_id != uid: 
                    user_acc.referrer_id = referrer_id
                    referrer_acc = get_user_account(referrer_id)
                    referrer_acc.points += REF_POINTS
                    referrer_acc.add_transaction('ref_bonus', REF_POINTS, details=f"دعوت از {uid}")
                    
                    try:
                        bot.send_message(referrer_id, f"🎉 کاربر جدید `{uid}` از طریق شما پیوست!\n`{REF_POINTS}` امتیاز دریافت کردید.\nامتیاز کل: `{referrer_acc.points}`", parse_mode='Markdown')
                    except:
                        pass
                    
                    try:
                        bot.send_message(ADMIN_ID, f"➕ کاربر جدید: `{uid}` (ارجاع دهنده: `{referrer_id}`)\n`{REF_POINTS}` امتیاز به دعوت‌کننده اضافه شد.", parse_mode='Markdown')
                    except:
                        pass
                else: 
                    try:
                        bot.send_message(ADMIN_ID, f"➕ کاربر جدید: `{uid}` (ارجاع نامعتبر: {message.text.split()[1]})", parse_mode='Markdown')
                    except:
                        pass
            except ValueError:
                try:
                    bot.send_message(ADMIN_ID, f"➕ کاربر جدید: `{uid}` (ارجاع نامعتبر)", parse_mode='Markdown')
                except:
                    pass
        else: 
            try:
                bot.send_message(ADMIN_ID, f"➕ کاربر جدید: `{uid}` (بدون ارجاع دهنده)", parse_mode='Markdown')
            except:
                pass
        save_data()

    # Send welcome message
    if message.text == '/help':
        msg_text = (f"💡 **راهنمای کامل ربات ارجاع**\n\n"
                    f"**🎯 چگونه کار می‌کند؟**\n"
                    f"• از لینک اختصاصی خود برای دعوت دوستان استفاده کنید\n"
                    f"• به ازای هر نفر که از لینک شما عضو شود، **{REF_POINTS} سکه** دریافت می‌کنید\n"
                    f"• سکه‌های خود را به USDT تبدیل کنید و برداشت نمایید\n\n"
                    f"**🔗 لینک اختصاصی**\n"
                    f"• لینک منحصر به فرد شما برای دعوت دوستان\n"
                    f"• در شبکه‌های اجتماعی، گروه‌ها و کانال‌ها به اشتراک بگذارید\n"
                    f"• هر کلیک و عضویت موفق = {REF_POINTS} سکه\n\n"
                    f"**💰 سیستم امتیازدهی**\n"
                    f"• دعوت موفق: +{REF_POINTS} سکه\n"
                    f"• جایزه روزانه: +{DAILY_BONUS} سکه (هر 24 ساعت)\n"
                    f"• بونوس سطح: امتیاز اضافی با ارتقای سطح\n"
                    f"• کسر امتیاز: -{LEAVE_DEDUCT} سکه اگر کاربر دعوت شده از کانال خارج شود\n\n"
                    f"**📤 نحوه برداشت**\n"
                    f"• ابتدا ولت USDT TRC20 خود را ثبت کنید\n"
                    f"• حداقل برداشت: {MIN_WITHDRAW} سکه\n"
                    f"• نرخ تبدیل: 20 سکه = 15 دلار USDT\n"
                    f"• درخواست‌ها توسط ادمین بررسی و پرداخت می‌شود\n\n"
                    f"**📈 سیستم سطح‌بندی**\n"
                    f"• سطح 1: 0 سکه (بدون بونوس)\n"
                    f"• سطح 2: 10 سکه (+5 بونوس)\n"
                    f"• سطح 3: 30 سکه (+10 بونوس)\n"
                    f"• سطح 4: 60 سکه (+15 بونوس)\n"
                    f"• سطح 5: 100 سکه (+20 بونوس)\n"
                    f"• و سطوح بالاتر...\n\n"
                    f"**⚠️ نکات مهم**\n"
                    f"• باید همیشه عضو کانال باشید\n"
                    f"• خروج از کانال = حذف حساب کاربری\n"
                    f"• دعوت‌های تقلبی شناسایی و حذف می‌شوند\n"
                    f"• برداشت‌ها ظرف 24-48 ساعت پردازش می‌شوند\n\n"
                    f"**🚀 نکات موفقیت**\n"
                    f"• لینک را در گروه‌های پرعضو به اشتراک بگذارید\n"
                    f"• از شبکه‌های اجتماعی استفاده کنید\n"
                    f"• به دوستان و خانواده معرفی کنید\n"
                    f"• هر روز جایزه روزانه خود را دریافت کنید")
    else:
        user_name = message.from_user.first_name or "کاربر"
        msg_text = f"👋 سلام {user_name}، به ربات خوش آمدید!\n\nاز دکمه‌های زیر برای استفاده از امکانات ربات استفاده کنید:"
    
    bot.send_message(uid, msg_text, reply_markup=create_main_menu_keyboard(uid), parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def text_input_handler(message: Message):
    uid = message.from_user.id
    user_acc = get_user_account(uid)

    # Check channel membership for non-admin users
    if uid != ADMIN_ID and not is_member(uid, REQUIRED_CHANNEL_ID):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ عضو شدم", callback_data="check_mem"))
        bot.send_message(uid, f"⚠️ برای تعامل با ربات، باید عضو کانال باشید:\n**[🔗 عضویت در کانال]({REQUIRED_CHANNEL_LINK})**", parse_mode='Markdown', reply_markup=kb)
        return

    # State machine for inputs
    if user_acc.state == 'wait_wallet': 
        wallet_handler(message)
    elif user_acc.state == 'wait_withdraw': 
        withdraw_handler(message)
    elif user_acc.state == 'admin_add_p': 
        admin_add_point_handler(message)
    elif user_acc.state == 'admin_broadcast': 
        admin_broadcast_handler(message)
    elif user_acc.state == 'admin_del_user': 
        admin_delete_user_handler(message)
    else: 
        bot.send_message(uid, "❓ متوجه نشدم. لطفاً از دکمه‌های منو استفاده کنید.", reply_markup=create_main_menu_keyboard(uid))

# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def query_handler(call: CallbackQuery): 
    uid = call.from_user.id
    data = call.data
    user_acc = get_user_account(uid)

    # Handle membership check
    if data == "check_mem":
        if is_member(uid, REQUIRED_CHANNEL_ID):
            bot.edit_message_text("✅ عضویت تایید شد! دسترسی فعال شد.", call.message.chat.id, call.message.message_id)
            bot.send_message(uid, "🎉 خوش آمدید! حالا می‌توانید از تمام امکانات ربات استفاده کنید.", reply_markup=create_main_menu_keyboard(uid))
            user_acc.state = None
            if not user_acc.invite_link: 
                bot_username = bot.get_me().username
                user_acc.invite_link = f"https://t.me/{bot_username}?start=user_{uid}"
                user_acc.level = 1 
                save_data()
        else: 
            bot.answer_callback_query(call.id, "❌ هنوز عضو نیستید! ابتدا عضو کانال شوید.", show_alert=True)
        return

    # Check channel membership for non-admin users
    if uid != ADMIN_ID and not is_member(uid, REQUIRED_CHANNEL_ID):
        bot.answer_callback_query(call.id, "⚠️ برای استفاده از این بخش، عضو کانال شوید.", show_alert=True)
        return

    # Handle main menu actions
    if data == "get_link": 
        bot.send_message(uid, f"🔗 **لینک اختصاصی شما:**\n`{user_acc.invite_link}`\n\n💡 این لینک را با دوستان خود به اشتراک بگذارید.\nهر دعوت موفق `{REF_POINTS}` امتیاز به شما می‌دهد!", parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        
    elif data == "get_points": 
        bot.answer_callback_query(call.id, f"💰 امتیاز شما: {user_acc.points}", show_alert=True)
        
    elif data == "set_wallet": 
        bot.send_message(uid, "💼 **ثبت کیف پول USDT**\n\nلطفاً آدرس کیف پول USDT TRC20 خود را ارسال کنید:\n\n⚠️ **توجه**: آدرس باید معتبر باشد و با حرف T شروع شود.")
        user_acc.state = 'wait_wallet'
        bot.answer_callback_query(call.id)
        
    elif data == "withdraw":
        if user_acc.points < MIN_WITHDRAW: 
            bot.answer_callback_query(call.id, f"❌ حداقل {MIN_WITHDRAW} امتیاز برای برداشت لازم است.", show_alert=True)
        elif not user_acc.wallet: 
            bot.answer_callback_query(call.id, "❌ ابتدا کیف پول خود را ثبت کنید.", show_alert=True)
        else: 
            bot.send_message(uid, f"📤 **درخواست برداشت**\n\nامتیاز شما: `{user_acc.points}`\nنرخ تبدیل: 20 امتیاز = 15 دلار\n\nمقدار دلار برای برداشت را وارد کنید:\n(حداقل 15 دلار - باید مضرب 15 باشد)", parse_mode='Markdown')
            user_acc.state = 'wait_withdraw'
            bot.answer_callback_query(call.id)
    
    elif data.startswith("trans_hist"): 
        show_transactions(call, uid, user_acc)
    
    elif data == "daily_bonus":
        handle_daily_bonus(call, uid, user_acc)
    
    elif data == "my_level":
        show_user_level(call, uid, user_acc)
    
    elif data == "help_menu": 
        start_help_handler(call.message)
        bot.answer_callback_query(call.id)
    


    # Admin panel actions
    elif data == "admin_panel":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ شما مجاز به دسترسی به این بخش نیستید.", show_alert=True)
            return
        bot.send_message(uid, "🔧 **پنل مدیریت**\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=create_admin_panel_keyboard())
        bot.answer_callback_query(call.id)

    elif data == "back_to_main":
        bot.send_message(uid, "🏠 بازگشت به منوی اصلی", reply_markup=create_main_menu_keyboard(uid))
        bot.answer_callback_query(call.id)

    elif data == "admin_stats": 
        show_admin_stats(call, uid)
        
    elif data == "admin_add_p": 
        bot.send_message(uid, "➕ **اضافه کردن امتیاز**\n\nID کاربر و مقدار امتیاز را وارد کنید:\nمثال: `123456789 5`", parse_mode='Markdown')
        user_acc.state = 'admin_add_p'
        bot.answer_callback_query(call.id)
        
    elif data.startswith("admin_man_wd"): 
        manage_withdrawals(call, uid, data)
        
    elif data.startswith("confirm_withdraw_") or data.startswith("reject_withdraw_"):
        handle_withdrawal_decision(call, uid, data)
    
    elif data == "admin_bcast": 
        bot.send_message(uid, "📣 **ارسال پیام همگانی**\n\nپیام خود را بنویسید تا برای تمام کاربران ارسال شود:")
        user_acc.state = 'admin_broadcast'
        bot.answer_callback_query(call.id)
        
    elif data == "admin_check_mem": 
        admin_manual_check_members(call, uid)
        
    elif data == "admin_del_user": 
        bot.send_message(uid, "🗑️ **حذف کاربر**\n\nID کاربر برای حذف را وارد کنید:")
        user_acc.state = 'admin_del_user'
        bot.answer_callback_query(call.id)

# --- Handler Functions ---
def wallet_handler(message: Message):
    """Handle wallet address input."""
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    user_acc.state = None
    
    if not is_member(uid, REQUIRED_CHANNEL_ID): 
        bot.send_message(uid, f"⚠️ ابتدا عضو کانال شوید و /start کنید.")
        return
        
    wallet = message.text.strip()
    
    # Validate USDT TRC20 address
    if not (26 <= len(wallet) <= 35 and wallet.startswith('T')):
        bot.send_message(uid, "❌ آدرس USDT TRC20 نامعتبر است.\nآدرس باید با T شروع شود و بین 26 تا 35 کاراکتر باشد.")
        return
        
    user_acc.wallet = wallet
    user_acc.add_transaction('set_wallet', wallet, "ثبت شده")
    bot.send_message(uid, f"✅ کیف پول شما با موفقیت ثبت شد:\n`{wallet}`\n\nحالا می‌توانید درخواست برداشت کنید.", parse_mode='Markdown')

def withdraw_handler(message: Message):
    """Handle withdrawal amount input."""
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    user_acc.state = None
    
    if not is_member(uid, REQUIRED_CHANNEL_ID): 
        bot.send_message(uid, f"⚠️ ابتدا عضو کانال شوید و /start کنید.")
        return
        
    try: 
        amt = float(message.text.strip())
        if amt <= 0 or amt % 15 != 0:
            raise ValueError("Invalid amount")
    except: 
        bot.send_message(uid, "❌ مقدار وارد شده نامعتبر است.\nلطفاً عدد مثبت و مضرب 15 وارد کنید.")
        return
    
    points_req = int((amt / 15) * 20)
    
    if user_acc.points < points_req:
        bot.send_message(uid, f"❌ امتیاز کافی ندارید.\nبرای {amt} دلار، {points_req} امتیاز لازم است.\nامتیاز شما: {user_acc.points}")
        return
    
    # Deduct points and create withdrawal request
    user_acc.points -= points_req
    user_acc.add_transaction('withdraw_req', -points_req, "در انتظار تایید", f"درخواست {amt} دلار")
    
    withdraw_reqs.append([uid, amt, user_acc.wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    save_data()
    
    bot.send_message(uid, f"📤 درخواست برداشت شما ثبت شد:\n\n💰 مبلغ: {amt} دلار\n🏦 آدرس: `{user_acc.wallet}`\n⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n⏳ درخواست شما در حال بررسی است و تا 24 ساعت آینده پردازش خواهد شد.", parse_mode='Markdown')
    
    # Notify admin
    try:
        bot.send_message(ADMIN_ID, f"📤 **درخواست برداشت جدید**\n\nکاربر: `{uid}`\nمبلغ: {amt} دلار\nآدرس: `{user_acc.wallet}`\nزمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", parse_mode='Markdown')
    except:
        pass

def admin_add_point_handler(message: Message):
    """Handle admin adding points to user."""
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    user_acc.state = None
    
    if uid != ADMIN_ID:
        return
        
    try:
        parts = message.text.strip().split()
        target_uid = int(parts[0])
        points_to_add = int(parts[1])
        
        if target_uid not in user_db:
            bot.send_message(uid, f"❌ کاربر {target_uid} یافت نشد.")
            return
            
        target_acc = get_user_account(target_uid)
        target_acc.points += points_to_add
        target_acc.add_transaction('admin_bonus', points_to_add, "اضافه شده", "توسط ادمین")
        
        bot.send_message(uid, f"✅ {points_to_add} امتیاز به کاربر {target_uid} اضافه شد.\nامتیاز کل کاربر: {target_acc.points}")
        
        try:
            bot.send_message(target_uid, f"🎁 مدیر {points_to_add} امتیاز به شما اضافه کرد!\nامتیاز کل شما: {target_acc.points}")
        except:
            pass
            
    except:
        bot.send_message(uid, "❌ فرمت نامعتبر. مثال: `123456789 5`", parse_mode='Markdown')

def admin_broadcast_handler(message: Message):
    """Handle admin broadcast message."""
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    user_acc.state = None
    
    if uid != ADMIN_ID:
        return
        
    broadcast_msg = message.text.strip()
    sent_count = 0
    failed_count = 0
    
    bot.send_message(uid, "📣 شروع ارسال پیام همگانی...")
    
    for target_uid in user_db.keys():
        try:
            bot.send_message(target_uid, f"📢 **پیام از مدیریت**\n\n{broadcast_msg}", parse_mode='Markdown')
            sent_count += 1
            time.sleep(0.05)  # Rate limiting
        except:
            failed_count += 1
    
    bot.send_message(uid, f"✅ ارسال پیام کامل شد.\n\n📊 آمار:\n• ارسال موفق: {sent_count}\n• ارسال ناموفق: {failed_count}")

def admin_delete_user_handler(message: Message):
    """Handle admin deleting user."""
    uid = message.from_user.id
    user_acc = get_user_account(uid)
    user_acc.state = None
    
    if uid != ADMIN_ID:
        return
        
    try:
        target_uid = int(message.text.strip())
        
        if target_uid not in user_db:
            bot.send_message(uid, f"❌ کاربر {target_uid} یافت نشد.")
            return
            
        if target_uid == ADMIN_ID:
            bot.send_message(uid, "❌ نمی‌توانید خودتان را حذف کنید!")
            return
            
        target_acc = get_user_account(target_uid)
        target_acc.delete_account()
        
        bot.send_message(uid, f"✅ کاربر {target_uid} با موفقیت حذف شد.")
        
        try:
            bot.send_message(target_uid, "⚠️ حساب کاربری شما توسط مدیر حذف شد.")
        except:
            pass
            
    except:
        bot.send_message(uid, "❌ ID نامعتبر. لطفاً عدد وارد کنید.")

# --- Helper Functions ---
def show_transactions(call: CallbackQuery, uid: int, user_acc: UserAccount):
    """Show user transaction history with pagination."""
    transactions = user_acc.get_transactions()
    
    if not transactions:
        bot.answer_callback_query(call.id, "📜 هیچ تراکنشی یافت نشد.", show_alert=True)
        return
    
    # Show last 10 transactions
    recent_transactions = transactions[-10:]
    
    msg = "📜 **تاریخچه تراکنش‌ها** (10 تراکنش اخیر):\n\n"
    
    for i, trans in enumerate(reversed(recent_transactions), 1):
        trans_type = trans.get('type', 'نامشخص')
        amount = trans.get('amount', 0)
        time_str = trans.get('time', 'نامشخص')
        status = trans.get('status', 'نامشخص')
        details = trans.get('details', '')
        
        type_emoji = {
            'ref_bonus': '🎉',
            'ref_deduct': '⚠️',
            'daily_bonus': '🎁',
            'level_up': '🌟',
            'withdraw_req': '📤',
            'withdraw': '💰',
            'admin_bonus': '🎁',
            'set_wallet': '💼'
        }.get(trans_type, '📝')
        
        msg += f"{i}. {type_emoji} **{trans_type}**\n"
        msg += f"   💰 مقدار: {amount}\n"
        msg += f"   📅 زمان: {time_str}\n"
        msg += f"   📊 وضعیت: {status}\n"
        if details:
            msg += f"   📝 جزئیات: {details}\n"
        msg += "\n"
    
    bot.send_message(uid, msg, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def handle_daily_bonus(call: CallbackQuery, uid: int, user_acc: UserAccount):
    """Handle daily bonus claim."""
    if user_acc.last_daily_bonus:
        last_bonus_time = datetime.strptime(user_acc.last_daily_bonus, "%Y-%m-%d %H:%M:%S")
        time_since_last = datetime.now() - last_bonus_time
        
        if time_since_last < timedelta(days=1):
            next_bonus_time = last_bonus_time + timedelta(days=1)
            time_left = next_bonus_time - datetime.now()
            
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            bot.answer_callback_query(call.id, f"❌ جایزه روزانه را قبلاً دریافت کردید!\nزمان باقی‌مانده: {hours} ساعت {minutes} دقیقه", show_alert=True)
            return
    
    # Give daily bonus
    user_acc.points += DAILY_BONUS
    user_acc.last_daily_bonus = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_acc.add_transaction('daily_bonus', DAILY_BONUS)
    
    bot.answer_callback_query(call.id, f"🎉 {DAILY_BONUS} امتیاز جایزه روزانه دریافت کردید!", show_alert=True)
    bot.send_message(uid, f"🎁 **جایزه روزانه دریافت شد!**\n\n+ {DAILY_BONUS} امتیاز\nامتیاز کل شما: {user_acc.points}\n\n⏰ جایزه بعدی تا 24 ساعت دیگر قابل دریافت است.", parse_mode='Markdown')

def show_user_level(call: CallbackQuery, uid: int, user_acc: UserAccount):
    """Show user level information."""
    current_level = user_acc.level
    current_points = user_acc.points
    current_level_info = LEVELS.get(current_level, {'p': 0, 'b': 0})
    next_level = current_level + 1
    next_level_info = LEVELS.get(next_level)
    
    msg = f"📈 **اطلاعات سطح شما**\n\n"
    msg += f"🏆 سطح فعلی: **{current_level}**\n"
    msg += f"💰 امتیاز شما: **{current_points}**\n\n"
    
    if next_level_info:
        points_needed = next_level_info['p'] - current_points
        if points_needed <= 0:
            msg += f"🎉 شما آماده ارتقا به سطح {next_level} هستید!\n"
        else:
            msg += f"📊 برای رسیدن به سطح {next_level}:\n"
            msg += f"   • امتیاز مورد نیاز: {next_level_info['p']}\n"
            msg += f"   • امتیاز باقی‌مانده: {points_needed}\n"
            msg += f"   • جایزه سطح بعد: {next_level_info['b']} امتیاز\n"
    else:
        msg += f"👑 تبریک! شما در بالاترین سطح ({current_level}) قرار دارید!"
    
    msg += f"\n💡 **راهنمای کسب امتیاز:**\n"
    msg += f"• دعوت دوستان: {REF_POINTS} امتیاز\n"
    msg += f"• جایزه روزانه: {DAILY_BONUS} امتیاز\n"
    msg += f"• جوایز سطح: متغیر"
    
    bot.send_message(uid, msg, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def show_admin_stats(call: CallbackQuery, uid: int):
    """Show admin statistics."""
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ شما مجاز به دسترسی به این بخش نیستید.", show_alert=True)
        return
    
    total_users = len(user_db)
    total_points = sum(user_data.get('p', 0) for user_data in user_db.values())
    total_withdrawals = len(withdraw_reqs)
    
    # Count users by level
    level_counts = {}
    for user_data in user_db.values():
        level = user_data.get('lvl', 1)
        level_counts[level] = level_counts.get(level, 0) + 1
    
    # Count users with referrals
    users_with_refs = sum(1 for user_data in user_db.values() if user_data.get('r') is not None)
    
    msg = f"📊 **آمار کلی ربات**\n\n"
    msg += f"👥 تعداد کل کاربران: **{total_users}**\n"
    msg += f"💰 مجموع امتیازات: **{total_points}**\n"
    msg += f"🔗 کاربران با ارجاع: **{users_with_refs}**\n"
    msg += f"📤 درخواست‌های برداشت: **{total_withdrawals}**\n\n"
    
    msg += f"📈 **توزیع سطوح:**\n"
    for level in sorted(level_counts.keys()):
        count = level_counts[level]
        msg += f"   • سطح {level}: {count} کاربر\n"
    
    if withdraw_reqs:
        total_withdraw_amount = sum(req[1] for req in withdraw_reqs)
        msg += f"\n💸 **مجموع درخواست‌های برداشت:** {total_withdraw_amount} دلار"
    
    bot.send_message(uid, msg, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def manage_withdrawals(call: CallbackQuery, uid: int, data: str):
    """Manage withdrawal requests."""
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ شما مجاز به دسترسی به این بخش نیستید.", show_alert=True)
        return
    
    if not withdraw_reqs:
        bot.answer_callback_query(call.id, "📤 هیچ درخواست برداشتی وجود ندارد.", show_alert=True)
        return
    
    msg = "📤 **مدیریت درخواست‌های برداشت**\n\n"
    
    kb = InlineKeyboardMarkup()
    
    for i, (req_uid, amount, wallet, req_time) in enumerate(withdraw_reqs):
        user_info = user_db.get(req_uid, {})
        msg += f"**{i+1}.** کاربر: `{req_uid}`\n"
        msg += f"   💰 مبلغ: {amount} دلار\n"
        msg += f"   🏦 ولت: `{wallet}`\n"
        msg += f"   📅 زمان: {req_time}\n"
        msg += f"   📊 امتیاز کاربر: {user_info.get('p', 0)}\n\n"
        
        kb.add(
            InlineKeyboardButton(f"✅ تایید #{i+1}", callback_data=f"confirm_withdraw_{i}"),
            InlineKeyboardButton(f"❌ رد #{i+1}", callback_data=f"reject_withdraw_{i}")
        )
    
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel"))
    
    bot.send_message(uid, msg, parse_mode='Markdown', reply_markup=kb)
    bot.answer_callback_query(call.id)

def handle_withdrawal_decision(call: CallbackQuery, uid: int, data: str):
    """Handle withdrawal approval/rejection."""
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ شما مجاز به دسترسی به این بخش نیستید.", show_alert=True)
        return
    
    try:
        idx = int(data.split('_')[-1])
        if 0 <= idx < len(withdraw_reqs):
            req_uid, amount, wallet, req_time = withdraw_reqs.pop(idx)
            save_data()
            
            is_approved = data.startswith("confirm_withdraw_")
            status = "پرداخت شد" if is_approved else "رد شد"
            
            # Add transaction to user history
            target_acc = get_user_account(req_uid)
            target_acc.add_transaction('withdraw', amount if is_approved else -amount, status, details=f"درخواست {amount} دلار")
            
            # If rejected, return points to user
            if not is_approved:
                points_to_return = int((amount / 15) * 20)
                target_acc.points += points_to_return
                target_acc.add_transaction('refund', points_to_return, "بازگردانده شده", f"رد درخواست {amount} دلار")
            
            bot.send_message(uid, f"✅ درخواست کاربر `{req_uid}` برای {amount} دلار **{status}**.", parse_mode='Markdown')
            
            # Notify user
            try:
                if is_approved:
                    bot.send_message(req_uid, f"🎉 **درخواست برداشت تایید شد!**\n\n💰 مبلغ: {amount} دلار\n🏦 آدرس: `{wallet}`\n\n✅ پرداخت انجام شد. از حمایت شما سپاسگزاریم!", parse_mode='Markdown')
                else:
                    points_returned = int((amount / 15) * 20)
                    bot.send_message(req_uid, f"❌ **درخواست برداشت رد شد**\n\n💰 مبلغ: {amount} دلار\n🔄 {points_returned} امتیاز به حساب شما بازگردانده شد.\n\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید.", parse_mode='Markdown')
            except Exception as e:
                print(f"ERROR notifying user {req_uid}: {e}")
        else:
            bot.answer_callback_query(call.id, "❌ درخواست نامعتبر یا قبلاً پردازش شده.", show_alert=True)
    except Exception as e:
        print(f"ERROR handling withdrawal decision: {e}")
        bot.answer_callback_query(call.id, "❌ خطا در پردازش درخواست.", show_alert=True)

def admin_manual_check_members(call: CallbackQuery, uid: int):
    """Manually check all members and remove non-members."""
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ شما مجاز به دسترسی به این بخش نیستید.", show_alert=True)
        return
    
    bot.send_message(uid, "🔍 شروع بررسی دستی عضویت کاربران...")
    
    removed_count = 0
    checked_count = 0
    
    user_ids = list(user_db.keys())
    
    for target_uid in user_ids:
        if target_uid == ADMIN_ID:
            continue
            
        checked_count += 1
        
        if not is_member(target_uid, REQUIRED_CHANNEL_ID):
            user_acc = get_user_account(target_uid)
            
            # Deduct points from referrer if exists
            if user_acc.referrer_id and user_acc.referrer_id in user_db:
                referrer_acc = get_user_account(user_acc.referrer_id)
                referrer_acc.points = max(0, referrer_acc.points - LEAVE_DEDUCT)
                referrer_acc.add_transaction('ref_deduct', -LEAVE_DEDUCT, details=f"خروج {target_uid}")
            
            # Remove user
            user_acc.delete_account()
            removed_count += 1
            
            try:
                bot.send_message(target_uid, f"😔 شما از کانال خارج شدید و حساب شما حذف شد.\nبرای استفاده مجدد، عضو کانال {REQUIRED_CHANNEL_LINK} شوید و /start کنید.")
            except:
                pass
        
        time.sleep(0.1)  # Rate limiting
    
    bot.send_message(uid, f"✅ بررسی دستی کامل شد.\n\n📊 نتایج:\n• کاربران بررسی شده: {checked_count}\n• کاربران حذف شده: {removed_count}")
    bot.answer_callback_query(call.id)

# --- Main execution ---
if __name__ == "__main__":
    print("LOG: Starting Telegram bot...")
    
    # Load existing data
    load_data()
    
    # Start periodic membership check in background
    check_thread = threading.Thread(target=periodic_check, daemon=True)
    check_thread.start()
    
    print("LOG: Bot started successfully. Listening for messages...")
    
    # Start bot polling
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        try:
            bot.send_message(ADMIN_ID, f"🚨 ربات با خطای جدی متوقف شد: `{e}`", parse_mode='Markdown')
        except:
            pass
