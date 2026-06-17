"""
BESHOY BOOST BOT - Universal Edition
يعمل على أي سيرفر - مستقل تماماً
FastAPI + Redis + 5 Ad Gates + Full Admin Panel
"""
import os
import re
import json
import secrets
import string
import random
import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager
import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging (لازم يكون قبل أي استخدام لـ logger)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "Nemo@1986")
SUPPORT_URL = os.environ.get("SUPPORT_URL", "https://t.me/your_support_username")
PORT = int(os.environ.get("PORT", "8000"))
BOT_NAME = "🚀 BESHOY BOOST BOT"
ADMIN_CMD = "beshoy"
FB_API = "https://graph.facebook.com/v18.0"
REDIS_NS = "beshoy"
STATE_TTL = 1800

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set!")

if ADMIN_PASS == "Nemo@1986":
    logger.warning("⚠️ ADMIN_PASS لسه الافتراضي! غيّره من متغيرات البيئة فوراً.")

# ─── Redis Connection ─────────────────────────────────────
redis_pool: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.from_url(REDIS_URL, decode_responses=True)
    return redis_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool
    redis_pool = redis.from_url(REDIS_URL, decode_responses=True)
    for i in range(10):
        try:
            await redis_pool.ping()
            logger.info("✅ Redis connected")
            break
        except Exception as e:
            logger.warning(f"⏳ Redis retry {i+1}/10: {e}")
            await asyncio.sleep(2)
    else:
        raise RuntimeError("❌ Redis مش بيرد بعد 10 محاولات")

    if WEBHOOK_URL:
        params = {"url": f"{WEBHOOK_URL}/webhook"}
        if WEBHOOK_SECRET:
            params["secret_token"] = WEBHOOK_SECRET
        try:
            r = await tg("setWebhook", params)
            logger.info(f"🔔 Webhook registered: {r}")
        except Exception as e:
            logger.error(f"❌ Webhook registration failed: {e}")
    else:
        logger.warning("⚠️ WEBHOOK_URL مش متظبط — البوت هيستلم الطلبات بس من غير setWebhook تلقائي.")

    yield

    if redis_pool:
        await redis_pool.close()
        logger.info("👋 Redis disconnected")

app = FastAPI(title=BOT_NAME, version="6.0.0", lifespan=lifespan)

# ─── Telegram API Helpers ─────────────────────────────────
TG = f"https://api.telegram.org/bot{TOKEN}"

async def tg(method: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{TG}/{method}", json=data)
        return r.json()

async def send_msg(cid, text, kb=None):
    d = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
    if kb:
        d["reply_markup"] = kb
    return await tg("sendMessage", d)

async def edit_msg(cid, mid, text, kb=None):
    d = {"chat_id": cid, "message_id": mid, "text": text, "parse_mode": "HTML"}
    if kb:
        d["reply_markup"] = kb
    return await tg("editMessageText", d)

async def answer_cb(cbid, text="", alert=False):
    return await tg("answerCallbackQuery", {
        "callback_query_id": cbid,
        "text": text,
        "show_alert": alert
    })

# ─── Keyboard Builders ────────────────────────────────────
def ikb(rows):
    return {"inline_keyboard": rows}

def btn(text, data="", url=""):
    b = {"text": text}
    if url:
        b["url"] = url
    else:
        b["callback_data"] = data
    return b

def kb_main(is_sub):
    rows = []
    if is_sub:
        rows.append([btn("🚀 إعلان جديد", "ad:start")])
    rows.append([btn("🎟 تفعيل كود", "redeem"), btn("🛠 دعم", url=SUPPORT_URL)])
    return ikb(rows)

def kb_gates():
    return ikb([
        [btn("🌑 Dark Post", "gate:dark_post"), btn("🚀 Boost Post", "gate:boost_post")],
        [btn("👍 Page Like", "gate:page_like"), btn("🤝 Partner Ship", "gate:partner_ship")],
        [btn("🎪 Event Campaign", "gate:event")],
        [btn("🏠 الرئيسية", "home")]
    ])

def kb_proxy():
    return ikb([
        [btn("🎲 تلقائي", "proxy:auto"), btn("✏️ يدوي", "proxy:custom")],
        [btn("⏭️ تخطي", "proxy:skip")],
        [btn("🏠 الرئيسية", "home")]
    ])

def kb_objectives():
    objs = {
        "CONVERSATIONS": "💬 محادثات",
        "MESSAGES_MESSENGER": "📨 ماسنجر",
        "MESSAGES_WHATSAPP": "📱 واتساب",
        "LINK_CLICKS": "🔗 نقرات",
        "POST_ENGAGEMENT": "📌 تفاعل",
        "VIDEO_VIEWS": "🎬 فيديو"
    }
    rows = [[btn(name, f"obj:{key}")] for key, name in objs.items()]
    rows.append([btn("🏠 الرئيسية", "home")])
    return ikb(rows)

def kb_gender():
    return ikb([
        [btn("👨 ذكر", "gender:male"), btn("👩 أنثى", "gender:female")],
        [btn("👫 الكل", "gender:all")],
        [btn("🏠 الرئيسية", "home")]
    ])

def kb_confirm():
    return ikb([
        [btn("✅ تأكيد", "confirm:yes"), btn("❌ إلغاء", "confirm:no")],
        [btn("🏠 الرئيسية", "home")]
    ])

def kb_back():
    return ikb([[btn("🔙 رجوع", "back")]])

def kb_home():
    return ikb([[btn("🏠 الرئيسية", "home")]])

def kb_admin():
    return ikb([
        [btn("🎟 توليد كود", "admin:gen_code"), btn("👤 تمديد مشترك", "admin:set_user")],
        [btn("🗑 حذف مشترك", "admin:remove_user"), btn("📢 رسالة جماعية", "admin:broadcast")],
        [btn("🌐 إضافة بروكسيات", "admin:add_proxies"), btn("📊 الإحصائيات", "admin:stats")],
        [btn("🏠 خروج", "home")]
    ])

def kb_back_admin():
    return ikb([[btn("🔙 لوحة التحكم", "admin:stats")]])

# ─── Database Functions (Redis) ───────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def gen_code(prefix="BM", length=12):
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(secrets.choice(chars) for _ in range(length))}"

