# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "codewords-client==0.4.6",
#   "fastapi==0.116.1",
#   "httpx==0.28.1",
#   "python-multipart==0.0.20",
# ]
# [tool.env-checker]
# env_vars = [
#   "PORT=8000",
#   "LOGLEVEL=INFO",
#   "TELEGRAM_BOT_TOKEN",
#   "FB_ACCESS_TOKEN",  # اختياري، سيُطلب من المستخدم إذا لم يوجد
# ]
# ///

"""
BESHOY BOOST BOT v4 — إنشاء إعلانات فيسبوك (Dark Posts) باستخدام Access Token
يدعم رفع الصور، استهداف متقدم، التحكم بحالة الإعلان (نشط/متوقف)
"""

import os
import re
import json
import secrets
import string
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict

import httpx
from codewords_client import logger, run_service, redis_client
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

app = FastAPI(title="Beshoy Boost Bot v4", version="4.0.0")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG = f"https://api.telegram.org/bot{TOKEN}"
BOT_NAME = "BESHOY BOOST BOT"
ADMIN_PASS = "Nemo@1986"
ADMIN_CMD = "beshoy"
SUPPORT_URL = "https://t.me/your_support_username"

# تسجيل الأخطاء
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot_errors.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# أهداف الإعلانات المدعومة
OBJECTIVES = {
    "CONVERSATIONS": "محادثات",
    "MESSAGES_MESSENGER": "رسائل ماسنجر",
    "MESSAGES_WHATSAPP": "رسائل واتساب",
    "LINK_CLICKS": "نقرات رابط",
    "POST_ENGAGEMENT": "تفاعل بوست",
    "VIDEO_VIEWS": "مشاهدات فيديو",
}
OBJECTIVE_IDS = list(OBJECTIVES.keys())

# دوال مساعدة
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def gen_code(prefix="BM", length=12):
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(secrets.choice(chars) for _ in range(length))}"

# ─── دوال تيليجرام ─────────────────────────────────────
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
    return await tg("answerCallbackQuery", {"callback_query_id": cbid, "text": text, "show_alert": alert})

# ─── لوحات المفاتيح ─────────────────────────────────────
def ikb(rows):
    return {"inline_keyboard": rows}

def btn(text, data="", url=""):
    b = {"text": text}
    if url:
        b["url"] = url
    else:
        b["callback_data"] = data
    return b

# لوحة رئيسية
def kb_main(is_sub):
    rows = []
    if is_sub:
        rows.append([btn("🚀 إعلان جديد", "ad:start")])
    rows.append([btn("🎟 تفعيل كود", "redeem"), btn("🛠 دعم", url=SUPPORT_URL)])
    return ikb(rows)

# لوحة اختيار الهدف
def kb_objectives():
    rows = [[btn(name, f"obj:{key}")] for key, name in OBJECTIVES.items()]
    rows.append([btn("🏠 الرئيسية", "home")])
    return ikb(rows)

# لوحة اختيار الجنس
def kb_gender():
    return ikb([
        [btn("👨 ذكر", "gender:male"), btn("👩 أنثى", "gender:female")],
        [btn("👫 الكل", "gender:all")],
        [btn("🏠 الرئيسية", "home")]
    ])

# لوحة حالة التشغيل
def kb_ad_status():
    return ikb([
        [btn("▶️ نشط فوراً", "status:ACTIVE")],
        [btn("⏸ متوقف مؤقتاً", "status:PAUSED")],
        [btn("🏠 الرئيسية", "home")]
    ])

# أزرار التحكم بالإعلان بعد التشغيل
def kb_ad_controls(ad_id, current_status):
    rows = []
    if current_status == "ACTIVE":
        rows.append([btn("⏸ إيقاف الإعلان", f"ctrl:pause:{ad_id}")])
    else:
        rows.append([btn("▶️ تشغيل الإعلان", f"ctrl:resume:{ad_id}")])
    rows.append([btn("🏠 الرئيسية", "home")])
    return ikb(rows)

# لوحة تأكيد
def kb_confirm():
    return ikb([
        [btn("✅ تأكيد", "confirm:yes")],
        [btn("❌ إلغاء", "confirm:no")],
        [btn("🏠 الرئيسية", "home")]
    ])

