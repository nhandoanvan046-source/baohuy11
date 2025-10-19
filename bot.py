import json
import random
import os
import requests
import asyncio
from typing import List, Dict, Any, Tuple
from telegram import Bot
from keep_alive import keep_alive   # giữ bot sống khi deploy

# ================= CONFIG =================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"   # ⚠️ Thay bằng token bot của bạn
CHAT_ID = -1002666964512            # ID nhóm chat Telegram
HISTORY_FILE = "history.json"
MODEL_FILE = "model.json"
LEARN_N = 20
PATTERN_LEN = 3
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
POLL_INTERVAL = 15   # giây
# ==========================================

# ======= Lưu & đọc dữ liệu =========
def load_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history: List[Dict[str, Any]]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_model() -> Dict[str, Any]:
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "weights": {"pattern": 1.0, "avg": 1.0, "freq": 1.0, "streak": 1.0},
        "stats": {"win": 0, "lose": 0}
    }

def save_model(model: Dict[str, Any]):
    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

# ======= Đọc cầu =========
def doc_cau(records: List[Dict[str, Any]], n: int = 12) -> str:
    if not records:
        return "Chưa có dữ liệu cầu."
    
    seq = [r.get("ket_qua") for r in records[-n:] if r.get("ket_qua")]
    if len(seq) < 4:
        return "Chưa đủ dữ liệu để đọc cầu."
    
    streak = 1
    last = seq[-1]
    for x in reversed(seq[:-1]):
        if x == last:
            streak += 1
        else:
            break
    if streak >= 4:
        return f"🔥 Cầu bệt {last}: {streak} phiên liên tiếp."
    if all(seq[i] != seq[i+1] for i in range(len(seq)-1)):
        return "♻️ Cầu đảo: Tài/Xỉu xen kẽ liên tục."
    if streak == 1 and seq[-2] != last:
        return f"⚡ Cầu {seq[-2]} vừa gãy, chuyển sang {last}."
    
    return "⏳ Cầu chưa rõ ràng, cần theo dõi thêm."

# ======= AI Dự đoán =========
def ai_predict(records: List[Dict[str, Any]], model: Dict[str, Any]) -> Tuple[str, int, Dict[str, Any]]:
    if not records:
        return "Tài", 50, {"note": "Chưa có dữ liệu"}

    weights = model["weights"]

    # --------- 1. Học mẫu ---------
    pattern_score = None
    if len(records) > PATTERN_LEN + 5:
        patterns = {}
        for i in range(len(records) - PATTERN_LEN):
            seq = tuple(r["ket_qua"] for r in records[i:i+PATTERN_LEN])
            nxt = records[i+PATTERN_LEN]["ket_qua"]
            if seq not in patterns:
                patterns[seq] = {"Tài": 0, "Xỉu": 0}
            patterns[seq][nxt] += 1

        current_seq = tuple(r["ket_qua"] for r in records[-PATTERN_LEN:])
        if current_seq in patterns:
            stats = patterns[current_seq]
            total = stats["Tài"] + stats["Xỉu"]
            pattern_score = (stats["Tài"] / total) * 100

    # --------- 2. Trung bình tổng ---------
    recs = records[-LEARN_N:]
    totals = [r.get("tong") for r in recs if r.get("tong")]
    avg_total = sum(totals) / len(totals) if totals else 10.5
    score_total = (avg_total - 10.5) / 4.5
    avg_score = 50 + score_total * 25

    # --------- 3. Tần suất gần nhất ---------
    last10 = records[-10:]
    tai_count = sum(1 for r in last10 if r.get("ket_qua") == "Tài")
    freq_score = (tai_count / max(1, len(last10))) * 100
    freq_score = 50 + (freq_score - 50) * 0.6

    # --------- 4. Streak ---------
    streak = 1
    last_result = records[-1].get("ket_qua")
    for r in reversed(records[:-1]):
        if r.get("ket_qua") == last_result:
            streak += 1
        else:
            break
    if last_result == "Tài":
        streak_score = 50 - min(20, streak * 5)
    else:
        streak_score = 50 + min(20, streak * 5)

    # --------- 5. Kết hợp ---------
    probs = []
    if pattern_score is not None:
        probs.append(pattern_score * weights["pattern"])
    probs.append(avg_score * weights["avg"])
    probs.append(freq_score * weights["freq"])
    probs.append(streak_score * weights["streak"])

    prob_tai = sum(probs) / sum(weights.values())
    prob_tai = max(10, min(90, prob_tai))

    predict = "Tài" if prob_tai >= 50 else "Xỉu"
    confidence = int(prob_tai if predict == "Tài" else 100 - prob_tai)

    debug = {
        "pattern_score": pattern_score,
        "avg_total": round(avg_total, 2),
        "freq_last10": f"{tai_count}T-{len(last10)-tai_count}X",
        "last_streak": f"{streak} {last_result}" if last_result else "N/A",
        "prob_tai": round(prob_tai, 2),
        "weights": weights
    }
    return predict, confidence, debug

