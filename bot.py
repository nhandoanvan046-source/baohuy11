import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ContextTypes, filters, ChatMemberHandler)
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# === Tạo thư mục & file cần thiết ===
os.makedirs("data", exist_ok=True)
for f in ["user.json", "acc.json", "log.json", "admins.json", "duyet_log.json", "pending.json"]:
    if not os.path.exists(f"data/{f}"):
        with open(f"data/{f}", "w") as file:
            json.dump({} if "user" in f or "admins" in f else [], file)

# === Load/save JSON ===
load_json = lambda path: json.load(open(path))
save_json = lambda path, data: json.dump(data, open(path, "w"), indent=2)

# === Check admin ===
def is_admin(uid):
    return uid == ADMIN_ID or str(uid) in load_json("data/admins.json")

# === LỆNH NGƯỜI DÙNG ===
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
        return await update.message.reply_text("⚠️ Dùng đúng cú pháp: /nap <sotien>")
    sotien = context.args[0]
    uid = update.effective_user.id
    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản theo thông tin sau:\n\n"
        f"- 📲 STK: 0971487462\n- 🏦 Ngân hàng: MB Bank\n- 💬 Nội dung: {uid}\n- 💰 Số tiền: {sotien} VND\n\n"
        f"📸 Sau đó gửi ảnh chuyển khoản vào bot. Ghi số tiền vào caption để tự duyệt."
    )

# === Gửi ảnh chuyển khoản ===
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = update.effective_user
    caption = update.message.caption
    photo_id = update.message.photo[-1].file_id

    if caption and caption.isdigit():
        sotien = int(caption)
        users = load_json("data/user.json")
        users[uid] = users.get(uid, 0) + sotien
        logs = load_json("data/duyet_log.json")
        logs.append({"uid": uid, "amount": sotien, "status": "Auto", "time": datetime.now().isoformat()})
        save_json("data/user.json", users)
        save_json("data/duyet_log.json", logs)
        await update.message.reply_text(f"✅ Đã cộng {sotien:,}đ vào tài khoản!")
        await context.bot.send_sticker(chat_id=uid, sticker="CAACAgUAAxkBAAEJyo5lgn-TGyazHhrbT-pZowABkKImZqAAAj0DAAKWAZhVIYyVMD-HdAE0BA")
        return

    pending = load_json("data/pending.json")
    tid = str(len(pending))
    pending[tid] = {"uid": uid, "photo_id": photo_id, "username": user.username or "Ẩn"}
    save_json("data/pending.json", pending)

    btns = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt 10k", callback_data=f"approve:{tid}:10000"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"deny:{tid}")
        ]
    ])
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=f"🧾 Giao dịch cần duyệt thủ công\n👤 @{user.username or 'Ẩn'} | UID: {uid}",
        reply_markup=btns
    )
    await update.message.reply_text("⏳ Giao dịch đang chờ admin duyệt")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    pending = load_json("data/pending.json")

    if data.startswith("approve"):
        _, tid, amount = data.split(":")
        if tid not in pending: return
        item = pending.pop(tid)
        users = load_json("data/user.json")
        users[item['uid']] = users.get(item['uid'], 0) + int(amount)
        save_json("data/user.json", users)
        save_json("data/pending.json", pending)
        await query.edit_message_caption(f"✅ Đã duyệt {amount}đ cho @{item['username']}")
        await context.bot.send_message(int(item['uid']), f"✅ Giao dịch {amount}đ đã được admin duyệt")
    elif data.startswith("deny"):
        _, tid = data.split(":")
        if tid not in pending: return
        item = pending.pop(tid)
        save_json("data/pending.json", pending)
        await query.edit_message_caption("❌ Giao dịch bị từ chối")
        await context.bot.send_message(int(item['uid']), "❌ Giao dịch đã bị từ chối")

async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_json("data/user.json")
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    if users.get(uid, 0) < 2000:
        return await update.message.reply_text("⚠️ Cần 2.000đ để mua acc")
    if not accs:
        return await update.message.reply_text("📦 Hết acc trong kho")
    acc = accs.pop(0)
    users[uid] = users.get(uid, 0) - 2000
    log.append({"uid": uid, "acc": acc})
    save_json("data/user.json", users)
    save_json("data/acc.json", accs)
    save_json("data/log.json", log)
    await update.message.reply_text(f"🔐 Acc: `{acc['user']}|{acc['pass']}`", parse_mode='Markdown')

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
    if not users: return await update.message.reply_text("📭 Chưa có dữ liệu")
    top_users = sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 Top người dùng:\n"
    for i, (uid, bal) in enumerate(top_users):
        msg += f"{i+1}. UID {uid} - {bal:,}đ\n"
    await update.message.reply_text(msg)

# === ADMIN ===
async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return
    accs = load_json("data/acc.json")
    accs.append({"user": context.args[0], "pass": context.args[1]})
    save_json("data/acc.json", accs)
    await update.message.reply_text("✅ Đã thêm acc")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1: return
    idx = int(context.args[0])
    accs = load_json("data/acc.json")
    if 0 <= idx < len(accs):
        accs.pop(idx)
        save_json("data/acc.json", accs)
        await update.message.reply_text("✅ Đã xoá acc")
    else:
        await update.message.reply_text("❌ ID không hợp lệ")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid, amount = context.args
    users = load_json("data/user.json")
    users[uid] = users.get(uid, 0) + int(amount)
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã cộng tiền")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid, amount = context.args
    users = load_json("data/user.json")
    users[uid] = max(0, users.get(uid, 0) - int(amount))
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã trừ tiền")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    await update.message.reply_text(f"📊 Còn {len(accs)} acc | Đã bán {len(log)}")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = context.args[0]
    admins = load_json("data/admins.json")
    admins[uid] = True
    save_json("data/admins.json", admins)
    await update.message.reply_text("✅ Đã thêm admin phụ")

# === CAPTCHA ===
new_users = {}

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.chat_member
    if m.new_chat_member.status != "member": return
    uid = m.from_user.id
    chat_id = m.chat.id
    new_users[uid] = datetime.now() + timedelta(minutes=1)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tôi không phải bot", callback_data=f"captcha:{uid}:{chat_id}")]])
    await context.bot.send_message(chat_id, f"👋 Chào mừng <a href='tg://user?id={uid}'>bạn</a>! Vui lòng xác minh trong 60s.", parse_mode='HTML', reply_markup=btn)

async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, uid, cid = q.data.split(":")
    if int(uid) != q.from_user.id: return await q.reply_text("❌ Không xác minh hộ người khác!")
    if int(uid) not in new_users: return await q.edit_message_text("❌ Quá hạn xác minh")
    del new_users[int(uid)]
    await q.edit_message_text("✅ Đã xác minh thành công")

async def check_kick(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    for uid, time in list(new_users.items()):
        if now > time:
            try:
                await context.bot.ban_chat_member(chat_id=context.job.chat_id, user_id=uid)
                await context.bot.unban_chat_member(chat_id=context.job.chat_id, user_id=uid)
                del new_users[uid]
            except: pass

# === KHỞI ĐỘNG ===
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
    app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_captcha))
    app.job_queue.run_repeating(check_kick, interval=10)
    print("🤖 Bot đang chạy...")
    app.run_polling()
    
