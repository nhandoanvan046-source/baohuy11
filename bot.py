import os
import asyncio
import aiohttp
import json
import random
import logging
import nest_asyncio
from datetime import datetime
from collections import deque, Counter
from typing import List, Dict, Tuple, Any
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# keep_alive.py must be in same folder (provided previously)
from keep_alive import keep_alive

nest_asyncio.apply()

# --------------- CONFIG ----------------
BOT_TOKEN = os.getenv("SUNWIN_BOT_TOKEN", "")  # set in environment
GROUP_ID = int(os.getenv("SUNWIN_GROUP_ID", "-1002666964512"))
API_URL = os.getenv("SUNWIN_API_URL", "https://sunwinsaygex.onrender.com/api/taixiu/sunwin")
HISTORY_FILE = os.getenv("HISTORY_FILE", "history.json")
LEARN_N = int(os.getenv("LEARN_N", "11"))
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "6"))  # base interval (seconds)
RESET_INTERVAL = int(os.getenv("RESET_INTERVAL", str(12 * 3600)))  # seconds
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "1000"))
# ---------------------------------------

# --------------- LOGGING ----------------
logging.basicConfig(
    filename="sunwin.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sunwin_ai")
# ---------------------------------------

# --------------- STORAGE ----------------
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
# ---------------------------------------

# --------------- UTIL: API ----------------
async def fetch_latest(session: aiohttp.ClientSession, retries=3, timeout=10) -> Tuple[Any, ...]:
    """
    Return (phien, ket_qua, x1, x2, x3, tong) or (None, None, None, None, None, None)
    Tolerant parsing for different API shapes.
    """
    for attempt in range(retries):
        try:
            async with session.get(API_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    # transient
                    await asyncio.sleep(1 + attempt)
                    continue
                d = await resp.json()

                # Try common keys
                phien = d.get("phien") or d.get("round") or d.get("id") or (d.get("data", [{}])[0].get("phien") if isinstance(d.get("data"), list) and d.get("data") else None)
                # result key variations
                ket_qua = d.get("ket_qua") or d.get("result") or d.get("ketqua") or d.get("kq")
                # faces handling
                def safe_int(v):
                    try:
                        return int(v)
                    except Exception:
                        return 0
                # Check nested data field if present
                if not (d.get("xuc_xac_1") or d.get("dice1")) and isinstance(d.get("data"), list) and d["data"]:
                    item = d["data"][0]
                    x1 = safe_int(item.get("xuc_xac_1") or item.get("dice1") or (item.get("xucxac", [0,0,0])[0] if item.get("xucxac") else 0))
                    x2 = safe_int(item.get("xuc_xac_2") or item.get("dice2") or (item.get("xucxac", [0,0,0])[1] if item.get("xucxac") else 0))
                    x3 = safe_int(item.get("xuc_xac_3") or item.get("dice3") or (item.get("xucxac", [0,0,0])[2] if item.get("xucxac") else 0))
                else:
                    x1 = safe_int(d.get("xuc_xac_1") or d.get("dice1") or 0)
                    x2 = safe_int(d.get("xuc_xac_2") or d.get("dice2") or 0)
                    x3 = safe_int(d.get("xuc_xac_3") or d.get("dice3") or 0)

                tong = safe_int(d.get("tong") or (x1 + x2 + x3 if x1 or x2 or x3 else 0))
                # Normalize ket_qua from total if missing
                if not ket_qua and tong:
                    ket_qua = "Tài" if tong >= 11 else "Xỉu"

                return phien, ket_qua, x1, x2, x3, tong
        except asyncio.TimeoutError:
            # try again
            if attempt == retries - 1:
                logger.warning("fetch_latest timeout (final).")
                return (None, None, None, None, None, None)
            await asyncio.sleep(1 + attempt)
        except Exception as e:
            logger.exception(f"fetch_latest error attempt {attempt}: {e}")
            if attempt == retries - 1:
                return (None, None, None, None, None, None)
            await asyncio.sleep(1 + attempt)
    return (None, None, None, None, None, None)
# -----------------------------------------

# --------------- STORAGE UTIL -------------
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
    # cap history
    if len(history_all) > MAX_HISTORY:
        del history_all[0: len(history_all) - MAX_HISTORY]
    # update deque
    history_trend.append(ket_qua)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_all, f, ensure_ascii=False, indent=2)