async def db_user(r, uid):
    raw = await r.get(f"{REDIS_NS}:u:{uid}")
    return json.loads(raw) if raw else None

async def db_save_user(r, uid, data):
    await r.set(f"{REDIS_NS}:u:{uid}", json.dumps(data, ensure_ascii=False))

async def db_ensure_user(r, uid, username="", first_name=""):
    user = await db_user(r, uid)
    if not user:
        user = {
            "uid": uid,
            "un": username,
            "fn": first_name,
            "joined": now_iso(),
            "removed": False,
            "sub": ""
        }
        await r.sadd(f"{REDIS_NS}:uids", uid)
        await db_inc_stat(r, "users")
    else:
        user["un"] = username
        user["fn"] = first_name
    await db_save_user(r, uid, user)
    return user

def is_sub(user):
    if not user or user.get("removed"):
        return False
    sub = user.get("sub", "")
    if not sub:
        return False
    try:
        return datetime.fromisoformat(sub) > datetime.now(timezone.utc)
    except:
        return False

async def db_state(r, uid):
    raw = await r.get(f"{REDIS_NS}:s:{uid}")
    return json.loads(raw) if raw else {"st": ""}

async def db_set_state(r, uid, data):
    await r.set(f"{REDIS_NS}:s:{uid}", json.dumps(data, ensure_ascii=False), ex=STATE_TTL)

async def db_clear_state(r, uid):
    await r.delete(f"{REDIS_NS}:s:{uid}")

async def db_use_code(r, code, uid):
    raw = await r.get(f"{REDIS_NS}:c:{code}")
    if not raw:
        return None
    c = json.loads(raw)
    if c.get("ub"):
        return None
    c["ub"] = uid
    c["ua"] = now_iso()
    await r.set(f"{REDIS_NS}:c:{code}", json.dumps(c))
    return int(c["h"])

async def db_mk_code(r, code, hours):
    await r.set(f"{REDIS_NS}:c:{code}", json.dumps({
        "h": hours,
        "ca": now_iso(),
        "ub": None,
        "ua": None
    }))

async def db_set_sub(r, uid, hours):
    user = await db_user(r, uid)
    if not user:
        user = {
            "uid": uid,
            "un": "",
            "fn": "",
            "joined": now_iso(),
            "removed": False,
            "sub": ""
        }
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
    user["sub"] = until
    user["removed"] = False
    await db_save_user(r, uid, user)
    return until

async def db_inc_stat(r, key, amount=1):
    await r.incrby(f"{REDIS_NS}:st:{key}", amount)

async def db_get_stat(r, key):
    val = await r.get(f"{REDIS_NS}:st:{key}")
    return int(val) if val else 0

async def db_add_proxies(r, text):
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
    if lines:
        await r.sadd(f"{REDIS_NS}:proxies", *lines)
    return len(lines)

async def db_get_random_proxy(r):
    proxies = await r.srandmember(f"{REDIS_NS}:proxies", 1)
    return proxies[0] if proxies else None

async def db_get_all_uids(r):
    return await r.smembers(f"{REDIS_NS}:uids")

# ─── Facebook API Functions ───────────────────────────────
def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    if not (proxy_str.startswith("http://") or proxy_str.startswith("https://")):
        proxy_str = f"http://{proxy_str}"
    return proxy_str

