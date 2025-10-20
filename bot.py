import json
import random
import os
import requests
import asyncio
from typing import List, Dict, Any, Tuple
from telegram import Bot
from keep_alive import keep_alive   # giữ bot sống khi deploy

# ================= CONFIG =================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"      # ⚠️ thay bằng token bot của bạn
CHAT_ID = -1002666964512          # ID nhóm chat Telegram
HISTORY_FILE = "history.json"
MODEL_FILE = "model.json"
LEARN_N = 20
PATTERN_LEN = 3
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
POLL_INTERVAL = 15   # giây
MAX_MEMORY = 50
# ==========================================

# ======= Lưu & đọc dữ liệu =========
def load_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history: List[Dict[str, Any]]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-200:], f, ensure_ascii=False, indent=2)

def load_model() -> Dict[str, Any]:
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            model = json.load(f)
    else:
        model = None

    if not model:
        model = {
            "weights": {
                "pattern": 1.0, "avg": 1.0, "freq": 1.0,
                "streak": 1.0, "markov": 1.0, "chanle": 1.0,
                "dice": 1.0
            },
            "stats": {"win": 0, "lose": 0, "memory": []},
            "money": {"base": 10, "current_bet": 10}
        }
    return model

def save_model(model: Dict[str, Any]):
    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

# ======= Đọc cầu =========
def doc_cau(records: List[Dict[str, Any]], n: int = 12) -> Tuple[str, str]:
    """ Trả về (mô tả cầu, loại cầu) """
    if not records:
        return "Chưa có dữ liệu cầu.", "none"
    
    seq = [r.get("ket_qua") for r in records[-n:] if r.get("ket_qua")]
    if len(seq) < 4:
        return "Chưa đủ dữ liệu để đọc cầu.", "none"
    
    streak = 1
    last = seq[-1]
    for x in reversed(seq[:-1]):
        if x == last:
            streak += 1
        else:
            break

    if streak >= 4:
        return f"🔥 Cầu bệt {last}: {streak} phiên liên tiếp.", "bet"
    if all(seq[i] != seq[i+1] for i in range(len(seq)-1)):
        return "♻️ Cầu đảo: Tài/Xỉu xen kẽ liên tục.", "dao"
    if streak == 1 and seq[-2] != last:
        return f"⚡ Cầu {seq[-2]} vừa gãy, chuyển sang {last}.", "gay"
    
    return "⏳ Cầu chưa rõ ràng, cần theo dõi thêm.", "none"

# ======= AI Dự đoán =========
def ai_predict(records: List[Dict[str, Any]], model: Dict[str, Any]) -> Tuple[str, int, Dict[str, Any], str]:
    if not records:
        return "Tài", 50, {"note": "Chưa có dữ liệu"}, "none"

    cau_text, cau_type = doc_cau(records)

    # --- Chiến thuật như người chơi ---
    if cau_type == "bet":
        predict = records[-1]["ket_qua"]
        return predict, 80, {"cau": "bet"}, "none"

    if cau_type == "dao":
        predict = "Xỉu" if records[-1]["ket_qua"] == "Tài" else "Tài"
        return predict, 75, {"cau": "dao"}, "none"

    if cau_type == "gay":
        predict = records[-1]["ket_qua"]
        return predict, 70, {"cau": "gay"}, "chuyen_cau"

    # --- Nếu không rõ thì quay về xác suất ---
    weights = model["weights"]
    recs = records[-LEARN_N:]
    totals = [r.get("tong") for r in recs if r.get("tong")]
    avg_total = sum(totals) / len(totals) if totals else 10.5
    score_total = (avg_total - 10.5) / 4.5
    avg_score = 50 + score_total * 25

    last10 = records[-10:]
    tai_count = sum(1 for r in last10 if r.get("ket_qua") == "Tài")
    freq_score = (tai_count / max(1, len(last10))) * 100
    freq_score = 50 + (freq_score - 50) * 0.6

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

    probs = [avg_score * weights["avg"], freq_score * weights["freq"], markov_score * weights["markov"]]
    prob_tai = sum(probs) / sum(weights.values())
    prob_tai = max(10, min(90, prob_tai))

    predict = "Tài" if prob_tai >= 50 else "Xỉu"
    confidence = int(prob_tai if predict == "Tài" else 100 - prob_tai)

    return predict, confidence, {
        "avg_total": round(avg_total, 2),
        "freq_last10": f"{tai_count}T-{len(last10)-tai_count}X",
        "markov_score": round(markov_score, 2),
        "prob_tai": round(prob_tai, 2)
    }, "none"

