# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "codewords-client==0.4.6",
#   "fastapi==0.116.1",
#   "httpx==0.28.1",
# ]
# [tool.env-checker]
# env_vars = [
#   "PORT=8000",
#   "LOGLEVEL=INFO",
#   "CODEWORDS_API_KEY",
#   "CODEWORDS_RUNTIME_URI",
#   "TELEGRAM_BOT_TOKEN",
# ]
# ///
"""
BESHOY BOOST BOT — Telegram Bot (Partner Ship Gate)
Webhook mode on CodeWords · Redis state · Facebook Graph API v18.0
"""
import os, re, json, secrets, string, random
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

import httpx
from codewords_client import logger, run_service, redis_client
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

app = FastAPI(title="Beshoy Boost Bot", version="1.0.0")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG = f"https://api.telegram.org/bot{TOKEN}"
BOT_NAME = "BESHOY BOOST BOT"
ADMIN_PASS = "Nemo@1986"
ADMIN_CMD = "beshoy"
SUPPORT_URL = "https://t.me/your_support_username"
OBJ_NAMES = {
    "CONVERSATIONS": "\U0001f4ac محادثات", "MESSAGES_MESSENGER": "\U0001f4e8 رسائل ماسنجر",
    "MESSAGES_WHATSAPP": "\U0001f4f1 رسائل واتساب", "LINK_CLICKS": "\U0001f517 نقرات رابط",
    "POST_ENGAGEMENT": "\U0001f4c8 تفاعل بوست", "VIDEO_VIEWS": "\U0001f3ac مشاهدات فيديو",
}

# ── Helpers ─────────────────────────────────────────
def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def gen_code(prefix="BM", length=12):
    a = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(secrets.choice(a) for _ in range(length))}"

# ── Telegram API ────────────────────────────────────
async def tg(method: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{TG}/{method}", json=data)
        return r.json()

async def send_msg(cid, text, kb=None):
    d: dict[str, Any] = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    return await tg("sendMessage", d)

async def edit_msg(cid, mid, text, kb=None):
    d: dict[str, Any] = {"chat_id": cid, "message_id": mid, "text": text, "parse_mode": "HTML"}
    if kb: d["reply_markup"] = kb
    return await tg("editMessageText", d)

async def answer_cb(cid, text="", alert=False):
    return await tg("answerCallbackQuery", {"callback_query_id": cid, "text": text, "show_alert": alert})

# ── Keyboards ───────────────────────────────────────
def ikb(rows): return {"inline_keyboard": rows}
def btn(t, d="", url=""):
    b = {"text": t}
    if url: b["url"] = url
    else: b["callback_data"] = d
    return b

def kb_main(sub):
    r = []
    if sub: r.append([btn("\U0001f91d إعلان بارتنر شيب", "gate:partner_ship")])
    r.append([btn("\U0001f39f تفعيل كود Redeem", "redeem"), btn("\U0001f6df الدعم", url=SUPPORT_URL)])
    return ikb(r)
def kb_proxy(): return ikb([[btn("\U0001f916 اختيار تلقائي","proxy:auto")],[btn("\u270f\ufe0f إدخال يدوي","proxy:custom")],[btn("\u23ed تخطي","proxy:skip")],[btn("\U0001f3e0 الرئيسية","home")]])
def kb_objectives():
    r = [[btn(n, f"obj:{k}")] for k, n in OBJ_NAMES.items()]
    r.append([btn("\U0001f3e0 الرئيسية","home")])
    return ikb(r)
def kb_confirm(): return ikb([[btn("\u2705 تأكيد","confirm:yes")],[btn("\u274c إلغاء","confirm:no")],[btn("\U0001f3e0 الرئيسية","home")]])
def kb_activate(): return ikb([[btn("\U0001f680 تفعيل الاعلان","activate:run")],[btn("\U0001f3e0 الرئيسية","home")]])
def kb_home(): return ikb([[btn("\U0001f3e0 الرئيسية","home")]])
def kb_back_proxy(): return ikb([[btn("\U0001f519 رجوع","proxy:back")]])
def kb_admin(): return ikb([[btn("\U0001f39f توليد كود","admin:gen_code")],[btn("\U0001f464 تمديد مشترك","admin:set_user")],[btn("\U0001f5d1 حذف مشترك","admin:remove_user")],[btn("\U0001f4e2 رسالة جماعية","admin:broadcast")],[btn("\U0001f310 إضافة بروكسيات","admin:add_proxies")],[btn("\U0001f4ca الإحصائيات","admin:stats")],[btn("\U0001f3e0 خروج","home")]])
def kb_back_admin(): return ikb([[btn("\U0001f519 لوحة التحكم","admin:stats")]])

# ── Facebook API ────────────────────────────────────
FB_API = "https://graph.facebook.com/v18.0"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def parse_cookies(raw: str) -> dict:
    cookies = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    return cookies

def fb_headers(cookies_str: str, proxy: str = None) -> tuple[dict, dict]:
    hdrs = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.facebook.com/",
        "Cookie": cookies_str,
    }
    proxies = None
    if proxy:
        proxies = {"http://": f"http://{proxy}", "https://": f"http://{proxy}"}
    return hdrs, proxies

