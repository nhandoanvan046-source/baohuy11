import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from keep_alive import keep_alive

# --- Cấu hình ---
BOT_TOKEN = "6367532329:AAEcax3tm_JLwGOtQcMnAECjiuaX0zkuITc"
_API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# --- Cấu hình log ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Lệnh /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌞 **Sunwin TX Bot**\n\n"
        "🎯 Gõ /taixiu để xem kết quả mới nhất.\n"
        "🔁 Hoặc nhấn nút bên dưới để cập nhật nhanh."
    )
    keyboard = [[InlineKeyboardButton("🎲 Xem kết quả", callback_data="refresh_taixiu")]]
    await update.message.reply_markdown(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Hàm lấy dữ liệu & gửi kết quả ---
async def send_taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    try:
        response = requests.get(_API_URL, timeout=8)
        data = response.json()

        if not data or "phien" not in data:
            text = "⚠️ Không thể lấy kết quả lúc này, thử lại sau."
        else:
            phien = data.get("phien", "N/A")
            taixiu = data.get("taixiu", "Không rõ")

            text = (
                f"🌞 **Sunwin TX**\n"
                f"🎯 Phiên: {phien}\n"
                f"🧠 Dự đoán: {'Tài' if taixiu == 'TÀI' else 'Xỉu'}\n"
                f"🏁 Kết quả: {taixiu}"
            )

        keyboard = [[InlineKeyboardButton("🔁 Làm mới", callback_data="refresh_taixiu")]]

        if query:
            await query.edit_message_text(
                text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
        else:
            await update.message.reply_markdown(
                text, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        logging.error(f"Lỗi API: {e}")
        err = "❌ Không thể kết nối tới máy chủ SUNWIN, thử lại sau."
        if query:
            await query.edit_message_text(err)
        else:
            await update.message.reply_text(err)

# --- Lệnh /taixiu ---
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_taixiu(update, context)

# --- Xử lý callback nút “Làm mới” ---
async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_taixiu(update, context, query=query)

# --- Chạy bot ---
def main():
    keep_alive()  # Giữ bot hoạt động 24/7

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh_taixiu$"))

    print("✅ Bot Sunwin TX đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