async def fb_check_token(token, proxy=None):
    url = f"{FB_API}/me"
    params = {"access_token": token, "fields": "id,name"}
    async with httpx.AsyncClient(timeout=15, proxy=parse_proxy(proxy)) as c:
        resp = await c.get(url, params=params)
        return resp.json()

async def fb_upload_image(token, page_id, image_bytes, proxy=None):
    url = f"{FB_API}/{page_id}/photos"
    files = {"source": ("image.jpg", image_bytes, "image/jpeg")}
    params = {"access_token": token, "published": "false"}
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, files=files, params=params)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

async def fb_create_dark_post(token, page_id, image_id, message, link="", proxy=None):
    url = f"{FB_API}/{page_id}/feed"
    payload = {
        "access_token": token,
        "message": message,
        "attached_media": f'[{{"media_fbid": "{image_id}"}}]',
        "published": "false"
    }
    if link:
        payload["link"] = link
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, data=payload)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

async def fb_create_campaign(token, account_id, objective, budget, status="PAUSED", proxy=None):
    url = f"{FB_API}/act_{account_id}/campaigns"
    params = {
        "access_token": token,
        "name": f"Boost_{int(datetime.now().timestamp())}",
        "objective": objective,
        "status": status,
        "special_ad_categories": "[]",
        "daily_budget": int(budget * 100)
    }
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

async def fb_create_adset(token, account_id, campaign_id, budget, targeting, status="PAUSED", proxy=None, opt_goal="REACH"):
    url = f"{FB_API}/act_{account_id}/adsets"
    params = {
        "access_token": token,
        "name": f"AdSet_{int(datetime.now().timestamp())}",
        "campaign_id": campaign_id,
        "daily_budget": int(budget * 100),
        "targeting": json.dumps(targeting),
        "status": status,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": opt_goal
    }
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

async def fb_create_ad(token, account_id, adset_id, creative, status="PAUSED", proxy=None):
    url = f"{FB_API}/act_{account_id}/ads"
    params = {
        "access_token": token,
        "name": f"Ad_{int(datetime.now().timestamp())}",
        "adset_id": adset_id,
        "creative": json.dumps(creative),
        "status": status
    }
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

async def fb_create_event(token, page_id, name, desc, start, end, proxy=None):
    url = f"{FB_API}/{page_id}/events"
    params = {
        "access_token": token,
        "name": name,
        "description": desc,
        "start_time": start,
        "end_time": end
    }
    async with httpx.AsyncClient(timeout=30, proxy=parse_proxy(proxy)) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
    if "id" in data:
        return {"ok": True, "id": data["id"]}
    return {"ok": False, "error": data.get("error", {}).get("message", "Unknown")}

# ─── Ad Execution Logic ───────────────────────────────────
async def execute_ad(r, uid, state):
    gate = state.get("gate")
    token = state.get("token")
    proxy = state.get("proxy")
    acc_id = state.get("account_id")
    budget = state.get("budget")
    days = state.get("days")
    try:
        if gate == "dark_post":
            page_id = state.get("page_id")
            image_id = state.get("image_id")
            message = state.get("message")
            link = state.get("link", "")
            country = state.get("country")
            age = state.get("age")
            gender = state.get("gender")

            dark_post = await fb_create_dark_post(token, page_id, image_id, message, link, proxy)
            if not dark_post.get("ok"):
                raise Exception(dark_post.get("error"))

            campaign = await fb_create_campaign(token, acc_id, "OUTCOME_ENGAGEMENT", budget, "PAUSED", proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {
                "geo_locations": {"countries": [country]},
                "age_min": int(age.split("-")[0]),
                "age_max": int(age.split("-")[1]),
                "genders": [1] if gender == "male" else [2] if gender == "female" else [1, 2]
            }
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, "PAUSED", proxy, "POST_ENGAGEMENT")
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"object_story_id": dark_post["id"]}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, "ACTIVE", proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            return {"ok": True, "ad_id": ad["id"], "campaign_id": campaign["id"], "adset_id": adset["id"]}

        elif gate == "boost_post":
            page_id = state.get("page_id")
            post_id = state.get("post_id")
            campaign = await fb_create_campaign(token, acc_id, "OUTCOME_ENGAGEMENT", budget, "PAUSED", proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {"geo_locations": {"countries": ["US"]}}
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, "PAUSED", proxy, "POST_ENGAGEMENT")
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"object_story_id": f"{page_id}_{post_id}"}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, "ACTIVE", proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            return {"ok": True, "ad_id": ad["id"]}

        elif gate == "page_like":
            page_id = state.get("page_id")
            campaign = await fb_create_campaign(token, acc_id, "OUTCOME_ENGAGEMENT", budget, "PAUSED", proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {"page_ids": [page_id], "geo_locations": {"countries": ["US"]}}
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, "PAUSED", proxy, "PAGE_ENGAGEMENT")
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"page_id": page_id, "use_page_actor_identity": True}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, "ACTIVE", proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            return {"ok": True, "ad_id": ad["id"]}

        elif gate == "partner_ship":
            obj = state.get("objective")
            obj_map = {
                "CONVERSATIONS": "OUTCOME_ENGAGEMENT",
                "MESSAGES_MESSENGER": "OUTCOME_ENGAGEMENT",
                "MESSAGES_WHATSAPP": "OUTCOME_ENGAGEMENT",
                "LINK_CLICKS": "OUTCOME_TRAFFIC",
                "POST_ENGAGEMENT": "OUTCOME_ENGAGEMENT",
                "VIDEO_VIEWS": "OUTCOME_AWARENESS"
            }
            fb_obj = obj_map.get(obj, "OUTCOME_ENGAGEMENT")
            campaign = await fb_create_campaign(token, acc_id, fb_obj, budget, "PAUSED", proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {"geo_locations": {"countries": ["US"]}}
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, "PAUSED", proxy)
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"page_id": state.get("page_id", ""), "message": "Partner Ship Ad"}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, "ACTIVE", proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            return {"ok": True, "ad_id": ad["id"]}

        elif gate == "event":
            page_id = state.get("page_id")
            name = state.get("event_name")
            desc = state.get("event_desc")
            start = state.get("event_start")
            end = state.get("event_end")

            event = await fb_create_event(token, page_id, name, desc, start, end, proxy)
            if not event.get("ok"):
                raise Exception(event.get("error"))

            campaign = await fb_create_campaign(token, acc_id, "OUTCOME_ENGAGEMENT", budget, "PAUSED", proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {"geo_locations": {"countries": ["US"]}}
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, "PAUSED", proxy)
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"event_id": event["id"]}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, "ACTIVE", proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            return {"ok": True, "ad_id": ad["id"], "event_id": event["id"]}

    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Home & State Helpers ─────────────────────────────────
