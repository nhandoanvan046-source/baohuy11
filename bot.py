import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ====== CẤU HÌNH BOT ======
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512  # ID nhóm muốn gửi auto
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# ====== LẤY DỮ LIỆU TỪ API ======
def get_taixiu_data():
    try:
        res = requests.get(API_URL, timeout=10)
        data = res.json()
        phien = data.get("phien", "Không rõ")
        ketqua = data.get("ketqua", "Không rõ")
        return phien, ketqua
    except Exception as e:
        print(f"[LỖI API] {e}")
        return None, None

# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌞 Xin chào, tôi là **Sunwin TX Bot**!\n\n"
        "🎮 Gõ /taixiu để xem kết quả mới nhất.\n"
        "🤖 Bot sẽ tự động gửi kết quả mỗi 1 phút!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ====== /taixiu ======
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua = get_taixiu_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu từ máy chủ.")
        return

    du_doan = "Tài" if ketqua == "Tài" else "Xỉu"
    msg = (
        f"🌞 **Sunwin TX**\n"
        f"🎯 **Phiên:** {phien}\n"
        f"🧠 **Dự đoán:** {du_doan}\n"
        f"🏁 **Kết quả:** {ketqua}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

    # Auto nhắn lại sau 5 giây
    await asyncio.sleep(5)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Bot sẽ cập nhật kết quả mới sau 1 phút!"
    )

# ====== AUTO GỬI KẾT QUẢ MỖI 1 PHÚT ======
async def auto_send(app):
    last_phien = None
    while True:
        await asyncio.sleep(60)  # 1 phút
        phien, ketqua = get_taixiu_data()
        if not phien or phien == last_phien:
            continue

        last_phien = phien
        du_doan = "Tài" if ketqua == "Tài" else "Xỉu"
        msg = (
            f"🌞 **Sunwin TX**\n"
            f"🎯 **Phiên:** {phien}\n"
            f"🧠 **Dự đoán:** {du_doan}\n"
            f"🏁 **Kết quả:** {ketqua}\n\n"
            f"⏰ Cập nhật tự động mỗi 1 phút!"
        )
        try:
            await app.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
            print(f"[AUTO] Gửi kết quả phiên {phien}")
        except Exception as e:
            print(f"[LỖI AUTO] {e}")

# ====== MAIN ======
async def main():
    print("🚀 Khởi động bot Sunwin TX...")
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    # Auto gửi kết quả mỗi 1 phút
    asyncio.create_task(auto_send(app))

    print("✅ Bot Sunwin TX đã sẵn sàng hoạt động!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
