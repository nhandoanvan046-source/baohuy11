import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging
from datetime import datetime

# --- CẤU HÌNH ---
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
CHAT_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- HÀM LẤY DỮ LIỆU API ---
async def fetch_result():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logging.warning(f"Lỗi API: {resp.status}")
                    return None
    except Exception as e:
        logging.error(f"Lỗi khi gọi API: {e}")
        return None


# --- LỆNH /tx ---
async def tx_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await fetch_result()
    if not data:
        await update.message.reply_text("❌ Không thể lấy dữ liệu từ API.")
        return

    phien = data.get("phien", "Không rõ")
    du_doan = data.get("du_doan", "Không rõ")
    ket_qua = data.get("ket_qua", "Không rõ")

    msg = (
        f"🌞 <b>Sunwin TX</b>\n"
        f"🎯 Phiên: <code>{phien}</code>\n"
        f"🧠 Dự đoán: <b>{du_doan}</b>\n"
        f"🏁 Kết quả: <b>{ket_qua}</b>\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
    )
    await update.message.reply_html(msg)


# --- AUTO GỬI KHI API LOAD PHIÊN MỚI ---
async def auto_send_new_result(app):
    last_phien = None
    await asyncio.sleep(3)

    while True:
        try:
            data = await fetch_result()
            if data:
                phien = data.get("phien")
                du_doan = data.get("du_doan")
                ket_qua = data.get("ket_qua")

                # Gửi khi có phiên mới
                if phien and phien != last_phien:
                    last_phien = phien
                    msg = (
                        f"🌞 <b>Sunwin TX</b>\n"
                        f"🎯 Phiên: <code>{phien}</code>\n"
                        f"🧠 Dự đoán: <b>{du_doan}</b>\n"
                        f"🏁 Kết quả: <b>{ket_qua}</b>\n"
                        f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
                    )
                    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
                    logging.info(f"🔔 Gửi kết quả mới: Phiên {phien}")

            await asyncio.sleep(5)  # Kiểm tra API mỗi 5 giây
        except Exception as e:
            logging.error(f"Lỗi vòng lặp auto gửi: {e}")
            await asyncio.sleep(10)


# --- MAIN ---
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("tx", tx_command))

    # Auto gửi khi có phiên mới
    app.create_task(auto_send_new_result(app))

    logging.info("✅ Bot Sunwin TX đang chạy & theo dõi API...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