async def send_home(r, cid, uid, mid=0):
    user = await db_user(r, uid)
    subscribed = is_sub(user)
    name = (user.get("fn") or "مستخدم") if user else "مستخدم"
    status = "✅ مشترك" if subscribed else "❌ غير مشترك"
    text = f"⚡ <b>{BOT_NAME}</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."
    kb = kb_main(subscribed)
    if mid:
        await edit_msg(cid, mid, text, kb)
    else:
        await send_msg(cid, text, kb)

# ─── Callback Handler ─────────────────────────────────────
async def on_callback(r, cb):
    try:
        uid = cb["from"]["id"]
        cid = cb["message"]["chat"]["id"]
        mid = cb["message"]["message_id"]
        data = cb["data"]
        cbid = cb["id"]
        state = await db_state(r, uid)
        st = state.get("st", "")

        if data == "home" or data == "back":
            await db_clear_state(r, uid)
            await send_home(r, cid, uid, mid)
            await answer_cb(cbid)
            return

        if data == "redeem":
            await db_set_state(r, uid, {"st": "redeem"})
            await edit_msg(cid, mid, "🎟 أرسل كود التفعيل:", kb_home())
            await answer_cb(cbid)
            return

        if data == "ad:start":
            user = await db_user(r, uid)
            if not is_sub(user):
                await answer_cb(cbid, "❌ اشترك أولاً بكود Redeem", True)
                return
            await edit_msg(cid, mid, "🚀 اختر البوابة الإعلانية:", kb_gates())
            await answer_cb(cbid)
            return

        if data.startswith("gate:"):
            gate = data.split(":")[1]
            state = {"st": f"gate_{gate}_token", "gate": gate}
            await db_set_state(r, uid, state)
            await edit_msg(cid, mid, "🔑 أرسل Access Token الخاص بفيسبوك:", kb_back())
            await answer_cb(cbid)
            return

        if data.startswith("proxy:"):
            action = data.split(":")[1]
            gate = state.get("gate")
            if action == "auto":
                p = await db_get_random_proxy(r)
                if not p:
                    await answer_cb(cbid, "لا توجد بروكسيات. اختر يدوي أو تخطي.", True)
                    return
                state["proxy"] = p
                state["st"] = f"gate_{gate}_acc"
                await db_set_state(r, uid, state)
                await edit_msg(cid, mid, f"✅ البروكسي: {p}\n🆔 أدخل Account ID:", kb_back())
            elif action == "custom":
                state["st"] = f"gate_{gate}_px_in"
                await db_set_state(r, uid, state)
                await edit_msg(cid, mid, "✏️ أدخل البروكسي يدوياً (user:pass@ip:port):", kb_back())
            elif action == "skip":
                state["proxy"] = None
                state["st"] = f"gate_{gate}_acc"
                await db_set_state(r, uid, state)
                await edit_msg(cid, mid, "⏭️ بدون بروكسي.\n🆔 أدخل Account ID:", kb_back())
            await answer_cb(cbid)
            return

        if data.startswith("obj:"):
            obj = data.split(":")[1]
            state["objective"] = obj
            state["st"] = st.replace("_obj", "_budget")
            await db_set_state(r, uid, state)
            await edit_msg(cid, mid, f"✅ الهدف: {obj}\n💰 أدخل الميزانية اليومية ($):", kb_back())
            await answer_cb(cbid)
            return

        if data.startswith("gender:"):
            gender = data.split(":")[1]
            state["gender"] = gender
            state["st"] = st.replace("_gender", "_budget")
            await db_set_state(r, uid, state)
            await edit_msg(cid, mid, f"✅ الجنس: {gender}\n💰 أدخل الميزانية اليومية ($):", kb_back())
            await answer_cb(cbid)
            return

        if data == "confirm:yes" and st.endswith("_review"):
            await edit_msg(cid, mid, "⏳ جاري إنشاء الإعلان...")
            await db_inc_stat(r, "requests")
            result = await execute_ad(r, uid, state)
            if result.get("ok"):
                await edit_msg(cid, mid, f"✅ تم إنشاء الإعلان بنجاح!\n\n🆔 Ad ID: <code>{result.get('ad_id')}</code>", kb_home())
            else:
                await edit_msg(cid, mid, f"❌ فشل إنشاء الإعلان:\n{result.get('error')}", kb_home())
            await db_clear_state(r, uid)
            await answer_cb(cbid)
            return

        if data == "confirm:no" and st.endswith("_review"):
            await db_clear_state(r, uid)
            await edit_msg(cid, mid, "❌ تم الإلغاء.", kb_home())
            await answer_cb(cbid)
            return

        if data.startswith("admin:"):
            await handle_admin_callback(r, uid, cid, mid, cbid, data, state)
            return

        await answer_cb(cbid)
    except Exception as e:
        logger.error(f"Callback error: {e}\n{traceback.format_exc()}")
        try:
            await answer_cb(cbid, f"خطأ: {str(e)}", True)
        except:
            pass

