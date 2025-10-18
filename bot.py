import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# --- CẤU HÌNH ---
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"


# --- LẤY KẾT QUẢ ---
def get_taixiu_result():
    try:
        res = requests.get(API_URL, timeout=10)
        data = res.json()
        phien = data.get("phien", "Không rõ")
        ketqua = data.get("ketqua", "Không rõ")
        du_doan = "Tài" if ketqua == "Tài" else "Xỉu"
        return (
            f"🌞 <b>Sunwin TX</b>\n"
            f"🎯 <b>Phiên:</b> {phien}\n"
            f"🧠 <b>Dự đoán:</b> {du_doan}\n"
            f"🏁 <b>Kết quả:</b> {ketqua}"
        )
    except Exception as e:
        return f"⚠️ Lỗi API: {e}"


# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "🌞 <b>Chào mừng đến với bot Sunwin TX!</b>\n"
        "Gõ /taixiu để xem kết quả mới nhất 🎯"
    )


# --- /taixiu ---
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang lấy kết quả mới nhất...")
    result = get_taixiu_result()
    await asyncio.sleep(2)
    await update.message.reply_html(result)

    # Auto phản hồi lại sau vài giây
    await asyncio.sleep(10)
    await update.message.reply_html("🔁 Đang cập nhật kết quả mới...")
    await update.message.reply_html(get_taixiu_result())


# --- GỬI AUTO VÀO NHÓM ---
async def auto_send_result(app):
    last_result = None
    while True:
        try:
            result = get_taixiu_result()
            if result != last_result:
                await app.bot.send_message(chat_id=GROUP_ID, text=result, parse_mode="HTML")
                last_result = result
        except Exception as e:
            print("❌ Auto send lỗi:", e)
        await asyncio.sleep(180)  # 3 phút


# --- MAIN ---
async def main():
    keep_alive()
    print("✅ Khởi động bot Sunwin TX...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    asyncio.create_task(auto_send_result(app))
    print("🤖 Bot đang chạy, chờ lệnh /taixiu...")
    await app.run_polling()  # <- phần cực kỳ quan trọng (chạy listener)


if __name__ == "__main__":
    asyncio.run(main())
