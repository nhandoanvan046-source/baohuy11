import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

keep_alive()

# ========== Khởi tạo ==========
os.makedirs("data", exist_ok=True)
for f in ["acc.json", "user.json", "log.json", "duyet_log.json", "admins.json"]:
    path = f"data/{f}"
    if not os.path.exists(path):
        with open(path, "w") as fp:
            json.dump({} if "user" in f or "admins" in f else [], fp)

os.makedirs("data/cache_img", exist_ok=True)

# ========== Hàm tiện ích ==========
def load_json(path): return json.load(open(path, "r"))
def save_json(path, data): json.dump(data, open(path, "w"), indent=2)
def is_admin(uid):
    if uid == ADMIN_ID: return True
    admins = load_json("data/admins.json")
    return str(uid) in admins

# ========== Giao diện ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Chào mừng đến với shop acc Liên Quân!\n\n"
        "🛒 Người dùng:\n"
        "/random - Mua acc random\n"
        "/myacc - Acc đã mua\n"
        "/sodu - Kiểm tra số dư\n"
        "/nap <sotien> - Nạp tiền\n"
        "/top - TOP người giàu\n\n"
        "🛠 Quản trị:\n"
        "/addacc <user> <pass>\n"
        "/delacc <id>\n"
        "/cong <uid> <sotien>\n"
        "/tru <uid> <sotien>\n"
        "/stats - Thống kê\n"
        "/addadmin <uid>"
    )

# ========== Người dùng ==========
async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_json("data/user.json")
    await update.message.reply_text(f"💰 Số dư của bạn: {users.get(uid, 0):,}đ")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /nap <sotien>")
        return
    sotien = context.args[0]
    await update.message.reply_text("📤 Vui lòng gửi ảnh chuyển khoản với caption: \n" + sotien)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    caption = update.message.caption or "Không rõ"
    file_id = update.message.photo[-1].file_id
    file = await context.bot.get_file(file_id)
    path = f"data/cache_img/{uid}.jpg"
    await file.download_to_drive(path)
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"duyet:{uid}:{caption}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"huy:{uid}")
        ]
    ])
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id,
        caption=f"🧾 Yêu cầu nạp tiền từ {uid} - {caption}", reply_markup=markup)
    await update.message.reply_text("✅ Đã gửi yêu cầu. Vui lòng chờ duyệt.")

async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_json("data/user.json")
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    
    if users.get(uid, 0) < 2000:
        await update.message.reply_text("⚠️ Bạn cần 2.000đ để mua acc.")
        return
    if not accs:
        await update.message.reply_text("📦 Hết acc trong kho.")
        return

    acc = accs.pop(0)
    users[uid] -= 2000
    log.append({"uid": uid, "acc": acc})
    
    save_json("data/user.json", users)
    save_json("data/acc.json", accs)
    save_json("data/log.json", log)

    await update.message.reply_text(f"🎉 Mua thành công!\n🔐 Acc: `{acc['user']}|{acc['pass']}`", parse_mode='Markdown')

async def myacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    log = load_json("data/log.json")
    accs = [f"{i+1}. {l['acc']['user']}|{l['acc']['pass']}" for i, l in enumerate(log) if l['uid'] == uid]
    if not accs:
        await update.message.reply_text("📭 Bạn chưa mua acc nào.")
    else:
        await update.message.reply_text("🗂 Acc đã mua:\n" + "\n".join(accs))

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_json("data/user.json")
    top_users = sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 Top người dùng giàu nhất:\n"
    for i, (uid, bal) in enumerate(top_users):
        msg += f"{i+1}. UID {uid} - {bal:,}đ\n"
    await update.message.reply_text(msg)

# ========== Admin ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("duyet"):
        _, uid, sotien = data.split(":")
        users = load_json("data/user.json")
        logs = load_json("data/duyet_log.json")
        users[uid] = users.get(uid, 0) + int(sotien)
        logs.append({"uid": uid, "status": "Duyệt", "amount": int(sotien)})
        save_json("data/user.json", users)
        save_json("data/duyet_log.json", logs)
        await context.bot.send_message(chat_id=int(uid), text=f"✅ Admin đã duyệt nạp {sotien}đ!")
        await query.edit_message_caption(f"✅ Đã duyệt nạp {sotien}đ cho UID {uid}")
    elif data.startswith("huy"):
        _, uid = data.split(":")
        await context.bot.send_message(chat_id=int(uid), text="❌ Yêu cầu nạp bị từ chối.")
        await query.edit_message_caption("❌ Đã từ chối yêu cầu nạp tiền.")

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Dùng: /addacc <user> <pass>")
        return
    accs = load_json("data/acc.json")
    accs.append({"user": context.args[0], "pass": context.args[1]})
    save_json("data/acc.json", accs)
    await update.message.reply_text("✅ Đã thêm acc.")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng: /delacc <id>")
        return
    accs = load_json("data/acc.json")
    try:
        idx = int(context.args[0]) - 1
        acc = accs.pop(idx)
        save_json("data/acc.json", accs)
        await update.message.reply_text(f"✅ Đã xoá acc: {acc['user']}")
    except:
        await update.message.reply_text("❌ Không tìm thấy acc.")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ Dùng: /cong <uid> <sotien>")
        return
    uid, amount = context.args
    users = load_json("data/user.json")
    users[uid] = users.get(uid, 0) + int(amount)
    save_json("data/user.json", users)
    await update.message.reply_text(f"✅ Đã cộng {amount}đ cho UID {uid}.")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ Dùng: /tru <uid> <sotien>")
        return
    uid, amount = context.args
    users = load_json("data/user.json")
    users[uid] = max(users.get(uid, 0) - int(amount), 0)
    save_json("data/user.json", users)
    await update.message.reply_text(f"✅ Đã trừ {amount}đ của UID {uid}.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    users = load_json("data/user.json")
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    total_bal = sum(users.values())
    await update.message.reply_text(
        f"📊 Thống kê:\n- Người dùng: {len(users)}\n- Số dư tổng: {total_bal:,}đ\n"
        f"- Acc còn: {len(accs)}\n- Acc đã bán: {len(log)}"
    )

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng: /addadmin <uid>")
        return
    uid = context.args[0]
    admins = load_json("data/admins.json")
    admins[uid] = True
    save_json("data/admins.json", admins)
    await update.message.reply_text(f"✅ Đã thêm admin UID {uid}.")

# ========== Khởi chạy ==========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("random", random))
    app.add_handler(CommandHandler("myacc", myacc))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(CommandHandler("delacc", delacc))
    app.add_handler(CommandHandler("cong", cong))
    app.add_handler(CommandHandler("tru", tru))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Bot đang chạy...")
    app.run_polling()