# ======= Dự đoán xúc xắc =========
def predict_dice(prob_tai: float) -> List[int]:
    if prob_tai >= 50:
        total = random.randint(11, 17)
    else:
        total = random.randint(4, 10)

    dice = []
    for i in range(2):
        val = random.randint(1, min(6, total - 1))
        dice.append(val)
        total -= val
    dice.append(max(1, min(6, total)))
    random.shuffle(dice)
    return dice

# ======= Cập nhật mô hình =========
def update_model(model: Dict[str, Any], predict: str, actual: str):
    if predict == actual:
        model["stats"]["win"] += 1
        for k in model["weights"]:
            model["weights"][k] = round(min(3.0, model["weights"][k] * 1.05), 2)
    else:
        model["stats"]["lose"] += 1
        for k in model["weights"]:
            model["weights"][k] = round(max(0.2, model["weights"][k] * 0.95), 2)

    total = model["stats"]["win"] + model["stats"]["lose"]
    winrate = model["stats"]["win"] / total * 100 if total else 0
    print(f"[Auto-Learning] ✅ Win: {model['stats']['win']} ❌ Lose: {model['stats']['lose']} | Winrate: {winrate:.1f}%")
    save_model(model)

# ======= Build Message =========
def build_message(phien, kq, predict, conf, debug, dice, total):
    cau_text = doc_cau(load_history())
    return (
        f"📣 Phiên mới: <b>{phien}</b> — Kết quả: <b>{kq}</b>\n\n"
        f"🤖 AI dự đoán: <u>{predict}</u> ({conf}%)\n"
        f"🎲 Dự đoán xúc xắc: {dice} → Tổng {total}\n\n"
        f"📊 Phân tích:\n"
        f"- Trung bình tổng: {debug.get('avg_total')}\n"
        f"- Tần suất 10 gần nhất: {debug.get('freq_last10')}\n"
        f"- Chuỗi hiện tại: {debug.get('last_streak')}\n"
        f"- Xác suất Tài: {debug.get('prob_tai')}%\n"
        f"- Trọng số: {debug.get('weights')}\n\n"
        f"🔍 Đọc cầu: {cau_text}"
    )

# ======= Auto Polling (async) =========
async def main():
    bot = Bot(BOT_TOKEN)
    last_phien = None
    model = load_model()

    print("🤖 Bot is running (async)...")

    while True:
        try:
            r = requests.get(API_URL, timeout=10)
            if r.status_code == 200:
                data = r.json()
                phien = str(data.get("phien"))
                kq = str(data.get("ket_qua")).capitalize()
                tong = int(data.get("tong", random.randint(4, 17)))

                if phien != last_phien:
                    history = load_history()
                    history.append({"phien": phien, "ket_qua": kq, "tong": tong})
                    save_history(history)

                    predict, conf, debug = ai_predict(history, model)
                    dice = predict_dice(debug["prob_tai"])
                    total = sum(dice)

                    msg = build_message(phien, kq, predict, conf, debug, dice, total)
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

                    update_model(model, predict, kq)
                    last_phien = phien

        except Exception as e:
            error_msg = f"❌ Lỗi API: {e}"
            print(error_msg)
            try:
                await bot.send_message(chat_id=CHAT_ID, text=error_msg)
            except:
                pass

        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    keep_alive()   # giữ cho bot chạy 24/7
    asyncio.run(main())
                
