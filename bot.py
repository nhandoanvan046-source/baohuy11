import asyncio, requests, json, os, nest_asyncio
from datetime import datetime
from collections import deque, Counter
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from keep_alive import keep_alive  # Render keep_alive

# ===== CẤU HÌNH =====
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"
GROUP_ID = -1002666964512
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
HISTORY_FILE = "history.json"
TREND_LEN = 10
ALERT_STREAK = 5
ALERT_SPECIAL = 3
WINRATE_THRESHOLD = 70
CHECK_INTERVAL = 5       # giây kiểm tra phiên mới
RESET_INTERVAL = 12*3600 # 12 giờ tự reset
USE_MINIBOARD = True
# ===================

# ===== LOAD HISTORY =====
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write("[]")

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    history_all = json.load(f)

history_trend = deque([r["ket_qua"] for r in history_all[-TREND_LEN:]], maxlen=TREND_LEN)
last_phien = history_all[-1]["phien"] if history_all else None

# ===== HỖ TRỢ API =====
def get_data():
    try:
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
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
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history_all.append(record)
    history_trend.append(ketqua)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_all, f, ensure_ascii=False, indent=2)

# ===== PHÂN TÍCH =====
def analyze_trend():
    tai = history_trend.count("Tài")
    xiu = history_trend.count("Xỉu")
    if len(history_trend) < 3:
        return "Chưa đủ dữ liệu để phân tích xu hướng"
    return f"Xu hướng: Tài {tai}/{len(history_trend)} | Xỉu {xiu}/{len(history_trend)}"

def winrate():
    tai = sum(1 for r in history_all if r["ket_qua"] == "Tài")
    xiu = sum(1 for r in history_all if r["ket_qua"] == "Xỉu")
    total = len(history_all)
    if total == 0:
        return "Chưa có dữ liệu winrate"
    return f"Winrate: Tài {tai}/{total} | Xỉu {xiu}/{total}"

def check_alert():
    last = list(history_trend)[-ALERT_STREAK:]
    if len(last) < ALERT_STREAK:
        return None
    if all(r == "Tài" for r in last):
        return "⚠️ 5 Tài liên tiếp!"
    if all(r == "Xỉu" for r in last):
        return "⚠️ 5 Xỉu liên tiếp!"
    return None

def check_special():
    last = list(history_trend)[-ALERT_SPECIAL:]
    if len(last) < ALERT_SPECIAL:
        return None
    tai = sum(1 for r in history_all if r["ket_qua"] == "Tài")
    xiu = sum(1 for r in history_all if r["ket_qua"] == "Xỉu")
    total = len(history_all)
    if all(r == "Tài" for r in last) and tai / total * 100 >= WINRATE_THRESHOLD:
        return "⚠️ 3 Tài liên tiếp + Winrate >70%!"
    if all(r == "Xỉu" for r in last) and xiu / total * 100 >= WINRATE_THRESHOLD:
        return "⚠️ 3 Xỉu liên tiếp + Winrate >70%!"
    return None

def predict_next():
    count = Counter(history_trend)
    if not count:
        return "Chưa đủ dữ liệu để dự đoán"
    return "Dự đoán phiên tiếp theo: Tài" if count["Tài"] > count["Xỉu"] else "Dự đoán phiên tiếp theo: Xỉu"

def analyze_cau(min_len=3, max_len=18):
    if len(history_trend) < min_len:
        return "Chưa đủ dữ liệu để phân tích cầu"
    trend = list(history_trend)
    results = []
    for length in range(min_len, min(max_len + 1, len(trend) + 1)):
        sub = trend[-length:]
        if all(x == "Tài" for x in sub):
            results.append(f"{length} Tài liên tiếp")
        elif all(x == "Xỉu" for x in sub):
            results.append(f"{length} Xỉu liên tiếp")
    if not results:
        return "Không có chuỗi đặc biệt 3–18 phiên gần nhất"
    return "Cầu phân tích:\n" + "\n".join(results)

# ===== MINI-BOARD XÚC XẮC =====
def dice_mini_board(x1,x2,x3):
    return f"🎲 {x1} | {x2} | {x3} → Tổng: {x1+x2+x3}"

# ===== TRỌNG SỐ ĐỘNG =====
def dynamic_weights():
    last_n = min(len(history_trend), 10)
    recent = list(history_trend)[-last_n:]
    
    streak_len = 1
    for i in range(2, last_n+1):
        if recent[-i] == recent[-i+1]:
            streak_len += 1
        else:
            break
    
    streak_w = max(0.2, 0.5 - 0.05*streak_len)
    winrate_w = min(0.5, 0.3 + 0.05*streak_len)
    avg_sum_w = 0.2
    face_w = 0.1
    
    return streak_w, winrate_w, avg_sum_w, face_w

