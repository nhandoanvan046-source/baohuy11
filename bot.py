import asyncio, requests, json, os
from datetime import datetime
from collections import deque, Counter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

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
# ===================

# ===== LOAD HISTORY =====
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: f.write("[]")

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    history_all = json.load(f)

history_trend = deque([r["ketqua"] for r in history_all[-TREND_LEN:]], maxlen=TREND_LEN)
last_phien = history_all[-1]["phien"] if history_all else None

# ===== HÀM HỖ TRỢ =====
def get_data():
    try:
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        d = r.json()
        return d.get("phien","Không rõ"), d.get("ketqua","Không rõ")
    except: return None, None

def save(phien, ketqua):
    record = {"phien":phien,"ketqua":ketqua,"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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
    tai = sum(1 for r in history_all if r["ketqua"]=="Tài")
    xiu = sum(1 for r in history_all if r["ketqua"]=="Xỉu")
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
    tai = sum(1 for r in history_all if r["ketqua"]=="Tài")
    xiu = sum(1 for r in history_all if r["ketqua"]=="Xỉu")
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

def build_msg(phien, ketqua):
    t = datetime.now().strftime("%H:%M:%S")
    trend = analyze_trend()
    wr = winrate()
    alert = check_alert()
    sp = check_special()
    predict = predict_next()
    
    # Phiên trước
    if len(history_all) >= 2:
        last = history_all[-2]
        prev = f"{last['ketqua']} (Phiên {last['phien']})"
    else:
        prev = "Chưa có"
    
    msg = f"🌞 Sunwin TX\n🕐 {t}\n🧩 Phiên: {phien}\n🎯 Kết quả: {ketqua}\n📜 Phiên trước: {prev}\n\n{trend}\n{wr}\n📌 {predict}"
    if alert: msg += f"\n⚠️ {alert}"
    if sp: msg += f"\n⚠️ {sp}"
    return msg

# ===== LỆNH BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌞 Sunwin TX Bot (AI + Alert)\n• /taixiu → Xem kết quả + xu hướng + winrate\n• Bot auto gửi theo phiên mới 🤖"
    )

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua = get_data()
    if not phien: 
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu"); 
        return
    save(phien, ketqua)
    await update.message.reply_text(build_msg(phien, ketqua))

# ===== AUTO GỬI THEO PHIÊN =====
async def auto_check(app):
    global last_phien
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        phien, ketqua = get_data()
        if not phien or phien == last_phien:
            continue
        last_phien = phien
        save(phien, ketqua)
        try:
            await app.bot.send_message(GROUP_ID, build_msg(phien, ketqua))
            print(f"[✅] {phien} ({ketqua}) gửi thành công")
        except Exception as e:
            print(f"[❌] Lỗi gửi {phien}: {e}")

# ===== CHẠY BOT =====
if __name__=="__main__":
    print("🚀 Khởi động bot Sunwin TX AI + Alert...")
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))

    # Tạo task async auto gửi theo phiên
    asyncio.get_event_loop().create_task(auto_check(app))
    app.run_polling()
        
