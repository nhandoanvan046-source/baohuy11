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

# === HÀM HỖ TRỢ ===
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

# === LỆNH NGƯỜI DÙNG ===
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
        "/addadmin <user_id> - Thêm admin"
    )

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    balances = load_json("balances.json")
    sodu = balances.get(user_id, 0)
    await update.message.reply_text(f"💰 Số dư hiện tại của bạn: {sodu} VND")

async def myacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    history = load_json("history.json")
    user_accs = history.get(user_id, [])

    if not user_accs:
        await update.message.reply_text("📭 Bạn chưa mua tài khoản nào.")
        return

    msg = "📦 Danh sách tài khoản bạn đã mua:\n\n"
    for idx, acc in enumerate(user_accs, 1):
        msg += f"{idx}. {acc}\n"
    await update.message.reply_text(msg)

async def random_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    balances = load_json("balances.json")
    acc_list = load_json("accounts.json")
    history = load_json("history.json")

    if not acc_list:
        await update.message.reply_text("🚫 Hết tài khoản để bán!")
        return

    price = 10000
    sodu = balances.get(user_id, 0)

    if sodu < price:
        await update.message.reply_text(f"❌ Bạn cần {price} VND để mua acc. Hiện tại bạn có {sodu} VND.")
        return

    acc_id, acc_data = random.choice(list(acc_list.items()))
    del acc_list[acc_id]

    balances[user_id] = sodu - price

    if user_id not in history:
        history[user_id] = []
    history[user_id].append(acc_data)

    save_json("balances.json", balances)
    save_json("accounts.json", acc_list)
    save_json("history.json", history)

    await update.message.reply_text(f"🎉 Bạn đã mua thành công 1 tài khoản:\n\n🆔 {acc_data}")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /nap <sotien>")
        return

    try:
        sotien = int(context.args[0])
    except:
        await update.message.reply_text("Số tiền phải là số!")
        return

    user_id = update.message.from_user.id
    pending = load_json('pending.json')
    pending[str(user_id)] = sotien
    save_json('pending.json', pending)

    await update.message.reply_text(
        f"Vui lòng chuyển khoản theo thông tin sau:\n\n"
        "📲 Số tài khoản: 0971487462\n"
        "🏦 Ngân hàng: MB Bank\n"
        f"💬 Nội dung chuyển khoản: {user_id}\n"
        f"💰 Số tiền: {sotien} VND\n\n"
        "Sau khi chuyển khoản, vui lòng gửi ảnh chuyển khoản vào đây."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Không có username"
    pending = load_json('pending.json')

    if str(user_id) not in pending:
        await update.message.reply_text("Bạn chưa yêu cầu nạp tiền! Vui lòng sử dụng lệnh /nap <sotien> trước.")
        return

    sotien = pending[str(user_id)]
    buttons = [[
        InlineKeyboardButton("✔ Duyệt", callback_data=f"duyet_{user_id}_{sotien}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"tuchoi_{user_id}")
    ]]
    markup = InlineKeyboardMarkup(buttons)

    await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💰 Yêu cầu nạp: {sotien} VND\n👤 User ID: {user_id}\n👑 Username: {username}", reply_markup=markup)
    await update.message.reply_text("Đã gửi ảnh nạp tiền cho admin. Vui lòng chờ duyệt!")

async def callback_duyet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Bạn không có quyền duyệt yêu cầu này!")
        return

    data = query.data
    if data.startswith("duyet_"):
        _, user_id, sotien = data.split("_")
        sotien = int(sotien)
        balances = load_json("balances.json")
        balances[user_id] = balances.get(user_id, 0) + sotien
        save_json("balances.json", balances)

        pending = load_json("pending.json")
        if user_id in pending:
            del pending[user_id]
            save_json("pending.json", pending)

        await query.edit_message_text(f"✅ Đã duyệt nạp {sotien} VND cho {user_id}")
        await context.bot.send_message(chat_id=int(user_id), text=f"🎉 Bạn đã được cộng {sotien} VND vào tài khoản!")

    elif data.startswith("tuchoi_"):
        _, user_id = data.split("_")
        pending = load_json("pending.json")
        if user_id in pending:
            del pending[user_id]
            save_json("pending.json", pending)
        await query.edit_message_text(f"❌ Đã từ chối yêu cầu nạp của {user_id}")
        await context.bot.send_message(chat_id=int(user_id), text="❌ Yêu cầu nạp tiền của bạn đã bị từ chối.")

# === LỆNH QUẢN TRỊ ===
async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Chỉ super admin mới được thêm admin!")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /addadmin <user_id>")
        return

    user_id = str(context.args[0])
    admins = load_json("admins.json")
    admins[user_id] = True
    save_json("admins.json", admins)

    await update.message.reply_text(f"✅ Đã thêm admin mới: {user_id}")

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Bạn không có quyền thêm tài khoản!")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /addacc <taikhoan> <matkhau>")
        return

    taikhoan = context.args[0]
    matkhau = context.args[1]
    acc = f"{taikhoan}|{matkhau}"

    accounts = load_json("accounts.json")
    new_id = str(max([int(k) for k in accounts.keys()], default=0) + 1)
    accounts[new_id] = acc
    save_json("accounts.json", accounts)

    await update.message.reply_text(f"✅ Đã thêm tài khoản #{new_id}: `{acc}`", parse_mode="Markdown")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Bạn không có quyền xóa tài khoản!")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Cú pháp: /delacc <id>")
        return

    acc_id = context.args[0]
    accounts = load_json("accounts.json")

    if acc_id not in accounts:
        await update.message.reply_text("❌ Không tìm thấy tài khoản với ID này.")
        return

    acc = accounts[acc_id]
    del accounts[acc_id]
    save_json("accounts.json", accounts)

    await update.message.reply_text(f"🗑 Đã xóa tài khoản #{acc_id}: `{acc}`", parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Bạn không có quyền xem thống kê!")
        return

    accounts = load_json("accounts.json")
    history = load_json("history.json")
    balances = load_json("balances.json")

    total_acc = len(accounts)
    total_users = len(balances)
    total_bought = sum(len(v) for v in history.values())

    msg = (
        "📊 Thống kê hệ thống:\n\n"
        f"📦 Tài khoản còn lại: {total_acc}\n"
        f"🛒 Tài khoản đã bán: {total_bought}\n"
        f"👥 Người dùng có số dư: {total_users}\n"
    )
    await update.message.reply_text(msg)

# === KHỞI CHẠY BOT ===
if __name__ == '__main__':
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('sodu', sodu))
    app.add_handler(CommandHandler('myacc', myacc))
    app.add_handler(CommandHandler('random', random_acc))
    app.add_handler(CommandHandler('nap', nap))
    app.add_handler(CommandHandler('addadmin', addadmin))
    app.add_handler(CommandHandler('addacc', addacc))
    app.add_handler(CommandHandler('delacc', delacc))
    app.add_handler(CommandHandler('stats', stats))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(callback_duyet))

    print("Bot đang chạy...")
    app.run_polling()
