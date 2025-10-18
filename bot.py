import asyncio, json, os, aiohttp
from datetime import datetime
from collections import deque, Counter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ===== CẤU HÌNH =====
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
SUNWIN_API = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
DICE_API = "https://sunwinsaygex.onrender.com/api/dice"
HISTORY_FILE = "history.json"
TREND_LEN = 10
ALERT_STREAK = 5
ALERT_SPECIAL = 3
WINRATE_THRESHOLD = 70
CHECK_INTERVAL = 5  # giây kiểm tra phiên mới
# ===================

# ===== LOAD HISTORY =====
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE,"w",encoding="utf-8") as f: f.write("[]")

with open(HISTORY_FILE,"r",encoding="utf-8") as f:
    history_all = json.load(f)

history_trend = deque([r["ketqua"] for r in history_all[-TREND_LEN:]], maxlen=TREND_LEN)
last_phien = history_all[-1]["phien"] if history_all else None

# ===== HÀM HỖ TRỢ =====
async def get_sunwin_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SUNWIN_API, timeout=10) as resp:
                d = await resp.json()
                return d.get("phien"), d.get("ketqua")
    except:
        return None, None

async def get_dice_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DICE_API, timeout=10) as resp:
                d = await resp.json()
                phien = d.get("phien_hien_tai")
                ketqua = d.get("ket_qua")
                x1 = d.get("xuc_xac_1")
                x2 = d.get("xuc_xac_2")
                x3 = d.get("xuc_xac_3")
                tong = d.get("tong")
                return phien, ketqua, (x1, x2, x3, tong)
    except:
        return None, None, (None, None, None, None)

