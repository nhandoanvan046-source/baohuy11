import telebot
import sqlite3
import random
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive

bot = telebot.TeleBot("6320148381:AAGv3DhPwHV9_KmOV5oC9PHCto6cQd5M808")
ADMIN_IDS = [5736655322]  # Thay ID admin của bạn vào đây

conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS requests (user_id INTEGER, username TEXT, amount INTEGER, created_at INTEGER)")
conn.commit()

bets = {}
betting_open = True

# Tự động tung xúc xắc mỗi 30 giây
def auto_roll():
    global bets
    while True:
        time.sleep(30)
        if bets:
            total = sum(random.randint(1, 6) for _ in range(3))
            winners = [uid for uid, v in bets.items() if v['choice'] == total]
            for uid in winners:
                payout = bets[uid]['amount'] * 3
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, uid))
            conn.commit()

            msg = f"🎲 Kết quả: {total}\n👥 Người chơi: {len(bets)}\n"
            if winners:
                msg += "🎉 Thắng:\n" + "\n".join([f"- {uid}" for uid in winners])
            else:
                msg += "❌ Không ai thắng!"
            for uid in bets:
                try: bot.send_message(uid, msg)
                except: pass
            bets = {}

threading.Thread(target=auto_roll, daemon=True).start()

# Xóa yêu cầu sau 24h
def cleanup_expired_requests():
    now = int(time.time())
    cur.execute("DELETE FROM requests WHERE created_at < ?", (now - 86400,))
    conn.commit()

@bot.message_handler(commands=["bet"])
def place_bet(message):
    args = message.text.split()
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        return bot.reply_to(message, "/bet <3-17> <số tiền>")

    choice = int(args[1])
    amount = int(args[2])
    if not (3 <= choice <= 17):
        return bot.reply_to(message, "🎲 Chọn số từ 3 đến 17!")

    user_id = message.from_user.id
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] < amount:
        return bot.reply_to(message, "❌ Bạn không đủ tiền!")

    bets[user_id] = {"choice": choice, "amount": amount}
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    bot.reply_to(message, f"✅ Đã cược {amount:,}đ vào số {choice}")

@bot.message_handler(commands=['addme'])
def handle_addme(message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return bot.reply_to(message, "❌ Dùng: /addme <số tiền>")

    amount = int(args[1])
    now = int(time.time())
    user = message.from_user

    cur.execute("DELETE FROM requests WHERE user_id = ?", (user.id,))
    cur.execute("INSERT INTO requests (user_id, username, amount, created_at) VALUES (?, ?, ?, ?)",
                (user.id, user.username or user.first_name, amount, now))
    conn.commit()

    bot.reply_to(message, "📨 Yêu cầu của bạn đã được gửi!")

@bot.message_handler(commands=['requests'])
def view_requests(message):
    if message.from_user.id not in ADMIN_IDS: return
    cleanup_expired_requests()
    cur.execute("SELECT * FROM requests LIMIT 10")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(message, "📭 Không có yêu cầu.")
    for uid, uname, amt, _ in rows:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_one_{uid}")
        )
        bot.send_message(message.chat.id, f"🧾 @{uname} xin {amt:,}đ", reply_markup=markup)

    bot.send_message(message.chat.id, "⬇️", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Duyệt tất cả", callback_data="approve_all")
    ))

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_one_"))
def approve_one(call):
    if call.from_user.id not in ADMIN_IDS: return
    uid = int(call.data.split("_")[-1])
    cur.execute("SELECT amount FROM requests WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    if not row: return bot.answer_callback_query(call.id, "❌ Hết hạn")
    amount = row[0]
    cur.execute("DELETE FROM requests WHERE user_id = ?", (uid,))
    cur.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (uid,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
    conn.commit()
    bot.answer_callback_query(call.id, "✅ Đã duyệt")
    try: bot.send_message(uid, f"💰 Bạn đã được cộng {amount:,}đ!")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "approve_all")
def approve_all(call):
    if call.from_user.id not in ADMIN_IDS: return
    cur.execute("SELECT * FROM requests")
    rows = cur.fetchall()
    for uid, _, amt, _ in rows:
        cur.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (uid,))
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
        try: bot.send_message(uid, f"💰 Bạn được cộng {amt:,}đ!")
        except: pass
    cur.execute("DELETE FROM requests")
    conn.commit()
    bot.answer_callback_query(call.id, "✅ Đã duyệt tất cả")

keep_alive()
bot.infinity_polling()
