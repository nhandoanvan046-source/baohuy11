import os
import asyncio
import aiohttp
import json
import random
import nest_asyncio
from datetime import datetime
from collections import deque, Counter
from typing import List, Tuple, Dict, Any
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

# ------------- CONFIG -------------
BOT_TOKEN = os.getenv("SUNWIN_BOT_TOKEN", "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs")
GROUP_ID = int(os.getenv("SUNWIN_GROUP_ID", "-1002666964512"))
API_URL = os.getenv("SUNWIN_API_URL", "https://sunwinsaygex.onrender.com/api/taixiu/sunwin")
HISTORY_FILE = "history.json"
LEARN_N = 11                # học 11 ván
CHECK_INTERVAL = 6          # giây (tăng nếu API rate-limit)
RESET_INTERVAL = 12 * 3600  # tự reset lịch sử sau 12h (tuỳ chọn)
# -----------------------------------

# ------------- STATE -------------
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False)

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    try:
        history_all: List[Dict[str, Any]] = json.load(f)
        if not isinstance(history_all, list):
            history_all = []
    except Exception:
        history_all = []

history_trend = deque([r.get("ket_qua") for r in history_all[-LEARN_N:]], maxlen=LEARN_N)
last_phien = history_all[-1]["phien"] if history_all else None
last_reset = datetime.now().timestamp()
# -----------------------------------

# ------------- UTIL: fetch API -------------
async def fetch_latest(session: aiohttp.ClientSession) -> Tuple[Any, ...]:
    """
    Return tuple (phien, ket_qua, x1, x2, x3, tong) or (None,...)
    """
    try:
        async with session.get(API_URL, timeout=10) as resp:
            if resp.status != 200:
                return (None, None, None, None, None, None)
            d = await resp.json()
            # tolerant parsing
            phien = d.get("phien") or d.get("round") or d.get("id")
            ket_qua = d.get("ket_qua") or d.get("result") or d.get("ketqua")
            # faces
            try:
                x1 = int(d.get("xuc_xac_1", d.get("dice1", 0) or 0))
                x2 = int(d.get("xuc_xac_2", d.get("dice2", 0) or 0))
                x3 = int(d.get("xuc_xac_3", d.get("dice3", 0) or 0))
            except Exception:
                x1 = x2 = x3 = 0
            tong = int(d.get("tong", x1 + x2 + x3 if x1 and x2 and x3 else 0))
            return (phien, ket_qua, x1, x2, x3, tong)
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] fetch_latest error: {e}")
        return (None, None, None, None, None, None)

# ------------- STORAGE -------------
def save_record(phien, ket_qua, x1, x2, x3, tong):
    rec = {
        "phien": phien,
        "ket_qua": ket_qua,
        "xuc_xac_1": int(x1 or 0),
        "xuc_xac_2": int(x2 or 0),
        "xuc_xac_3": int(x3 or 0),
        "tong": int(tong or 0),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history_all.append(rec)
    history_trend.append(ket_qua)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_all, f, ensure_ascii=False, indent=2)

# ------------- ANALYSIS: xí ngầu -------------
def face_frequency(records: List[Dict[str, Any]]) -> Tuple[Counter, float]:
    """Return Counter of faces 1..6 and average total per game"""
    faces = []
    totals = []
    for r in records:
        for k in ("xuc_xac_1", "xuc_xac_2", "xuc_xac_3"):
            v = r.get(k)
            if isinstance(v, int) and 1 <= v <= 6:
                faces.append(v)
        t = r.get("tong") or ( (r.get("xuc_xac_1") or 0) + (r.get("xuc_xac_2") or 0) + (r.get("xuc_xac_3") or 0) )
        if t:
            totals.append(int(t))
    freq = Counter(faces)
    avg_total = sum(totals)/len(totals) if totals else 0.0
    return freq, avg_total

def detect_pairs_triples(records: List[Dict[str, Any]]) -> Tuple[int, int, List[Tuple[int,int]]]:
    """
    Return (num_pairs, num_triples, list_of_recent_pair_values)
    """
    num_pairs = 0
    num_triples = 0
    recent_pairs = []
    for r in records:
        faces = [r.get("xuc_xac_1") or 0, r.get("xuc_xac_2") or 0, r.get("xuc_xac_3") or 0]
        if faces.count(faces[0]) == 3 or (faces.count(faces[1]) == 3) or (faces.count(faces[2]) == 3):
            num_triples += 1
        elif (faces[0] == faces[1]) or (faces[0] == faces[2]) or (faces[1] == faces[2]):
            num_pairs += 1
            # record which face is paired
            for v in set(faces):
                if faces.count(v) == 2:
                    recent_pairs.append((v, sum(faces)))
    return num_pairs, num_triples, recent_pairs

