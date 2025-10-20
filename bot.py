import json
import random
import os
import requests
import asyncio
from typing import List, Dict, Any, Tuple
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

# ================= CONFIG =================
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"   # ⚠️ Thay bằng token bot của bạn
CHAT_ID = -1002666964512        # ID nhóm chat Telegram
HISTORY_FILE = "history.json"
MODEL_FILE = "model.json"
CHATLOG_FILE = "chatlog.txt"
LEARN_N = 20
PATTERN_LEN = 3
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"
POLL_INTERVAL = 15
MAX_MEMORY = 50
# ==========================================

# ======= Lưu log =========
def log_event(text: str):
    with open(CHATLOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

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
        "stats": {"win": 0, "lose": 0, "memory": []},
        "mood": "neutral"
    }

def save_model(model: Dict[str, Any]):
    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

# ======= Đọc cầu =========
def doc_cau(records: List[Dict[str, Any]], n: int = 12) -> str:
    if not records: return "Chưa có dữ liệu cầu."
    seq = [r.get("ket_qua") for r in records[-n:] if r.get("ket_qua")]
    if len(seq) < 4: return "Chưa đủ dữ liệu để đọc cầu."

    streak = 1
    last = seq[-1]
    for x in reversed(seq[:-1]):
        if x == last: streak += 1
        else: break

    # cầu bệt
    if streak >= 4: return f"🔥 Cầu bệt {last}: {streak} phiên liên tiếp."
    # cầu đảo 1-1
    if all(seq[i] != seq[i+1] for i in range(len(seq)-1)): 
        return "♻️ Cầu 1-1 xen kẽ: Tài/Xỉu liên tục."
    # cầu gãy
    if streak == 1 and seq[-2] != last:
        return f"⚡ Cầu {seq[-2]} vừa gãy, chuyển sang {last}."
    return "⏳ Cầu chưa rõ ràng."

# ======= AI dự đoán =========
def ai_predict(records: List[Dict[str, Any]], model: Dict[str, Any]) -> Tuple[str, int, str]:
    if not records: return "Tài", 50, "Chưa có dữ liệu."

    cau_text = doc_cau(records)
    reason = ""
    predict = "Tài"
    conf = 60

    if "Cầu bệt" in cau_text:
        last = records[-1]["ket_qua"]
        predict, reason, conf = last, f"Ôm cầu bệt {last}", 75
    elif "Cầu 1-1" in cau_text:
        last = records[-1]["ket_qua"]
        predict = "Tài" if last == "Xỉu" else "Xỉu"
        reason, conf = "Cầu 1-1, đánh ngược", 70
    elif "Cầu vừa gãy" in cau_text:
        last = records[-1]["ket_qua"]
        predict, reason, conf = last, "Cầu gãy, tôi chuyển cầu", 65
    else:
        # fallback thống kê
        last10 = records[-10:]
        tai_count = sum(1 for r in last10 if r["ket_qua"] == "Tài")
        prob_tai = (tai_count / max(1,len(last10))) * 100
        predict = "Tài" if prob_tai >= 50 else "Xỉu"
        conf = int(abs(prob_tai-50)+50)
        reason = f"Thống kê 10 ván gần đây: {tai_count} Tài"

    return predict, conf, reason

# ======= AI dự đoán xúc xắc =========
def ai_predict_dice(records: List[Dict[str, Any]]) -> List[int]:
    last50 = records[-50:]
    if not last50: return [random.randint(1,6) for _ in range(3)]
    freq = {i:1 for i in range(1,7)}
    for r in last50:
        if r.get("dice"):
            for d in r["dice"]: freq[d]+=1
    return random.choices(list(freq.keys()), weights=list(freq.values()), k=3)

# ======= Cập nhật mô hình =========
def update_model(model: Dict[str, Any], predict: str, actual: str):
    if predict == actual: model["stats"]["win"]+=1; model["mood"]="happy"
    else: model["stats"]["lose"]+=1; model["mood"]="sad"
    save_model(model)
    return predict == actual

