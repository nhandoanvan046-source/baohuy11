import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from keep_alive import keep_alive
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

def load_json(file):
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)
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

# ========= LỆNH NGƯỜI DÙNG =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Chào mừng đến với shop acc Liên Quân!

"
        "🛒 Người dùng:
"
        "/random - Mua acc random
"
        "/myacc - Acc đã mua
"
        "/sodu - Kiểm tra số dư
"
        "/nap <sotien> - Nạp tiền
"
        "/top - TOP người giàu

"
        "🛠 Quản trị:
"
        "/addacc <user> <pass>
"
        "/delacc <id>
"
        "/cong <uid> <sotien>
"
        "/tru <uid> <sotien>
"
        "/stats - Thống kê
"
        "/addadmin <uid>"
    )

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    balances = load_json("balances.json")
    await update.message.reply_text(f"💰 Số dư: {balances.get(uid, 0)} VND")

async def myacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    history = load_json("history.json")
    accs = history.get(uid, [])
    if not accs:
        return await update.message.reply_text("📭 Bạn chưa mua acc nào.")
    msg = "\n".join([f"{i+1}. {acc}" for i, acc in enumerate(accs)])
    await update.message.reply_text(f"📦 Acc đã mua:\n\n{msg}")

async def random_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    balances = load_json("balances.json")
    accs = load_json("accounts.json")
    history = load_json("history.json")
    price = 2000

    if not accs:
        return await update.message.reply_text("❌ Hết acc để bán.")
    if balances.get(uid, 0) < price:
        return await update.message.reply_text(f"❌ Cần {price} VND. Bạn có {balances.get(uid, 0)}.")

    acc_id, acc_data = random.choice(list(accs.items()))
    balances[uid] = balances.get(uid, 0) - price
    history.setdefault(uid, []).append(acc_data)
    del accs[acc_id]

    save_json("balances.json", balances)
    save_json("accounts.json", accs)
    save_json("history.json", history)

    user, pwd = acc_data.split('|')
    await update.message.reply_text(
        f"🎉 Mua thành công:\n👤 `{user}`\n🔐 `{pwd}`\n💰 Còn lại: {balances[uid]} VND", parse_mode="Markdown")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        return await update.message.reply_text("Cú pháp: /nap <sotien>")
    try:
        sotien = int(context.args[0])
    except:
        return await update.message.reply_text("Số tiền phải là số!")
    uid = str(update.message.from_user.id)
    pending = load_json("pending.json")
    pending[uid] = sotien
    save_json("pending.json", pending)
    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản theo thông tin sau:\n\n"
        f"- 📲 STK: 0971487462\n"
        f"- 🏦 Ngân hàng: MB Bank\n"
        f"- 💬 Nội dung: {uid}\n"
        f"- 💰 Số tiền: {sotien:,} VND\n\n"
        f"📸 Sau đó gửi ảnh chuyển khoản vào bot để admin duyệt."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    username = update.message.from_user.username or "Không có"
    pending = load_json("pending.json")
    if uid not in pending:
        return await update.message.reply_text("❌ Dùng /nap <sotien> trước khi gửi ảnh.")

    photo = update.message.photo[-1]
    if photo.file_size < 10000:
        return await update.message.reply_text("❌ Ảnh quá nhỏ hoặc mờ.")

    sotien = pending[uid]
    caption = (
        f"💰 Yêu cầu nạp: {sotien:,} VND\n"
        f"👤 User ID: {uid}\n"
        f"👑 Username: @{username}"
    )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✔ Duyệt", callback_data=f"duyet_{uid}_{sotien}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"tuchoi_{uid}")
    ]])
    await context.bot.send_photo(
        ADMIN_ID, photo.file_id,
        caption=caption,
        reply_markup=markup
    )
    await update.message.reply_text("✅ Đã gửi ảnh cho admin, vui lòng đợi duyệt!")

