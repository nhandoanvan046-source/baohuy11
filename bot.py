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
CHAT_ID = -1002666964512       # ID nhóm chat Telegram
HISTORY_FILE = "history.json"
MODEL_FILE = "model.json"
LEARN_N = 20
PATTERN_LEN = 3
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
POLL_INTERVAL = 15   # giây
MAX_MEMORY = 50      # số dự đoán AI nhớ gần nhất
# ==========================================


# ======= Lưu & đọc dữ liệu =========
def load_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history: List[Dict[str, Any]]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-200:], f, ensure_ascii=False, indent=2)  # chỉ lưu 200 phiên gần nhất

def load_model() -> Dict[str, Any]:
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "weights": {
            "pattern": 1.0, "avg": 1.0, "freq": 1.0,
            "streak": 1.0, "markov": 1.0, "chanle": 1.0,
            "dice": 1.0
        },
        "stats": {"win": 0, "lose": 0, "memory": []},
        "money": {"base": 10, "current_bet": 10}
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


# ======= AI Dự đoán Tài/Xỉu =========
def ai_predict(records: List[Dict[str, Any]], model: Dict[str, Any]) -> Tuple[str, int, Dict[str, Any]]:
    if not records:
        return "Tài", 50, {"note": "Chưa có dữ liệu"}

    weights = model["weights"]

    # --------- Pattern Detection ---------
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

    # --------- Trung bình tổng ---------
    recs = records[-LEARN_N:]
    totals = [r.get("tong") for r in recs if r.get("tong")]
    avg_total = sum(totals) / len(totals) if totals else 10.5
    score_total = (avg_total - 10.5) / 4.5
    avg_score = 50 + score_total * 25

    # --------- Tần suất gần nhất ---------
    last10 = records[-10:]
    tai_count = sum(1 for r in last10 if r.get("ket_qua") == "Tài")
    freq_score = (tai_count / max(1, len(last10))) * 100
    freq_score = 50 + (freq_score - 50) * 0.6

    # --------- Streak ---------
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

    # --------- Markov Chain ---------
    markov_score = 50
    if len(records) > 20:
        trans = {"Tài": {"Tài": 1, "Xỉu": 1}, "Xỉu": {"Tài": 1, "Xỉu": 1}}
        for i in range(len(records)-1):
            a, b = records[i]["ket_qua"], records[i+1]["ket_qua"]
            if a and b:
                trans[a][b] += 1
        last = records[-1]["ket_qua"]
        prob_tai = trans[last]["Tài"] / (trans[last]["Tài"] + trans[last]["Xỉu"])
        markov_score = prob_tai * 100

    # --------- Chẵn/Lẻ ---------
    chan = sum(1 for r in last10 if r.get("tong") % 2 == 0)
    le = len(last10) - chan
    chanle_score = (chan / (chan+le)) * 100 if le+chan else 50

    # --------- Kết hợp ---------
    probs = []
    if pattern_score is not None:
        probs.append(pattern_score * weights["pattern"])
    probs.append(avg_score * weights["avg"])
    probs.append(freq_score * weights["freq"])
    probs.append(streak_score * weights["streak"])
    probs.append(markov_score * weights["markov"])
    probs.append(chanle_score * weights["chanle"])

    prob_tai = sum(probs) / sum(weights.values())
    prob_tai = max(10, min(90, prob_tai))

    predict = "Tài" if prob_tai >= 50 else "Xỉu"
    confidence = int(prob_tai if predict == "Tài" else 100 - prob_tai)

    return predict, confidence, {
        "pattern_score": pattern_score,
        "avg_total": round(avg_total, 2),
        "freq_last10": f"{tai_count}T-{len(last10)-tai_count}X",
        "last_streak": f"{streak} {last_result}" if last_result else "N/A",
        "markov_score": round(markov_score, 2),
        "chanle_score": round(chanle_score, 2),
        "prob_tai": round(prob_tai, 2),
        "weights": weights
    }


# ======= AI Dự đoán Xúc Xắc =========
def ai_predict_dice(records: List[Dict[str, Any]], model: Dict[str, Any]) -> List[int]:
    last50 = records[-50:]
    if not last50:
        return [random.randint(1, 6) for _ in range(3)]

    # Thống kê tần suất mặt xúc xắc
    freq = {i: 1 for i in range(1, 7)}  # tránh chia 0
    for r in last50:
        dice = r.get("dice")
        if dice:
            for d in dice:
                freq[d] += 1

    # Xác suất chọn mặt theo tần suất
    faces = list(freq.keys())
    weights = list(freq.values())
    dice_pred = random.choices(faces, weights=weights, k=3)
    return dice_pred


# ======= Cập nhật mô hình =========
def update_model(model: Dict[str, Any], predict: str, actual: str, dice_pred: List[int], dice_actual: List[int]):
    if predict == actual:
        model["stats"]["win"] += 1
    else:
        model["stats"]["lose"] += 1

    # học dice: nếu đoán đúng ≥2 mặt thì coi như win
    match = sum(1 for d in dice_pred if d in dice_actual)
    if match >= 2:
        model["weights"]["dice"] = min(3.0, model["weights"]["dice"] * 1.1)
    else:
        model["weights"]["dice"] = max(0.5, model["weights"]["dice"] * 0.9)

    # memory
    model["stats"]["memory"].append(1 if predict == actual else 0)
    if len(model["stats"]["memory"]) > MAX_MEMORY:
        model["stats"]["memory"].pop(0)

    save_model(model)


# ======= Build Message =========
def build_message(phien, kq, predict, conf, debug, dice_pred, dice_actual, tong):
    cau_text = doc_cau(load_history())
    dice_pred_txt = " ".join(str(d) for d in dice_pred)
    dice_real_txt = " ".join(str(d) for d in dice_actual) if dice_actual else "N/A"
    return (
        f"📣 Phiên mới: <b>{phien}</b> — Kết quả: <b>{kq}</b>\n\n"
        f"🤖 AI dự đoán: <u>{predict}</u> ({conf}%)\n"
        f"🎲 Dự đoán xúc xắc: [{dice_pred_txt}] → Tổng {sum(dice_pred)}\n"
        f"✅ Kết quả xúc xắc: [{dice_real_txt}] → Tổng {tong}\n\n"
        f"📊 Phân tích:\n"
        f"- Trung bình tổng: {debug.get('avg_total')}\n"
        f"- Tần suất 10 gần nhất: {debug.get('freq_last10')}\n"
        f"- Chuỗi hiện tại: {debug.get('last_streak')}\n"
        f"- Markov: {debug.get('markov_score')}%\n"
        f"- Chẵn/Lẻ: {debug.get('chanle_score')}%\n"
        f"- Xác suất Tài: {debug.get('prob_tai')}%\n\n"
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
                dice_actual = data.get("dice") or []

                if phien != last_phien:
                    history = load_history()
                    history.append({"phien": phien, "ket_qua": kq, "tong": tong, "dice": dice_actual})
                    save_history(history)

                    predict, conf, debug = ai_predict(history, model)
                    dice_pred = ai_predict_dice(history, model)

                    msg = build_message(phien, kq, predict, conf, debug, dice_pred, dice_actual, tong)
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

                    update_model(model, predict, kq, dice_pred, dice_actual)
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
    