# لوحة رجوع
def kb_back():
    return ikb([[btn("🔙 رجوع", "back")]])

# لوحة المشرف
def kb_admin():
    return ikb([
        [btn("🎟 توليد كود", "admin:gen_code")],
        [btn("👤 تمديد مشترك", "admin:set_user")],
        [btn("🗑 حذف مشترك", "admin:remove_user")],
        [btn("📢 رسالة جماعية", "admin:broadcast")],
        [btn("🌐 إضافة بروكسيات", "admin:add_proxies")],
        [btn("📊 الإحصائيات", "admin:stats")],
        [btn("🏠 خروج", "home")]
    ])

# لوحة رجوع للمشرف
def kb_back_admin():
    return ikb([[btn("🔙 لوحة التحكم", "admin:stats")]])

# ─── دوال فيسبوك الجديدة (باستخدام Access Token) ────
FB_API = "https://graph.facebook.com/v18.0"

async def fb_check_token(access_token: str) -> dict:
    """التحقق من صلاحية التوكن وجلب معلومات المستخدم"""
    url = f"{FB_API}/me"
    params = {"access_token": access_token, "fields": "id,name,accounts{id,name}"}
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.get(url, params=params)
        return resp.json()

async def fb_upload_image(access_token: str, page_id: str, image_bytes: bytes) -> str:
    """رفع صورة إلى صفحة فيسبوك (غير منشورة) وإرجاع معرف الصورة"""
    url = f"{FB_API}/{page_id}/photos"
    files = {"source": ("image.jpg", image_bytes, "image/jpeg")}
    params = {"access_token": access_token, "published": "false"}
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, files=files, params=params)
        data = resp.json()
        if "id" in data:
            return data["id"]
        else:
            raise Exception(f"فشل رفع الصورة: {data}")

async def fb_create_dark_post(access_token: str, page_id: str, image_id: str,
                               message: str, headline: str = None, description: str = None) -> str:
    """إنشاء منشور غير منشور (Dark Post) مرتبط بصفحة"""
    url = f"{FB_API}/{page_id}/feed"
    payload = {
        "access_token": access_token,
        "message": message,
        "attached_media": f'{{"media_fbid":"{image_id}"}}',
        "published": "false",
    }
    if headline:
        payload["child_attachments"] = [{"link": "", "name": headline, "description": description or ""}]
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, data=payload)
        data = resp.json()
        if "id" in data:
            return data["id"]
        else:
            raise Exception(f"فشل إنشاء المنشور: {data}")

async def fb_create_campaign(access_token: str, account_id: str, objective: str, status: str = "PAUSED") -> str:
    """إنشاء حملة إعلانية"""
    url = f"{FB_API}/act_{account_id}/campaigns"
    params = {
        "access_token": access_token,
        "name": f"Boost_{int(datetime.now().timestamp())}",
        "objective": objective,
        "status": status,
        "special_ad_categories": [],
    }
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
        if "id" in data:
            return data["id"]
        else:
            raise Exception(f"فشل إنشاء الحملة: {data}")

async def fb_create_adset(access_token: str, account_id: str, campaign_id: str,
                           daily_budget: float, targeting: dict, status: str = "PAUSED") -> str:
    """إنشاء مجموعة إعلانات مع الاستهداف"""
    url = f"{FB_API}/act_{account_id}/adsets"
    params = {
        "access_token": access_token,
        "name": f"AdSet_{int(datetime.now().timestamp())}",
        "campaign_id": campaign_id,
        "daily_budget": int(daily_budget * 100),
        "targeting": targeting,
        "status": status,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "REACH",
    }
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
        if "id" in data:
            return data["id"]
        else:
            raise Exception(f"فشل إنشاء مجموعة الإعلانات: {data}")

async def fb_create_ad(access_token: str, account_id: str, adset_id: str, dark_post_id: str, status: str = "PAUSED") -> str:
    """إنشاء الإعلان النهائي المرتبط بالمنشور غير المنشور"""
    url = f"{FB_API}/act_{account_id}/ads"
    params = {
        "access_token": access_token,
        "name": f"Ad_{int(datetime.now().timestamp())}",
        "adset_id": adset_id,
        "creative": {"object_story_id": dark_post_id},
        "status": status,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, params=params)
        data = resp.json()
        if "id" in data:
            return data["id"]
        else:
            raise Exception(f"فشل إنشاء الإعلان: {data}")

