import asyncio
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ==== CẤU HÌNH ====
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512  # ID nhóm Telegram
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
AUTO_DELAY = 60  # Thời gian auto gửi (giây)
# ===================


# ===== LẤY DỮ LIỆU API =====
def get_taixiu_data():
    """Lấy dữ liệu tài xỉu từ API"""
    try:
        res = requests.get(API_URL, timeout=10)
        res.raise_for_status()
        data = res.json()
        phien = data.get("phien", "Không rõ")
        ketqua = data.get("ketqua", "Không rõ")
        return phien, ketqua
    except Exception as e:
        print(f"[❌ LỖI API] {e}")
        return None, None


# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🌞 **Sunwin TX Bot**\n\n"
        "🎯 Lệnh có sẵn:\n"
        "• `/taixiu` → Xem kết quả mới nhất\n"
        "• Bot sẽ tự gửi kết quả vào nhóm mỗi 1 phút 🕐"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ===== /taixiu =====
async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua = get_taixiu_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu từ máy chủ.")
        return

    du_doan = "Tài" if ketqua == "Tài" else "Xỉu"
    time_now = datetime.now().strftime("%H:%M:%S")

    msg = (
        f"🌞 **Sunwin TX**\n"
        f"🕐 **Thời gian:** {time_now}\n"
        f"🧩 **Phiên:** {phien}\n"
        f"🎯 **Dự đoán:** {du_doan}\n"
        f"🏁 **Kết quả:** {ketqua}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

    # Gửi thêm tin auto sau 1 phút (tự động update)
    await asyncio.sleep(60)
    phien, ketqua = get_taixiu_data()
    if phien:
        auto_msg = (
            f"⏰ Cập nhật mới!\n"
            f"🧩 Phiên: {phien}\n"
            f"🏁 Kết quả: {ketqua}"
        )
        await update.message.reply_text(auto_msg, parse_mode="Markdown")


# ===== GỬI AUTO MỖI 1 PHÚT =====
async def auto_send(app):
    last_phien = None
    while True:
        await asyncio.sleep(AUTO_DELAY)
        phien, ketqua = get_taixiu_data()
        if not phien or phien == last_phien:
            continue
        last_phien = phien

        du_doan = "Tài" if ketqua == "Tài" else "Xỉu"
        time_now = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"🌞 **Sunwin TX**\n"
            f"🕐 **{time_now}**\n"
            f"🧩 **Phiên:** {phien}\n"
            f"🎯 **Dự đoán:** {du_doan}\n"
            f"🏁 **Kết quả:** {ketqua}\n\n"
            "⚙️ Bot auto cập nhật mỗi 1 phút!"
        )
        try:
            await app.bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
            print(f"[✅ AUTO] Gửi phiên {phien} ({ketqua}) lúc {time_now}")
        except Exception as e:
            print(f"[❌ LỖI GỬI AUTO] {e}")


# ===== CHẠY BOT =====
async def main():
    print("🚀 Đang khởi động bot Sunwin TX...")
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    # Tạo task chạy song song auto
    asyncio.create_task(auto_send(app))

    print("✅ Bot Sunwin TX đã sẵn sàng hoạt động!")
    await app.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot đã dừng thủ công.")