# ===== AI DỰ ĐOÁN 3 PHIÊN NÂNG CAO =====
def ai_predict_next_n_advanced(n=3, last_n=5, face_n=10):
    if len(history_trend) < last_n or not history_all:
        return ["Chưa đủ dữ liệu dự đoán cầu"]

    predictions = []
    trend_copy = list(history_trend)
    
    for i in range(n):
        recent = trend_copy[-last_n:]
        streak_score = sum((1 if r=="Tài" else -1)/ (j+1) for j,r in enumerate(recent[::-1]))
        
        tai_count = sum(1 for r in history_all if r["ket_qua"]=="Tài")
        xiu_count = sum(1 for r in history_all if r["ket_qua"]=="Xỉu")
        total = len(history_all)
        winrate_score = (tai_count - xiu_count)/total if total else 0

        faces=[]
        for h in history_all[-face_n:]:
            faces.extend([
                int(h.get("xuc_xac_1",0)),
                int(h.get("xuc_xac_2",0)),
                int(h.get("xuc_xac_3",0))
            ])
        if faces:
            avg_sum = sum(faces)/len(faces)
            avg_sum_score = 1 if avg_sum>10 else -1
            low_faces = faces.count(1)+faces.count(2)
            high_faces = faces.count(5)+faces.count(6)
            face_score = 1 if high_faces > low_faces else -1
        else:
            avg_sum_score = 0
            face_score = 0

        streak_w, winrate_w, avg_sum_w, face_w = dynamic_weights()
        final_score = streak_score*streak_w + winrate_score*winrate_w + avg_sum_score*avg_sum_w + face_score*face_w
        
        recent_n = min(10, len(history_trend))
        tai_recent = list(history_trend)[-recent_n:].count("Tài")
        xiu_recent = recent_n - tai_recent
        prob_base = abs(final_score)*50 + 50
        prob_adjust = (tai_recent - xiu_recent)/recent_n * 10
        prob = min(max(prob_base + prob_adjust, 50), 95)
        
        choice = "Tài" if final_score > 0 else "Xỉu"
        predictions.append(f"Phiên +{i+1}: {choice} ({prob:.0f}%)")
        trend_copy.append(choice)

    return predictions

# ===== BUILD MESSAGE =====
def build_msg(phien, ketqua, tong, x1,x2,x3):
    t=datetime.now().strftime("%H:%M:%S")
    trend=analyze_trend()
    wr=winrate()
    alert=check_alert()
    sp=check_special()
    predict=predict_next()
    cau_analysis=analyze_cau(3,18)
    predict_ai_multi="\n".join(ai_predict_next_n_advanced(3, last_n=5, face_n=10))
    prev="Chưa có"
    if len(history_all)>=2:
        last=history_all[-2]
        prev=f"{last['ket_qua']} (Phiên {last['phien']})"
    dice_display=dice_mini_board(x1,x2,x3) if USE_MINIBOARD else f"{x1}|{x2}|{x3}→Tổng:{tong}"
    msg=(
        f"Sunwin TX 🎲 v4.1\n"
        f"🕒 {t}\n"
        f"🧩 Phiên: {phien}\n"
        f"Xúc xắc: {dice_display}\n"
        f"Kết quả: {ketqua}\n"
        f"Phiên trước: {prev}\n\n"
        f"{trend}\n{wr}\n{predict}\n{predict_ai_multi}\n{cau_analysis}"
    )
    if alert: msg+=f"\n{alert}"
    if sp: msg+=f"\n{sp}"
    return msg

# ===== LỆNH BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Sunwin TX Bot v4.1\n• /taixiu → Xem kết quả + xu hướng + winrate + cầu 3–18\nBot auto gửi theo phiên mới 🤖"
    )

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua, x1, x2, x3, tong = get_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu")
        return
    save(phien, ketqua, x1,x2,x3,tong)
    await update.message.reply_text(build_msg(phien, ketqua, tong, x1,x2,x3))

async def prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(history_all)<2:
        await update.message.reply_text("Chưa có phiên trước")
        return
    last=history_all[-2]
    msg=f"Phiên trước: {last['phien']}\nKết quả: {last['ket_qua']}"
    await update.message.reply_text(msg)

# ===== AUTO GỬI =====
async def auto_check(app):
    global last_phien
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        phien, ketqua, x1, x2, x3, tong = get_data()
        if not phien or phien==last_phien:
            continue
        last_phien=phien
        save(phien, ketqua, x1,x2,x3,tong)
        try:
            await app.bot.send_message(GROUP_ID, build_msg(phien, ketqua, tong, x1,x2,x3))
            print(f"[✅] {phien} ({ketqua}) gửi thành công")
        except Exception as e:
            print(f"[❌] Lỗi gửi {phien}: {e}")

# ===== AUTO RESET 12H =====
async def auto_reset():
    global history_all, history_trend, last_phien
    while True:
        await asyncio.sleep(RESET_INTERVAL)
        history_all.clear()
        history_trend.clear()
        last_phien=None
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("[♻️] Auto reset dữ liệu 12h thành công")

# ===== CHẠY BOT =====
async def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taixiu", taixiu))
    app.add_handler(CommandHandler("prev", prev))

    asyncio.create_task(auto_check(app))
    asyncio.create_task(auto_reset())

    await app.start()
    await app.updater.start_polling()
    print("[🚀] Bot chạy thành công")
    await app.idle()

nest_asyncio.apply()
asyncio.run(main())
        
