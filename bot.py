import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from keep_alive import keep_alive
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
admin_id_env = os.getenv("ADMIN_ID")
if admin_id_env is None:
    raise Exception("ADMIN_ID chưa được cấu hình trong file .env!")
ADMIN_ID = int(admin_id_env)

# Load và lưu dữ liệu
def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(user_id):
    admin_list = load_json("admins.json")
    return str(user_id) in admin_list

# /addadmin <user_id>
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ super admin mới có quyền thêm admin.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /addadmin <user_id>")
        return

    user_id = context.args[0]
    admins = load_json("admins.json")
    if user_id in admins:
        await update.message.reply_text("User này đã là admin.")
        return

    admins[user_id] = True
    save_json("admins.json", admins)
    await update.message.reply_text(f"✅ Đã thêm admin: {user_id}")

    try:
        await context.bot.send_message(chat_id=int(user_id), text="🎉 Bạn đã được thêm làm admin!")
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Chào mừng bạn đến shop acc Liên Quân!\n\n"
        "/random - Mua acc ngẫu nhiên\n"
        "/myacc - Xem acc đã mua\n"
        "/sodu - Xem số dư\n"
        "/nap <sotien> - Yêu cầu nạp tiền\n\n"
        "Quản lý (Admin):\n"
        "/addacc <taikhoan> <matkhau> - Thêm acc\n"
        "/delacc <id> - Xóa acc\n"
        "/stats - Xem thống kê\n"
        "/cong <user_id> <sotien> - Cộng tiền cho người dùng\n"
        "/tru <user_id> <sotien> - Trừ tiền người dùng\n"
        "/addadmin <user_id> - Thêm admin mới"
    )

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_json('balances.json')
    user_id = str(update.message.from_user.id)
    balance = balances.get(user_id, 0)
    await update.message.reply_text(f"💰 Số dư hiện tại: {balance} VND")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /nap <sotien>")
        return
    try:
        sotien = int(context.args[0])
    except:
        await update.message.reply_text("Số tiền phải là số!")
        return
    user_id = str(update.message.from_user.id)
    pending = load_json('pending.json')
    pending[user_id] = sotien
    save_json('pending.json', pending)
    await update.message.reply_text(
        f"Vui lòng chuyển khoản:\n\n"
        "📲 STK: 0971487462\n"
        "🏦 Ngân hàng: MB Bank\n"
        f"🖬 Nội dung: {user_id}\n"
        f"💰 Số tiền: {sotien} VND\n\n"
        "Gửi ảnh chuyển khoản vào đây cho admin duyệt."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "Không có username"
    pending = load_json('pending.json')
    if user_id not in pending:
        await update.message.reply_text("Bạn chưa yêu cầu nạp tiền! /nap <sotien> trước.")
        return
    sotien = pending[user_id]
    buttons = [[
        InlineKeyboardButton("✔ Duyệt", callback_data=f"duyet_{user_id}_{sotien}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"tu_choi_{user_id}")
    ]]
    markup = InlineKeyboardMarkup(buttons)
    await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 Yêu cầu nạp: {sotien} VND\n👤 ID: {user_id}\n👑 @{username}",
        reply_markup=markup
    )
    await update.message.reply_text("Đã gửi ảnh cho admin, vui lòng chờ duyệt!")

async def duyet_tien_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Bạn không có quyền duyệt!")
        return
    data = query.data
    if data.startswith("duyet_"):
        _, user_id, sotien = data.split("_")
        sotien = int(sotien)
        balances = load_json('balances.json')
        balances[user_id] = balances.get(user_id, 0) + sotien
        save_json('balances.json', balances)
        pending = load_json('pending.json')
        if user_id in pending:
            del pending[user_id]
            save_json('pending.json', pending)
        await query.edit_message_text(f"✅ Đã duyệt nạp {sotien} VND cho user {user_id}")
        try:
            await context.bot.send_message(chat_id=int(user_id), text=f"🎉 Bạn đã được duyệt {sotien} VND!")
        except: pass
    elif data.startswith("tu_choi_"):
        _, user_id = data.split("_")
        pending = load_json('pending.json')
        if user_id in pending:
            del pending[user_id]
            save_json('pending.json', pending)
        await query.edit_message_text(f"❌ Đã từ chối yêu cầu nạp tiền của user {user_id}")
        try:
            await context.bot.send_message(chat_id=int(user_id), text="❌ Yêu cầu nạp bị từ chối.")
        except: pass

# Lệnh /tru để trừ tiền người dùng
async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Bạn không có quyền sử dụng lệnh này!")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /tru <user_id> <sotien>")
        return

    try:
        user_id = str(context.args[0])
        sotien = int(context.args[1])
    except:
        await update.message.reply_text("Sai định dạng, vui lòng kiểm tra lại!")
        return

    balances = load_json('balances.json')
    if user_id not in balances or balances[user_id] < sotien:
        await update.message.reply_text("❌ Không đủ tiền hoặc user không tồn tại.")
        return

    balances[user_id] -= sotien
    save_json('balances.json', balances)

    # Kiểm tra nếu user đã mua acc nào
    accounts = load_json('acc.json')
    bought = [acc for acc in accounts if acc.get('owner_id') == int(user_id)]
    acc_info = "\n\n📦 Acc đã mua:\n" + "\n".join(f"{acc['taikhoan']} / {acc['matkhau']}" for acc in bought) if bought else ""

    await update.message.reply_text(f"✅ Đã trừ {sotien} VND của user {user_id}.")
    try:
        await context.bot.send_message(
            chat_id=int(user_id), 
            text=f"⚠️ Tài khoản bạn đã bị trừ {sotien} VND bởi admin.{acc_info}"
        )
    except:
        pass

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('sodu', sodu))
    app.add_handler(CommandHandler('nap', nap))
    app.add_handler(CommandHandler('tru', tru))
    app.add_handler(CommandHandler('addadmin', addadmin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(duyet_tien_callback))

    print("Bot đang chạy...")
    app.run_polling()
