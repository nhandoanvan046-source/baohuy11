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

# keep_alive (optional)
try:
    from keep_alive import keep_alive
except Exception:
    def keep_alive():
        pass

nest_asyncio.apply()

# ---------------- CONFIG ----------------
BOT_TOKEN = "6367532329:AAFUobZTDtBrWWfjXanXHny9mBRN0eHyAGs"  # <-- Đã gắn token bạn cung cấp
GROUP_ID = -1002666964512   # <-- THAY BẰNG ID NHÓM của bạn (ví dụ: -100xxxxxxxxxx)
API_URL = "https://sunwinsaygex.onrender.com/api/taixiu/sunwin"

HISTORY_FILE = "history.json"
LEARN_N = 11
CHECK_INTERVAL = 6.0
RESET_INTERVAL = 12 * 3600  # 12 giờ
MAX_HISTORY = 3000
# ----------------------------------------

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="sunwin.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sunwin_ai")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console)
# ----------------------------------------

# ---------------- STORAGE ----------------
try:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history_all: List[Dict[str, Any]] = json.load(f)
        if not isinstance(history_all, list):
            history_all = []
except FileNotFoundError:
    history_all = []
except Exception as e:
    logger.exception("Error loading history file, starting empty.")
    history_all = []

history_trend = deque([r.get("ket_qua") for r in history_all[-LEARN_N:]], maxlen=LEARN_N)
last_phien = history_all[-1]["phien"] if history_all else None
last_reset = datetime.now().timestamp()
file_lock = asyncio.Lock()
# ----------------------------------------

# ----------------- UTIL: API -----------------
async def fetch_latest(session: aiohttp.ClientSession, retries=3, timeout=10) -> Tuple[Any, ...]:
    """
    Fetch latest record from API.
    Returns (phien, ket_qua, x1, x2, x3, tong) or (None, None, None, None, None, None)
    """
    for attempt in range(retries):
        try:
            async with session.get(API_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"API returned status {resp.status}: {text[:200]}")
                    await asyncio.sleep(1 + attempt)
                    continue
                d = await resp.json()

                # flexible parsing for different API shapes
                phien = d.get("phien") or d.get("round") or d.get("id")
                ket_qua = d.get("ket_qua") or d.get("result") or d.get("ketqua") or d.get("kq")

                def safe_int(v):
                    try:
                        return int(v)
                    except Exception:
                        return 0

                x1 = x2 = x3 = 0
                # nested data array common shape
                if isinstance(d.get("data"), list) and d["data"]:
                    item = d["data"][0]
                    x1 = safe_int(item.get("xuc_xac_1") or item.get("dice1") or (item.get("xucxac") and item.get("xucxac")[0]))
                    x2 = safe_int(item.get("xuc_xac_2") or item.get("dice2") or (item.get("xucxac") and item.get("xucxac")[1]))
                    x3 = safe_int(item.get("xuc_xac_3") or item.get("dice3") or (item.get("xucxac") and item.get("xucxac")[2]))
                    if not phien:
                        phien = item.get("phien") or phien
                else:
                    x1 = safe_int(d.get("xuc_xac_1") or d.get("dice1"))
                    x2 = safe_int(d.get("xuc_xac_2") or d.get("dice2"))
                    x3 = safe_int(d.get("xuc_xac_3") or d.get("dice3"))

                tong = safe_int(d.get("tong") or (x1 + x2 + x3 if (x1 or x2 or x3) else 0))

                if not ket_qua and tong:
                    ket_qua = "Tài" if tong >= 11 else "Xỉu"

                return phien, ket_qua, x1, x2, x3, tong
        except asyncio.TimeoutError:
            logger.warning("fetch_latest timeout, retrying...")
            if attempt == retries - 1:
                return (None, None, None, None, None, None)
            await asyncio.sleep(1 + attempt)
        except Exception as e:
            logger.exception(f"fetch_latest error attempt {attempt}: {e}")
            if attempt == retries - 1:
                return (None, None, None, None, None, None)
            await asyncio.sleep(1 + attempt)
    return (None, None, None, None, None, None)
# --------------------------------------------

# ---------------- STORAGE UTIL ----------------
async def save_record_async(phien, ket_qua, x1, x2, x3, tong):
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
    if len(history_all) > MAX_HISTORY:
        del history_all[0: len(history_all) - MAX_HISTORY]
    history_trend.append(ket_qua)
    async with file_lock:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_all, f, ensure_ascii=False, indent=2)
# ----------------------------------------------

