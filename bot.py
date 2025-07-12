import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters)
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

keep_alive()
os.makedirs("data", exist_ok=True)
for file in ["acc.json", "user.json", "log.json", "duyet_log.json", "admins.json"]:
    if not os.path.exists(f"data/{file}"):
        with open(f"data/{file}", "w") as f:
            json.dump({} if "user" in file or "admins" in file else [], f)

load_json = lambda path: json.load(open(path))
save_json = lambda path, data: json.dump(data, open(path, "w"), indent=2)

def is_admin(uid):
    return uid == ADMIN_ID or str(uid) in load_json("data/admins.json")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Chào mừng đến với shop acc Liên Quân!\n\n"
        "🛒 Người dùng:\n/random - Mua acc random\n/myacc - Acc đã mua\n/sodu - Kiểm tra số dư\n/nap <sotien> - Nạp tiền\n/top - TOP người giàu\n\n"
        "🛠 Quản trị:\n/addacc <user> <pass>\n/delacc <id>\n/cong <uid> <sotien>\n/tru <uid> <sotien>\n/stats\n/addadmin <uid>"
    )

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_json("data/user.json")
    await update.message.reply_text(f"💰 Số dư của bạn: {users.get(uid, 0):,}đ")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /nap <sotien>")
        return
    sotien = context.args[0]
    uid = update.effective_user.id
    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản theo thông tin sau:\n\n"
        f"- 📲 STK: 0971487462\n- 🏦 Ngân hàng: MB Bank\n- 💬 Nội dung: {uid}\n- 💰 Số tiền: {sotien} VND\n\n"
        f"📸 Sau đó gửi ảnh chuyển khoản vào bot. Hệ thống sẽ tự duyệt."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = update.effective_user
    caption = update.message.caption

    if not caption or not caption.isdigit():
        await update.message.delete()
        return

    sotien = int(caption)
    users = load_json("data/user.json")
    logs = load_json("data/duyet_log.json")

    users[uid] = users.get(uid, 0) + sotien
    logs.append({"uid": uid, "status": "Auto", "amount": sotien, "time": datetime.now().isoformat()})

    save_json("data/user.json", users)
    save_json("data/duyet_log.json", logs)

    await update.message.reply_text(f"✅ Đã tự động cộng {sotien:,}đ vào tài khoản bạn!")

    photo = update.message.photo[-1].file_id
    text = (
        f"📥 Giao dịch mới auto duyệt:\n"
        f"👤 @{user.username or 'Không rõ'} | UID: `{uid}`\n"
        f"💰 Số tiền: {sotien:,}đ\n"
        f"🕒 {datetime.now().strftime('%H:%M:%S %d-%m-%Y')}"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=text, parse_mode="Markdown")

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
    users[uid] = users.get(uid, 0) - 2000
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
    if not users:
        await update.message.reply_text("📭 Chưa có người dùng nào nạp tiền.")
        return
    top_users = sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 Top người dùng giàu nhất:\n"
    for i, (uid, bal) in enumerate(top_users):
        msg += f"{i+1}. UID {uid} - {bal:,}đ\n"
    await update.message.reply_text(msg)

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /addacc <user> <pass>")
        return
    accs = load_json("data/acc.json")
    accs.append({"user": context.args[0], "pass": context.args[1]})
    save_json("data/acc.json", accs)
    await update.message.reply_text("✅ Đã thêm acc.")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /delacc <id>")
        return
    accs = load_json("data/acc.json")
    try:
        idx = int(context.args[0])
        if 0 <= idx < len(accs):
            accs.pop(idx)
            save_json("data/acc.json", accs)
            await update.message.reply_text("✅ Đã xoá acc.")
        else:
            await update.message.reply_text("❌ ID không hợp lệ.")
    except ValueError:
        await update.message.reply_text("❌ ID phải là số.")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /cong <uid> <sotien>")
        return
    uid, tien = context.args
    users = load_json("data/user.json")
    try:
        tien = int(tien)
        users[uid] = users.get(uid, 0) + tien
        save_json("data/user.json", users)
        await update.message.reply_text("✅ Đã cộng tiền.")
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /tru <uid> <sotien>")
        return
    uid, tien = context.args
    users = load_json("data/user.json")
    try:
        tien = int(tien)
        users[uid] = max(0, users.get(uid, 0) - tien)
        save_json("data/user.json", users)
        await update.message.reply_text("✅ Đã trừ tiền.")
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    await update.message.reply_text(f"📊 Còn {len(accs)} acc\n🧾 Đã bán: {len(log)}")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: /addadmin <uid>")
        return
    uid = context.args[0]
    admins = load_json("data/admins.json")
    admins[uid] = True
    save_json("data/admins.json", admins)
    await update.message.reply_text("✅ Đã thêm admin phụ.")

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
    print("🤖 Bot đang chạy...")
    app.run_polling()
    
