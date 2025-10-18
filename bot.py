import requests
import logging
import threading
import asyncio
from flask import Flask
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CẤU HÌNH ---
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
CHAT_ID = -1002666964512  # 👈 nhóm bạn muốn bot gửi kết quả vào

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ĐỊNH DẠNG KẾT QUẢ ---
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

# --- LỆNH /taixiu ---
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(API_URL, timeout=10)
        data = res.json()
        text = format_result(data)
        await update.message.reply_html(text)
    except Exception as e:
        logger.error(f"Lỗi /taixiu: {e}")
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu Sunwin.")

# --- GỬI KẾT QUẢ TỰ ĐỘNG ---
async def auto_send():
    bot = Bot(token=BOT_TOKEN)
    last_phien = None

    while True:
        try:
            res = requests.get(API_URL, timeout=10)
            data = res.json()
            phien = data.get("phien")

            if phien and phien != last_phien:
                text = format_result(data)
                await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
                logger.info(f"Đã gửi kết quả phiên {phien}")
                last_phien = phien

        except Exception as e:
            logger.error(f"Lỗi auto_send: {e}")

        await asyncio.sleep(60)  # ⏱ kiểm tra API mỗi 60 giây

# --- LỆNH /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xin chào! Bot đang gửi kết quả Tài Xỉu Sunwin tự động mỗi khi có phiên mới."
    )

# --- FLASK KEEP ALIVE ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot Sunwin Tài Xỉu đang hoạt động trên Render!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# --- CHẠY BOT ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    # Chạy song song auto_send
    asyncio.create_task(auto_send())
    await app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(main())