# ─── Message Handler ──────────────────────────────────────
async def on_message(r, msg):
    try:
        uid = msg["from"]["id"]
        cid = msg["chat"]["id"]
        mid = msg["message_id"]
        text = msg.get("text", "").strip()
        state = await db_state(r, uid)
        st = state.get("st", "")
        user = await db_ensure_user(r, uid, msg["from"].get("username", ""), msg["from"].get("first_name", ""))

        if text == "/start":
            await db_clear_state(r, uid)
            await send_home(r, cid, uid)
            return

        if text == f"/{ADMIN_CMD}":
            await db_set_state(r, uid, {"st": "admin_pw"})
            await send_msg(cid, "🔐 أدخل كلمة المرور:", kb_home())
            return

        if st == "admin_pw":
            if text == ADMIN_PASS:
                await db_set_state(r, uid, {"st": "admin_menu"})
                await send_msg(cid, "✅ مرحباً مشرف!", kb_admin())
            else:
                await send_msg(cid, "❌ كلمة مرور خاطئة", kb_home())
            return

        if st == "redeem":
            hours = await db_use_code(r, text, uid)
            if not hours:
                await send_msg(cid, "❌ كود غير صالح أو مستخدم", kb_home())
                return
            until = await db_set_sub(r, uid, hours)
            await db_clear_state(r, uid)
            user = await db_user(r, uid)
            await send_msg(cid, f"✅ تم التفعيل حتى: {until}", kb_main(is_sub(user)))
            return

        if st.startswith("admin_"):
            await handle_admin_message(r, uid, cid, text, state)
            return

        if st.startswith("gate_"):
            await handle_gate_message(r, uid, cid, mid, text, msg, state)
            return

        await send_home(r, cid, uid)
    except Exception as e:
        logger.error(f"Message error: {e}\n{traceback.format_exc()}")
        try:
            await send_msg(cid, f"❌ خطأ: {str(e)}", kb_home())
        except:
            pass

