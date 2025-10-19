import asyncio, requests, json, os, nest_asyncio
from datetime import datetime
from collections import deque, Counter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive  # Render keep_alive

# ========== CẤU HÌNH ==========
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
HISTORY_FILE = "history.json"
CHECK_INTERVAL = 5       # giây
RESET_INTERVAL = 12 * 3600
TREND_LEN = 10
USE_MINIBOARD = True
# ==============================

# ========== KHỞI TẠO ==========
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("[]")

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    history_all = json.load(f)

history_trend = deque([r["ket_qua"] for r in history_all[-TREND_LEN:]], maxlen=TREND_LEN)
last_phien = history_all[-1]["phien"] if history_all else None
last_reset = datetime.now().timestamp()
# ==============================


# ========== HÀM API ==========
def get_data():
    try:
        r = requests.get(API_URL, timeout=10)
        d = r.json()
        return (
            d.get("phien"),
            d.get("ket_qua"),
            d.get("xuc_xac_1"),
            d.get("xuc_xac_2"),
            d.get("xuc_xac_3"),
            d.get("tong"),
        )
    except:
        return None, None, None, None, None, None


def save(phien, ketqua, x1, x2, x3, tong):
    record = {
        "phien": phien,
        "ket_qua": ketqua,
        "xuc_xac_1": x1,
        "xuc_xac_2": x2,
        "xuc_xac_3": x3,
        "tong": tong,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    history_all.append(record)
    history_trend.append(ketqua)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_all, f, ensure_ascii=False, indent=2)
# ==============================


# ========== PHÂN TÍCH ==========
def analyze_trend():
    tai = history_trend.count("Tài")
    xiu = history_trend.count("Xỉu")
    return f"📈 Xu hướng: Tài {tai}/{len(history_trend)} | Xỉu {xiu}/{len(history_trend)}"


def detect_cau_pattern():
    if len(history_trend) < 6:
        return "❗ Chưa đủ dữ liệu nhận dạng cầu"
    s = list(history_trend)
    # Cầu bệt (liên tiếp 4+)
    for side in ["Tài", "Xỉu"]:
        if all(r == side for r in s[-5:]):
            return f"🔥 Cầu bệt {side} ({len([r for r in s[::-1] if r==side])} ván)"
    # Cầu đảo (Tài/Xỉu xen kẽ)
    if all(s[i] != s[i+1] for i in range(-6, -1)):
        return "🔁 Cầu đảo (Tài/Xỉu xen kẽ)"
    return "⚪ Không rõ cầu"


def winrate():
    if not history_all:
        return "Chưa có dữ liệu"
    tai = sum(1 for r in history_all if r["ket_qua"] == "Tài")
    total = len(history_all)
    return f"🏆 Winrate: Tài {tai}/{total} ({tai/total*100:.1f}%)"


# ====== AI DỰ ĐOÁN ==========
def ai_predict_next():
    if len(history_trend) < 5:
        return "Chưa đủ dữ liệu AI học"
    last = list(history_trend)[-10:]
    score = sum(1 if r == "Tài" else -1 for r in last)
    return "🧠 Dự đoán: Tài" if score > 0 else "🧠 Dự đoán: Xỉu"


def ai_predict_next_faces():
    if len(history_all) < 5:
        return "🎲 Chưa đủ dữ liệu xúc xắc"
    faces = [r["tong"] for r in history_all[-10:]]
    avg = sum(faces) / len(faces)
    return f"🎲 AI xúc xắc: {'Tài' if avg > 10 else 'Xỉu'} (TB tổng {avg:.1f})"


def ai_predict_next_n(n=3):
    preds = []
    trend_copy = list(history_trend)
    for i in range(n):
        score = sum(1 if r == "Tài" else -1 for r in trend_copy[-10:])
        choice = "Tài" if score >= 0 else "Xỉu"
        preds.append(f"Phiên +{i+1}: {choice}")
        trend_copy.append(choice)
    return "\n".join(preds)
# ==============================


# ========== HIỂN THỊ ==========
def dice_mini_board(x1, x2, x3):
    return f"🎲 {x1} | {x2} | {x3} → Tổng: {x1+x2+x3}"


def build_msg(phien, ketqua, tong, x1, x2, x3):
    t = datetime.now().strftime("%H:%M:%S")
    trend = analyze_trend()
    pattern = detect_cau_pattern()
    wr = winrate()
    predict = ai_predict_next()
    predict_faces = ai_predict_next_faces()
    multi = ai_predict_next_n(3)
    dice_display = dice_mini_board(x1, x2, x3) if USE_MINIBOARD else f"{x1}|{x2}|{x3}→Tổng:{tong}"

    return (
        f"🎯 Sunwin AI v4.2\n"
        f"🕒 {t}\n"
        f"🧩 Phiên: {phien}\n"
        f"{dice_display}\n"
        f"Kết quả: {ketqua}\n\n"
        f"{trend}\n{pattern}\n{wr}\n\n"
        f"{predict}\n{predict_faces}\n{multi}"
    )
# ==============================


# ========== LỆNH BOT ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Sunwin AI v4.2\n"
        "• /taixiu → Xem kết quả, xu hướng, winrate, AI dự đoán\n"
        "• Bot auto gửi khi có phiên mới 🎲"
    )


async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua, x1, x2, x3, tong = get_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu API.")
        return
    save(phien, ketqua, x1, x2, x3, tong)
    await update.message.reply_text(build_msg(phien, ketqua, tong, x1, x2, x3))
# ==============================


# ========== AUTO GỬI ==========
async def auto_check(app):
    global last_phien, last_reset
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        if datetime.now().timestamp() - last_reset >= RESET_INTERVAL:
            history_all.clear()
            history_trend.clear()
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            last_reset = datetime.now().timestamp()
            print("[🔄] Auto reset 12h thành công")

        phien, ketqua, x1, x2, x3, tong = get_data()
        if not phien or phien == last_phien:
            continue
        last_phien = phien
        save(phien, ketqua, x1, x2, x3, tong)
        try:
            await app.bot.send_message(GROUP_ID, build_msg(phien, ketqua, tong, x1, x2, x3))
            print(f"[✅] Đã gửi phiên {phien} ({ketqua})")
        except Exception as e:
            print(f"[❌] Gửi lỗi: {e}")
# ==============================


# ========== CHẠY BOT ==========
async def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    asyncio.create_task(auto_check(app))
    await app.run_polling()


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
        