# ========= ADMIN =========
async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 2:
        return await update.message.reply_text("Dùng: /addacc <taikhoan> <matkhau>")
    acc = f"{context.args[0]}|{context.args[1]}"
    accs = load_json("accounts.json")
    accs[str(max(map(int, accs.keys()), default=0)+1)] = acc
    save_json("accounts.json", accs)
    await update.message.reply_text("✅ Đã thêm acc.")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    if len(context.args) < 1: return
    accs = load_json("accounts.json")
    if context.args[0] in accs:
        del accs[context.args[0]]
        save_json("accounts.json", accs)
        await update.message.reply_text("🗑 Đã xóa acc.")
    else:
        await update.message.reply_text("❌ ID không tồn tại.")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    try:
        uid, money = context.args[0], int(context.args[1])
    except:
        return await update.message.reply_text("Cú pháp: /cong <uid> <sotien>")
    balances = load_json("balances.json")
    balances[uid] = balances.get(uid, 0) + money
    save_json("balances.json", balances)
    await update.message.reply_text(f"✅ Đã cộng {money} VND cho {uid}")
    await context.bot.send_message(int(uid), f"💰 Bạn được cộng {money} VND.")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    try:
        uid, money = context.args[0], int(context.args[1])
    except:
        return await update.message.reply_text("Cú pháp: /tru <uid> <sotien>")
    balances = load_json("balances.json")
    if balances.get(uid, 0) < money:
        return await update.message.reply_text("❌ Không đủ tiền để trừ.")
    balances[uid] -= money
    save_json("balances.json", balances)
    await update.message.reply_text(f"✅ Đã trừ {money} VND.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id): return
    accs = load_json("accounts.json")
    history = load_json("history.json")
    balances = load_json("balances.json")
    msg = (f"📦 Còn: {len(accs)} acc\n"
           f"🛒 Đã bán: {sum(len(v) for v in history.values())}\n"
           f"👥 Người dùng: {len(balances)}")
    await update.message.reply_text(msg)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_json("balances.json")
    top10 = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 TOP 10 người giàu:\n"
    for i, (uid, vnd) in enumerate(top10, 1):
        try:
            member = await context.bot.get_chat(int(uid))
            name = f"@{member.username}" if member.username else f"ID ****{uid[-4:]}"
        except:
            name = f"ID ****{uid[-4:]}"
        msg += f"{i}. {name}: {vnd:,} VND\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    uid = context.args[0]
    admins = load_json("admins.json")
    admins[uid] = True
    save_json("admins.json", admins)
    await update.message.reply_text(f"✅ Đã thêm admin {uid}")

# ========= CALLBACK =========
async def callback_duyet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.strip()
    if not is_admin(query.from_user.id): return await query.edit_message_text("❌ Không có quyền")

    if data.startswith("duyet_"):
        _, uid, sotien = data.split("_")
        sotien = int(sotien)
        balances = load_json("balances.json")
        balances[uid] = balances.get(uid, 0) + sotien
        save_json("balances.json", balances)
        pending = load_json("pending.json")
        pending.pop(uid, None)
        save_json("pending.json", pending)
        await query.edit_message_text(f"✅ Duyệt nạp {sotien:,} VND cho {uid}")
        await context.bot.send_message(int(uid), f"🎉 Bạn đã được cộng {sotien:,} VND!")
    elif data.startswith("tuchoi_"):
        _, uid = data.split("_")
        pending = load_json("pending.json")
        pending.pop(uid, None)
        save_json("pending.json", pending)
        await query.edit_message_text(f"❌ Đã từ chối yêu cầu nạp của {uid}")
        await context.bot.send_message(int(uid), "❌ Yêu cầu nạp bị từ chối.")

# ========= CHẠY =========
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("myacc", myacc))
    app.add_handler(CommandHandler("random", random_acc))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(CommandHandler("delacc", delacc))
    app.add_handler(CommandHandler("cong", cong))
    app.add_handler(CommandHandler("tru", tru))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(callback_duyet))
    print("🤖 Bot đã chạy!")
    app.run_polling()