async def fb_update_ad_status(access_token: str, ad_id: str, status: str) -> bool:
    """تحديث حالة الإعلان (ACTIVE أو PAUSED)"""
    url = f"{FB_API}/{ad_id}"
    params = {"access_token": access_token, "status": status}
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.post(url, params=params)
        return resp.status_code == 200

# ─── دوال قاعدة البيانات (Redis) ─────────────────────
async def db_user(r, ns, uid):
    raw = await r.get(f"{ns}:u:{uid}")
    return json.loads(raw) if raw else None

async def db_save_user(r, ns, uid, data):
    await r.set(f"{ns}:u:{uid}", json.dumps(data, ensure_ascii=False))

async def db_ensure_user(r, ns, uid, username="", first_name=""):
    user = await db_user(r, ns, uid)
    if not user:
        user = {
            "uid": uid,
            "un": username,
            "fn": first_name,
            "cn": "",
            "joined": now_iso(),
            "removed": False,
            "sub": "",
            "fb_token": "",  # سنخزن التوكن هنا مشفراً (اختياري)
        }
    else:
        user["un"] = username
        user["fn"] = first_name
    await db_save_user(r, ns, uid, user)
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

async def db_state(r, ns, uid):
    raw = await r.get(f"{ns}:s:{uid}")
    return json.loads(raw) if raw else {"st": ""}

async def db_set_state(r, ns, uid, data):
    await r.set(f"{ns}:s:{uid}", json.dumps(data, ensure_ascii=False))

async def db_clear_state(r, ns, uid):
    await r.delete(f"{ns}:s:{uid}")

async def db_use_code(r, ns, code, uid):
    raw = await r.get(f"{ns}:c:{code}")
    if not raw:
        return None
    c = json.loads(raw)
    if c.get("ub"):
        return None
    c["ub"] = uid
    c["ua"] = now_iso()
    await r.set(f"{ns}:c:{code}", json.dumps(c))
    return int(c["h"])

async def db_mk_code(r, ns, code, hours):
    await r.set(f"{ns}:c:{code}", json.dumps({"h": hours, "ca": now_iso(), "ub": None, "ua": None}))

async def db_set_sub(r, ns, uid, hours):
    user = await db_user(r, ns, uid)
    if not user:
        user = {"uid": uid, "un": "", "fn": "", "cn": "", "joined": now_iso(), "removed": False, "sub": ""}
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
    user["sub"] = until
    user["removed"] = False
    await db_save_user(r, ns, uid, user)
    return until

async def db_save_ad(r, ns, uid, ad_data):
    """حفظ بيانات الإعلان المنشأ للمستخدم"""
    await r.set(f"{ns}:ad:{uid}", json.dumps(ad_data, ensure_ascii=False))

async def db_get_ad(r, ns, uid):
    raw = await r.get(f"{ns}:ad:{uid}")
    return json.loads(raw) if raw else None

async def db_delete_ad(r, ns, uid):
    await r.delete(f"{ns}:ad:{uid}")

async def db_inc_stat(r, ns, key, amount=1):
    await r.incrby(f"{ns}:st:{key}", amount)

async def db_get_stat(r, ns, key):
    val = await r.get(f"{ns}:st:{key}")
    return int(val) if val else 0

# ─── الصفحة الرئيسية ──────────────────────────────────
async def send_home(r, ns, cid, uid, mid=0):
    user = await db_user(r, ns, uid)
    subscribed = is_sub(user)
    name = (user.get("cn") or user.get("fn") or "مستخدم") if user else "مستخدم"
    status = "✅ مشترك" if subscribed else "❌ غير مشترك"
    text = f"⚡ <b>{BOT_NAME}</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."
    kb = kb_main(subscribed)
    if mid:
        await edit_msg(cid, mid, text, kb)
    else:
        await send_msg(cid, text, kb)

