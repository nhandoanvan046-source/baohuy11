import asyncio
import aiohttp
import logging
from datetime import datetime
from telegram import Bot
from keep_alive import keep_alive

# ---------------- CẤU HÌNH ----------------
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
CHAT_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
CHECK_INTERVAL = 8  # giây giữa mỗi lần kiểm tra
MAX_RETRY = 5       # số lần thử reconnect Telegram
# -------------------------------------------

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] %(message)s",
    level=logging.INFO
)

bot = Bot(token=BOT_TOKEN)
last_phien = None  # Lưu phiên cuối cùng đã gửi

# ---------------- KEEP ALIVE ----------------
keep_alive()
# --------------------------------------------

async def fetch_data():
    """Lấy dữ liệu từ API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logging.warning(f"⚠️ API lỗi: {resp.status}")
                    return None
    except Exception as e:
        logging.error(f"❌ Lỗi khi fetch API: {e}")
        return None

async def send_message_safe(text):
    """Gửi tin nhắn Telegram, tự reconnect khi lỗi"""
    for i in range(MAX_RETRY):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
            return True
        except Exception as e:
            logging.warning(f"⚠️ Gửi thất bại ({i+1}/{MAX_RETRY}): {e}")
            await asyncio.sleep(5)
    logging.error("❌ Không thể gửi tin nhắn sau nhiều lần thử!")
    return False

async def auto_send_result():
    """Tự động gửi kết quả khi API có phiên mới"""
    global last_phien

    while True:
        data = await fetch_data()
        if data:
            try:
                phien = data.get("phien")
                du_doan = data.get("du_doan", "Không rõ")
                ket_qua = data.get("ket_qua", "Chưa có")

                # Nếu có phiên mới → gửi tin
                if phien and phien != last_phien:
                    last_phien = phien
                    text = (
                        f"🌞 <b>Sunwin TX</b>\n"
                        f"🎯 <b>Phiên:</b> <code>{phien}</code>\n"
                        f"🧠 <b>Dự đoán:</b> <b>{du_doan}</b>\n"
                        f"🏁 <b>Kết quả:</b> <b>{ket_qua}</b>\n"
                        f"⏰ <i>{datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</i>"
                    )
                    await send_message_safe(text)
                    logging.info(f"✅ Đã gửi kết quả phiên {phien}")
            except Exception as e:
                logging.error(f"❌ Lỗi xử lý dữ liệu API: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    """Chạy bot chính — auto reconnect nếu có lỗi"""
    while True:
        try:
            logging.info("🚀 Bot Sunwin TX đang khởi động...")
            await auto_send_result()
        except Exception as e:
            logging.error(f"💥 Lỗi chính: {e}")
            logging.info("🔁 Đang thử kết nối lại sau 10s...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
    
