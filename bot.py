import asyncio
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from keep_alive import keep_alive

# =========================
# 🔐 Cấu hình cơ bản
# =========================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# =========================
# 🧠 Hàm lấy dữ liệu API
# =========================
def get_taixiu_result():
    try:
        response = requests.get(API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            phien = data.get("phien", "Không rõ")
            ketqua = data.get("ketqua", "Không rõ")

            # Dự đoán (random hoặc theo kết quả)
            du_doan = "Tài" if ketqua == "Tài" else "Xỉu"

            text = (
                f"🌞 <b>Sunwin Tài Xỉu</b>\n"
                f"🎯 <b>Phiên:</b> <code>{phien}</code>\n"
                f"🧠 <b>Dự đoán:</b> {du_doan}\n"
                f"🏁 <b>Kết quả:</b> <u>{ketqua}</u>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"✅ Cập nhật tự động từ hệ thống Sunwin"
            )
            return text
        else:
            return "⚠️ Không thể lấy dữ liệu (máy chủ phản hồi lỗi)."
    except Exception as e:
        return f"❌ Lỗi kết nối API: {str(e)}"

# =========================
# 💬 Xử lý lệnh /taixiu
# =========================
async def taixiu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang lấy kết quả Tài Xỉu...", parse_mode="HTML")
    result = get_taixiu_result()
    await update.message.reply_text(result, parse_mode="HTML")

# =========================
# 🧠 Lệnh /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🌞 <b>Chào mừng bạn đến với bot Sunwin TX!</b>\n\n"
        "🎯 Lệnh khả dụng:\n"
        "• /taixiu – Xem kết quả Tài Xỉu mới nhất\n"
        "• /help – Hướng dẫn sử dụng\n\n"
        "🚀 Bot cập nhật dữ liệu tự động từ hệ thống Sunwin."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# =========================
# 🧩 Lệnh /help
# =========================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🧭 <b>Hướng dẫn sử dụng</b>\n\n"
        "🎲 /taixiu – Hiển thị kết quả phiên Tài Xỉu mới nhất.\n"
        "💡 Bot tự động lấy dữ liệu từ hệ thống Sunwin, không cần nhập tay.\n"
        "⚙️ Nếu không có phản hồi, kiểm tra lại API hoặc bot token."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# =========================
# 🚀 Chạy bot
# =========================
async def main():
    print("✅ Bot Sunwin TX đang khởi động...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("taixiu", taixiu_command))

    print("🤖 Bot Sunwin TX đã sẵn sàng nhận lệnh!")
    await app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
