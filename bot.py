import json
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from keep_alive import keep_alive
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN hoặc ADMIN_ID chưa được cấu hình trong file .env!")
ADMIN_ID = int(ADMIN_ID)

FILE_BALANCES = "balances.json"
FILE_PENDING = "pending.json"
FILE_ACCOUNTS = "acc.json"
FILE_ADMINS = "admins.json"

def load_json(filename, default=None):
    default = default or {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_admins():
    admins = load_json(FILE_ADMINS, default=[])
    if ADMIN_ID not in admins:
        admins.append(ADMIN_ID)
        save_json(FILE_ADMINS, admins)
    return admins

def is_admin(user_id):
    return user_id in get_admins()

async def send_shop_info(chat_id, bot):
    msg = (
        "🎮 *SHOP ACC LIÊN QUÂN*\n\n"
        "🔄 /random - Mua acc ngẫu nhiên\n"
        "🆔 /mua <id> - Mua acc theo ID\n"
        "📦 /myacc - Xem acc đã mua\n"
        "💰 /sodu - Kiểm tra số dư\n"
        "💳 /nap <sotien> - Nạp tiền\n"
        "📊 /stats - Thống kê shop\n"
        "🏆 /top - Top 10 người có số dư cao nhất\n"
        "⚙️ /addadmin <user_id> - Thêm admin (chỉ admin chính)\n"
        "➕ /addacc - Thêm nhiều acc\n"
        "📥 /cong <user_id> <sotien>\n"
        "📤 /trutien <user_id> <sotien>\n"
    )
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_shop_info(update.effective_chat.id, ctx.bot)

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_shop_info(update.effective_chat.id, ctx.bot)

async def sodu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    balances = load_json(FILE_BALANCES)
    user_id = str(update.effective_user.id)
    bal = balances.get(user_id, 0)
    await update.message.reply_text(f"💰 Số dư của bạn: {bal:,} VND")

async def nap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("❗ Cú pháp: /nap <sotien>")
    try:
        amount = int(ctx.args[0])
        if amount <= 0:
            raise ValueError()
    except:
        return await update.message.reply_text("❗ Số tiền không hợp lệ!")

    user_id = str(update.effective_user.id)
    pending = load_json(FILE_PENDING)
    pending[user_id] = amount
    save_json(FILE_PENDING, pending)

    msg = (
        f"💳 Vui lòng chuyển khoản:\n\n"
        f"- 📲 *STK:* `0971487462`\n"
        f"- 🏦 *Ngân hàng:* MB Bank\n"
        f"- 💬 *Nội dung:* `{user_id}`\n"
        f"- 💰 *Số tiền:* `{amount:,} VND`\n\n"
        "Sau đó gửi ảnh chuyển khoản vào bot để admin duyệt."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Không có username"
    pending = load_json(FILE_PENDING)
    if user_id not in pending:
        return await update.message.reply_text("❗ Bạn chưa yêu cầu nạp tiền bằng /nap!")

    amount = pending[user_id]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Duyệt {amount:,} VND", callback_data=f"duyet_{user_id}_{amount}"),
            InlineKeyboardButton(f"❌ Từ chối {amount:,} VND", callback_data=f"tuchoi_{user_id}_{amount}"),
        ]
    ])

    await ctx.bot.forward_message(ADMIN_ID, update.message.chat.id, update.message.message_id)
    await ctx.bot.send_message(
        ADMIN_ID,
        f"💰 *Yêu cầu nạp:* {amount:,} VND\n👤 *User ID:* {user_id}\n👑 *Username:* @{username}",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await update.message.reply_text("✅ Đã gửi ảnh nạp tiền cho admin. Vui lòng chờ duyệt!")

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("duyet_") or data.startswith("tuchoi_"):
        action, user_id, amount = data.split("_")
        amount = int(amount)
        pending = load_json(FILE_PENDING)
        if action == "duyet":
            balances = load_json(FILE_BALANCES)
            balances[user_id] = balances.get(user_id, 0) + amount
            save_json(FILE_BALANCES, balances)
            msg_user = f"✅ Admin đã duyệt nạp {amount:,} VND vào tài khoản bạn."
            msg_admin = f"✅ Đã cộng {amount:,} VND cho user {user_id}"
        else:
            msg_user = f"❌ Admin đã từ chối yêu cầu nạp {amount:,} VND của bạn."
            msg_admin = f"❌ Đã từ chối nạp tiền user {user_id}"
        pending.pop(user_id, None)
        save_json(FILE_PENDING, pending)
        await ctx.bot.send_message(int(user_id), msg_user)
        await query.edit_message_text(msg_admin)

async def random_acc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    balances = load_json(FILE_BALANCES)
    accounts = load_json(FILE_ACCOUNTS)
    user_id = str(update.effective_user.id)
    available = [a for a in accounts if a.get("trangthai") == "chua_ban"]
    if not available:
        return await update.message.reply_text("❌ Hết acc để random!")
    price = 1000
    if balances.get(user_id, 0) < price:
        return await update.message.reply_text("❌ Bạn không đủ tiền!")
    acc = random.choice(available)
    acc["trangthai"] = "da_ban"
    acc["owner_id"] = user_id
    save_json(FILE_ACCOUNTS, accounts)
    balances[user_id] -= price
    save_json(FILE_BALANCES, balances)
    await update.message.reply_text(
        f"🎉 Bạn nhận acc:\n👤 `{acc['taikhoan']}`\n🔑 `{acc['matkhau']}`",
        parse_mode="Markdown"
    )

async def mua_acc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("📌 Cú pháp: /mua <id>")
    try:
        acc_id = int(ctx.args[0])
    except:
        return await update.message.reply_text("❗ ID không hợp lệ!")
    accounts = load_json(FILE_ACCOUNTS)
    balances = load_json(FILE_BALANCES)
    user_id = str(update.effective_user.id)
    for acc in accounts:
        if acc.get("id") == acc_id:
            if acc.get("trangthai") != "chua_ban":
                return await update.message.reply_text("❗ Acc đã được bán.")
            price = acc.get("gia", 1000)
            if balances.get(user_id, 0) < price:
                return await update.message.reply_text(f"❗ Bạn không đủ {price:,} VND để mua acc này.")
            acc["trangthai"] = "da_ban"
            acc["owner_id"] = user_id
            balances[user_id] -= price
            save_json(FILE_ACCOUNTS, accounts)
            save_json(FILE_BALANCES, balances)
            return await update.message.reply_text(
                f"🎉 Mua thành công acc:\n👤 `{acc['taikhoan']}`\n🔑 `{acc['matkhau']}`\n💰 Còn lại: {balances[user_id]:,} VND",
                parse_mode="Markdown"
            )
    await update.message.reply_text("❗ Không tìm thấy acc với ID đã nhập.")

async def myacc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    accounts = load_json(FILE_ACCOUNTS)
    user_id = str(update.effective_user.id)
    owned = [a for a in accounts if a.get("owner_id") == user_id]
    if not owned:
        return await update.message.reply_text("📭 Bạn chưa mua acc nào.")
    msg = "📦 *Tài khoản bạn đã mua:*\n\n"
    for i, acc in enumerate(owned, 1):
        msg += f"{i}. `{acc['taikhoan']}` / `{acc['matkhau']}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    balances = load_json(FILE_BALANCES)
    accounts = load_json(FILE_ACCOUNTS)
    total_users = len(balances)
    total_acc = len(accounts)
    unsold = sum(1 for a in accounts if a.get("trangthai") == "chua_ban")
    total_balance = sum(balances.values())
    msg = (
        f"📊 *Thống kê:*\n\n"
        f"👥 User có số dư: {total_users}\n"
        f"📦 Tổng acc: {total_acc}\n"
        f"🆓 Acc chưa bán: {unsold}\n"
        f"💰 Tổng số dư: {total_balance:,} VND"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    balances = load_json(FILE_BALANCES)
    if not balances:
        return await update.message.reply_text("Chưa có dữ liệu.")
    sorted_users = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 *Top 10 số dư cao nhất:*\n\n"
    for i, (uid, bal) in enumerate(sorted_users, 1):
        msg += f"{i}. `{uid}` — {bal:,} VND\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cong(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Bạn không phải admin.")
    if len(ctx.args) < 2:
        return await update.message.reply_text("Cú pháp: /cong <uid> <sotien>")
    uid, amount = ctx.args[0], int(ctx.args[1])
    balances = load_json(FILE_BALANCES)
    balances[uid] = balances.get(uid, 0) + amount
    save_json(FILE_BALANCES, balances)
    await update.message.reply_text(f"✅ Đã cộng {amount:,} VND cho {uid}")

async def trutien(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Bạn không phải admin.")
    if len(ctx.args) < 2:
        return await update.message.reply_text("Cú pháp: /trutien <uid> <sotien>")
    uid, amount = ctx.args[0], int(ctx.args[1])
    balances = load_json(FILE_BALANCES)
    if balances.get(uid, 0) < amount:
        return await update.message.reply_text("❌ User không đủ tiền")
    balances[uid] -= amount
    save_json(FILE_BALANCES, balances)
    await update.message.reply_text(f"✅ Đã trừ {amount:,} VND từ {uid}")

async def addadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Chỉ admin chính mới thêm được.")
    if not ctx.args:
        return await update.message.reply_text("Cú pháp: /addadmin <user_id>")
    new_admin = int(ctx.args[0])
    admins = get_admins()
    if new_admin in admins:
        return await update.message.reply_text("⚠️ Đã là admin.")
    admins.append(new_admin)
    save_json(FILE_ADMINS, admins)
    await update.message.reply_text(f"✅ Đã thêm admin `{new_admin}`", parse_mode="Markdown")

async def addacc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Bạn không phải admin.")
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        return await update.message.reply_text("Cú pháp: /addacc <tk mk>\n1 dòng 1 acc")
    accounts = load_json(FILE_ACCOUNTS)
    added, skipped = 0, 0
    max_id = max([a.get("id", 0) for a in accounts], default=0)
    for line in text.split("\n"):
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        tk, mk = parts[0], parts[1]
        if any(a["taikhoan"] == tk for a in accounts):
            skipped += 1
            continue
        max_id += 1
        accounts.append({"id": max_id, "taikhoan": tk, "matkhau": mk, "trangthai": "chua_ban"})
        added += 1
    save_json(FILE_ACCOUNTS, accounts)
    await update.message.reply_text(f"✅ Thêm {added} acc, bỏ qua {skipped} đã tồn tại.")

if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("random", random_acc))
    app.add_handler(CommandHandler("mua", mua_acc))
    app.add_handler(CommandHandler("myacc", myacc))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("cong", cong))
    app.add_handler(CommandHandler("trutien", trutien))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot đang chạy...")
    app.run_polling()