def save(phien, ketqua, x1=None, x2=None, x3=None):
    record = {
        "phien": phien,
        "ketqua": ketqua,
        "x1": x1,
        "x2": x2,
        "x3": x3,
        "tong": (x1+x2+x3) if x1 else None,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history_all.append(record)
    history_trend.append(ketqua)
    with open(HISTORY_FILE,"w",encoding="utf-8") as f:
        json.dump(history_all,f,ensure_ascii=False,indent=2)

# ===== PHÂN TÍCH TÀI/XỈU =====
def analyze_trend():
    tai = history_trend.count("Tài")
    xiu = history_trend.count("Xỉu")
    if len(history_trend)<3: return "📊 Chưa đủ dữ liệu"
    if tai==xiu: return "⚖️ Cân bằng"
    return f"🔥 Tài {tai}/{len(history_trend)}" if tai>xiu else f"💧 Xỉu {xiu}/{len(history_trend)}"

def winrate():
    tai = sum(1 for r in history_all if r["ketqua"]=="Tài")
    xiu = sum(1 for r in history_all if r["ketqua"]=="Xỉu")
    total = len(history_all)
    if total==0: return "📊 Chưa có dữ liệu"
    return f"Tài {tai}/{total} | Xỉu {xiu}/{total}"

def check_alert():
    last = list(history_trend)[-ALERT_STREAK:]
    if len(last)<ALERT_STREAK: return None
    if all(r=="Tài" for r in last): return "🔥 5 Tài liên tiếp!"
    if all(r=="Xỉu" for r in last): return "💧 5 Xỉu liên tiếp!"
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
    return "Dự đoán: Tài" if count["Tài"]>count["Xỉu"] else "Dự đoán: Xỉu"

def analyze_cau(min_len=3,max_len=18):
    if len(history_trend)<min_len: return "📊 Chưa đủ dữ liệu"
    trend = list(history_trend)
    results = []
    for length in range(min_len,min(max_len+1,len(trend)+1)):
        sub = trend[-length:]
        if all(x=="Tài" for x in sub):
            results.append(f"🔥 {length} Tài liên tiếp")
        elif all(x=="Xỉu" for x in sub):
            results.append(f"💧 {length} Xỉu liên tiếp")
    if not results: return "⚖️ Không có chuỗi đặc biệt"
    return " | ".join(results)

def auto_cau_alert():
    trend = list(history_trend)
    alerts = []
    for length in range(18,2,-1):
        if len(trend)<length: continue
        sub = trend[-length:]
        if all(x=="Tài" for x in sub):
            alerts.append(f"🔥 {length} Tài liên tiếp")
        elif all(x=="Xỉu" for x in sub):
            alerts.append(f"💧 {length} Xỉu liên tiếp")
    if alerts: return " | ".join(alerts)
    return None

# ===== PHÂN TÍCH CẦU XÍ NGẦU =====
def analyze_dice_cau(n=10):
    """Phân tích cầu viên 1-3 n phiên gần nhất"""
    res = []
    for i in range(1,4):
        line = []
        for r in history_all[-n:]:
            xi = r.get(f"x{i}")
            if xi is not None:
                line.append(str(xi))
        res.append(f"🎲 Viên {i}: {' → '.join(line)}")
    return "\n".join(res) if res else "Chưa có dữ liệu"

# ===== BUILD MESSAGE =====
async def build_msg(phien, ketqua):
    prev = "Chưa có"
    if len(history_all)>=2:
        last = history_all[-2]
        prev = f"{last['ketqua']} ({last['phien']})"

    trend = analyze_trend()
    wr = winrate()
    predict = predict_next()
    cau = analyze_cau(3,18)
    alert = check_alert()
    sp = check_special()
    cau_alert = auto_cau_alert()
    dice_cau = analyze_dice_cau(10)  # 10 phiên gần nhất

    # Xúc xắc phiên hiện tại
    _, _, dice = await get_dice_data()
    x1,x2,x3,tong = dice
    dice_msg = f"[{x1} | {x2} | {x3}] → {tong}" if x1 else "Chưa có dữ liệu"

    msg = (
        f"🌞 Sunwin TX - Phiên {phien}\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}\n"
        f"🎯 Kết quả: {ketqua}\n"
        f"📜 Phiên trước: {prev}\n"
        f"🎲 Xúc xắc hiện tại: {dice_msg}\n"
        f"🔥 Xu hướng: {trend}\n"
        f"🏆 Winrate: {wr}\n"
        f"📌 Dự đoán: {predict}\n"
        f"⚖️ Cầu 3–18: {cau}"
    )
    if alert: msg += f"\n⚠️ Alert: {alert}"
    if sp: msg += f"\n⚠️ Special: {sp}"
    if cau_alert: msg += f"\n📊 Cầu tự động: {cau_alert}"
    msg += f"\n🎲 Cầu viên 1–3 (10 phiên gần nhất):\n{dice_cau}"
    return msg

# ===== LỆNH BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌞 Sunwin TX Bot (AI + Alert + Cầu 3–18 + Xúc xắc)\n"
        "• /taixiu → Xem kết quả + xu hướng + winrate + cầu 3–18 + xúc xắc\n"
        "• Bot auto gửi theo phiên mới 🤖"
    )

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua = await get_sunwin_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu")
        return
    # Lấy dice hiện tại
    _, _, dice = await get_dice_data()
    x1,x2,x3,_ = dice
    save(phien, ketqua, x1, x2, x3)
    await update.message.reply_text(await build_msg(phien, ketqua))

async def prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(history_all)<2:
        await update.message.reply_text("📜 Chưa có phiên trước")
        return
    last = history_all[-2]
    await update.message.reply_text(f"📜 Phiên trước: {last['phien']}\n🎯 Kết quả: {last['ketqua']}")

# ===== AUTO GỬI THEO PHIÊN =====
async def auto_check(app):
    global last_phien
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            phien, ketqua = await get_sunwin_data()
            if not phien or not ketqua or phien==last_phien:
                continue
            _, _, dice = await get_dice_data()
            x1,x2,x3,_ = dice
            last_phien = phien
            save(phien, ketqua, x1, x2, x3)
            await app.bot.send_message(GROUP_ID, await build_msg(phien, ketqua))
            print(f"[✅] {phien} ({ketqua}) gửi thành công")
        except Exception as e:
            print(f"[❌] Lỗi auto_check: {e}")

# ===== CHẠY BOT =====
if __name__=="__main__":
    print("🚀 Khởi động bot Sunwin TX AI + Alert + Cầu 3–18 + Xúc xắc + Phân tích viên...")
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.add_handler(CommandHandler("prev", prev))
    app.create_task(auto_check(app))
    app.run_polling()
                                                  
