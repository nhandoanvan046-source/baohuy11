import asyncio, requests, json, os
from datetime import datetime
from collections import deque, Counter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive  # Giữ bot chạy trên Render

# ===== CẤU HÌNH =====
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
HISTORY_FILE = "history.json"
TREND_LEN = 10
ALERT_STREAK = 5
ALERT_SPECIAL = 3
WINRATE_THRESHOLD = 70
CHECK_INTERVAL = 5  # giây kiểm tra phiên mới

DICE_EMOJI = {1:"⚀",2:"⚁",3:"⚂",4:"⚃",5:"⚄",6:"⚅"}

# ===== LOAD HISTORY =====
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: f.write("[]")

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    history_all = json.load(f)

history_trend = deque([r["ket_qua"] for r in history_all[-TREND_LEN:]], maxlen=TREND_LEN)
last_phien = history_all[-1]["phien"] if history_all else None

# ===== HÀM HỖ TRỢ =====
def get_data():
    try:
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        d = r.json()
        return (
            d.get("phien_hien_tai"),
            d.get("ket_qua"),
            d.get("tong"),
            d.get("xuc_xac_1"),
            d.get("xuc_xac_2"),
            d.get("xuc_xac_3")
        )
    except:
        return None, None, None, None, None, None

def save(phien, ketqua, tong, x1, x2, x3):
    record = {
        "phien": phien,
        "ket_qua": ketqua,
        "tong": tong,
        "x1": x1,
        "x2": x2,
        "x3": x3,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history_all.append(record)
    history_trend.append(ketqua)
    with open(HISTORY_FILE,"w",encoding="utf-8") as f:
        json.dump(history_all,f,ensure_ascii=False,indent=2)

def analyze_trend():
    tai = history_trend.count("Tài")
    xiu = history_trend.count("Xỉu")
    if len(history_trend)<3: return "📊 Chưa đủ dữ liệu"
    if tai==xiu: return "⚖️ Xu hướng cân bằng!"
    return f"🔥 Tài {tai}/{len(history_trend)}" if tai>xiu else f"💧 Xỉu {xiu}/{len(history_trend)}"

def winrate():
    tai = sum(1 for r in history_all if r["ket_qua"]=="Tài")
    xiu = sum(1 for r in history_all if r["ket_qua"]=="Xỉu")
    total = len(history_all)
    if total==0: return "📊 Chưa có dữ liệu"
    return f"🏆 Tài {tai}/{total}\n🏆 Xỉu {xiu}/{total}"

def check_alert():
    last = list(history_trend)[-ALERT_STREAK:]
    if len(last)<ALERT_STREAK: return None
    if all(r=="Tài" for r in last): return "🔥 5 phiên Tài liên tiếp!"
    if all(r=="Xỉu" for r in last): return "💧 5 phiên Xỉu liên tiếp!"
    return None

def check_special():
    last = list(history_trend)[-ALERT_SPECIAL:]
    if len(last)<ALERT_SPECIAL: return None
    tai = sum(1 for r in history_all if r["ket_qua"]=="Tài")
    xiu = sum(1 for r in history_all if r["ket_qua"]=="Xỉu")
    total = len(history_all)
    if all(r=="Tài" for r in last) and tai/total*100>=WINRATE_THRESHOLD:
        return "🔥⚠️ 3 Tài liên tiếp + Winrate >70%!"
    if all(r=="Xỉu" for r in last) and xiu/total*100>=WINRATE_THRESHOLD:
        return "💧⚠️ 3 Xỉu liên tiếp + Winrate >70%!"
    return None

def predict_next():
    count = Counter(history_trend)
    if not count: return "📊 Chưa đủ dữ liệu"
    return "Dự đoán phiên tiếp theo: Tài" if count["Tài"]>count["Xỉu"] else "Dự đoán phiên tiếp theo: Xỉu"

def analyze_cau(min_len=3, max_len=18):
    if len(history_trend) < min_len:
        return "📊 Chưa đủ dữ liệu để phân tích cầu"

    trend = list(history_trend)
    results = []

    for length in range(min_len, min(max_len+1, len(trend)+1)):
        sub = trend[-length:]
        if all(x=="Tài" for x in sub):
            results.append(f"🔥 {length} Tài liên tiếp")
        elif all(x=="Xỉu" for x in sub):
            results.append(f"💧 {length} Xỉu liên tiếp")

    if not results:
        return "⚖️ Không có chuỗi Tài/Xỉu đặc biệt 3–18 phiên gần nhất"
    return "\n".join(results)

def build_msg(phien, ketqua, tong, x1, x2, x3):
    t = datetime.now().strftime("%H:%M:%S")
    trend = analyze_trend()
    wr = winrate()
    alert = check_alert()
    sp = check_special()
    predict = predict_next()
    cau_analysis = analyze_cau(3,18)

    prev = "Chưa có"
    if len(history_all) >= 2:
        last = history_all[-2]
        prev = f"{last['ket_qua']} (Phiên {last['phien']})"

    dice = f"{DICE_EMOJI.get(x1,'?')} | {DICE_EMOJI.get(x2,'?')} | {DICE_EMOJI.get(x3,'?')}"
    msg = (
        f"🌞 Sunwin TX\n"
        f"🕐 {t}\n"
        f"🧩 Phiên: {phien}\n"
        f"🎲 Xúc xắc: {dice} → Tổng: {tong}\n"
        f"🎯 Kết quả: {ketqua}\n"
        f"📜 Phiên trước: {prev}\n\n"
        f"{trend}\n{wr}\n📌 {predict}\n{cau_analysis}"
    )
    if alert: msg += f"\n⚠️ {alert}"
    if sp: msg += f"\n⚠️ {sp}"
    return msg

# ===== LỆNH BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌞 Sunwin TX Bot (AI + Alert + Phân tích cầu)\n"
        "• /taixiu → Xem kết quả + xu hướng + winrate + cầu 3–18\n"
        "• Bot auto gửi theo phiên mới 🤖"
    )

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua, tong, x1, x2, x3 = get_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu")
        return
    save(phien, ketqua, tong, x1, x2, x3)
    await update.message.reply_text(build_msg(phien, ketqua, tong, x1, x2, x3))

async def prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(history_all) < 2:
        await update.message.reply_text("📜 Chưa có phiên trước")
        return
    last = history_all[-2]
    msg = f"📜 Phiên trước: {last['phien']}\n🎯 Kết quả: {last['ket_qua']}\n🎲 {DICE_EMOJI.get(last['x1'],'?')} | {DICE_EMOJI.get(last['x2'],'?')} | {DICE_EMOJI.get(last['x3'],'?')} → Tổng: {last['tong']}"
    await update.message.reply_text(msg)

# ===== AUTO GỬI THEO PHIÊN =====
async def auto_check(app):
    global last_phien
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        phien, ketqua, tong, x1, x2, x3 = get_data()
        if not phien or phien == last_phien:
            continue
        last_phien = phien
        save(phien, ketqua, tong, x1, x2, x3)
        try:
            await app.bot.send_message(GROUP_ID, build_msg(phien, ketqua, tong, x1, x2, x3))
            print(f"[✅] {phien} ({ketqua}) gửi thành công")
        except Exception as e:
            print(f"[❌] Lỗi gửi {phien}: {e}")

# ===== CHẠY BOT =====
async def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.add_handler(CommandHandler("prev", prev))

    # Auto gửi theo phiên mới
    asyncio.create_task(auto_check(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
    
