import telebot
from telebot import types
import psycopg2
import random
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# SOZLAMALAR
# ==========================================
TOKEN        = os.getenv('BOT_TOKEN')
ADMIN_ID     = int(os.getenv('ADMIN_ID', 0))
DATABASE_URL = os.getenv('DATABASE_URL')

if not TOKEN:
    raise SystemExit("Xato: .env faylida BOT_TOKEN belgilang.")
if not DATABASE_URL:
    raise SystemExit("Xato: .env faylida DATABASE_URL belgilang.")

# Railway ba'zan "postgres://" beradi, psycopg2 "postgresql://" talab qiladi
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

bot    = telebot.TeleBot(TOKEN)
BOT_ID = bot.get_me().id

# ==========================================
# POSTGRESQL BAZA SOZLAMALARI
# ==========================================
db_lock = threading.Lock()

def get_conn():
    """Har safar yangi ulanish — thread xavfsiz."""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id   BIGINT PRIMARY KEY,
                    first_name TEXT,
                    coins      INTEGER DEFAULT 0
                )
            ''')
        conn.commit()

init_db()

def update_user(user_id, first_name, amount):
    with db_lock:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT coins FROM users WHERE user_id = %s', (user_id,))
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        'INSERT INTO users (user_id, first_name, coins) VALUES (%s, %s, %s)',
                        (user_id, first_name, amount)
                    )
                else:
                    new_coins = row[0] + amount
                    cur.execute(
                        'UPDATE users SET first_name = %s, coins = %s WHERE user_id = %s',
                        (first_name, new_coins, user_id)
                    )
            conn.commit()


# ==========================================
# KEEP-ALIVE SERVER (Railway uchun)
# Railway sahifasini yopsangiz ham bot ishlayveradi.
# PORT ni Railway avtomatik belgilaydi.
# ==========================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'K1 Bot ishlayapdi!')

    def log_message(self, format, *args):
        pass  # Keraksiz loglarni o'chirish

def start_health_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Health server {port}-portda ishga tushdi.")
    server.serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()


# ==========================================
# ORQA FONDA XABARNI O'CHIRISH (Taymer)
# ==========================================
def auto_delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Xabarni o'chirishda xatolik: {e}")


# ==========================================
# 1-QISM: YANGI A'ZOLARNI KUTIB OLISH
# ==========================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        if new_user.id == BOT_ID:
            continue

        try:
            bot.restrict_chat_member(
                message.chat.id, new_user.id,
                permissions=types.ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            print(f"Bloklashda xato: {e}")

        eq_type = random.choice(['add', 'sub', 'mul'])

        if eq_type == 'add':
            x_val    = random.randint(2, 15)
            a_val    = random.randint(1, 15)
            question = f"x + {a_val} = {x_val + a_val}"
        elif eq_type == 'sub':
            x_val    = random.randint(10, 30)
            a_val    = random.randint(1, x_val - 1)
            question = f"x - {a_val} = {x_val - a_val}"
        else:
            a_val    = random.randint(2, 9)
            x_val    = random.randint(2, 10)
            question = f"{a_val} ✖️ x = {a_val * x_val}"

        correct_answer = x_val

        options = [correct_answer]
        while len(options) < 4:
            fake = correct_answer + random.randint(-5, 5)
            if fake not in options and fake >= 0:
                options.append(fake)
        random.shuffle(options)

        markup  = types.InlineKeyboardMarkup()
        buttons = []
        for opt in options:
            cb = f"verify_{new_user.id}_pass" if opt == correct_answer else f"verify_{new_user.id}_fail"
            buttons.append(types.InlineKeyboardButton(text=str(opt), callback_data=cb))
        markup.add(buttons[0], buttons[1])
        markup.add(buttons[2], buttons[3])

        welcome_text = (
            f"🔐 **K1 FIREWALL: KIBER-HIMOYA TIZIMI**\n\n"
            f"Tizimga xush kelibsiz, [{new_user.first_name}](tg://user?id={new_user.id})!\n"
            f"Siz Qo'qon shahar 1-son texnikumining yopiq tarmog'iga ulandingiz.\n\n"
            f"⚠️ **DIQQAT: SIZ HOZIR MUTE (Yozish huquqi yo'q) HOLATIDASIZ!**\n"
            f"Guruhda yoza olishingiz uchun inson ekanligingizni tasdiqlashingiz shart.\n\n"
            f"🧠 **Vazifa:** Pastdagi tenglamada `x` ning qiymatini toping.\n\n"
            f"👉 **{question}**\n"
            f"❓ **x = ?**\n\n"
            f"*(Tenglamani yechishga erinmang!)*"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=markup)


# ==========================================
# 2-QISM: TENGLAMANI TEKSHIRISH
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def verify_user(call):
    parts          = call.data.split('_')
    target_user_id = int(parts[1])
    action         = parts[2]

    if call.from_user.id != target_user_id:
        bot.answer_callback_query(call.id, "🛑 Ruxsat yo'q! Bu test faqat yangi a'zolar uchun.", show_alert=True)
        return

    if action == 'pass':
        bot.answer_callback_query(call.id, "✅ Kod qabul qilindi! K1 tarmog'iga ruxsat berildi.", show_alert=True)
        try:
            bot.restrict_chat_member(
                call.message.chat.id, target_user_id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            bot.delete_message(call.message.chat.id, call.message.message_id)

            success_text = (
                f"🟢 **Tizimga to'liq ulandingiz, [{call.from_user.first_name}](tg://user?id={target_user_id})!**\n\n"
                f"💎 **K1-Coin qanday yig'iladi?**\n"
                f"Guruhda foydali ma'lumotlar ulashing, tengdoshlaringizga yordam bering va LIDER bo'ling! "
                f"Faol xabarlaringiz uchun adminlar maxsus tangalar taqdim etadi.\n\n"
                f"⚠️ **Muhim:** *Tangalar faqat guruh reytingi uchun, o'qish balansingizga ta'sir etmaydi.*\n\n"
                f"🚀 `/top` buyrug'i bilan reytingni ko'ring! Omad!"
            )
            sent_msg = bot.send_message(call.message.chat.id, success_text, parse_mode='Markdown')
            threading.Timer(30.0, auto_delete_message, args=(call.message.chat.id, sent_msg.message_id)).start()
        except Exception as e:
            print(f"Ruxsat berishda xato: {e}")
    else:
        bot.answer_callback_query(call.id, "❌ Noto'g'ri javob! Qaytadan hisoblang.", show_alert=True)


# ==========================================
# 3-QISM: K1-COIN BOSHQRUVI
# ==========================================
@bot.message_handler(func=lambda m: m.text and (m.text.startswith('+') or m.text.startswith('-')))
def add_coins(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Coin berish uchun talabaning xabariga 'Reply' qilib yozing!")
        return
    try:
        amount      = int(message.text)
        target_user = message.reply_to_message.from_user
        if target_user.is_bot:
            bot.reply_to(message, "🤖 Botlarga K1-Coin berish mumkin emas!")
            return
        update_user(target_user.id, target_user.first_name, amount)
        if amount > 0:
            text = f"🪙 {target_user.first_name} ga {amount} ta K1-Coin taqdim etildi!\nZo'r harakat qilyapsiz!"
        else:
            text = f"🛑 {target_user.first_name} hisobidan {abs(amount)} ta K1-Coin olib tashlandi.\nQoidalarni buzmang!"
        bot.reply_to(message.reply_to_message, text)
    except ValueError:
        pass


# ==========================================
# 4-QISM: TOP REYTING (/top)
# ==========================================
@bot.message_handler(commands=['top', 'reyting'])
def show_top(message):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT first_name, coins FROM users ORDER BY coins DESC LIMIT 10')
            top_users = cur.fetchall()

    if not top_users:
        bot.reply_to(message, "Hozircha guruhda hech kim K1-Coin yig'madi.")
        return

    text   = "🏆 **K1 GURUH REYTINGI (TOP-10)** 🏆\n\n"
    medals = ['🥇', '🥈', '🥉']

    for idx, user in enumerate(top_users):
        m     = medals[idx] if idx < 3 else f"{idx + 1}."
        text += f"{m} {user[0]} — {user[1]} Coin\n"

    text += "\n💡 *K1-Coin yig'ish uchun darslarda faol bo'ling va vazifalarni bajaring!*"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================
print("K1 Ekotizimi Boti ishga tushdi...")
bot.infinity_polling(timeout=20, long_polling_timeout=10)
