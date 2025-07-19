import telebot
from telebot import types
import json
import os

API_TOKEN = '6320148381:AAGCb3fXaCVSW6Gu4ho3PBLN4RV__hDyxk0'
bot = telebot.TeleBot(API_TOKEN)
ADMIN_IDS = [5736655322]  # Thay bằng ID admin thật

# File lưu cảnh cáo và video
WARN_FILE = 'warns.json'
VIDEO_FILE = 'video.txt'
CAPTCHA_FILE = 'captcha.json'

if not os.path.exists(WARN_FILE):
    with open(WARN_FILE, 'w') as f:
        json.dump({}, f)

if not os.path.exists(CAPTCHA_FILE):
    with open(CAPTCHA_FILE, 'w') as f:
        json.dump({"enabled": False}, f)

def is_admin(message):
    return message.from_user.id in ADMIN_IDS

def load_warns():
    with open(WARN_FILE) as f:
        return json.load(f)

def save_warns(data):
    with open(WARN_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@bot.message_handler(commands=['setvideo'])
def set_video(message):
    if not is_admin(message):
        return
    if message.reply_to_message and message.reply_to_message.video:
        file_id = message.reply_to_message.video.file_id
        with open(VIDEO_FILE, 'w') as f:
            f.write(file_id)
        bot.reply_to(message, "✅ Video uptime đã được lưu.")
    else:
        bot.reply_to(message, "Vui lòng reply một video để lưu.")

@bot.message_handler(commands=['getvideo'])
def get_video(message):
    if os.path.exists(VIDEO_FILE):
        with open(VIDEO_FILE) as f:
            bot.send_video(message.chat.id, f.read())
    else:
        bot.reply_to(message, "Chưa có video uptime nào.")

@bot.message_handler(commands=['sendvideo'])
def send_video(message):
    if not is_admin(message):
        return
    if os.path.exists(VIDEO_FILE):
        with open(VIDEO_FILE) as f:
            bot.send_video(message.chat.id, f.read())
    else:
        bot.reply_to(message, "Chưa có video uptime nào.")

@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not is_admin(message):
        return
    if not message.reply_to_message:
        return bot.reply_to(message, "Hãy reply người cần cảnh cáo.")
    user_id = str(message.reply_to_message.from_user.id)
    warns = load_warns()
    warns[user_id] = warns.get(user_id, 0) + 1
    save_warns(warns)
    if warns[user_id] >= 3:
        bot.kick_chat_member(message.chat.id, int(user_id))
        bot.reply_to(message, f"🚫 Người dùng đã bị ban do nhận 3 cảnh cáo.")
    else:
        bot.reply_to(message, f"⚠️ Đã cảnh cáo {warns[user_id]}/3.")

@bot.message_handler(commands=['warnings'])
def show_warnings(message):
    if not is_admin(message):
        return
    if not message.reply_to_message:
        return bot.reply_to(message, "Hãy reply người cần kiểm tra.")
    user_id = str(message.reply_to_message.from_user.id)
    warns = load_warns()
    count = warns.get(user_id, 0)
    bot.reply_to(message, f"⚠️ Người này có {count}/3 cảnh cáo.")

@bot.message_handler(commands=['resetwarns'])
def reset_warnings(message):
    if not is_admin(message):
        return
    if not message.reply_to_message:
        return bot.reply_to(message, "Hãy reply người cần xóa cảnh cáo.")
    user_id = str(message.reply_to_message.from_user.id)
    warns = load_warns()
    if user_id in warns:
        del warns[user_id]
        save_warns(warns)
        bot.reply_to(message, "✅ Đã xóa cảnh cáo.")
    else:
        bot.reply_to(message, "❌ Người này không có cảnh cáo.")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if is_admin(message) and message.reply_to_message:
        bot.kick_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message, "🚫 Đã ban người dùng.")

@bot.message_handler(commands=['kick'])
def kick_user(message):
    if is_admin(message) and message.reply_to_message:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message, "👢 Đã kick người dùng.")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if is_admin(message) and message.reply_to_message:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=types.ChatPermissions(can_send_messages=False))
        bot.reply_to(message, "🔇 Đã tắt tiếng người dùng.")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if is_admin(message) and message.reply_to_message:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=types.ChatPermissions(can_send_messages=True,
                                                                   can_send_media_messages=True,
                                                                   can_send_other_messages=True,
                                                                   can_add_web_page_previews=True))
        bot.reply_to(message, "🔊 Đã bỏ tắt tiếng.")

@bot.message_handler(commands=['lock'])
def lock_group(message):
    if is_admin(message):
        bot.set_chat_permissions(message.chat.id, types.ChatPermissions(can_send_messages=False))
        bot.reply_to(message, "🔒 Nhóm đã bị khóa.")

@bot.message_handler(commands=['unlock'])
def unlock_group(message):
    if is_admin(message):
        bot.set_chat_permissions(message.chat.id, types.ChatPermissions(can_send_messages=True,
                                                                         can_send_media_messages=True,
                                                                         can_send_other_messages=True,
                                                                         can_add_web_page_previews=True))
        bot.reply_to(message, "🔓 Nhóm đã được mở khóa.")

@bot.message_handler(commands=['captcha'])
def toggle_captcha(message):
    if not is_admin(message):
        return
    with open(CAPTCHA_FILE, 'r') as f:
        data = json.load(f)
    data["enabled"] = not data["enabled"]
    with open(CAPTCHA_FILE, 'w') as f:
        json.dump(data, f)
    status = "Bật" if data["enabled"] else "Tắt"
    bot.reply_to(message, f"✅ Đã {status} xác minh captcha (demo).")

from keep_alive import keep_alive
import threading

threading.Thread(target=keep_alive).start()
print("Bot is running...")
bot.polling()
