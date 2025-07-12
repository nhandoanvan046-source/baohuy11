"
import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from keep_alive import keep_alive

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 123456789)

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
    admins = load_json("admins.json")
    return str(user_id) in admins or user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Chào mừng bạn đến shop acc Liên Quân!\n\n"
        "/random - Mua acc ngẫu nhiên\n"
        "/myacc - Xem acc đã mua\n"
        "/sodu - Xem số dư\n"
        "/nap <sotien> - Yêu cầu nạp tiền\n\n"
        "🔐 Admin:\n"
        "/addacc <taikhoan> <matkhau> - Thêm acc\n"
        "/delacc <id> - Xóa acc\n"
        "/stats - Xem thống kê\n"
        "/cong <user_id> <sotien> - Cộng tiền\n"
        "/tru <user_id> <sotien> - Trừ tiền\n"
        "/addadmin <user_id> - Thêm admin"
    )

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_json('balances.json')
    user_id = str(update.message.from_user.id)
    balance = balances.get(user_id, 0)
    await update.message.reply_text(f"💰 Số dư: {balance} VND")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /nap <sotien>")
        return
    try:
        sotien = int(context.args[0])
    except:
        await update.message.reply_text("Số tiền không hợp lệ!")
        return
    user_id = str(update.message.from_user.id)
    pending = load_json('pending.json')
    pending[user_id] = sotien
    save_json('pending.json', pending)
    await update.message.reply_text(
        f"📲 STK: 0971487462\n🏦 MB Bank\n🖋 Nội dung: {user_id}\n💰 Số tiền: {sotien} VND\nGửi ảnh chuyển khoản để admin duyệt."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "Không có username"
    pending = load_json('pending.json')
    if user_id not in pending:
        await update.message.reply_text("Bạn chưa dùng lệnh /nap")
        return
    sotien = pending[user_id]
    buttons = [[
        InlineKeyboardButton("✔ Duyệt", callback_data=f"duyet_{user_id}_{sotien}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"tu_choi_{user_id}")
    ]]
    markup = InlineKeyboardMarkup(buttons)
    await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💰 Yêu cầu nạp: {sotien} VND\n👤 ID: {user_id}\n👑 @{username}", reply_markup=markup)
    await update.message.reply_text("⏳ Đã gửi ảnh cho admin, vui lòng chờ duyệt!")

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
        await query.edit_message_text(f"✅ Đã duyệt nạp {sotien} VND cho {user_id}")
        await context.bot.send_message(
            chat_id=int(user_id), 
            text=(
                f"🎉 Nạp tiền thành công!\n"
                f"+ {sotien} VND đã được cộng vào tài khoản.\n"
                f"💰 Kiểm tra số dư bằng lệnh /sodu."
            )
        )
    elif data.startswith("tu_choi_"):
        _, user_id = data.split("_")
        pending = load_json('pending.json')
        if user_id in pending:
            del pending[user_id]
            save_json('pending.json', pending)
        await query.edit_message_text(f"❌ Đã từ chối yêu cầu nạp của {user_id}")
        await context.bot.send_message(chat_id=int(user_id), text="❌ Yêu cầu nạp bị từ chối.")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ super admin được thêm admin!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /addadmin <user_id>")
        return
    user_id = context.args[0]
    admins = load_json("admins.json")
    if user_id in admins:
        await update.message.reply_text("User đã là admin!")
    else:
        admins[user_id] = True
        save_json("admins.json", admins)
        await update.message.reply_text(f"✅ Đã thêm admin {user_id}")
        await context.bot.send_message(chat_id=int(user_id), text="🎉 Bạn đã được cấp quyền admin!")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Không có quyền!")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /tru <user_id> <sotien>")
        return
    user_id = str(context.args[0])
    try:
        sotien = int(context.args[1])
    except:
        await update.message.reply_text("Số tiền không hợp lệ")
        return
    balances = load_json('balances.json')
    if balances.get(user_id, 0) < sotien:
        await update.message.reply_text("❌ Không đủ tiền!")
        return
    balances[user_id] -= sotien
    save_json('balances.json', balances)
    accs = load_json('acc.json')
    owned = [f"{a['taikhoan']} / {a['matkhau']}" for a in accs if a.get('owner_id') == int(user_id)]
    info = "\n📦 Acc đã mua:\n" + "\n".join(owned) if owned else ""
    await update.message.reply_text(f"✅ Đã trừ {sotien} VND từ {user_id}")
    await context.bot.send_message(chat_id=int(user_id), text=f"⚠️ Bạn đã bị trừ {sotien} VND bởi admin.{info}")

async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    balances = load_json('balances.json')
    accounts = load_json('acc.json')

    balance = balances.get(user_id, 0)
    price = 2000
    price_str = f"{price:,}".replace(",", ".")
    balance_str = f"{balance:,}".replace(",", ".")
    available = [a for a in accounts if a['trangthai'] == 'chua_ban']

    if not available:
        await update.message.reply_text("🚫 Hiện không còn acc nào để bán.")
        return

    if balance < price:
        await update.message.reply_text(
            f"❌ Bạn không đủ tiền!\n"
            f"💸 Giá mỗi acc: {price_str} VND\n"
            f"💰 Số dư hiện tại: {balance_str} VND"
        )
        return

    acc = random.choice(available)
    balances[user_id] = balance - price
    acc['trangthai'] = 'da_ban'
    acc['owner_id'] = int(user_id)
    save_json('balances.json', balances)
    save_json('acc.json', accounts)

    new_balance_str = f"{balances[user_id]:,}".replace(",", ".")

    await update.message.reply_text(
        f"🎁 Bạn đã mua acc với giá {price_str} VND:\n"
        f"🔑 Tài khoản: {acc['taikhoan']}\n"
        f"🔐 Mật khẩu: {acc['matkhau']}\n"
        f"💰 Số dư còn lại: {new_balance_str} VND"
    )

keep_alive()
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('sodu', sodu))
app.add_handler(CommandHandler('nap', nap))
app.add_handler(CommandHandler('tru', tru))
app.add_handler(CommandHandler('addadmin', addadmin))
app.add_handler(CommandHandler('random', random))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(CallbackQueryHandler(duyet_tien_callback))
print("✅ Bot đang chạy...")
app.run_polling()
