import asyncio
import json
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# Đọc cấu hình
with open("config.json", "r") as f:
    config = json.load(f)

BOT_TOKEN = config["BOT_TOKEN"]
CHAT_ID = config["CHAT_ID"]
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

last_phien = None  # Lưu phiên đã gửi để tránh spam

# --- Lệnh /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌞 Bot Sunwin TX đang hoạt động!\nGõ /tx để xem kết quả Tài Xỉu mới nhất 🎲")

# --- Lệnh /tx ---
async def tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_wait = await update.message.reply_text("⏳ Đang lấy dữ liệu từ Sunwin...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    await msg_wait.edit_text("❌ Không thể kết nối API Sunwin.")
                    return
                data = await resp.json()

        phien = data.get("phien", "N/A")
        du_doan = data.get("du_doan", "Không có")
        ketqua = data.get("ketqua", "Không có")

        text = (
            f"🌞 Sunwin TX\n"
            f"🎯 Phiên: {phien}\n"
            f"🧠 Dự đoán: {du_doan}\n"
            f"🏁 Kết quả: {ketqua}"
        )

        await msg_wait.edit_text(text)

    except Exception as e:
        await msg_wait.edit_text(f"⚠️ Lỗi: {e}")

# --- Hàm lấy dữ liệu từ API ---
async def get_taixiu():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL) as resp:
            if resp.status != 200:
                return None
            return await resp.json()

# --- Auto gửi kết quả mỗi phút ---
async def auto_send(app):
    global last_phien
    while True:
        try:
            data = await get_taixiu()
            if not data:
                print("❌ Không lấy được dữ liệu API.")
                await asyncio.sleep(60)
                continue

            phien = data.get("phien")
            du_doan = data.get("du_doan", "Không có")
            ketqua = data.get("ketqua", "Không có")

            if phien != last_phien:
                text = (
                    f"🌞 Sunwin TX\n"
                    f"🎯 Phiên: {phien}\n"
                    f"🧠 Dự đoán: {du_doan}\n"
                    f"🏁 Kết quả: {ketqua}"
                )
                await app.bot.send_message(chat_id=CHAT_ID, text=text)
                last_phien = phien
                print(f"✅ Gửi kết quả mới - Phiên {phien}")

            await asyncio.sleep(60)  # 1 phút

        except Exception as e:
            print(f"⚠️ Lỗi auto_send: {e}")
            await asyncio.sleep(60)

# --- Main ---
async def main():
    keep_alive()  # Duy trì Render online
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tx", tx))

    # Task auto gửi
    asyncio.create_task(auto_send(app))

    print("✅ Bot Sunwin TX đang chạy và auto gửi kết quả mỗi phút...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
