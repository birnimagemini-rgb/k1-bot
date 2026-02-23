import telebot
from telebot import types
import sqlite3
import random
import os
from dotenv import load_dotenv

load_dotenv()

# 1. BOT TOKENI va ADMIN_ID .env faylidan olinadi
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

if not TOKEN:
    raise SystemExit("Xato: .env faylida BOT_TOKEN belgilang.")

bot = telebot.TeleBot(TOKEN)

# ==========================================
# BAZA (DATABASE) SOZLAMALARI
# ==========================================
conn = sqlite3.connect('k1_guruh_coins.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        coins INTEGER DEFAULT 0
    )
''')
conn.commit()

def update_user(user_id, first_name, amount):
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute('INSERT INTO users (user_id, first_name, coins) VALUES (?, ?, ?)', (user_id, first_name, amount))
    else:
        new_coins = row[0] + amount
        cursor.execute('UPDATE users SET first_name = ?, coins = ? WHERE user_id = ?', (first_name, new_coins, user_id))
    conn.commit()


# ==========================================
# 1-QISM: YANGI A'ZOLARNI KUTIB OLISH VA TENGLAMA BERISH
# ==========================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        # Agar botning o'zi qo'shilsa, indamaydi
        if new_user.id == bot.get_me().id:
            continue 

        # 1. Darhol Mute qilish (Yozishni taqiqlash)
        try:
            bot.restrict_chat_member(message.chat.id, new_user.id, can_send_messages=False)
        except Exception as e:
            print(f"Bloklashda xato (Bot admin bo'lmasligi mumkin): {e}")

        # 2. Tasodifiy 5-sinf tenglamasini yaratish (x ni topish)
        eq_type = random.choice(['add', 'sub', 'mul'])
        
        if eq_type == 'add':
            # x + A = B
            x_val = random.randint(2, 15)
            a_val = random.randint(1, 15)
            question = f"x + {a_val} = {x_val + a_val}"
        elif eq_type == 'sub':
            # x - A = B
            x_val = random.randint(10, 30)
            a_val = random.randint(1, x_val - 1)
            question = f"x - {a_val} = {x_val - a_val}"
        else:
            # A * x = B
            a_val = random.randint(2, 9)
            x_val = random.randint(2, 10)
            question = f"{a_val} ✖️ x = {a_val * x_val}"
            
        correct_answer = x_val

        # 3. 4 ta variant yaratish (1 ta to'g'ri, 3 ta xato)
        options = [correct_answer]
        while len(options) < 4:
            fake_answer = correct_answer + random.randint(-5, 5)
            if fake_answer not in options and fake_answer >= 0:
                options.append(fake_answer)
        
        # Variantlarni aralashtirib tashlash
        random.shuffle(options)

        # 4. Tugmalarni yasash
        markup = types.InlineKeyboardMarkup()
        buttons = []
        for opt in options:
            cb_data = f"verify_{new_user.id}_pass" if opt == correct_answer else f"verify_{new_user.id}_fail"
            buttons.append(types.InlineKeyboardButton(text=str(opt), callback_data=cb_data))
        
        # Tugmalarni 2 tadan qilib 2 qatorga terish
        markup.add(buttons[0], buttons[1])
        markup.add(buttons[2], buttons[3])

        # 5. Kiber-uslubdagi chiroyli xush kelibsiz matni
        welcome_text = (
            f"🔐 **K1 FIREWALL: KIBER-HIMOYA TIZIMI**\n\n"
            f"Tizimga xush kelibsiz, [{new_user.first_name}](tg://user?id={new_user.id})!\n"
            f"Siz eng ilg'or tarmoqqa ulandingiz. Guruhda yozish ruxsatini olish uchun xavfsizlikdan o'tishingiz shart.\n\n"
            f"🧠 **Vazifa:** Quyidagi tenglamada `x` ning qiymatini toping. (Tenglamani yechishga erinmang!!!)\n\n"
            f"👉 **{question}**\n"
            f"❓ **x = ?**"
        )

        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=markup)


# ==========================================
# 2-QISM: TENGLAMANI TEKSHIRISH VA RUXSAT BERISH
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def verify_user(call):
    data_parts = call.data.split('_')
    target_user_id = int(data_parts[1])
    action = data_parts[2]

    # Faqat yangi qo'shilgan odamgina o'z tugmasini bosa oladi
    if call.from_user.id == target_user_id:
        if action == 'pass':
            # TO'G'RI JAVOB
            bot.answer_callback_query(call.id, "✅ Kod qabul qilindi! K1 tarmog'iga ruxsat berildi.", show_alert=True)
            
            try:
                # 1. Yozishga ruxsat berish
                bot.restrict_chat_member(
                    call.message.chat.id, target_user_id, 
                    can_send_messages=True, can_send_media_messages=True,
                    can_send_other_messages=True, can_add_web_page_previews=True
                )
                
                # 2. Tenglama xabarini o'chirib tashlash
                bot.delete_message(call.message.chat.id, call.message.message_id)
                
                # 3. 🎉 QOIDALARNI TUSHUNTIRUVCHI YANGI XABAR
                success_text = (
                    f"🟢 **Tizimga to'liq ulandingiz, [{call.from_user.first_name}](tg://user?id={target_user_id})!**\n\n"
                    f"💎 **K1-Coin qanday yig'iladi?**\n"
                    f"Guruhda qiziqarli IT yangiliklar ulashing, zo'r kodlar tashlang, tengdoshlaringizga yordam bering va eng muhimi — guruhda LIDER bo'ling! Foydali xabarlaringiz uchun adminlar tomonidan sizga maxsus tangalar taqdim etiladi.\n\n"
                    f"⚠️ **Muhim eslatma:** *Bu guruhdagi tangalar sizning asosiy o'qish balansingizga ta'sir o'tkazmaydi. Ular faqatgina guruh reytingini aniqlash va qiziqarli raqobat uchun ishlaydi.*\n\n"
                    f"🚀 Dasturlashga doir ma'lumotlar tashlab `/top` reytingida 1-o'ringa chiqing! Omad!"
                )
                bot.send_message(call.message.chat.id, success_text, parse_mode='Markdown')
                
            except Exception as e:
                print(f"Ruxsat berishda xato: {e}")
        else:
            # XATO JAVOB
            bot.answer_callback_query(call.id, "❌ Noto'g'ri javob! Qaytadan hisoblang.", show_alert=True)
    else:
        # Boshqalar bossa chiqadigan ogohlantirish
        bot.answer_callback_query(call.id, "🛑 Ruxsat yo'q! Bu mantiqiy test faqat yangi a'zolar uchun.", show_alert=True)


# ==========================================
# 3-QISM: K1-COIN BOSHQRUVI (+10 yoki -5)
# ==========================================
@bot.message_handler(func=lambda message: message.text and (message.text.startswith('+') or message.text.startswith('-')))
def add_coins(message):
    if message.from_user.id != ADMIN_ID:
        return 
    
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Coin berish uchun talabaning xabariga 'Reply' qilib yozing!")
        return

    try:
        amount = int(message.text)
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
# 4-QISM: TOP REYTINGNI KO'RISH (/top)
# ==========================================
@bot.message_handler(commands=['top', 'reyting'])
def show_top(message):
    cursor.execute('SELECT first_name, coins FROM users ORDER BY coins DESC LIMIT 10')
    top_users = cursor.fetchall()
    
    if not top_users:
        bot.reply_to(message, "Hozircha guruhda hech kim K1-Coin yig'madi.")
        return

    text = "🏆 **K1 GURUH REYTINGI (TOP-10)** 🏆\n\n"
    medal = ['🥇', '🥈', '🥉']
    
    for idx, user in enumerate(top_users):
        m = medal[idx] if idx < 3 else f"{idx+1}."
        text += f"{m} {user[0]} — {user[1]} Coin\n"
        
    text += "\n💡 *K1-Coin yig'ish uchun darslarda faol bo'ling va vazifalarni bajaring!*"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================
print("K1 Ekotizimi Boti ishga tushdi...")
bot.polling(none_stop=True)