# ---------------- AI (cải tiến) ----------------
def ai_predict(records: List[Dict[str, Any]]) -> Tuple[str, int, Dict[str, Any]]:
    """
    Improved AI: combine 3 signals:
      - avg_total (40%)
      - freq last 10 (30%)
      - streak effect (30%)
    Returns (predict_side, confidence_percent, debug_info)
    """
    if not records:
        return "N/A", 0, {}

    # Use the last LEARN_N games for average
    recs = records[-LEARN_N:]
    totals = [r.get("tong") for r in recs if r.get("tong") is not None]
    avg_total = sum(totals) / len(totals) if totals else 10.5

    # 1) avg_total -> probability of Tài
    # normalize: avg_total 3..18, center 10.5 -> map roughly +/-25%
    score_total = (avg_total - 10.5) / 4.5  # approx in [-1..1]
    prob_total = 50 + score_total * 25
    prob_total = max(5, min(95, prob_total))

    # 2) freq last 10
    last10 = records[-10:] if len(records) >= 10 else records
    tai_count = sum(1 for r in last10 if (r.get("ket_qua") or "").lower().startswith("t"))
    len_last10 = len(last10) if last10 else 1
    tai_pct = (tai_count / len_last10) * 100
    # dampen extremes
    prob_freq = 50 + (tai_pct - 50) * 0.6
    prob_freq = max(5, min(95, prob_freq))

    # 3) streak effect (short-term reversal tendency)
    last_result = (records[-1].get("ket_qua") or "").capitalize() if records else ""
    streak = 1
    for r in reversed(records[:-1]):
        if (r.get("ket_qua") or "").capitalize() == last_result and last_result:
            streak += 1
        else:
            break
    if not last_result:
        prob_streak = 50.0
    else:
        # If long streak of Tài, slightly lower P(Tài) (reversion). If streak small, neutral.
        max_shift = 20  # max +/- shift from 50 due to streak
        shift = min(max_shift, max(0, (streak - 1) * 5))
        if last_result == "Tài":
            prob_streak = 50 - shift
        else:
            prob_streak = 50 + shift
    prob_streak = max(5, min(95, prob_streak))

    # Weighted ensemble
    prob_tai = 0.40 * prob_total + 0.30 * prob_freq + 0.30 * prob_streak
    prob_tai = max(5, min(95, prob_tai))

    predict = "Tài" if prob_tai >= 50 else "Xỉu"
    confidence = int(round(prob_tai if predict == "Tài" else 100 - prob_tai))

    debug = {
        "avg_total": round(avg_total, 2),
        "prob_total": round(prob_total, 2),
        "tai_last10": f"{tai_count}/{len_last10}",
        "prob_freq": round(prob_freq, 2),
        "last_streak": f"{streak}x{last_result}" if last_result else "N/A",
        "prob_streak": round(prob_streak, 2),
        "ensemble_prob_tai": round(prob_tai, 2)
    }
    return predict, confidence, debug
# ----------------------------------------------

# ----------------- Gợi ý xúc xắc -----------------
def generate_dice_for_side(side: str) -> Tuple[List[int], int]:
    valid_totals = list(range(11, 19)) if side.lower().startswith("t") else list(range(3, 11))
    total = random.choice(valid_totals)
    # attempt random search
    for _ in range(3000):
        d = [random.randint(1, 6) for _ in range(3)]
        if sum(d) == total:
            return d, total
    # deterministic fallback
    for a in range(1, 7):
        for b in range(1, 7):
            c = total - a - b
            if 1 <= c <= 6:
                return [a, b, c], total
    return [1, 1, 1], 3
# -------------------------------------------------

# ---------------- Message builder ----------------
def build_message(phien, kq, x1, x2, x3, predict, conf, debug, suggested_dice, suggested_total):
    t = datetime.now().strftime("%H:%M:%S")
    return (
        f"📣 Phiên: <b>{phien}</b>  —  Kết quả: <b>{kq}</b>\n"
        f"🎲 Kết quả xúc xắc: {x1}+{x2}+{x3} = {x1 + x2 + x3}\n\n"
        f"🎯 <b>AI DỰ ĐOÁN</b>\n"
        f"🕒 {t}\n\n"
        f"🤖 Dự đoán tiếp: <u>{predict}</u>  (<i>{conf}%</i>)\n"
        f"🎲 Gợi ý xúc xắc: [{suggested_dice[0]}][{suggested_dice[1]}][{suggested_dice[2]}] → Tổng {suggested_total}\n\n"
        f"📊 Phân tích:\n"
        f"- Trung bình tổng (last {LEARN_N}): {debug.get('avg_total')}\n"
        f"- Tài trong 10 gần nhất: {debug.get('tai_last10')}\n"
        f"- Chuỗi hiện tại: {debug.get('last_streak')}\n\n"
        f"<i>Lưu ý:</i> AI dùng heuristic (không bảo đảm kết quả).\n"
    )

