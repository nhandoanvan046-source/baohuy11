import json
import random
import os
import requests
import asyncio
from typing import List, Dict, Any, Tuple
from telegram import Bot
from keep_alive import keep_alive   # giữ bot sống khi deploy

# ================= CONFIG =================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"   # ⚠️ Token bot
CHAT_ID = -1002666964512       # ID nhóm chat Telegram
HISTORY_FILE = "history.json"
MODEL_FILE = "model.json"
CHATLOG_FILE = "chatlog.txt"
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
            return json.load(f)
    return {
        "weights": {
            "pattern": 1.0, "avg": 1.0, "freq": 1.0,
            "streak": 1.0, "markov": 1.0, "chanle": 1.0,
            "dice": 1.0
        },
        "stats": {"win": 0, "lose": 0, "memory": [], "total": 0},
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

    # 🔥 Cầu bệt
    if streak >= 4:
        return f"🔥 Cầu bệt {last}: {streak} phiên liên tiếp."

    # ♻️ Cầu 1-1 xen kẽ (khác đảo loạn)
    if all(seq[i] != seq[i+1] for i in range(len(seq)-1)) and len(seq) >= 6:
        return "🔄 Cầu 1-1: Tài/Xỉu xen kẽ rõ ràng."

    # ♻️ Cầu đảo loạn
    if all(seq[i] != seq[i+1] for i in range(len(seq)-1)):
        return "♻️ Cầu đảo: Tài/Xỉu liên tục đổi."

    # ⚡ Cầu gãy
    if streak == 1 and seq[-2] != last:
        return f"⚡ Cầu {seq[-2]} vừa gãy, chuyển sang {last}."
    
    return "⏳ Cầu chưa rõ ràng, cần theo dõi thêm."


# ======= AI Dự đoán =========
def ai_predict(records: List[Dict[str, Any]], model: Dict[str, Any]) -> Tuple[str, int, str]:
    if not records:
        return "Tài", 50, "Chưa có dữ liệu, đánh thử Tài."

    cau_text = doc_cau(records)

    # Người chơi logic: cầu bệt
    if "Cầu bệt" in cau_text:
        last = records[-1]["ket_qua"]
        return last, 80, f"Thấy cầu bệt {last}, ôm cầu theo."

    # Cầu 1-1 xen kẽ
    if "Cầu 1-1" in cau_text:
        last = records[-1]["ket_qua"]
        next_move = "Xỉu" if last == "Tài" else "Tài"
        return next_move, 75, f"Cầu 1-1 rõ ràng, theo nhịp đảo, chọn {next_move}."

    # Cầu đảo loạn
    if "Cầu đảo" in cau_text:
        last = records[-1]["ket_qua"]
        next_move = "Xỉu" if last == "Tài" else "Tài"
        return next_move, 65, f"Cầu đảo liên tục, đánh ngược {last}."

    # Cầu gãy
    if "Cầu" in cau_text and "gãy" in cau_text:
        last = records[-1]["ket_qua"]
        return last, 70, f"Cầu vừa gãy, chuyển sang {last}."

    # Thống kê xác suất
    last10 = records[-10:]
    tai_count = sum(1 for r in last10 if r.get("ket_qua") == "Tài")
    if tai_count > len(last10)/2:
        return "Tài", 60, "Thống kê 10 ván gần đây nhiều Tài hơn."
    else:
        return "Xỉu", 60, "Thống kê 10 ván gần đây nhiều Xỉu hơn."


# ======= AI Dự đoán Xúc Xắc =========
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


# ======= Cập nhật mô hình =========
def update_model(model: Dict[str, Any], win_flag: bool):
    if win_flag:
        model["stats"]["win"] += 1
    else:
        model["stats"]["lose"] += 1
    model["stats"]["total"] += 1

    model["stats"]["memory"].append(1 if win_flag else 0)
    if len(model["stats"]["memory"]) > MAX_MEMORY:
        model["stats"]["memory"].pop(0)

    save_model(model)


# ======= Build Message =========
def build_message(phien, kq, predict, conf, reason, dice_pred, dice_actual, tong, cau_text, model):
    dice_pred_txt = " ".join(str(d) for d in dice_pred)
    dice_real_txt = " ".join(str(d) for d in dice_actual) if dice_actual else "N/A"

    win_rate = 0
    if model["stats"]["total"] > 0:
        win_rate = round(model["stats"]["win"] / model["stats"]["total"] * 100, 2)

    return (
        f"📣 Phiên mới: <b>{phien}</b> — Kết quả: <b>{kq}</b>\n\n"
        f"🤖 AI dự đoán: <u>{predict}</u> ({conf}%)\n"
        f"🗣️ Lý do: {reason}\n\n"
        f"🎲 Dự đoán xúc xắc: [{dice_pred_txt}] → Tổng {sum(dice_pred)}\n"
        f"✅ Kết quả xúc xắc: [{dice_real_txt}] → Tổng {tong}\n\n"
        f"🔍 Đọc cầu: {cau_text}\n\n"
        f"📊 Thống kê: {model['stats']['win']}W / {model['stats']['lose']}L "
        f"({win_rate}% win)"
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

                    predict, conf, reason = ai_predict(history, model)
                    dice_pred = ai_predict_dice(history)
                    cau_text = doc_cau(history)

                    msg = build_message(phien, kq, predict, conf, reason, dice_pred, dice_actual, tong, cau_text, model)
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

                    # ✅ Xác định win/lose
                    win_flag = (predict == kq)
                    update_model(model, win_flag)

                    # AI trò chuyện thêm sau mỗi ván
                    if win_flag:
                        await bot.send_message(chat_id=CHAT_ID, text="😎 Ván này chuẩn phết, bắt đúng luôn!")
                    else:
                        await bot.send_message(chat_id=CHAT_ID, text="😅 Hơi trượt, nhưng mình sẽ rút kinh nghiệm.")

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
    keep_alive()
    asyncio.run(main())
    