# ------------- CẦU (trend) detection -------------
def is_alternate(seq: List[str], check_len=6) -> bool:
    if len(seq) < check_len:
        return False
    sub = seq[-check_len:]
    for i in range(1, len(sub)):
        if sub[i] == sub[i-1]:
            return False
    return True

def detect_cau(records: List[Dict[str, Any]]) -> Tuple[str, int, str]:
    """Return (pattern_text, streak_len, last_side)"""
    seq = [(r.get("ket_qua") or "").capitalize() for r in records[-LEARN_N:]]
    if not seq:
        return "Không đủ dữ liệu", 0, ""
    last = seq[-1]
    # streak
    streak = 1
    for i in range(len(seq)-2, -1, -1):
        if seq[i] == last:
            streak += 1
        else:
            break
    if streak >= 3:
        return f"Cầu bệt {last} ({streak})", streak, last
    if is_alternate(seq, check_len=6):
        return "Cầu đảo (xen kẽ)", streak, last
    return "Cầu hỗn hợp", streak, last

# ------------- AI DỰ ĐOÁN (1 kết quả duy nhất) -------------
def ai_predict(records: List[Dict[str, Any]]) -> Tuple[str, int, Dict[str, Any]]:
    """
    Return (predict_choice, confidence_pct, debug_info)
    debug_info includes avg_total, face_freq, pairs/triples counts, pattern
    """
    recs = records[-LEARN_N:]
    seq = [(r.get("ket_qua") or "").capitalize() for r in recs]
    pattern_text, streak, last = detect_cau(recs)

    # face stats
    face_freq, avg_total = face_frequency(recs)
    pairs, triples, recent_pairs = detect_pairs_triples(recs)

    # base prob for Tài (true if >10.5)
    # we compute score from several signals
    score = 0.0

    # avg total signal
    # if avg_total > 10.5 -> bias Tài, else bias Xỉu
    avg_signal = (avg_total - 10.5) / 4.5  # normalized roughly between -1..1
    score += avg_signal * 0.6  # weight

    # streak signal: if bệt, bias to last; if very long streak -> increase chance of gãy (invert part)
    if pattern_text.startswith("Cầu bệt"):
        score += (1 if last.lower().startswith("t") else -1) * 0.8
        if streak >= 5:
            # longer streak increases chance gãy -> reduce score magnitude
            score *= 0.6
    elif pattern_text.startswith("Cầu đảo"):
        # favor flip of last
        score += (-1 if last.lower().startswith("t") else 1) * 0.4

    # face freq: if many high faces (5 or 6) -> bias Tài
    high_faces = face_freq.get(5, 0) + face_freq.get(6, 0)
    low_faces = face_freq.get(1, 0) + face_freq.get(2, 0)
    if (high_faces + low_faces) > 0:
        face_signal = (high_faces - low_faces) / (high_faces + low_faces)
        score += face_signal * 0.2

    # pairs/triples: triples slightly favor that exact total patterns (we treat as weak signal)
    if triples > 0:
        # if triple occurred many times, don't overfit; small bias
        score += 0.1 * triples

    # normalize score to probability for Tài
    prob_tai = 50 + (score * 25)  # score -1..1 -> ~25% swing
    prob_tai = max(10, min(95, prob_tai + random.uniform(-3, 3)))  # jitter
    predict = "Tài" if prob_tai >= 50 else "Xỉu"
    confidence = int(prob_tai if predict == "Tài" else 100 - prob_tai)
    debug = {
        "avg_total": round(avg_total, 2),
        "face_freq": dict(face_freq.most_common()),
        "pairs": pairs,
        "triples": triples,
        "recent_pairs": recent_pairs,
        "pattern": pattern_text,
        "streak": streak,
        "score": round(score, 3),
        "prob_tai": round(prob_tai, 2)
    }
    return predict, confidence, debug

# ------------- GỢI Ý XÚC XẮC -------------
def generate_dice_for_side(side: str) -> Tuple[List[int], int]:
    """
    side "Tài" => total in 11..18
    side "Xỉu" => total in 3..10
    Return (dice_list, total)
    """
    if side == "Tài":
        valid_totals = list(range(11, 19))
    elif side == "Xỉu":
        valid_totals = list(range(3, 11))
    else:
        valid_totals = list(range(3, 19))
    total = random.choice(valid_totals)
    # random search to find combination
    for _ in range(2000):
        d = [random.randint(1,6) for _ in range(3)]
        if sum(d) == total:
            return d, total
    # deterministic fallback
    for d1 in range(1,7):
        for d2 in range(1,7):
            d3 = total - d1 - d2
            if 1 <= d3 <= 6:
                return [d1, d2, d3], total
    return [1,1,1], 3

