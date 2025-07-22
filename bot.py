import telebot
import sqlite3
import time
import threading
import random
from datetime import datetime
from keep_alive import keep_alive
import os
import shutil

bot = telebot.TeleBot("6320148381:AAGv3DhPwHV9_KmOV5oC9PHCto6cQd5M808")  # Thay bằng token thật
ADMIN_IDS = [5736655322]  # Thay bằng Telegram user ID của bạn

# Kết nối SQLite
conn = sqlite3.connect("game.db", check_same_thread=False)
cur = conn.cursor()

# Tạo bảng nếu chưa có
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS requests (
    user_id INTEGER,
    username TEXT,
    amount INTEGER,
    created_at INTEGER
)''')
conn.commit()

# Lệnh /addme <số tiền>
@bot.message_handler(commands=['addme'])
def add_me(message):
    try:
        amount = int(message.text.split()[1])
        user_id = message.from_user.id
        username = message.from_user.username or ""
        created_at = int(time.time())

        cur.execute("INSERT INTO requests VALUES (?, ?, ?, ?)", (user_id, username, amount, created_at))
        conn.commit()
        bot.reply_to(message, "✅ Đã gửi yêu cầu nạp. Admin sẽ duyệt sớm.")
    except:
        bot.reply_to(message, "❌ Sai cú pháp. Dùng: /addme <số tiền>")

# Admin duyệt nạp
@bot.message_handler(commands=['approve'])
def approve(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(message.text.split()[1])
        cur.execute("SELECT amount FROM requests WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return bot.reply_to(message, "❌ Không tìm thấy yêu cầu.")

        amount = row[0]
        cur.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, "", 0))
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        cur.execute("DELETE FROM requests WHERE user_id = ?", (user_id,))
        conn.commit()
        bot.reply_to(message, f"✅ Đã cộng {amount:,}đ cho {user_id}")
    except:
        bot.reply_to(message, "❌ Sai cú pháp. Dùng: /approve <user_id>")

# Người chơi đặt cược
bets = []

@bot.message_handler(commands=['bet'])
def place_bet(message):
    try:
        _, number, amount = message.text.split()
        number = int(number)
        amount = int(amount)
        user_id = message.from_user.id
        username = message.from_user.username or ""

        if number < 3 or number > 17:
            return bot.reply_to(message, "⚠️ Chỉ cược từ 3 đến 17.")

        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < amount:
            return bot.reply_to(message, "❌ Không đủ tiền.")

        bets.append((user_id, username, number, amount))
        bot.reply_to(message, f"🎯 Bạn đã cược {amount:,}đ vào số {number}")
    except:
        bot.reply_to(message, "❌ Sai cú pháp. Dùng: /bet <số> <tiền>")

# Roll tự động mỗi 30 giây
def roll_dice():
    while True:
        time.sleep(30)
        if bets:
            dice = [random.randint(1, 6) for _ in range(3)]
            total = sum(dice)
            winners = []

            for user_id, username, guess, amount in bets:
                if guess == total:
                    prize = amount * 5
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user_id))
                    winners.append((username, prize))
                else:
                    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))

            conn.commit()

            msg = f"🎲 Kết quả: {dice} = {total}\n\n"
            if winners:
                msg += "🏆 Người thắng:\n"
                for u, p in winners:
                    name = f"@{u}" if u else "Ẩn danh"
                    msg += f"{name}: +{p:,}đ\n"
            else:
                msg += "Không ai đoán đúng 😢"

            for admin_id in ADMIN_IDS:
                bot.send_message(admin_id, msg)
            bets.clear()

threading.Thread(target=roll_dice, daemon=True).start()

# Xoá yêu cầu nạp sau 24h
def cleanup_requests():
    while True:
        time.sleep(3600)
        now = int(time.time())
        cur.execute("DELETE FROM requests WHERE ? - created_at > 86400", (now,))
        conn.commit()

threading.Thread(target=cleanup_requests, daemon=True).start()

# Tự động backup game.db mỗi 24h
def auto_backup():
    while True:
        time.sleep(86400)  # 24h
        now = datetime.now()
        if not os.path.exists("backup"):
            os.makedirs("backup")
        filename = now.strftime("backup/game_%Y-%m-%d_%H-%M.db")
        shutil.copyfile("game.db", filename)

threading.Thread(target=auto_backup, daemon=True).start()

# Bảng xếp hạng
@bot.message_handler(commands=['top'])
def top_players(message):
    cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows:
        return bot.reply_to(message, "❌ Chưa có người chơi nào.")
    msg = "🏆 Bảng xếp hạng:\n\n"
    for i, (username, balance) in enumerate(rows, 1):
        name = f"@{username}" if username else f"Người chơi {i}"
        msg += f"{i}. {name} – {balance:,}đ\n"
    bot.reply_to(message, msg)

# Lệnh /help
@bot.message_handler(commands=['help'])
def help_cmd(message):
    msg = (
        "<b>🎮 Hướng dẫn chơi tài xỉu:</b>\n\n"
        "• /bet <số> <tiền> – Cược từ 3 đến 17\n"
        "• /addme <tiền> – Gửi yêu cầu nạp tiền\n"
        "• /top – Xem bảng xếp hạng\n"
        "• /help – Xem hướng dẫn\n\n"
        "⏱ Mỗi 30 giây bot sẽ roll xúc xắc tự động!"
    )
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

# Khởi động bot
keep_alive()
bot.infinity_polling()
