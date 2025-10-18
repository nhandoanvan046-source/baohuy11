import logging
import aiohttp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
GROUP_ID = -1002666964512  # nhóm để bot gửi kết quả auto

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== HÀM GỌI API ==================
async def get_taixiu_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Lỗi API: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Lỗi khi gọi API: {e}")
        return None

# ================== LỆNH /tx ==================
async def tx_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await get_taixiu_data()
    if not data:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu từ API!")
        return

    phien = data.get("phien", "Không rõ")
    du_doan = data.get("du_doan", "Không rõ")
    ket_qua = data.get("ket_qua", "Không rõ")

    text = f"🌞 Sunwin TX\n🎯 Phiên: {phien}\n🧠 Dự đoán: {du_doan}\n🏁 Kết quả: {ket_qua}"
    await update.message.reply_text(text)

# ================== AUTO GỬI KẾT QUẢ ==================
async def auto_send_tx(app):
    last_phien = None
    await app.bot.send_message(GROUP_ID, "✅ Bắt đầu auto gửi kết quả Sunwin TX mỗi 1 phút!")

    while True:
        try:
            data = await get_taixiu_data()
            if data:
                phien = data.get("phien", "Không rõ")
                du_doan = data.get("du_doan", "Không rõ")
                ket_qua = data.get("ket_qua", "Không rõ")

                # Gửi khi có phiên mới
                if phien != last_phien:
                    text = (
                        f"🌞 Sunwin TX\n🎯 Phiên: {phien}\n🧠 Dự đoán: {du_doan}\n🏁 Kết quả: {ket_qua}"
                    )
                    await app.bot.send_message(GROUP_ID, text)
                    last_phien = phien
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Lỗi auto TX: {e}")
            await asyncio.sleep(10)

# ================== KHỞI CHẠY BOT ==================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("tx", tx_command))

    # chạy auto loop song song
    asyncio.create_task(auto_send_tx(app))

    print("✅ Bot Sunwin TX đã khởi động và auto gửi kết quả mỗi 1 phút!")
    await app.run_polling()

# ================== CHẠY ==================
if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