# ------------- BUILD MESSAGE -------------
def build_analysis_message(records: List[Dict[str, Any]], predict_choice: str, confidence: int, debug: Dict[str, Any], suggested_dice: List[int], total: int) -> str:
    last_recs = records[-LEARN_N:]
    seq = " ".join([(r.get("ket_qua") or "NA") for r in last_recs])
    t = datetime.now().strftime("%H:%M:%S")
    most_common_faces = ", ".join(f"{k}({v})" for k,v in debug["face_freq"].items()) if debug["face_freq"] else "N/A"
    recent_pair_text = ", ".join(f"{v}:{s}" for v,s in debug["recent_pairs"]) if debug.get("recent_pairs") else "N/A"
    msg = (
        f"🎯 <b>AI DỰ ĐOÁN v4.4 — PHÂN TÍCH XÍ NGẦU</b>\n"
        f"🕒 <b>Giờ:</b> {t}\n\n"
        f"📋 <b>{LEARN_N} ván gần nhất:</b>\n{seq}\n\n"
        f"📊 <b>Trung bình tổng:</b> {debug['avg_total']}\n"
        f"🎲 <b>Mặt thường ra:</b> {most_common_faces}\n"
        f"💠 <b>Bộ đôi:</b> {debug['pairs']} | <b>Bộ ba:</b> {debug['triples']} | <b>Ví dụ đôi gần nhất:</b> {recent_pair_text}\n"
        f"🔎 <b>Cầu hiện tại:</b> {debug['pattern']} (streak {debug['streak']})\n\n"
        f"🤖 <b>AL dự đoán:</b> <u>{predict_choice}</u>  (<i>{confidence}%</i>)\n"
        f"🎲 <b>Xúc xắc gợi ý:</b> [{suggested_dice[0]}][{suggested_dice[1]}][{suggested_dice[2]}] → Tổng: {total}\n\n"
        f"<i>Ghi chú:</i> AL dùng heuristic kết hợp trung bình tổng, tần suất mặt, cặp/bộ ba & chuỗi. Không đảm bảo 100%.\n"
    )
    return msg

# ------------- COMMAND: /du_doan -------------
async def du_doan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history_all:
        await update.message.reply_text("Chưa có dữ liệu lịch sử để phân tích.")
        return
    predict_choice, confidence, debug = ai_predict(history_all)
    dice, total = generate_dice_for_side(predict_choice)
    msg = build_analysis_message(history_all, predict_choice, confidence, debug, dice, total)
    await update.message.reply_html(msg)

# ------------- AUTO-CHECK LOOP -------------
async def auto_check_and_send(app):
    global last_phien, last_reset, history_all, history_trend
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # auto reset
                if datetime.now().timestamp() - last_reset >= RESET_INTERVAL:
                    history_all.clear()
                    history_trend = deque(maxlen=LEARN_N)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)
                    last_reset = datetime.now().timestamp()
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto reset history")

                phien, ket_qua, x1, x2, x3, tong = await fetch_latest(session)
                if not phien:
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                if phien == last_phien:
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue

                # normalize ket_qua -> "Tài"/"Xỉu"
                kq = (ket_qua or "").strip()
                if kq:
                    if kq.lower().startswith("t") or "tài" in kq.lower():
                        kq = "Tài"
                    elif kq.lower().startswith("x") or "xỉu" in kq.lower():
                        kq = "Xỉu"
                else:
                    kq = "Unknown"

                # save
                save_record(phien, kq, x1 or 0, x2 or 0, x3 or 0, tong or 0)
                last_phien = phien

                # predict and send summary (single prediction)
                predict_choice, confidence, debug = ai_predict(history_all)
                dice, total = generate_dice_for_side(predict_choice)
                header = f"📣 <b>Phiên mới:</b> {phien}  —  Kết quả: {kq}\n"
                body = build_analysis_message(history_all, predict_choice, confidence, debug, dice, total)
                text = header + "\n" + body
                try:
                    await app.bot.send_message(GROUP_ID, text, parse_mode="HTML")
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent phien {phien} {kq}")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Send error: {e}")

                await asyncio.sleep(CHECK_INTERVAL)
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] auto loop error: {e}")
                await asyncio.sleep(max(1, CHECK_INTERVAL))

# ------------- START BOT -------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("du_doan", du_doan))
    task = asyncio.create_task(auto_check_and_send(app))
    try:
        await app.run_polling()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

if __name__ == "__main__":
    print("Start Sunwin AI v4.4 — Phân tích xí ngầu + Dự đoán (11 ván)")
    asyncio.run(main())
            
