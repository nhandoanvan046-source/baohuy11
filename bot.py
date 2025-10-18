import os
import requests
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)
from keep_alive import keep_alive  # Giữ bot hoạt động 24/7 trên Render

# --- CẤU HÌNH ---
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"  # Token bot
GROUP_ID = -1002666964512  # ID nhóm muốn bot tự gửi kết quả
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"


# --- HÀM LẤY DỮ LIỆU API ---
def get_taixiu_result():
    try:
        res = requests.get(API_URL, timeout=10)
        if res.status_code != 200:
            return f"⚠️ API lỗi ({res.status_code})"
        data = res.json()
        phien = data.get("phien")
        ketqua = data.get("ketqua")
        du_doan = "Tài" if ketqua == "Tài" else "Xỉu"

        text = (
            f"🌞 <b>Sunwin TX</b>\n"
            f"🎯 <b>Phiên:</b> {phien}\n"
            f"🧠 <b>Dự đoán:</b> {du_doan}\n"
            f"🏁 <b>Kết quả:</b> {ketqua}"
        )
        return text
    except Exception as e:
        return f"⚠️ Lỗi khi lấy dữ liệu API: {e}"


# --- LỆNH /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌞 <b>Chào mừng đến với bot Sunwin Tài Xỉu!</b>\n"
        "Gõ /taixiu để xem kết quả mới nhất 🎯"
    )
    await update.message.reply_html(text)


# --- LỆNH /taixiu ---
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang lấy kết quả mới nhất, vui lòng đợi...")
    result = get_taixiu_result()
    await asyncio.sleep(2)
    await update.message.reply_html(result)

    # 🌀 Tự động trả lời lại sau vài giây
    await asyncio.sleep(10)
    await update.message.reply_html("🔁 Đang cập nhật kết quả mới...")
    new_result = get_taixiu_result()
    await update.message.reply_html(new_result)


# --- HÀM AUTO GỬI KẾT QUẢ VÀO NHÓM ---
async def auto_send_result(app):
    last_result = None
    while True:
        try:
            result = get_taixiu_result()
            if result != last_result:
                await app.bot.send_message(chat_id=GROUP_ID, text=result, parse_mode="HTML")
                last_result = result
        except Exception as e:
            print("❌ Lỗi auto gửi:", e)
        await asyncio.sleep(180)  # Gửi lại mỗi 3 phút


# --- CHẠY BOT ---
async def main():
    keep_alive()  # Giữ bot online 24/7
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Lệnh chính
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    print("✅ Bot Sunwin TX đang khởi động...")
    await app.initialize()
    await app.start()
    print("🤖 Bot Sunwin TX đã sẵn sàng nhận lệnh!")

    # Auto gửi kết quả vào nhóm
    asyncio.create_task(auto_send_result(app))

    # Chạy polling để bot phản hồi
    await app.updater.start_polling()
    await app.updater.idle()


if __name__ == "__main__":
    asyncio.run(main())