# ======= Dự đoán xúc xắc =========
def ai_predict_dice(records: List[Dict[str, Any]]) -> List[int]:
    last50 = records[-50:]
    if not last50:
        return [random.randint(1, 6) for _ in range(3)]
    freq = {i: 1 for i in range(1, 7)}
    for r in last50:
        dice = r.get("dice")
        if dice:
            for d in dice:
                freq[d] += 1
    faces = list(freq.keys())
    weights = list(freq.values())
    return random.choices(faces, weights=weights, k=3)

# ======= Update model =========
def update_model(model: Dict[str, Any], predict: str, actual: str):
    if predict == actual:
        model["stats"]["win"] += 1
    else:
        model["stats"]["lose"] += 1
    model["stats"]["memory"].append(1 if predict == actual else 0)
    if len(model["stats"]["memory"]) > MAX_MEMORY:
        model["stats"]["memory"].pop(0)
    save_model(model)

# ======= Build message =========
def build_message(phien, kq, predict, conf, debug, dice_pred, dice_actual, tong, cau_text, note):
    dice_pred_txt = "\n".join([f"Xúc_xắc_{i+1}: {d}" for i, d in enumerate(dice_pred)])
    dice_real_txt = "\n".join([f"Xúc_xắc_{i+1}: {d}" for i, d in enumerate(dice_actual)]) if dice_actual else "N/A"

    msg = (
        f"📣 Phiên mới: <b>{phien}</b> — Kết quả: <b>{kq}</b>\n\n"
        f"🤖 AI dự đoán: <u>{predict}</u> ({conf}%)\n"
        f"🎲 Dự đoán xúc xắc:\n{dice_pred_txt}\n"
        f"✅ Kết quả xúc xắc:\n{dice_real_txt} → Tổng {tong}\n\n"
        f"🔍 Đọc cầu: {cau_text}\n"
    )

    if note == "chuyen_cau":
        msg += "\n⚡ <b>AI chuyển cầu!</b>\n"

    if debug:
        msg += (
            "\n📊 Phân tích:\n"
            f"- Trung bình tổng: {debug.get('avg_total')}\n"
            f"- Tần suất 10 gần nhất: {debug.get('freq_last10')}\n"
            f"- Markov: {debug.get('markov_score')}%\n"
            f"- Xác suất Tài: {debug.get('prob_tai')}%\n"
        )
    return msg

# ======= Build stats =========
def build_stats_message(model: Dict[str, Any]) -> str:
    total_games = model["stats"]["win"] + model["stats"]["lose"]
    if total_games == 0:
        return "📊 Chưa có dữ liệu thống kê."
    win = model["stats"]["win"]
    lose = model["stats"]["lose"]
    winrate = round(win / total_games * 100, 2)
    return (
        f"📊 Thống kê sau {total_games} phiên:\n"
        f"✅ Thắng: {win}\n"
        f"❌ Thua: {lose}\n"
        f"🎯 Winrate: {winrate}%"
    )

# ======= Auto Polling =========
async def main():
    bot = Bot(BOT_TOKEN)
    last_phien = None
    model = load_model()

    print("🤖 Bot is running...")

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

                    predict, conf, debug, note = ai_predict(history, model)
                    dice_pred = ai_predict_dice(history)
                    cau_text, _ = doc_cau(history)

                    msg = build_message(phien, kq, predict, conf, debug, dice_pred, dice_actual, tong, cau_text, note)
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

                    update_model(model, predict, kq)
                    last_phien = phien

                    # gửi thống kê sau mỗi 10 phiên
                    total_games = model["stats"]["win"] + model["stats"]["lose"]
                    if total_games % 10 == 0:
                        stats_msg = build_stats_message(model)
                        await bot.send_message(chat_id=CHAT_ID, text=stats_msg, parse_mode="HTML")

        except Exception as e:
            error_msg = f"❌ Lỗi API: {e}"
            print(error_msg)
            try:
                await bot.send_message(chat_id=CHAT_ID, text=error_msg)
            except:
                pass

        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
    