# ─── معالجة التحديثات ──────────────────────────────────
async def handle_update(upd: dict):
    try:
        async with redis_client() as (r, ns):
            if "callback_query" in upd:
                await on_callback(r, ns, upd["callback_query"])
            elif "message" in upd:
                await on_message(r, ns, upd["message"])
    except Exception as e:
        logger.error(f"Update error: {e}\n{traceback.format_exc()}")

# ─── معالجة الضغط على الأزرار ─────────────────────────
async def on_callback(r, ns, cb):
    try:
        uid = cb["from"]["id"]
        cid = cb["message"]["chat"]["id"]
        mid = cb["message"]["message_id"]
        data = cb["data"]
        cbid = cb["id"]
        state = await db_state(r, ns, uid)
        current_state = state.get("st", "")

        # ----- الرئيسية -----
        if data == "home":
            await db_clear_state(r, ns, uid)
            await send_home(r, ns, cid, uid, mid)
            await answer_cb(cbid)
            return

        if data == "back":
            # رجوع للخطوة السابقة (حسب السياق)
            if current_state.startswith("ad_"):
                # نرجع خطوة واحدة
                steps = ["token", "account", "page", "objective", "image", "text", "target_country", "target_age", "target_gender", "budget", "days", "review", "status"]
                # نجد الخطوة الحالية ونرجع للتي قبلها
                for i, step in enumerate(steps):
                    if current_state == f"ad_{step}":
                        if i > 0:
                            prev = steps[i-1]
                            state["st"] = f"ad_{prev}"
                            await db_set_state(r, ns, uid, state)
                            await send_msg(cid, f"🔙 عدنا إلى خطوة {prev}", kb_back())
                            await answer_cb(cbid)
                            return
            await send_home(r, ns, cid, uid, mid)
            await answer_cb(cbid)
            return

        # ----- تفعيل كود -----
        if data == "redeem":
            await db_set_state(r, ns, uid, {"st": "redeem"})
            await edit_msg(cid, mid, "🎟 أرسل كود التفعيل:", kb_home())
            await answer_cb(cbid)
            return

        # ----- بدء إعلان جديد -----
        if data == "ad:start":
            user = await db_user(r, ns, uid)
            if not is_sub(user):
                await answer_cb(cbid, "❌ اشترك أولاً بكود Redeem", True)
                return
            # نطلب التوكن (إذا لم يكن محفوظاً)
            fb_token = user.get("fb_token", "")
            if fb_token:
                state["st"] = "ad_account"
                state["token"] = fb_token
                await db_set_state(r, ns, uid, state)
                await edit_msg(cid, mid, "✅ تم استخدام التوكن المحفوظ.\nأدخل Account ID (رقم الحساب الإعلاني):", kb_back())
            else:
                state["st"] = "ad_token"
                await db_set_state(r, ns, uid, state)
                await edit_msg(cid, mid, "🔑 أرسل Access Token الخاص بفيسبوك (طويل الصلاحية):", kb_back())
            await answer_cb(cbid)
            return

        # ----- اختيار الهدف (من الأزرار) -----
        if data.startswith("obj:") and current_state == "ad_objective":
            obj_key = data.split(":")[1]
            if obj_key not in OBJECTIVE_IDS:
                await answer_cb(cbid, "هدف غير صالح", True)
                return
            state["objective"] = obj_key
            state["st"] = "ad_image"
            await db_set_state(r, ns, uid, state)
            await edit_msg(cid, mid, f"✅ الهدف: {OBJECTIVES[obj_key]}\n\n📸 الآن أرسل الصورة (JPG/PNG):", kb_back())
            await answer_cb(cbid)
            return

        # ----- اختيار الجنس -----
        if data.startswith("gender:") and current_state == "ad_target_gender":
            gender = data.split(":")[1]
            state["gender"] = gender
            state["st"] = "ad_budget"
            await db_set_state(r, ns, uid, state)
            await edit_msg(cid, mid, f"✅ الجنس: {gender}\n\n💰 الآن أدخل الميزانية اليومية (بالدولار، مثال 10):", kb_back())
            await answer_cb(cbid)
            return

        # ----- تأكيد المراجعة -----
        if data == "confirm:yes" and current_state == "ad_review":
            state["st"] = "ad_status"
            await db_set_state(r, ns, uid, state)
            await edit_msg(cid, mid, "✅ تم التأكيد.\nاختر حالة التشغيل:", kb_ad_status())
            await answer_cb(cbid)
            return

        if data == "confirm:no" and current_state == "ad_review":
            await db_clear_state(r, ns, uid)
            await edit_msg(cid, mid, "❌ تم الإلغاء.", kb_home())
            await answer_cb(cbid)
            return

        # ----- اختيار حالة التشغيل (نشط/متوقف) -----
        if data.startswith("status:") and current_state == "ad_status":
            status = data.split(":")[1]
            if status not in ["ACTIVE", "PAUSED"]:
                await answer_cb(cbid, "حالة غير صالحة", True)
                return
            state["ad_status"] = status
            await db_set_state(r, ns, uid, state)

            # الآن نقوم بإنشاء الإعلان
            await edit_msg(cid, mid, "⏳ جاري إنشاء الإعلان...")
            try:
                result = await create_facebook_ad(r, ns, uid, state)
                if result["success"]:
                    # حفظ بيانات الإعلان
                    ad_data = {
                        "ad_id": result["ad_id"],
                        "campaign_id": result["campaign_id"],
                        "adset_id": result["adset_id"],
                        "status": status,
                        "created_at": now_iso(),
                        "details": {k: state.get(k) for k in ["objective", "daily_budget", "days", "target_country", "target_age", "gender"]}
                    }
                    await db_save_ad(r, ns, uid, ad_data)
                    # عرض رسالة النجاح مع أزرار التحكم
                    txt = (
                        f"✅ <b>تم إنشاء الإعلان بنجاح!</b>\n\n"
                        f"🆔 Ad ID: <code>{result['ad_id']}</code>\n"
                        f"📊 الحالة: {status}\n"
                        f"🎯 الهدف: {OBJECTIVES.get(state.get('objective'), '')}\n"
                        f"💰 الميزانية: {state.get('daily_budget')}$/يوم\n"
                        f"📅 المدة: {state.get('days')} أيام\n"
                        f"🌍 الدولة: {state.get('target_country')}\n"
                        f"👤 العمر: {state.get('target_age')}\n"
                        f"⚧ الجنس: {state.get('gender')}"
                    )
                    await edit_msg(cid, mid, txt, kb_ad_controls(result["ad_id"], status))
                    await db_clear_state(r, ns, uid)
                else:
                    await edit_msg(cid, mid, f"❌ فشل إنشاء الإعلان:\n{result['error']}", kb_home())
            except Exception as e:
                await edit_msg(cid, mid, f"❌ خطأ: {str(e)}", kb_home())
            await answer_cb(cbid)
            return

        # ----- التحكم بالإعلان (إيقاف/تشغيل) -----
        if data.startswith("ctrl:"):
            parts = data.split(":")
            if len(parts) != 3:
                await answer_cb(cbid, "بيانات غير صالحة", True)
                return
            action = parts[1]  # pause أو resume
            ad_id = parts[2]
            user = await db_user(r, ns, uid)
            token = user.get("fb_token", "")
            if not token:
                await answer_cb(cbid, "لا يوجد توكن مخزن", True)
                return
            new_status = "PAUSED" if action == "pause" else "ACTIVE"
            success = await fb_update_ad_status(token, ad_id, new_status)
            if success:
                # تحديث الحالة في قاعدة البيانات
                ad = await db_get_ad(r, ns, uid)
                if ad:
                    ad["status"] = new_status
                    await db_save_ad(r, ns, uid, ad)
                await edit_msg(cid, mid, f"✅ تم {'إيقاف' if action=='pause' else 'تشغيل'} الإعلان بنجاح.", kb_ad_controls(ad_id, new_status))
            else:
                await edit_msg(cid, mid, "❌ فشل تحديث حالة الإعلان.", kb_home())
            await answer_cb(cbid)
            return

        # ----- أوامر المشرف (مختصرة) -----
        if data.startswith("admin:"):
            await handle_admin_callback(r, ns, uid, cid, mid, cbid, data, state)
            return

        # أي callback غير معالج
        await answer_cb(cbid)

    except Exception as e:
        logger.error(f"Callback error: {e}\n{traceback.format_exc()}")
        try:
            await answer_cb(cbid, f"خطأ: {str(e)}", True)
        except:
            pass