# ======= AI trò chuyện sau ván =========
def ai_chat_after_game(win_flag: bool, model: Dict[str, Any]) -> str:
    if win_flag:
        msgs = ["😎 Thấy chưa, tôi nói mà!", "🔥 Ăn nhẹ nhàng!", "😁 Lại win rồi anh em!"]
    else:
        msgs = ["😤 Hơi đen, cầu gãy rồi!", "😅 Thua nhưng không nản!", "🤔 Sai 1 ly đi 1 dặm."]
    return random.choice(msgs)

# ======= Build Message =========
def build_message(phien, kq, predict, conf, reason, dice_pred, dice_actual, tong, model):
    dice_pred_txt = " ".join(str(d) for d in dice_pred)
    dice_real_txt = " ".join(str(d) for d in dice_actual) if dice_actual else "N/A"
    cau_text = doc_cau(load_history())
    return (
        f"📣 Phiên {phien} — Kết quả: <b>{kq}</b>\n\n"
        f"🤖 AI dự đoán: <u>{predict}</u> ({conf}%)\n"
        f"📝 Lý do: {reason}\n"
        f"🎲 Dự đoán xúc xắc: [{dice_pred_txt}] | KQ: [{dice_real_txt}] → Tổng {tong}\n\n"
        f"🔍 Đọc cầu: {cau_text}\n"
        f"📊 Thống kê: {model['stats']['win']} win / {model['stats']['lose']} lose"
    )

# ======= Nhận chat từ người dùng =========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.message.from_user.first_name
    log_event(f"{user}: {text}")
    reply = f"👀 Tôi ghi lại ý kiến của {user}: '{text}'"
    await context.bot.send_message(chat_id=CHAT_ID, text=reply)

# ======= Auto Polling =========
async def auto_predict(bot: Bot):
    last_phien = None
    model = load_model()
    while True:
        try:
            r = requests.get(API_URL, timeout=10)
            if r.status_code==200:
                data=r.json()
                phien=str(data.get("phien"))
                kq=str(data.get("ket_qua")).capitalize()
                tong=int(data.get("tong", random.randint(4,17)))
                dice_actual=data.get("dice") or []

                if phien!=last_phien:
                    history=load_history()
                    history.append({"phien":phien,"ket_qua":kq,"tong":tong,"dice":dice_actual})
                    save_history(history)

                    # 👉 AI hỏi trước khi dự đoán
                    ask_msg=random.choice([
                        "🤔 Theo anh em thì ván này ra gì?",
                        "❓ Mọi người nghĩ cầu này tiếp tục không?",
                        "👀 Có ai thấy cầu bệt không?"
                    ])
                    await bot.send_message(chat_id=CHAT_ID, text=ask_msg)
                    log_event(f"AI hỏi: {ask_msg}")

                    await asyncio.sleep(random.randint(5,8))

                    predict,conf,reason=ai_predict(history,model)
                    dice_pred=ai_predict_dice(history)
                    msg=build_message(phien,kq,predict,conf,reason,dice_pred,dice_actual,tong,model)
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
                    log_event(msg.replace("\n"," "))

                    win_flag=update_model(model,predict,kq)
                    chat_msg=ai_chat_after_game(win_flag,model)
                    await bot.send_message(chat_id=CHAT_ID, text=chat_msg)
                    log_event(f"AI: {chat_msg}")
                    last_phien=phien
        except Exception as e:
            err=f"❌ Lỗi API: {e}"
            print(err); log_event(err)
            try: await bot.send_message(chat_id=CHAT_ID,text=err)
            except: pass
        await asyncio.sleep(POLL_INTERVAL)

# ======= MAIN =========
if __name__=="__main__":
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    bot = Bot(BOT_TOKEN)
    loop=asyncio.get_event_loop()
    loop.create_task(auto_predict(bot))
    app.run_polling()
        
