import requests
import logging
import threading
import asyncio
from flask import Flask
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ======================
# 🔧 CẤU HÌNH
# ======================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# ======================
# 🧾 LOGGING
# ======================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Lưu danh sách chat đang bật auto
active_chats = {}

# ======================
# 🎨 HÀM ĐỊNH DẠNG KẾT QUẢ
# ======================
def format_result(data):
    phien = data.get("phien", "Không rõ")
    du_doan = data.get("du_doan", "Không rõ")
    ket_qua = data.get("ket_qua", "Đang cập nhật")

    return (
        f"🌞 <b>Sunwin Tài Xỉu</b>\n"
        f"🎯 <b>Phiên:</b> {phien}\n"
        f"🧠 <b>Dự đoán:</b> {du_doan}\n"
        f"🏁 <b>Kết quả:</b> {ket_qua}"
    )

# ======================
# ⚡ LỆNH /taixiu
# ======================
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    try:
        res = requests.get(API_URL, timeout=10)
        data = res.json()
        text = format_result(data)
        await update.message.reply_html(text)

        # Nếu chưa bật auto thì bật
        if chat_id not in active_chats or not active_chats[chat_id]:
            active_chats[chat_id] = True
            await update.message.reply_text("🔁 Đã bật chế độ cập nhật tự động kết quả Tài Xỉu...")
            asyncio.create_task(auto_update(chat_id))
        else:
            await update.message.reply_text("✅ Auto đang chạy rồi!")

    except Exception as e:
        logger.error(f"Lỗi /taixiu: {e}")
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu Sunwin.")

# ======================
# 🤖 CHẾ ĐỘ AUTO UPDATE
# ======================
async def auto_update(chat_id):
    bot = Bot(token=BOT_TOKEN)
    last_phien = None
    while active_chats.get(chat_id, False):
        try:
            res = requests.get(API_URL, timeout=10)
            data = res.json()
            phien = data.get("phien")

            if phien and phien != last_phien:
                text = format_result(data)
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
                logger.info(f"📢 Gửi kết quả phiên {phien} tới chat {chat_id}")
                last_phien = phien

        except Exception as e:
            logger.error(f"Lỗi auto_update: {e}")

        await asyncio.sleep(60)  # Kiểm tra API mỗi 60 giây

# ======================
# 🛑 LỆNH /stop
# ======================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in active_chats and active_chats[chat_id]:
        active_chats[chat_id] = False
        await update.message.reply_text("🛑 Đã tắt chế độ tự động cập nhật.")
    else:
        await update.message.reply_text("⚙️ Auto chưa bật hoặc đã tắt rồi.")

# ======================
# 🚀 LỆNH /start
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xin chào!\n\n"
        "Gõ /taixiu để xem kết quả mới nhất và bật chế độ auto cập nhật.\n"
        "Gõ /stop để tắt auto.\n\n"
        "🌞 Bot Sunwin Tài Xỉu by AURAVN"
    )

# ======================
# 🌐 FLASK KEEP ALIVE (Render)
# ======================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot Sunwin Tài Xỉu đang hoạt động trên Render!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# ======================
# 🧩 MAIN
# ======================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.add_handler(CommandHandler("stop", stop))

    logger.info("🚀 Bot Sunwin Tài Xỉu đã khởi động thành công!")
    await app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(main())
