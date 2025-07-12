import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters)
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio
from PIL import Image
import pytesseract
import io
import re

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

keep_alive()
os.makedirs("data", exist_ok=True)
for file in ["acc.json", "user.json", "log.json", "duyet_log.json", "admins.json", "nap_pending.json"]:
    if not os.path.exists(f"data/{file}"):
        with open(f"data/{file}", "w") as f:
            json.dump({} if "json" in file else [], f)

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
    uid = str(update.effective_user.id)

    nap_pending = load_json("data/nap_pending.json")
    nap_pending[uid] = {"amount": sotien, "time": datetime.now().isoformat()}
    save_json("data/nap_pending.json", nap_pending)

    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản theo thông tin sau:\n\n"
        f"- 📲 STK: 0971487462\n- 🏦 Ngân hàng: MB Bank\n- 💬 Nội dung: {uid}\n- 💰 Số tiền: {sotien} VND\n\n"
        f"📸 Gửi ảnh trong vòng 20 phút. Sau đó lệnh sẽ hết hạn."
    )

    async def auto_clear():
        await asyncio.sleep(1200)
        nap_pending = load_json("data/nap_pending.json")
        if uid in nap_pending:
            del nap_pending[uid]
            save_json("data/nap_pending.json", nap_pending)
    asyncio.create_task(auto_clear())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = update.effective_user

    nap_pending = load_json("data/nap_pending.json")
    if uid not in nap_pending:
        await update.message.reply_text("❌ Bạn chưa dùng /nap hoặc đã quá hạn 20 phút.")
        return

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    img = Image.open(io.BytesIO(photo_bytes))

    try:
        text = pytesseract.image_to_string(img, lang='eng+vie')
        matches = re.findall(r"\d{1,2}:\d{2}\s+\d{1,2}/\d{1,2}/\d{4}", text)
        if not matches:
            await update.message.reply_text("❌ Không tìm thấy thời gian giao dịch trong ảnh.")
            return

        tg_str = matches[0]
        tg_time = datetime.strptime(tg_str, "%H:%M %d/%m/%Y")
        if (datetime.now() - tg_time).total_seconds() > 43200:
            await update.message.reply_text("⚠️ Giao dịch quá cũ (quá 12h). Không chấp nhận.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi OCR: {e}")
        return

    caption = update.message.caption
    if not caption or not caption.isdigit():
        await update.message.delete()
        return

    sotien = int(caption)
    users = load_json("data/user.json")
    logs = load_json("data/duyet_log.json")

    users[uid] = users.get(uid, 0) + sotien
    logs.append({"uid": uid, "status": "Auto-OCR", "amount": sotien, "time": datetime.now().isoformat()})

    save_json("data/user.json", users)
    save_json("data/duyet_log.json", logs)

    if uid in nap_pending:
        del nap_pending[uid]
        save_json("data/nap_pending.json", nap_pending)

    await update.message.reply_text(f"✅ Đã cộng {sotien:,}đ vào tài khoản.")

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file.file_id,
        caption=f"🧾 OCR Time: `{tg_str}`\n👤 @{user.username or 'Không rõ'} | UID: `{uid}`\n💰 {sotien:,}đ",
        parse_mode='Markdown'
    )

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
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return
    accs = load_json("data/acc.json")
    accs.append({"user": context.args[0], "pass": context.args[1]})
    save_json("data/acc.json", accs)
    await update.message.reply_text("✅ Đã thêm acc.")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1: return
    accs = load_json("data/acc.json")
    idx = int(context.args[0])
    if 0 <= idx < len(accs):
        accs.pop(idx)
        save_json("data/acc.json", accs)
        await update.message.reply_text("✅ Đã xoá acc.")
    else:
        await update.message.reply_text("❌ ID không hợp lệ.")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2: return
    uid, tien = context.args
    users = load_json("data/user.json")
    users[uid] = users.get(uid, 0) + int(tien)
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã cộng tiền.")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2: return
    uid, tien = context.args
    users = load_json("data/user.json")
    users[uid] = max(0, users.get(uid, 0) - int(tien))
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã trừ tiền.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    await update.message.reply_text(f"📊 Còn {len(accs)} acc\n🧾 Đã bán: {len(log)}")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1: return
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
import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters)
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio
from PIL import Image
import pytesseract
import io
import re

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

