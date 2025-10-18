import requests
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CẤU HÌNH ---
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- LỆNH /taixiu ---
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(API_URL, timeout=10)
        data = response.json()

        # Dự đoán + kết quả
        phien = data.get("phien", "Không rõ")
        du_doan = data.get("du_doan", "Không rõ")
        ket_qua = data.get("ket_qua", "Đang cập nhật")

        text = (
            f"🌞 <b>Sunwin Tài Xỉu</b>\n"
            f"🎯 <b>Phiên:</b> {phien}\n"
            f"🧠 <b>Dự đoán:</b> {du_doan}\n"
            f"🏁 <b>Kết quả:</b> {ket_qua}"
        )

        await update.message.reply_html(text)

    except requests.exceptions.RequestException:
        await update.message.reply_text("⚠️ Lỗi kết nối tới máy chủ Sunwin.")
    except Exception as e:
        logger.error(f"Lỗi khi xử lý /taixiu: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra khi xử lý lệnh.")

# --- LỆNH /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Xin chào! Gõ /taixiu để xem kết quả Sunwin.")

# --- KHỞI TẠO BOT ---
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.run_polling(stop_signals=None)

# --- KEEP ALIVE (Render) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot Sunwin đang hoạt động!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# --- CHẠY CẢ BOT VÀ WEB ---
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