# ─── دالة إنشاء الإعلان الفعلية ──────────────────────
async def create_facebook_ad(r, ns, uid, state) -> dict:
    """إنشاء حملة + مجموعة إعلانات + إعلان باستخدام البيانات في state"""
    try:
        token = state.get("token")
        account_id = state.get("account_id")
        page_id = state.get("page_id")
        objective = state.get("objective")
        image_id = state.get("image_id")
        message = state.get("ad_text")
        headline = state.get("headline")
        description = state.get("description")
        country = state.get("target_country")
        age_min, age_max = state.get("target_age").split("-")
        gender = state.get("gender")
        daily_budget = float(state.get("daily_budget"))
        days = int(state.get("days"))
        ad_status = state.get("ad_status")

        # إنشاء المنشور غير المنشور (Dark Post)
        dark_post_id = await fb_create_dark_post(token, page_id, image_id, message, headline, description)

        # إنشاء الحملة
        campaign_id = await fb_create_campaign(token, account_id, objective, "PAUSED")  # نبدأ موقوفة

        # إنشاء مجموعة إعلانات مع الاستهداف
        targeting = {
            "geo_locations": {"countries": [country]},
            "age_min": int(age_min),
            "age_max": int(age_max),
            "genders": [1] if gender == "male" else [2] if gender == "female" else [1, 2]
        }
        adset_id = await fb_create_adset(token, account_id, campaign_id, daily_budget, targeting, "PAUSED")

        # إنشاء الإعلان النهائي
        ad_id = await fb_create_ad(token, account_id, adset_id, dark_post_id, ad_status)

        return {
            "success": True,
            "ad_id": ad_id,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── معالجة الرسائل النصية والصور ──────────────────
async def on_message(r, ns, msg):
    try:
        uid = msg["from"]["id"]
        cid = msg["chat"]["id"]
        text = msg.get("text", "").strip()
        state = await db_state(r, ns, uid)
        current_state = state.get("st", "")
        user = await db_ensure_user(r, ns, uid, msg["from"].get("username", ""), msg["from"].get("first_name", ""))

        # ----- /start -----
        if text == "/start":
            if not user.get("joined"):
                await db_inc_stat(r, ns, "users")
            await db_clear_state(r, ns, uid)
            await send_home(r, ns, cid, uid)
            return

        # ----- /beshoy (لوحة المشرف) -----
        if text == f"/{ADMIN_CMD}":
            await db_set_state(r, ns, uid, {"st": "admin_pw"})
            await send_msg(cid, "🔐 أدخل كلمة المرور:", kb_home())
            return

        # ----- كود التفعيل -----
        if current_state == "redeem":
            hours = await db_use_code(r, ns, text, uid)
            if not hours:
                await send_msg(cid, "❌ كود غير صالح أو مستخدم", kb_home())
                return
            until = await db_set_sub(r, ns, uid, hours)
            await db_clear_state(r, ns, uid)
            user = await db_user(r, ns, uid)
            await send_msg(cid, f"✅ تم التفعيل حتى: {until}", kb_main(is_sub(user)))
            return

        # ----- إدخال Access Token -----
        if current_state == "ad_token":
            # نتحقق من صحة التوكن
            try:
                info = await fb_check_token(text)
                if "id" not in info:
                    await send_msg(cid, f"❌ التوكن غير صالح: {info.get('error', {}).get('message', 'خطأ')}", kb_home())
                    return
                # حفظ التوكن في user
                user["fb_token"] = text
                await db_save_user(r, ns, uid, user)
                state["token"] = text
                state["st"] = "ad_account"
                await db_set_state(r, ns, uid, state)
                await send_msg(cid, "✅ تم التحقق من التوكن.\nأدخل Account ID (رقم الحساب الإعلاني):", kb_back())
            except Exception as e:
                await send_msg(cid, f"❌ فشل التحقق: {str(e)}", kb_home())
            return

        # ----- Account ID -----
        if current_state == "ad_account":
            if not re.match(r'^\d{10,20}$', text):
                await send_msg(cid, "❌ Account ID يجب أن يكون 10-20 رقماً", kb_home())
                return
            state["account_id"] = text
            state["st"] = "ad_page"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ تم حفظ Account ID.\nأدخل Page ID (معرف الصفحة):", kb_back())
            return

        # ----- Page ID -----
        if current_state == "ad_page":
            if not re.match(r'^\d+$', text):
                await send_msg(cid, "❌ Page ID يجب أن يكون أرقاماً فقط", kb_home())
                return
            state["page_id"] = text
            state["st"] = "ad_objective"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ تم حفظ Page ID.\nاختر هدف الإعلان:", kb_objectives())
            return

        # ----- استقبال الصورة -----
        if current_state == "ad_image":
            if "photo" not in msg:
                await send_msg(cid, "❌ أرسل صورة (JPG أو PNG).", kb_back())
                return
            # تحميل الصورة من تيليجرام
            photo = msg["photo"][-1]
            file_id = photo["file_id"]
            # نستخدم getFile لتحميل الملف
            file_info = await tg("getFile", {"file_id": file_id})
            if not file_info.get("ok"):
                await send_msg(cid, "❌ فشل تحميل الصورة", kb_home())
                return
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
            async with httpx.AsyncClient() as c:
                resp = await c.get(file_url)
                if resp.status_code != 200:
                    await send_msg(cid, "❌ فشل تنزيل الصورة", kb_home())
                    return
                image_bytes = resp.content

            # رفع الصورة إلى فيسبوك
            try:
                image_id = await fb_upload_image(state["token"], state["page_id"], image_bytes)
                state["image_id"] = image_id
                state["st"] = "ad_text"
                await db_set_state(r, ns, uid, state)
                await send_msg(cid, "✅ تم رفع الصورة.\nالآن أرسل النص الأساسي للإعلان (Primary Text):", kb_back())
            except Exception as e:
                await send_msg(cid, f"❌ فشل رفع الصورة: {str(e)}", kb_home())
            return

        # ----- نص الإعلان -----
        if current_state == "ad_text":
            if len(text) < 5:
                await send_msg(cid, "❌ النص قصير جداً (على الأقل 5 أحرف)", kb_back())
                return
            state["ad_text"] = text
            state["st"] = "ad_headline"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ تم حفظ النص.\nأرسل العنوان الرئيسي (Headline) أو اكتب 'تخطي':", kb_back())
            return

        # ----- Headline و Description -----
        if current_state == "ad_headline":
            if text.lower() != "تخطي":
                state["headline"] = text
                state["st"] = "ad_description"
                await db_set_state(r, ns, uid, state)
                await send_msg(cid, "✅ تم حفظ العنوان.\nأرسل وصف إضافي (Description) أو 'تخطي':", kb_back())
            else:
                state["headline"] = ""
                state["st"] = "ad_target_country"
                await db_set_state(r, ns, uid, state)
                await send_msg(cid, "✅ تم التخطي.\nأدخل الدولة المستهدفة (رمز الدولة، مثل: EG, US, SA):", kb_back())
            return

        if current_state == "ad_description":
            if text.lower() != "تخطي":
                state["description"] = text
            else:
                state["description"] = ""
            state["st"] = "ad_target_country"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ تم.\nأدخل الدولة المستهدفة (رمز الدولة، مثل: EG, US, SA):", kb_back())
            return

        # ----- الدولة -----
        if current_state == "ad_target_country":
            if len(text) != 2 or not text.isalpha():
                await send_msg(cid, "❌ رمز الدولة يجب أن يكون حرفين (مثل EG)", kb_back())
                return
            state["target_country"] = text.upper()
            state["st"] = "ad_target_age"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ الدولة: " + text.upper() + "\nأدخل الفئة العمرية (مثال: 18-65):", kb_back())
            return

        # ----- العمر -----
        if current_state == "ad_target_age":
            if not re.match(r'^\d{1,2}-\d{1,2}$', text):
                await send_msg(cid, "❌ الصيغة غير صحيحة. استخدم 18-65 مثلاً.", kb_back())
                return
            ages = text.split("-")
            if int(ages[0]) < 13 or int(ages[1]) > 65 or int(ages[0]) >= int(ages[1]):
                await send_msg(cid, "❌ عمر غير صحيح (13-65)", kb_back())
                return
            state["target_age"] = text
            state["st"] = "ad_target_gender"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, "✅ العمر: " + text + "\nاختر الجنس:", kb_gender())
            return

        # ----- الميزانية -----
        if current_state == "ad_budget":
            try:
                budget = float(text)
                if budget < 1 or budget > 10000:
                    raise ValueError
            except:
                await send_msg(cid, "❌ الميزانية يجب أن تكون رقماً بين 1 و 10000", kb_back())
                return
            state["daily_budget"] = budget
            state["st"] = "ad_days"
            await db_set_state(r, ns, uid, state)
            await send_msg(cid, f"✅ الميزانية: {budget}$/يوم\nأدخل عدد الأيام (1-365):", kb_back())
            return

        # ----- عدد الأيام -----
        if current_state == "ad_days":
            try:
                days = int(text)
                if days < 1 or days > 365:
                    raise ValueError
            except:
                await send_msg(cid, "❌ يجب أن يكون عدد الأيام بين 1 و 365", kb_back())
                return
            state["days"] = days
            state["st"] = "ad_review"
            await db_set_state(r, ns, uid, state)

            # عرض مراجعة
            review = (
                f"📋 <b>مراجعة البيانات</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔑 التوكن: {state.get('token', '')[:10]}...\n"
                f"🆔 Account: {state.get('account_id')}\n"
                f"📄 Page: {state.get('page_id')}\n"
                f"🎯 الهدف: {OBJECTIVES.get(state.get('objective'), '')}\n"
                f"🖼 الصورة: تم رفعها\n"
                f"📝 النص: {state.get('ad_text', '')[:30]}...\n"
                f"📌 العنوان: {state.get('headline', 'بدون')}\n"
                f"🌍 الدولة: {state.get('target_country')}\n"
                f"👤 العمر: {state.get('target_age')}\n"
                f"⚧ الجنس: {state.get('gender')}\n"
                f"💰 الميزانية: {state.get('daily_budget')}$/يوم\n"
                f"📅 المدة: {days} أيام\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"هل البيانات صحيحة؟"
            )
            await send_msg(cid, review, kb_confirm())
            return

        # ----- كلمة مرور المشرف -----
        if current_state == "admin_pw":
            if text != ADMIN_PASS:
                await send_msg(cid, "❌ كلمة مرور خاطئة", kb_home())
                return
            await db_clear_state(r, ns, uid)
            await send_msg(cid, "✅ مرحباً مشرف!", kb_admin())
            return

        # ----- أوامر المشرف النصية -----
        if current_state.startswith("admin_"):
            await handle_admin_message(r, ns, uid, cid, text, state)
            return

        # أي رسالة أخرى → الرئيسية
        await send_home(r, ns, cid, uid)

    except Exception as e:
        logger.error(f"Message error: {e}\n{traceback.format_exc()}")
        try:
            await send_msg(cid, f"❌ خطأ: {str(e)}", kb_home())
        except:
            pass

# ─── دوال المشرف (مختصرة) ──────────────────────────
async def handle_admin_callback(r, ns, uid, cid, mid, cbid, data, state):
    # فقط استجابة سريعة للأزرار (تطوير لاحق)
    await answer_cb(cbid, "جاري التطوير...", False)

async def handle_admin_message(r, ns, uid, cid, text, state):
    # تطوير لاحق
    await send_msg(cid, "وظيفة المشرف قيد التطوير", kb_admin())

# ─── نقاط نهاية FastAPI ──────────────────────────────
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
    if not TOKEN:
        return SetupRes(success=False, message="TELEGRAM_BOT_TOKEN not set")
    if req.webhook_url:
        r = await tg("setWebhook", {"url": req.webhook_url})
        return SetupRes(success=r.get("ok", False), message=str(r.get("description", "")), bot_info=r)
    r = await tg("deleteWebhook", {})
    info = await tg("getMe", {})
    return SetupRes(success=r.get("ok", False), message="Webhook removed", bot_info=info.get("result", {}))

if __name__ == "__main__":
    run_service(app)