# -----------------------------------------

# --------------- ANALYSIS -----------------
def face_frequency(records: List[Dict[str, Any]]) -> Tuple[Counter, float]:
    faces = []
    totals = []
    for r in records:
        for k in ("xuc_xac_1", "xuc_xac_2", "xuc_xac_3"):
            v = r.get(k)
            if isinstance(v, int) and 1 <= v <= 6:
                faces.append(v)
        t = r.get("tong") or ((r.get("xuc_xac_1") or 0) + (r.get("xuc_xac_2") or 0) + (r.get("xuc_xac_3") or 0))
        if t:
            totals.append(int(t))
    freq = Counter(faces)
    avg_total = sum(totals)/len(totals) if totals else 0.0
    return freq, avg_total

def detect_pairs_triples(records: List[Dict[str, Any]]) -> Tuple[int, int, List[Tuple[int,int]]]:
    num_pairs = 0
    num_triples = 0
    recent_pairs = []
    for r in records:
        faces = [r.get("xuc_xac_1") or 0, r.get("xuc_xac_2") or 0, r.get("xuc_xac_3") or 0]
        if len(set(faces)) == 1:
            num_triples += 1
        elif len(set(faces)) == 2:
            num_pairs += 1
            for v in set(faces):
                if faces.count(v) == 2:
                    recent_pairs.append((v, sum(faces)))
    return num_pairs, num_triples, recent_pairs

def is_alternate(seq: List[str], check_len=6) -> bool:
    if len(seq) < check_len:
        return False
    sub = seq[-check_len:]
    return all(sub[i] != sub[i-1] for i in range(1, len(sub)))

def detect_cau(records: List[Dict[str, Any]]) -> Tuple[str, int, str]:
    seq = [(r.get("ket_qua") or "").capitalize() for r in records[-LEARN_N:]]
    if not seq:
        return "Không đủ dữ liệu", 0, ""
    last = seq[-1]
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
# -----------------------------------------

# --------------- AI PREDICT ----------------
def ai_predict(records: List[Dict[str, Any]]) -> Tuple[str, int, Dict[str, Any]]:
    recs = records[-LEARN_N:]
    pattern_text, streak, last = detect_cau(recs)
    face_freq, avg_total = face_frequency(recs)
    pairs, triples, recent_pairs = detect_pairs_triples(recs)

    score = 0.0
    # avg total signal
    avg_signal = (avg_total - 10.5) / 4.5
    score += avg_signal * 0.6

    # streak signal
    if pattern_text.startswith("Cầu bệt"):
        score += (1 if last.lower().startswith("t") else -1) * 0.8
        if streak >= 5:
            score *= 0.6
    elif pattern_text.startswith("Cầu đảo"):
        score += (-1 if last.lower().startswith("t") else 1) * 0.4

    high_faces = face_freq.get(5, 0) + face_freq.get(6, 0)
    low_faces = face_freq.get(1, 0) + face_freq.get(2, 0)
    if (high_faces + low_faces) > 0:
        face_signal = (high_faces - low_faces) / (high_faces + low_faces)
        score += face_signal * 0.2

    if triples > 0:
        score += 0.1 * triples

    # normalize to prob_tai
    prob_tai = 50 + (score * 25)
    prob_tai = max(10, min(95, prob_tai + random.uniform(-3, 3)))
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
# -----------------------------------------

# --------------- SUGGEST DICE ----------------
def generate_dice_for_side(side: str) -> Tuple[List[int], int]:
    valid_totals = list(range(11, 19)) if side.lower().startswith("t") else list(range(3, 11))
    # choose total weighted towards high/low
    total = random.choice(valid_totals)
    # try random search
    for _ in range(2000):
        d = [random.randint(1,6) for _ in range(3)]
        if sum(d) == total:
            return d, total
    # fallback deterministic
    for d1 in range(1,7):
        for d2 in range(1,7):
            d3 = total - d1 - d2
            if 1 <= d3 <= 6:
                return [d1, d2, d3], total
    return [1,1,1], 3
# -----------------------------------------