# ─── Gate Message Handler ─────────────────────────────────
async def handle_gate_message(r, uid, cid, mid, text, msg, state):
    st = state.get("st")
    gate = state.get("gate")

    if st.endswith("_token"):
        info = await fb_check_token(text, state.get("proxy"))
        if "id" not in info:
            await send_msg(cid, f"❌ التوكن غير صالح: {info.get('error', {}).get('message', '')}", kb_home())
            await db_clear_state(r, uid)
            return
        state["token"] = text
        state["st"] = f"gate_{gate}_proxy"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم التحقق من التوكن.\n🌐 اختر البروكسي:", kb_proxy())
        return

    if st.endswith("_px_in"):
        state["proxy"] = text
        state["st"] = f"gate_{gate}_acc"
        await db_set_state(r, uid, state)
        await send_msg(cid, f"✅ البروكسي: {text}\n🆔 أدخل Account ID:", kb_back())
        return

    if st.endswith("_acc"):
        if not re.match(r'^\d{10,20}$', text):
            await send_msg(cid, "❌ Account ID غير صحيح (10-20 رقم)", kb_back())
            return
        state["account_id"] = text
        state["st"] = f"gate_{gate}_page"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ Account ID.\n📄 أدخل Page ID:", kb_back())
        return

    if st.endswith("_page"):
        if not re.match(r'^\d+$', text):
            await send_msg(cid, "❌ Page ID غير صحيح", kb_back())
            return
        state["page_id"] = text
        if gate == "dark_post":
            state["st"] = f"gate_{gate}_image"
            await send_msg(cid, "✅ تم حفظ Page ID.\n📸 أرسل الصورة:", kb_back())
        elif gate == "boost_post":
            state["st"] = f"gate_{gate}_postid"
            await send_msg(cid, "✅ تم حفظ Page ID.\n📝 أدخل Post ID:", kb_back())
        elif gate == "page_like":
            state["st"] = f"gate_{gate}_budget"
            await send_msg(cid, "✅ تم حفظ Page ID.\n💰 أدخل الميزانية اليومية ($):", kb_back())
        elif gate == "partner_ship":
            state["st"] = f"gate_{gate}_obj"
            await send_msg(cid, "✅ تم حفظ Page ID.\n🎯 اختر الهدف:", kb_objectives())
        elif gate == "event":
            state["st"] = f"gate_{gate}_name"
            await send_msg(cid, "✅ تم حفظ Page ID.\n🎪 أدخل اسم الحدث:", kb_back())
        await db_set_state(r, uid, state)
        return

    if st == "gate_dark_post_image":
        if "photo" not in msg:
            await send_msg(cid, "❌ أرسل صورة (JPG أو PNG).", kb_back())
            return
        photo = msg["photo"][-1]
        file_id = photo["file_id"]
        file_info = await tg("getFile", {"file_id": file_id})
        if not file_info.get("ok"):
            await send_msg(cid, "❌ فشل تحميل الصورة", kb_home())
            return
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        async with httpx.AsyncClient() as c:
            resp = await c.get(file_url)
            image_bytes = resp.content

        result = await fb_upload_image(state["token"], state["page_id"], image_bytes, state.get("proxy"))
        if not result.get("ok"):
            await send_msg(cid, f"❌ فشل رفع الصورة: {result.get('error')}", kb_home())
            return
        state["image_id"] = result["id"]
        state["st"] = "gate_dark_post_message"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم رفع الصورة.\n💬 أرسل النص الأساسي للإعلان:", kb_back())
        return

    if st == "gate_dark_post_message":
        if len(text) < 5:
            await send_msg(cid, "❌ النص قصير جداً (على الأقل 5 أحرف)", kb_back())
            return
        state["message"] = text
        state["st"] = "gate_dark_post_link"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ النص.\n🔗 أرسل الرابط (اختياري) أو اكتب 'تخطي':", kb_back())
        return

    if st == "gate_dark_post_link":
        if text.lower() == "تخطي" or text.lower() == "skip":
            state["link"] = ""
        else:
            state["link"] = text
        state["st"] = "gate_dark_post_country"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم.\n🌍 أدخل الدولة المستهدفة (رمز الدولة، مثل: EG, US, SA):", kb_back())
        return

    if st == "gate_dark_post_country":
        if len(text) != 2 or not text.isalpha():
            await send_msg(cid, "❌ رمز الدولة يجب أن يكون حرفين (مثل EG)", kb_back())
            return
        state["country"] = text.upper()
        state["st"] = "gate_dark_post_age"
        await db_set_state(r, uid, state)
        await send_msg(cid, f"✅ الدولة: {text.upper()}\n👤 أدخل الفئة العمرية (مثال: 18-65):", kb_back())
        return

    if st == "gate_dark_post_age":
        if not re.match(r'^\d{1,2}-\d{1,2}$', text):
            await send_msg(cid, "❌ الصيغة غير صحيحة. استخدم 18-65 مثلاً.", kb_back())
            return
        ages = text.split("-")
        if int(ages[0]) < 13 or int(ages[1]) > 65 or int(ages[0]) >= int(ages[1]):
            await send_msg(cid, "❌ عمر غير صحيح (13-65)", kb_back())
            return
        state["age"] = text
        state["st"] = "gate_dark_post_gender"
        await db_set_state(r, uid, state)
        await send_msg(cid, f"✅ العمر: {text}\n⚧ اختر الجنس:", kb_gender())
        return

    if st == "gate_boost_post_postid":
        if len(text) < 5:
            await send_msg(cid, "❌ Post ID قصير جداً", kb_back())
            return
        state["post_id"] = text
        state["st"] = "gate_boost_post_budget"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ Post ID.\n💰 أدخل الميزانية اليومية ($):", kb_back())
        return

    if st == "gate_event_name":
        if len(text) < 3:
            await send_msg(cid, "❌ اسم الحدث قصير جداً", kb_back())
            return
        state["event_name"] = text
        state["st"] = "gate_event_desc"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ الاسم.\n📝 أدخل وصف الحدث:", kb_back())
        return

    if st == "gate_event_desc":
        if len(text) < 10:
            await send_msg(cid, "❌ وصف الحدث قصير جداً (على الأقل 10 أحرف)", kb_back())
            return
        state["event_desc"] = text
        state["st"] = "gate_event_start"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ الوصف.\n🕐 أدخل وقت البداية (YYYY-MM-DD HH:MM):", kb_back())
        return

    if st == "gate_event_start":
        state["event_start"] = text
        state["st"] = "gate_event_end"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ البداية.\n🕐 أدخل وقت النهاية (YYYY-MM-DD HH:MM):", kb_back())
        return

    if st == "gate_event_end":
        state["event_end"] = text
        state["st"] = "gate_event_budget"
        await db_set_state(r, uid, state)
        await send_msg(cid, "✅ تم حفظ النهاية.\n💰 أدخل الميزانية اليومية ($):", kb_back())
        return

    if st.endswith("_budget"):
        try:
            budget = float(text)
            if budget < 1 or budget > 10000:
                raise ValueError
        except:
            await send_msg(cid, "❌ الميزانية يجب أن تكون رقماً بين 1 و 10000", kb_back())
            return
        state["budget"] = budget
        state["st"] = st.replace("_budget", "_days")
        await db_set_state(r, uid, state)
        await send_msg(cid, f"✅ الميزانية: {budget}$/يوم\n📅 أدخل عدد الأيام (1-365):", kb_back())
        return

    if st.endswith("_days"):
        try:
            days = int(text)
            if days < 1 or days > 365:
                raise ValueError
        except:
            await send_msg(cid, "❌ يجب أن يكون عدد الأيام بين 1 و 365", kb_back())
            return
        state["days"] = days
        state["st"] = st.replace("_days", "_review")
        await db_set_state(r, uid, state)

        summary = f"📋 <b>مراجعة البيانات</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"🔑 التوكن: {state.get('token', '')[:10]}...\n"
        summary += f"🌐 البروكسي: {state.get('proxy') or 'بدون'}\n"
        summary += f"🆔 Account: {state.get('account_id')}\n"
        summary += f"📄 Page: {state.get('page_id')}\n"
        if gate == "dark_post":
            summary += f"🖼 الصورة: تم رفعها\n"
            summary += f"📝 النص: {state.get('message', '')[:30]}...\n"
            summary += f"🔗 الرابط: {state.get('link') or 'بدون'}\n"
            summary += f"🌍 الدولة: {state.get('country')}\n"
            summary += f"👤 العمر: {state.get('age')}\n"
            summary += f"⚧ الجنس: {state.get('gender')}\n"
        elif gate == "boost_post":
            summary += f"📝 Post ID: {state.get('post_id')}\n"
        elif gate == "partner_ship":
            summary += f"🎯 الهدف: {state.get('objective')}\n"
        elif gate == "event":
            summary += f"🎪 الحدث: {state.get('event_name')}\n"
            summary += f"🕐 البداية: {state.get('event_start')}\n"
            summary += f"🕐 النهاية: {state.get('event_end')}\n"
        summary += f"💰 الميزانية: {state.get('budget')}$/يوم\n"
        summary += f"📅 المدة: {state.get('days')} أيام\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"هل البيانات صحيحة؟"

        await send_msg(cid, summary, kb_confirm())
        return