keep_alive()
os.makedirs("data", exist_ok=True)
for file in ["acc.json", "user.json", "log.json", "duyet_log.json", "admins.json", "nap_pending.json"]:
    if not os.path.exists(f"data/{file}"):
        with open(f"data/{file}", "w") as f:
            json.dump({} if "json" in file else [], f)

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
    uid = str(update.effective_user.id)

    nap_pending = load_json("data/nap_pending.json")
    nap_pending[uid] = {"amount": sotien, "time": datetime.now().isoformat()}
    save_json("data/nap_pending.json", nap_pending)

    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản theo thông tin sau:\n\n"
        f"- 📲 STK: 0971487462\n- 🏦 Ngân hàng: MB Bank\n- 💬 Nội dung: {uid}\n- 💰 Số tiền: {sotien} VND\n\n"
        f"📸 Gửi ảnh trong vòng 20 phút. Sau đó lệnh sẽ hết hạn."
    )

    async def auto_clear():
        await asyncio.sleep(1200)
        nap_pending = load_json("data/nap_pending.json")
        if uid in nap_pending:
            del nap_pending[uid]
            save_json("data/nap_pending.json", nap_pending)
    asyncio.create_task(auto_clear())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = update.effective_user

    nap_pending = load_json("data/nap_pending.json")
    if uid not in nap_pending:
        await update.message.reply_text("❌ Bạn chưa dùng /nap hoặc đã quá hạn 20 phút.")
        return

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    img = Image.open(io.BytesIO(photo_bytes))

    try:
        text = pytesseract.image_to_string(img, lang='eng+vie')
        matches = re.findall(r"\d{1,2}:\d{2}\s+\d{1,2}/\d{1,2}/\d{4}", text)
        if not matches:
            await update.message.reply_text("❌ Không tìm thấy thời gian giao dịch trong ảnh.")
            return

        tg_str = matches[0]
        tg_time = datetime.strptime(tg_str, "%H:%M %d/%m/%Y")
        if (datetime.now() - tg_time).total_seconds() > 43200:
            await update.message.reply_text("⚠️ Giao dịch quá cũ (quá 12h). Không chấp nhận.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi OCR: {e}")
        return

    caption = update.message.caption
    if not caption or not caption.isdigit():
        await update.message.delete()
        return

    sotien = int(caption)
    users = load_json("data/user.json")
    logs = load_json("data/duyet_log.json")

    users[uid] = users.get(uid, 0) + sotien
    logs.append({"uid": uid, "status": "Auto-OCR", "amount": sotien, "time": datetime.now().isoformat()})

    save_json("data/user.json", users)
    save_json("data/duyet_log.json", logs)

    if uid in nap_pending:
        del nap_pending[uid]
        save_json("data/nap_pending.json", nap_pending)

    await update.message.reply_text(f"✅ Đã cộng {sotien:,}đ vào tài khoản.")

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file.file_id,
        caption=f"🧾 OCR Time: `{tg_str}`\n👤 @{user.username or 'Không rõ'} | UID: `{uid}`\n💰 {sotien:,}đ",
        parse_mode='Markdown'
    )

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
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return
    accs = load_json("data/acc.json")
    accs.append({"user": context.args[0], "pass": context.args[1]})
    save_json("data/acc.json", accs)
    await update.message.reply_text("✅ Đã thêm acc.")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1: return
    accs = load_json("data/acc.json")
    idx = int(context.args[0])
    if 0 <= idx < len(accs):
        accs.pop(idx)
        save_json("data/acc.json", accs)
        await update.message.reply_text("✅ Đã xoá acc.")
    else:
        await update.message.reply_text("❌ ID không hợp lệ.")

async def cong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2: return
    uid, tien = context.args
    users = load_json("data/user.json")
    users[uid] = users.get(uid, 0) + int(tien)
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã cộng tiền.")

async def tru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 2: return
    uid, tien = context.args
    users = load_json("data/user.json")
    users[uid] = max(0, users.get(uid, 0) - int(tien))
    save_json("data/user.json", users)
    await update.message.reply_text("✅ Đã trừ tiền.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    accs = load_json("data/acc.json")
    log = load_json("data/log.json")
    await update.message.reply_text(f"📊 Còn {len(accs)} acc\n🧾 Đã bán: {len(log)}")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) != 1: return
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
