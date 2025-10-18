import asyncio, requests, json, os
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
CHECK_INTERVAL = 10  # giây
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
        r = requests.get(API_URL, timeout=15)
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
    except Exception as e:
        print(f"[❌] Lỗi get_data: {e}")
        return None, None, None, None, None, None

def save(phien, ketqua, x1=None, x2=None, x3=None, tong=None):
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

def analyze_cau_advanced(min_len=3, max_len=18):
    trend = list(history_trend)
    if len(trend) < min_len:
        return "Chưa đủ dữ liệu để phân tích cầu"
    
    results = []
    longest = {"Tài":0, "Xỉu":0}
    
    for i in range(len(trend)):
        count = 1
        for j in range(i+1, len(trend)):
            if trend[j] == trend[i]:
                count += 1
            else:
                break
        if count >= min_len:
            results.append(f"{count} {trend[i]} liên tiếp (phiên {i+1}-{i+count})")
            if count > longest[trend[i]]:
                longest[trend[i]] = count
    
    if not results:
        return "Không có chuỗi đặc biệt 3–18 phiên gần nhất"

    alerts = []
    for key, val in longest.items():
        if val >= 5:
            alerts.append(f"⚠️ Chuỗi dài {val} {key} liên tiếp!")
    
    return "Cầu phân tích:\n" + "\n".join(results + alerts)

# ===== DỰ ĐOÁN XÍ NGẦU & CẦU =====
def predict_next_trend():
    if not history_trend:
        return "Chưa đủ dữ liệu để dự đoán"
    last3 = list(history_trend)[-3:]
    if all(r == "Tài" for r in last3):
        return "Ước lượng: Xỉu có khả năng xuất hiện để cân bằng"
    elif all(r == "Xỉu" for r in last3):
        return "Ước lượng: Tài có khả năng xuất hiện để cân bằng"
    else:
        total = len(history_all)
        tai_count = sum(1 for r in history_all if r["ket_qua"] == "Tài")
        xiu_count = sum(1 for r in history_all if r["ket_qua"] == "Xỉu")
        return f"Dự đoán thống kê: {'Tài' if tai_count>=xiu_count else 'Xỉu'} (Winrate: Tài {tai_count/total*100:.1f}% | Xỉu {xiu_count/total*100:.1f}%)"

def auto_predict_cau():
    if len(history_trend) < 3:
        return "Chưa đủ dữ liệu dự đoán cầu"
    last3 = list(history_trend)[-3:]
    if all(r == "Tài" for r in last3):
        return "⚡ Dự đoán cầu: Xỉu có khả năng ra để cân bằng"
    elif all(r == "Xỉu" for r in last3):
        return "⚡ Dự đoán cầu: Tài có khả năng ra để cân bằng"
    else:
        tai_count = sum(1 for r in history_all if r["ket_qua"] == "Tài")
        xiu_count = sum(1 for r in history_all if r["ket_qua"] == "Xỉu")
        return f"⚡ Dự đoán cầu theo winrate: {'Tài' if tai_count>=xiu_count else 'Xỉu'}"

def dice_face_probability_advanced(last_n=10):
    faces = []
    for h in history_all[-last_n:]:
        faces.extend([h.get("xuc_xac_1"), h.get("xuc_xac_2"), h.get("xuc_xac_3")])
    counts = Counter(faces)
    total = sum(counts.values())
    if total == 0:
        return "Chưa có dữ liệu mặt xúc xắc"
    
    max_count = max(counts.values())
    most_likely = [face for face, count in counts.items() if count == max_count]
    symbols = {1:'⚀',2:'⚁',3:'⚂',4:'⚃',5:'⚄',6:'⚅'}
    
    prob_str = f"Xác suất mặt xúc xắc ({last_n} phiên gần nhất):\n"
    for face in range(1,7):
        prob = counts.get(face,0)/total*100
        mark = "🔥" if face in most_likely else ""
        prob_str += f"{symbols[face]} {prob:.1f}% {mark}\n"
    
    return prob_str.strip()

def dice_mini_board(x1,x2,x3):
    symbols = {1:'⚀',2:'⚁',3:'⚂',4:'⚃',5:'⚄',6:'⚅'}
    return f"{symbols.get(x1,'?')} {symbols.get(x2,'?')} {symbols.get(x3,'?')} → Tổng: {x1+x2+x3}"

# ===== BUILD MESSAGE =====
def build_msg(phien, ketqua, tong, x1, x2, x3):
    t = datetime.now().strftime("%H:%M:%S")
    trend = analyze_trend()
    wr = winrate()
    alert = check_alert()
    sp = check_special()
    predict = predict_next_trend()
    predict_cau = auto_predict_cau()
    cau_analysis = analyze_cau_advanced()
    dice_stats = dice_face_probability_advanced(10)
    prev = "Chưa có"
    if len(history_all) >= 2:
        last = history_all[-2]
        prev = f"{last['ket_qua']} (Phiên {last['phien']})"
    dice_display = dice_mini_board(x1, x2, x3) if USE_MINIBOARD else f"{x1} | {x2} | {x3} → Tổng: {tong}"

    msg = (
        f"Sunwin TX 🎲\n"
        f"🕒 {t}\n"
        f"🧩 Phiên: {phien}\n"
        f"Xúc xắc: {dice_display}\n"
        f"Kết quả: {ketqua}\n"
        f"Phiên trước: {prev}\n\n"
        f"{trend}\n{wr}\n{predict}\n{predict_cau}\n{cau_analysis}\n{dice_stats}"
    )
    if alert:
        msg += f"\n{alert}"
    if sp:
        msg += f"\n{sp}"
    return msg

# ===== LỆNH BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Sunwin TX Bot\n• /taixiu → Xem kết quả + xu hướng + winrate + cầu 3–18 + dự đoán\nBot auto gửi theo phiên mới 🤖"
    )

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phien, ketqua, x1, x2, x3, tong = get_data()
    if not phien:
        await update.message.reply_text("⚠️ Không thể lấy dữ liệu")
        return
    save(phien, ketqua, x1, x2, x3, tong)
    await update.message.reply_text(build_msg(phien, ketqua, tong, x1, x2, x3))

async def prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(history_all) < 2:
        await update.message.reply_text("Chưa có phiên trước")
        return
    last = history_all[-2]
    msg = f"Phiên trước: {last['phien']}\nKết quả: {last['ket_qua']}\nXúc xắc: {last.get('xuc_xac_1')}|{last.get('xuc_xac_2')}|{last.get('xuc_xac_3')}"
    await update.message.reply_text(msg)

# ===== AUTO GỬI THEO PHIÊN =====
async def auto_check(app):
    global last_phien
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        phien, ketqua, x1, x2, x3, tong = get_data()
        if not phien or phien == last_phien:
            continue
        last_phien = phien
        save(phien, ketqua, x1, x2, x3, tong)
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

    # Auto gửi theo phiên
    asyncio.create_task(auto_check(app))
    await app.run_polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
        