async def fb_create_campaign(account_id: str, cookies_str: str, objective: str,
                              daily_budget: float, days: int, ad_code: str,
                              proxy: str = None) -> dict:
    """Create a Facebook ad campaign via Graph API using cookies auth."""
    hdrs, proxies = fb_headers(cookies_str, proxy)
    budget_cents = str(int(daily_budget * 100))
    obj_map = {
        "CONVERSATIONS": "OUTCOME_ENGAGEMENT",
        "MESSAGES_MESSENGER": "OUTCOME_ENGAGEMENT",
        "MESSAGES_WHATSAPP": "OUTCOME_ENGAGEMENT",
        "LINK_CLICKS": "OUTCOME_TRAFFIC",
        "POST_ENGAGEMENT": "OUTCOME_ENGAGEMENT",
        "VIDEO_VIEWS": "OUTCOME_AWARENESS",
    }
    fb_objective = obj_map.get(objective, "OUTCOME_ENGAGEMENT")
    try:
        async with httpx.AsyncClient(timeout=60, proxies=proxies, follow_redirects=True) as c:
            resp = await c.post(
                f"{FB_API}/act_{account_id}/campaigns",
                headers=hdrs,
                json={
                    "name": f"Partner Ship - {ad_code[:20]}",
                    "objective": fb_objective,
                    "status": "ACTIVE",
                    "special_ad_categories": [],
                    "daily_budget": budget_cents,
                }
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("id"):
                return {"ok": True, "campaign_id": data["id"], "msg": "Campaign created"}
            return {"ok": False, "error": data.get("error", {}).get("message", resp.text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Validation ──────────────────────────────────────
def v_proxy(p): return bool(re.match(r'^[\w.:@/-]+$', p.strip()) and ":" in p)
def v_cookies(c): return len(c) >= 50 and all(k in c for k in ["c_user", "xs", "datr"])
def v_id(v, mn=10, mx=20): return bool(re.match(rf'^\d{{{mn},{mx}}}$', v.strip()))
def v_budget(v):
    try:
        a = float(v); return (True, round(a,2)) if 1 <= a <= 10000 else (False, None)
    except: return (False, None)
def v_days(v):
    try:
        a = int(v); return (True, a) if 1 <= a <= 365 else (False, None)
    except: return (False, None)

# ── Redis DB ────────────────────────────────────────
async def db_user(r, ns, uid):
    raw = await r.get(f"{ns}:u:{uid}"); return json.loads(raw) if raw else None
async def db_save_user(r, ns, uid, d):
    await r.set(f"{ns}:u:{uid}", json.dumps(d, ensure_ascii=False))
async def db_ensure(r, ns, uid, un="", fn=""):
    u = await db_user(r, ns, uid)
    if not u:
        u = {"uid": uid, "un": un, "fn": fn, "cn": "", "joined": now_iso(), "removed": False, "sub": ""}
    else:
        u["un"], u["fn"] = un, fn
    await db_save_user(r, ns, uid, u); return u
def is_sub(u):
    if not u or u.get("removed"): return False
    s = u.get("sub", "")
    if not s: return False
    try: return datetime.fromisoformat(s) > datetime.now(timezone.utc)
    except: return False
async def db_state(r, ns, uid):
    raw = await r.get(f"{ns}:s:{uid}"); return json.loads(raw) if raw else {"st": ""}
async def db_set_st(r, ns, uid, d):
    await r.set(f"{ns}:s:{uid}", json.dumps(d, ensure_ascii=False))
async def db_clr(r, ns, uid): await r.delete(f"{ns}:s:{uid}")
async def db_use_code(r, ns, code, uid):
    raw = await r.get(f"{ns}:c:{code}")
    if not raw: return None
    c = json.loads(raw)
    if c.get("ub"): return None
    c["ub"], c["ua"] = uid, now_iso()
    await r.set(f"{ns}:c:{code}", json.dumps(c)); return int(c["h"])
async def db_mk_code(r, ns, code, h):
    await r.set(f"{ns}:c:{code}", json.dumps({"h": h, "ca": now_iso(), "ub": None, "ua": None}))
async def db_set_sub(r, ns, uid, h):
    u = await db_user(r, ns, uid)
    if not u: u = {"uid": uid, "un":"","fn":"","cn":"","joined":now_iso(),"removed":False,"sub":""}
    until = (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat(timespec="seconds")
    u["sub"], u["removed"] = until, False
    await db_save_user(r, ns, uid, u); return until
async def db_inc(r, ns, k, a=1): await r.incrby(f"{ns}:st:{k}", a)
async def db_stat(r, ns, k):
    v = await r.get(f"{ns}:st:{k}"); return int(v) if v else 0
async def db_proxy(r, ns):
    c = await r.llen(f"{ns}:px")
    if c == 0: return None
    return await r.lindex(f"{ns}:px", random.randint(0, c-1))
async def db_add_px(r, ns, text):
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
    for l in lines: await r.rpush(f"{ns}:px", l)
    return len(lines)

# ── Home Screen ─────────────────────────────────────
async def send_home(r, ns, cid, uid, mid=0):
    u = await db_user(r, ns, uid)
    sub = is_sub(u)
    name = (u.get("cn") or u.get("fn") or "مستخدم") if u else "مستخدم"
    status = "✅ مشترك" if sub else "❌ غير مشترك"
    txt = f"⚡ <b>{BOT_NAME}</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."
    if mid: await edit_msg(cid, mid, txt, kb_main(sub))
    else: await send_msg(cid, txt, kb_main(sub))

# ── Update Router ───────────────────────────────────
async def handle_update(upd: dict):
    try:
        async with redis_client() as (r, ns):
            if "callback_query" in upd: await on_cb(r, ns, upd["callback_query"])
            elif "message" in upd: await on_msg(r, ns, upd["message"])
    except Exception as e:
        logger.error("Update handling error", error=str(e))

async def on_cb(r, ns, cb):
    uid, cid, mid = cb["from"]["id"], cb["message"]["chat"]["id"], cb["message"]["message_id"]
    data, cbid = cb.get("data", ""), cb["id"]
    st = await db_state(r, ns, uid); state = st.get("st", "")

    if data == "home":
        await db_clr(r, ns, uid); await send_home(r, ns, cid, uid, mid); await answer_cb(cbid); return
    if data == "redeem":
        await db_set_st(r, ns, uid, {"st": "redeem"}); await edit_msg(cid, mid, "\U0001f39f ارسل كود التفعيل الآن:", kb_home()); await answer_cb(cbid); return
    if data == "gate:partner_ship":
        u = await db_user(r, ns, uid)
        if not is_sub(u): await answer_cb(cbid, "اشترك أولًا بكود Redeem.", True); return
        await db_inc(r, ns, "reqs")
        await db_set_st(r, ns, uid, {"st": "ps_proxy", "g": "ps"})
        await edit_msg(cid, mid, "\U0001f6aa <b>\U0001f91d إعلان بارتنر شيب</b>\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001f4cb <b>الخطوات:</b>\n1\ufe0f\u20e3 البروكسي\n2\ufe0f\u20e3 الكوكيز\n3\ufe0f\u20e3 Account ID\n4\ufe0f\u20e3 Ad Code\n5\ufe0f\u20e3 الهدف + الميزانية\n6\ufe0f\u20e3 مراجعة وتشغيل\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001f53d <b>خطوة 1:</b> اختر البروكسي", kb_proxy()); await answer_cb(cbid); return
    # Proxy
    if data in ("proxy:auto","proxy:skip","proxy:custom") and state == "ps_proxy":
        if data == "proxy:auto":
            p = await db_proxy(r, ns)
            if not p: await answer_cb(cbid, "لا توجد بروكسيات", True); return
            st["px"] = p; st["st"] = "ps_cook"; await db_set_st(r, ns, uid, st)
            await edit_msg(cid, mid, f"\u2705 <b>بروكسي:</b> {p}\n\n\U0001f53d <b>خطوة 2:</b> أدخل الكوكيز", kb_back_proxy())
        elif data == "proxy:skip":
            st["px"] = None; st["st"] = "ps_cook"; await db_set_st(r, ns, uid, st)
            await edit_msg(cid, mid, "\u23ed بدون بروكسي\n\n\U0001f53d <b>خطوة 2:</b> أدخل الكوكيز", kb_back_proxy())
        elif data == "proxy:custom":
            st["st"] = "ps_px_in"; await db_set_st(r, ns, uid, st)
            await edit_msg(cid, mid, "\u270f\ufe0f أدخل البروكسي يدوياً:", kb_home())
        await answer_cb(cbid); return
    if data == "proxy:back" and state == "ps_cook":
        st["st"] = "ps_proxy"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f53d <b>خطوة 1:</b> اختر البروكسي", kb_proxy()); await answer_cb(cbid); return
    # Objective
    if data.startswith("obj:") and state == "ps_obj":
        obj = data.split(":",1)[1]; st["obj"] = obj; st["st"] = "ps_budget"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, f"\u2705 <b>الهدف:</b> {OBJ_NAMES.get(obj,obj)}\n\n\U0001f53d <b>خطوة 7:</b> الميزانية اليومية ($)", kb_home()); await answer_cb(cbid); return
    # Confirm
    if data in ("confirm:yes","confirm:no") and state == "ps_confirm":
        if data == "confirm:no":
            await db_clr(r, ns, uid); await edit_msg(cid, mid, "\u274c تم الإلغاء.", kb_home())
        else:
            st["st"] = "ps_activate"; await db_set_st(r, ns, uid, st)
            await edit_msg(cid, mid, "\u2705 <b>تم التأكيد!</b>\n\nاضغط لتفعيل الاعلان.", kb_activate())
        await answer_cb(cbid); return
    # Activate
    if data == "activate:run" and state == "ps_activate":
        await edit_msg(cid, mid, "\u23f3 <b>جاري تشغيل الإعلان...</b>\n\U0001f517 ربط Ad Code...")
        await answer_cb(cbid)
        # Call Facebook Graph API
        full_cookies = st.get("full_cook", "")
        result = await fb_create_campaign(
            account_id=st.get("acc", ""),
            cookies_str=full_cookies,
            objective=st.get("obj", "CONVERSATIONS"),
            daily_budget=st.get("bgt", 10),
            days=st.get("days", 7),
            ad_code=st.get("acode", ""),
            proxy=st.get("px")
        )
        if result.get("ok"):
            cmp_id = result.get("campaign_id", "")
            await edit_msg(cid, mid, f"\u2705 <b>تم تشغيل الإعلان بنجاح!</b>\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001f522 Account: {st.get('acc','')}\n\U0001f4cb Ad Code: {st.get('acode','')}\n\U0001f3af الهدف: {OBJ_NAMES.get(st.get('obj',''),'')}\n\U0001f4b0 الميزانية: {st.get('bgt',10)}$/يوم\n\U0001f4c5 المدة: {st.get('days',7)} أيام\n\U0001f4c4 Campaign ID: <code>{cmp_id}</code>\n\n\U0001f389 <b>مبروك! الإعلان يعمل الآن</b>", kb_home())
        else:
            err = result.get("error", "Unknown error")
            await edit_msg(cid, mid, f"\u274c <b>فشل تشغيل الإعلان</b>\n\nالخطأ: {err}\n\n\U0001f4a1 تأكد من صحة الكوكيز و Account ID", kb_home())
        await db_clr(r, ns, uid); return
    # Admin
    if data.startswith("admin:"):
        await on_admin_cb(r, ns, uid, cid, mid, cbid, data, st); return
    await answer_cb(cbid)

async def on_admin_cb(r, ns, uid, cid, mid, cbid, data, st):
    if data == "admin:stats":
        rq = await db_stat(r, ns, "reqs"); uc = await db_stat(r, ns, "uc")
        await edit_msg(cid, mid, f"\U0001f4ca <b>الإحصائيات</b>\n\nالطلبات: {rq}\nالمستخدمون: {uc}", kb_admin())
    elif data == "admin:gen_code":
        st["st"] = "a_gen"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f39f اكتب مدة الكود بالساعات (مثال: 24)", kb_back_admin())
    elif data == "admin:set_user":
        st["st"] = "a_set"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f464 اكتب: user_id | الاسم | ساعات\nمثال: 123456789 | VIP | 168", kb_back_admin())
    elif data == "admin:remove_user":
        st["st"] = "a_rm"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f5d1 اكتب user_id المراد حذفه:", kb_back_admin())
    elif data == "admin:broadcast":
        st["st"] = "a_bc"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f4e2 اكتب الرسالة الجماعية:", kb_back_admin())
    elif data == "admin:add_proxies":
        st["st"] = "a_px"; await db_set_st(r, ns, uid, st)
        await edit_msg(cid, mid, "\U0001f310 ارسل البروكسيات، كل واحد في سطر.", kb_back_admin())
    await answer_cb(cbid)

async def on_msg(r, ns, msg):
    uid, cid = msg["from"]["id"], msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    st = await db_state(r, ns, uid); state = st.get("st", "")

    if text == "/start":
        await db_ensure(r, ns, uid, msg["from"].get("username",""), msg["from"].get("first_name",""))
        existing = await db_user(r, ns, uid)
        if not existing or not existing.get("joined"):
            await db_inc(r, ns, "uc", 1)
        await db_clr(r, ns, uid); await send_home(r, ns, cid, uid); return
    if text == f"/{ADMIN_CMD}":
        await db_set_st(r, ns, uid, {"st": "a_pw"}); await send_msg(cid, "\U0001f510 اكتب باسورد لوحة التحكم:"); return

    # Redeem
    if state == "redeem":
        h = await db_use_code(r, ns, text, uid)
        if not h: await send_msg(cid, "\u274c الكود غير صالح أو تم استخدامه.", kb_home()); return
        until = await db_set_sub(r, ns, uid, h); await db_clr(r, ns, uid)
        u = await db_user(r, ns, uid); await send_msg(cid, f"\u2705 تم تفعيل الاشتراك حتى:\n{until}", kb_main(is_sub(u))); return

    # PS Gate inputs
    if state == "ps_px_in":
        if not v_proxy(text): await send_msg(cid, "\u274c صيغة بروكسي غير صحيحة", kb_home()); return
        st["px"] = text; st["st"] = "ps_cook"; await db_set_st(r, ns, uid, st)
        await send_msg(cid, f"\u2705 <b>بروكسي:</b> {text}\n\n\U0001f53d <b>خطوة 2:</b> أدخل الكوكيز", kb_back_proxy()); return
    if state == "ps_cook":
        if not v_cookies(text): await send_msg(cid, "\u274c الكوكيز ناقصة (لازم c_user, xs, datr)", kb_home()); return
        st["cook"] = text[:200]+"..."; st["full_cook"] = text; st["st"] = "ps_acc"; await db_set_st(r, ns, uid, st)
        await send_msg(cid, "\u2705 تم حفظ الكوكيز\n\n\U0001f53d <b>خطوة 3:</b> أدخل Account ID (10-20 رقم)"); return
    if state == "ps_acc":
        if not v_id(text): await send_msg(cid, "\u274c Account ID غير صحيح (10-20 رقم)", kb_home()); return
        st["acc"] = text.strip(); st["st"] = "ps_acode"; await db_set_st(r, ns, uid, st)
        await send_msg(cid, f"\u2705 <b>Account:</b> {text.strip()}\n\n\U0001f53d <b>خطوة 4:</b> أدخل Ad Code"); return
    if state == "ps_acode":
        if len(text) < 5: await send_msg(cid, "\u274c Ad Code قصير جداً", kb_home()); return
        st["acode"] = text.strip(); st["st"] = "ps_obj"; await db_set_st(r, ns, uid, st)
        await send_msg(cid, "\u2705 تم حفظ Ad Code\n\n\U0001f53d <b>خطوة 6:</b> اختر هدف الإعلان", kb_objectives()); return
    if state == "ps_budget":
        ok, val = v_budget(text)
        if not ok: await send_msg(cid, "\u274c الميزانية لازم رقم (1$ - 10000$)", kb_home()); return
        st["bgt"] = val; st["st"] = "ps_days"; await db_set_st(r, ns, uid, st)
        await send_msg(cid, f"\u2705 <b>الميزانية:</b> {val}$/يوم\n\n\U0001f53d <b>خطوة 8:</b> عدد الأيام (1-365)"); return
    if state == "ps_days":
        ok, val = v_days(text)
        if not ok: await send_msg(cid, "\u274c عدد الأيام لازم رقم (1-365)", kb_home()); return
        st["days"] = val; st["st"] = "ps_confirm"; await db_set_st(r, ns, uid, st)
        sm = (f"\U0001f4cb <b>مراجعة البيانات:</b>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
              f"\U0001f310 بروكسي: {st.get('px') or 'بدون'}\n"
              f"\U0001f522 Account: {st.get('acc','')}\n"
              f"\U0001f4cb Ad Code: {st.get('acode','')}\n\U0001f3af الهدف: {OBJ_NAMES.get(st.get('obj',''),'')}\n"
              f"\U0001f4b0 الميزانية: {st.get('bgt',10)}$/يوم\n\U0001f4c5 المدة: {val} أيام\n"
              f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\nأكّد لتشغيل الإعلان.")
        await send_msg(cid, sm, kb_confirm()); return

    # Admin inputs
    if state == "a_pw":
        if text != ADMIN_PASS: await send_msg(cid, "\u274c باسورد خطأ."); return
        await db_clr(r, ns, uid); rq = await db_stat(r, ns, "reqs")
        await send_msg(cid, f"\u2705 <b>لوحة التحكم</b>\n\nالطلبات: {rq}", kb_admin()); return
    if state == "a_gen":
        try: h = int(text); assert h > 0
        except: await send_msg(cid, "اكتب رقم ساعات صحيح."); return
        code = gen_code(); await db_mk_code(r, ns, code, h); await db_clr(r, ns, uid)
        await send_msg(cid, f"\u2705 تم توليد الكود:\n<code>{code}</code>\nالمدة: {h} ساعة", kb_admin()); return
    if state == "a_set":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 3: await send_msg(cid, "الصيغة غلط. استخدم: user_id | الاسم | ساعات"); return
        try: tid = int(parts[0]); nm = parts[1]; h = int(parts[2])
        except: await send_msg(cid, "user_id والساعات لازم أرقام."); return
        await db_ensure(r, ns, tid); u = await db_user(r, ns, tid); u["cn"] = nm; await db_save_user(r, ns, tid, u)
        until = await db_set_sub(r, ns, tid, h); await db_clr(r, ns, uid)
        await send_msg(cid, f"\u2705 تم ضبط {nm}\nحتى: {until}", kb_admin()); return
    if state == "a_rm":
        try: tid = int(text)
        except: await send_msg(cid, "اكتب user_id صحيح."); return
        u = await db_user(r, ns, tid)
        if u: u["removed"] = True; await db_save_user(r, ns, tid, u)
        await db_clr(r, ns, uid); await send_msg(cid, "\u2705 تم حذف المستخدم.", kb_admin()); return
    if state == "a_bc":
        await db_clr(r, ns, uid); await send_msg(cid, "\U0001f4e2 ميزة البث الجماعي قريباً!", kb_admin()); return
    if state == "a_px":
        c = await db_add_px(r, ns, text); await db_clr(r, ns, uid)
        await send_msg(cid, f"\u2705 تمت إضافة {c} بروكسي.", kb_admin()); return

    await db_ensure(r, ns, uid, msg["from"].get("username",""), msg["from"].get("first_name",""))
    await send_home(r, ns, cid, uid)

# ── FastAPI Endpoints ───────────────────────────────
@app.post("/")
async def root(request: Request):
    body = await request.json()
    if "update_id" in body:
        await handle_update(body)
        return {"ok": True}
    return {"status": "running", "bot": BOT_NAME}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    payload = body.get("payload", body)
    if "update_id" in payload:
        await handle_update(payload)
    return {"ok": True}

class SetupReq(BaseModel):
    webhook_url: str = Field("", description="Webhook URL to register with Telegram")
class SetupRes(BaseModel):
    success: bool
    message: str
    bot_info: dict = {}

@app.post("/setup", response_model=SetupRes)
async def setup(req: SetupReq):
    if not TOKEN: return SetupRes(success=False, message="TELEGRAM_BOT_TOKEN not set")
    if req.webhook_url:
        r = await tg("setWebhook", {"url": req.webhook_url})
        return SetupRes(success=r.get("ok",False), message=str(r.get("description","")), bot_info=r)
    r = await tg("deleteWebhook", {}); info = await tg("getMe", {})
    return SetupRes(success=r.get("ok",False), message="Webhook removed", bot_info=info.get("result",{}))

if __name__ == "__main__":
    run_service(app)