# ─── Admin Handlers ───────────────────────────────────────
async def handle_admin_callback(r, uid, cid, mid, cbid, data, state):
    action = data.split(":")[1]
    if action == "stats":
        users = await db_get_stat(r, "users")
        reqs = await db_get_stat(r, "requests")
        proxies = await r.scard(f"{REDIS_NS}:proxies")
        await edit_msg(cid, mid, f"📊 <b>الإحصائيات</b>\n\n👤 المستخدمون: {users}\n📋 الطلبات: {reqs}\n🌐 البروكسيات: {proxies}", kb_admin())
    elif action == "gen_code":
        await db_set_state(r, uid, {"st": "admin_gen_code"})
        await edit_msg(cid, mid, "🎟️ أدخل مدة الكود بالساعات:", kb_back_admin())
    elif action == "set_user":
        await db_set_state(r, uid, {"st": "admin_set_user"})
        await edit_msg(cid, mid, "👤 أدخل: uid | hours\nمثال: 123456789 | 168", kb_back_admin())
    elif action == "remove_user":
        await db_set_state(r, uid, {"st": "admin_remove_user"})
        await edit_msg(cid, mid, "🗑️ أدخل UID المستخدم:", kb_back_admin())
    elif action == "broadcast":
        await db_set_state(r, uid, {"st": "admin_broadcast"})
        await edit_msg(cid, mid, "📢 أدخل الرسالة الجماعية:", kb_back_admin())
    elif action == "add_proxies":
        await db_set_state(r, uid, {"st": "admin_add_proxies"})
        await edit_msg(cid, mid, "🌐 أرسل البروكسيات (كل بروكسي في سطر):", kb_back_admin())
    elif action == "menu":
        await db_set_state(r, uid, {"st": "admin_menu"})
        await edit_msg(cid, mid, "✅ لوحة التحكم:", kb_admin())
    await answer_cb(cbid)