# ---------------- COMMANDS ----------------
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "📌 Lệnh hỗ trợ:\n"
        "/du_doan - Dự đoán (dựa trên lịch sử)\n"
        "/stats - Thống kê tổng\n"
        "/history - 10 ván gần nhất\n"
        "/help - Xem hướng dẫn\n"
    )
    await update.message.reply_text(txt)

async def cmd_du_doan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history_all:
        await update.message.reply_text("❌ Chưa có dữ liệu lịch sử.")
        return
    predict, conf, debug = ai_predict(history_all)
    dice, total = generate_dice_for_side(predict)
    # show a concise explanation
    msg = (
        f"🤖 AI dự đoán: <b>{predict}</b> ({conf}%)\n\n"
        f"📊 Chi tiết: AvgTotal={debug.get('avg_total')}, last10={debug.get('tai_last10')}, streak={debug.get('last_streak')}"
    )
    await update.message.reply_html(msg)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(history_all)
    if total == 0:
        await update.message.reply_text("Chưa có dữ liệu.")
        return
    freq = Counter((r.get("ket_qua") or "").capitalize() for r in history_all)
    tai = freq.get("Tài", 0)
    xiu = freq.get("Xỉu", 0)
    await update.message.reply_text(f"📊 Tổng bản ghi: {total}\nTài: {tai}\nXỉu: {xiu}")

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last = history_all[-10:]
    if not last:
        await update.message.reply_text("Chưa có dữ liệu.")
        return
    lines = []
    for r in last:
        lines.append(f"{r.get('phien')} — {r.get('ket_qua')} ({r.get('xuc_xac_1')}+{r.get('xuc_xac_2')}+{r.get('xuc_xac_3')}={r.get('tong')})")
    await update.message.reply_text("🕑 10 ván gần nhất:\n" + "\n".join(lines))

# -----------------------------------------

# ---------------- AUTO LOOP ----------------
async def auto_check_and_send(app, session: aiohttp.ClientSession):
    global last_phien, last_reset, history_all, history_trend
    winrate_history = deque(maxlen=50)
    while True:
        try:
            # auto reset
            if datetime.now().timestamp() - last_reset >= RESET_INTERVAL:
                history_all.clear()
                history_trend = deque(maxlen=LEARN_N)
                async with file_lock:
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)
                last_reset = datetime.now().timestamp()
                logger.info("Auto reset history")

            phien, ket_qua_raw, x1, x2, x3, tong = await fetch_latest(session)
            if not phien:
                await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1, 2))
                continue
            if phien == last_phien:
                await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1, 2))
                continue

            # normalize ket_qua
            kq = "Tài" if (ket_qua_raw and (str(ket_qua_raw).lower().startswith("t") or "tài" in str(ket_qua_raw).lower())) else "Xỉu"
            # save
            await save_record_async(phien, kq, x1 or 0, x2 or 0, x3 or 0, tong or (x1 + x2 + x3))
            last_phien = phien

            # predict & send
            predict, conf, debug = ai_predict(history_all)
            suggested_dice, suggested_total = generate_dice_for_side(predict)
            msg = build_message(phien, kq, x1 or 0, x2 or 0, x3 or 0, predict, conf, debug, suggested_dice, suggested_total)
            try:
                await app.bot.send_message(GROUP_ID, msg, parse_mode="HTML")
                logger.info(f"Sent phien {phien} kq {kq} -> predict {predict} ({conf}%)")
            except Exception as e:
                logger.exception(f"Send message error: {e}")

            # update internal winrate history (for sparkline later if needed)
            recent_winrate = None
            try:
                last_n = history_all[-20:]
                if last_n:
                    tai_count = sum(1 for r in last_n if (r.get("ket_qua") or "").lower().startswith("t"))
                    recent_winrate = round((tai_count / len(last_n)) * 100, 1)
                    winrate_history.append(recent_winrate)
            except Exception:
                pass

            await asyncio.sleep(CHECK_INTERVAL + random.uniform(-1.5, 2.5))
        except asyncio.CancelledError:
            logger.info("Auto loop canceled")
            break
        except Exception as e:
            logger.exception(f"Auto loop exception: {e}")
            await asyncio.sleep(max(1, CHECK_INTERVAL))
# -----------------------------------------

# ---------------- RUN ----------------
async def main():
    if not BOT_TOKEN or BOT_TOKEN.strip() == "":
        raise RuntimeError("BOT_TOKEN not configured in code.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("du_doan", cmd_du_doan))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("history", cmd_history))

    session = aiohttp.ClientSession()
    task = asyncio.create_task(auto_check_and_send(app, session))
    try:
        await app.run_polling()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await session.close()

if __name__ == "__main__":
    keep_alive()
    print("🚀 Sunwin AI (improved) starting...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        raise
        