# --------------- MINI CHARTS ----------------
def confidence_bar(conf: int) -> str:
    # 10 blocks bar
    blocks = max(0, min(10, int(round(conf/10))))
    return "▰" * blocks + "▱" * (10 - blocks) + f" {conf}%"

def sparkline_from_values(values: List[float], width=10) -> str:
    # map values (0..100) to blocks ▁▂▃▄▅▆▇█
    blocks = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    mn = min(values)
    mx = max(values)
    if mx == mn:
        return blocks[len(blocks)//2] * min(width, len(values))
    res = []
    # take last width values (pad if needed)
    seq = values[-width:]
    for v in seq:
        norm = (v - mn) / (mx - mn)  # 0..1
        idx = int(norm * (len(blocks) - 1))
        res.append(blocks[idx])
    return "".join(res)

def winrate(records: List[Dict[str, Any]], n=20) -> float:
    recent = [r.get("ket_qua") for r in records[-n:] if r.get("ket_qua")]
    if not recent:
        return 0.0
    tai = sum(1 for r in recent if (str(r).lower().startswith("t") or "tài" in str(r).lower()))
    return round((tai / len(recent)) * 100, 1)
# -----------------------------------------

# --------------- MESSAGE BUILDER ------------
def mini_board(records: List[Dict[str, Any]], n=11) -> str:
    last = records[-n:] if len(records) >= n else records
    seq = []
    for r in last:
        k = (r.get("ket_qua") or "?")
        if isinstance(k, str) and k.lower().startswith("t"):
            seq.append("Tài")
        elif isinstance(k, str) and k.lower().startswith("x"):
            seq.append("Xỉu")
        else:
            seq.append("N/A")
    return " ".join(seq)

def most_common_faces_text(face_freq: Dict[int,int]) -> str:
    if not face_freq:
        return "N/A"
    return ", ".join(f"{k}({v})" for k,v in face_freq.items())

def build_analysis_message(records: List[Dict[str, Any]], predict_choice: str, confidence: int, debug: Dict[str, Any], suggested_dice: List[int], total: int, phien=None, kq=None, winrate_history_vals: List[float]=None) -> str:
    t = datetime.now().strftime("%H:%M:%S")
    last_recs = records[-LEARN_N:]
    seq = " ".join([(r.get("ket_qua") or "NA") for r in last_recs])
    face_text = most_common_faces_text(debug["face_freq"])
    recent_pair_text = ", ".join(f"{v}:{s}" for v,s in (debug.get("recent_pairs") or [])) or "N/A"
    wr = winrate(records, n=20)
    spark = sparkline_from_values(winrate_history_vals or [wr], width=10)
    conf_bar = confidence_bar(confidence)
    msg = (
        f"📣 Phiên mới: {phien or '?'}  —  Kết quả: {kq or '?'}\n\n"
        f"🎯 <b>AI DỰ ĐOÁN v4.5 — PHÂN TÍCH XÍ NGẦU</b>\n"
        f"🕒 <b>Giờ:</b> {t}\n\n"
        f"📋 <b>{LEARN_N} ván gần nhất:</b>\n{seq}\n\n"
        f"📈 <b>Winrate (20v):</b> {wr}%  {spark}\n\n"
        f"📊 <b>Trung bình tổng:</b> {debug['avg_total']}\n"
        f"🎲 <b>Mặt thường ra:</b> {face_text}\n"
        f"💠 <b>Bộ đôi:</b> {debug['pairs']} | <b>Bộ ba:</b> {debug['triples']} | <b>Ví dụ đôi gần nhất:</b> {recent_pair_text}\n"
        f"🔎 <b>Cầu hiện tại:</b> {debug['pattern']} (streak {debug['streak']})\n\n"
        f"🤖 <b>AI dự đoán:</b> <u>{predict_choice}</u>  (<i>{confidence}%</i>)\n"
        f"📊 <b>Độ tin cậy:</b> {conf_bar}\n"
        f"🎲 <b>Xúc xắc gợi ý:</b> [{suggested_dice[0]}][{suggested_dice[1]}][{suggested_dice[2]}] → Tổng: {total}\n\n"
        f"<i>Ghi chú:</i> AI dùng heuristic kết hợp trung bình tổng, tần suất mặt, cặp/bộ ba & chuỗi. Không đảm bảo 100%.\n"
    )
    return msg
# -----------------------------------------

# --------------- COMMANDS -------------------
async def du_doan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history_all:
        await update.message.reply_text("❌ Chưa có dữ liệu lịch sử để phân tích.")
        return
    predict_choice, confidence, debug = ai_predict(history_all)
    dice, total = generate_dice_for_side(predict_choice)
    # build a small history of winrates for sparkline
    winrate_vals = []
    # compute rolling winrate for last windows
    for i in range(max(0, len(history_all) - 100), len(history_all), 5):
        winrate_vals.append(winrate(history_all[:i+1], n=20))
    msg = build_analysis_message(history_all, predict_choice, confidence, debug, dice, total, phien="N/A", kq="N/A", winrate_history_vals=winrate_vals)
    await update.message.reply_html(msg)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # simple stats command
    total = len(history_all)
    if total == 0:
        await update.message.reply_text("Chưa có dữ liệu.")
        return
    freq = Counter(r.get("ket_qua") for r in history_all)
    tai = freq.get("Tài", 0) + freq.get("tài", 0)
    xiu = freq.get("Xỉu", 0) + freq.get("xỉu", 0)
    await update.message.reply_text(f"📊 Tổng bản ghi: {total}\nTài: {tai}\nXỉu: {xiu}")

# -----------------------------------------

# --------------- AUTO LOOP ------------------
async def auto_check_and_send(app):
    global last_phien, last_reset, history_all, history_trend
    async with aiohttp.ClientSession() as session:
        # keep small rolling history of winrates for sparkline
        winrate_history = []
        while True:
            try:
                # auto reset history optionally
                if datetime.now().timestamp() - last_reset >= RESET_INTERVAL:
                    history_all.clear()
                    history_trend = deque(maxlen=LEARN_N)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)
                    last_reset = datetime.now().timestamp()
                    logger.info("Auto reset history")

                phien, ket_qua, x1, x2, x3, tong = await fetch_latest(session)
                if not phien:
                    await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1, 2))
                    continue
                if phien == last_phien:
                    await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1, 2))
                    continue

                # normalize ket_qua -> "Tài"/"Xỉu"
                kq = (ket_qua or "").strip()
                if kq:
                    if kq.lower().startswith("t") or "tài" in kq.lower():
                        kq = "Tài"
                    elif kq.lower().startswith("x") or "xỉu" in kq.lower():
                        kq = "Xỉu"
                else:
                    # fallback from tong
                    kq = "Tài" if tong and tong >= 11 else "Xỉu"

                save_record(phien, kq, x1 or 0, x2 or 0, x3 or 0, tong or 0)
                last_phien = phien

                # update winrate history
                wr = winrate(history_all, n=20)
                winrate_history.append(wr)
                if len(winrate_history) > 50:
                    winrate_history.pop(0)

                # predict and send message
                predict_choice, confidence, debug = ai_predict(history_all)
                suggested_dice, suggested_total = generate_dice_for_side(predict_choice)
                msg = build_analysis_message(history_all, predict_choice, confidence, debug, suggested_dice, suggested_total, phien=phien, kq=kq, winrate_history_vals=winrate_history)
                try:
                    await app.bot.send_message(GROUP_ID, msg, parse_mode="HTML")
                    logger.info(f"Sent phien {phien} kq {kq} - predict {predict_choice} ({confidence}%)")
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent phien {phien} {kq}")
                except Exception as e:
                    logger.exception(f"Send message error: {e}")
                    print(f"Send error: {e}")

                # sleep with jitter to reduce rate-limit risk
                await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1.5, 2.5))
            except Exception as e:
                logger.exception(f"Auto loop exception: {e}")
                await asyncio.sleep(max(1, CHECK_INTERVAL))
# -----------------------------------------

# --------------- RUN BOT --------------------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("SUNWIN_BOT_TOKEN (BOT_TOKEN) is not set in environment.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("du_doan", du_doan))
    app.add_handler(CommandHandler("stats", stats))

    # create background task for auto loop
    task = asyncio.create_task(auto_check_and_send(app))
    try:
        await app.run_polling()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

if __name__ == "__main__":
    # start keep-alive for Render/VPS
    keep_alive()
    print("🚀 Start Sunwin AI v4.5 — Phân tích nâng cao + Winrate + Mini charts")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        raise
                    