async def handle_admin_message(r, uid, cid, text, state):
    st = state.get("st")
    if st == "admin_gen_code":
        try:
            hours = int(text)
            code = gen_code()
            await db_mk_code(r, code, hours)
            await send_msg(cid, f"✅ الكود:\n<code>{code}</code>\nالمدة: {hours} ساعة", kb_admin())
        except:
            await send_msg(cid, "❌ رقم ساعات غير صحيح", kb_admin())
        await db_set_state(r, uid, {"st": "admin_menu"})
        return

    if st == "admin_set_user":
        parts = text.split("|")
        if len(parts) != 2:
            await send_msg(cid, "❌ الصيغة: uid | hours", kb_admin())
            return
        try:
            tid = int(parts[0].strip())
            hours = int(parts[1].strip())
            until = await db_set_sub(r, tid, hours)
            await send_msg(cid, f"✅ تم تمديد {tid} حتى {until}", kb_admin())
        except:
            await send_msg(cid, "❌ بيانات غير صحيحة", kb_admin())
        await db_set_state(r, uid, {"st": "admin_menu"})
        return

    if st == "admin_remove_user":
        try:
            tid = int(text)
            user = await db_user(r, tid)
            if user:
                user["removed"] = True
                await db_save_user(r, tid, user)
            await send_msg(cid, "✅ تم حذف المستخدم", kb_admin())
        except:
            await send_msg(cid, "❌ UID غير صحيح", kb_admin())
        await db_set_state(r, uid, {"st": "admin_menu"})
        return

    if st == "admin_broadcast":
        uids = await db_get_all_uids(r)
        success = 0
        for u in uids:
            try:
                await send_msg(int(u), f"📢 رسالة من الإدارة:\n\n{text}")
                success += 1
            except:
                pass
        await send_msg(cid, f"✅ تم الإرسال لـ {success} مستخدم", kb_admin())
        await db_set_state(r, uid, {"st": "admin_menu"})
        return

    if st == "admin_add_proxies":
        count = await db_add_proxies(r, text)
        await send_msg(cid, f"✅ تمت إضافة {count} بروكسي", kb_admin())
        await db_set_state(r, uid, {"st": "admin_menu"})
        return

# ─── FastAPI Endpoints ────────────────────────────────────
@app.post("/")
async def root(request: Request):
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    if "update_id" in body:
        await handle_update(body)
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    payload = body.get("payload", body)
    if "update_id" in payload:
        await handle_update(payload)
    return {"ok": True}

async def handle_update(upd: dict):
    try:
        r = await get_redis()
        if "callback_query" in upd:
            await on_callback(r, upd["callback_query"])
        elif "message" in upd:
            await on_message(r, upd["message"])
    except Exception as e:
        logger.error(f"Update error: {e}\n{traceback.format_exc()}")

class SetupReq(BaseModel):
    webhook_url: str = Field("", description="Webhook URL to register with Telegram")

class SetupRes(BaseModel):
    success: bool
    message: str
    bot_info: dict = {}

@app.post("/setup")
async def setup(req: SetupReq):
    if not TOKEN:
        return SetupRes(success=False, message="TELEGRAM_BOT_TOKEN not set")
    if req.webhook_url:
        r = await tg("setWebhook", {"url": req.webhook_url})
        return SetupRes(success=r.get("ok", False), message=str(r.get("description", "")), bot_info=r)
    r = await tg("deleteWebhook", {})
    info = await tg("getMe", {})
    return SetupRes(success=r.get("ok", False), message="Webhook removed", bot_info=info.get("result", {}))

@app.get("/health")
async def health():
    return {"status": "healthy", "bot": BOT_NAME}

# ─── Main Entry Point ─────────────────────────────────────
async def main():
    import uvicorn
    logger.info(f"🚀 Starting {BOT_NAME} on port {PORT} (webhook mode)")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
