import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌞 Chào mừng bạn đến với **Sunwin TX Bot**!\n\n"
        "Gõ /taixiu để xem kết quả mới nhất 🔥",
        parse_mode="Markdown"
    )

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
            "⏰ Auto cập nhật mỗi 1 phút!"
        )
        try:
            await app.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
            print(f"[AUTO] Gửi kết quả phiên {phien}")
        except Exception as e:
            print(f"[LỖI AUTO] {e}")

async def main():
    print("🚀 Đang khởi động bot Sunwin TX...")
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    asyncio.create_task(auto_send(app))
    print("✅ Bot Sunwin TX đã sẵn sàng hoạt động!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
