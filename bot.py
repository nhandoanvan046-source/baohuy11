import asyncio
import json
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ===== ĐỌC CẤU HÌNH =====
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config["BOT_TOKEN"]
CHAT_ID = config["CHAT_ID"]
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

last_phien = None  # Lưu phiên cuối cùng đã gửi để tránh spam

# ===== LỆNH /START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌞 Bot Sunwin TX đang hoạt động!\n"
        "• /tx → xem kết quả Tài Xỉu mới nhất\n"
        "• Bot sẽ tự động gửi kết quả mỗi 1 phút 🚀"
    )

# ===== LỆNH /TX =====
async def tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Đang lấy dữ liệu Sunwin...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    await msg.edit_text("❌ Không thể kết nối API Sunwin.")
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
        await msg.edit_text(text)

    except Exception as e:
        await msg.edit_text(f"⚠️ Lỗi khi xử lý dữ liệu: {e}")

# ===== HÀM LẤY DỮ LIỆU API =====
async def get_taixiu():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except:
        return None

# ===== AUTO GỬI KẾT QUẢ MỚI =====
async def auto_send(app):
    global last_phien
    while True:
        try:
            data = await get_taixiu()
            if not data:
                print("⚠️ Không lấy được dữ liệu API.")
                await asyncio.sleep(60)
                continue

            phien = data.get("phien")
            du_doan = data.get("du_doan", "Không có")
            ketqua = data.get("ketqua", "Không có")

            # Gửi nếu là phiên mới
            if phien != last_phien and phien is not None:
                text = (
                    f"🌞 Sunwin TX\n"
                    f"🎯 Phiên: {phien}\n"
                    f"🧠 Dự đoán: {du_doan}\n"
                    f"🏁 Kết quả: {ketqua}"
                )
                await app.bot.send_message(chat_id=CHAT_ID, text=text)
                last_phien = phien
                print(f"✅ Đã gửi kết quả mới (Phiên {phien})")

            await asyncio.sleep(60)  # Kiểm tra mỗi 1 phút

        except Exception as e:
            print(f"⚠️ Lỗi auto_send: {e}")
            await asyncio.sleep(60)

# ===== CHẠY BOT =====
async def main():
    keep_alive()  # Giữ bot online khi treo Render
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tx", tx))

    # Task auto gửi dữ liệu song song
    asyncio.create_task(auto_send(app))

    print("✅ Bot Sunwin TX đang chạy...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
