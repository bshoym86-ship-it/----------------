"""
BESHOY BOT - النسخة الكاملة
aiogram 3.20+ + JSON (بدون Redis)
مع أزرار ملوّنة (Bot API 9.4)
"""
import os
import json
import secrets
import string
import logging
import aiohttp
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── الإعدادات ───────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "Nemo@1986")
SUPPORT_URL = os.environ.get("SUPPORT_URL", "https://t.me/your_support")
DATA_FILE = "data.json"
FB_API = "https://graph.facebook.com/v18.0"

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN مش متظبط!")

if ADMIN_PASS == "Nemo@1986":
    logger.warning("⚠️ غيّر ADMIN_PASS من متغيرات البيئة!")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ─── قاعدة البيانات (ملف JSON) ───────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "codes": {}, "proxies": [], "stats": {"users": 0, "requests": 0}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "codes": {}, "proxies": [], "stats": {"users": 0, "requests": 0}}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=2)

DB = load_data()

# ─── States ──────────────────────────────────────────────
class AdStates(StatesGroup):
    waiting_token = State()
    waiting_account_id = State()
    waiting_page_id = State()
    waiting_objective = State()
    waiting_image = State()
    waiting_message = State()
    waiting_country = State()
    waiting_age = State()
    waiting_post_id = State()
    waiting_event_name = State()
    waiting_event_desc = State()
    waiting_event_start = State()
    waiting_event_end = State()
    waiting_budget = State()
    waiting_days = State()
    waiting_proxy_choice = State()
    waiting_proxy_manual = State()
    waiting_ad_status = State()
    waiting_redeem_code = State()
    waiting_admin_password = State()
    waiting_admin_gen_code = State()
    waiting_admin_set_user = State()
    waiting_admin_remove_user = State()
    waiting_admin_broadcast = State()
    waiting_admin_add_proxies = State()

# ─── دوال مساعدة ─────────────────────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def gen_code():
    chars = string.ascii_uppercase + string.digits
    return f"BM-{''.join(secrets.choice(chars) for _ in range(12))}"

def is_sub(uid: int) -> bool:
    user = DB["users"].get(str(uid))
    if not user or user.get("removed"):
        return False
    sub = user.get("sub", "")
    if not sub:
        return False
    try:
        return datetime.fromisoformat(sub) > datetime.now(timezone.utc)
    except:
        return False

def ensure_user(uid: int, username: str = "", first_name: str = ""):
    uid_str = str(uid)
    if uid_str not in DB["users"]:
        DB["users"][uid_str] = {
            "uid": uid, "un": username, "fn": first_name,
            "joined": now_iso(), "removed": False, "sub": ""
        }
        DB["stats"]["users"] = DB["stats"].get("users", 0) + 1
        save_data()
    else:
        DB["users"][uid_str]["un"] = username
        DB["users"][uid_str]["fn"] = first_name
        save_data()
    return DB["users"][uid_str]

def parse_proxy(proxy_str: str) -> dict:
    """معالجة البروكسي بجميع الأشكال"""
    proxy_str = proxy_str.strip()
    if proxy_str.count(":") == 3:
        parts = proxy_str.split(":")
        return {
            "http": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}",
            "https": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        }
    elif proxy_str.count(":") == 1:
        parts = proxy_str.split(":")
        return {
            "http": f"http://{parts[0]}:{parts[1]}",
            "https": f"http://{parts[0]}:{parts[1]}"
        }
    elif "@" in proxy_str:
        return {
            "http": f"http://{proxy_str}",
            "https": f"http://{proxy_str}"
        }
    elif proxy_str.startswith("http"):
        return {
            "http": proxy_str,
            "https": proxy_str
        }
    return None

def get_random_proxy() -> dict:
    """الحصول على بروكسي عشوائي من القائمة"""
    if not DB.get("proxies"):
        return None
    proxy_str = secrets.choice(DB["proxies"])
    return parse_proxy(proxy_str)

# ─── دالة الأزرار (Bot API 9.4 - القيم الصحيحة فقط) ──────
# القيم الصحيحة: "primary" (أزرق) | "success" (أخضر) | "danger" (أحمر)
# "secondary" غير موجودة في Telegram API وتسبب خطأ
def _btn(text: str, *,
         callback_data: Optional[str] = None,
         url: Optional[str] = None,
         style: Optional[str] = None) -> InlineKeyboardButton:
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    # فقط القيم الصحيحة المدعومة من Telegram
    if style in ("primary", "success", "danger"):
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

# ─── لوحات المفاتيح ──────────────────────────────────────
def kb_main(subscribed: bool):
    rows = []
    if subscribed:
        rows.append([_btn("🚀 إعلان جديد", callback_data="ad:start", style="primary")])
    rows.append([
        _btn("🎟 تفعيل كود", callback_data="redeem", style="success"),
        _btn("🛠 دعم", url=SUPPORT_URL)          # بدون style لأن "secondary" غير صالحة
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_gates():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🌑 Dark Post", callback_data="gate:dark_post", style="primary"),
         _btn("🚀 Boost Post", callback_data="gate:boost_post", style="primary")],
        [_btn("👍 Page Like", callback_data="gate:page_like", style="primary"),
         _btn("🤝 Partner Ship", callback_data="gate:partner_ship", style="primary")],
        [_btn("🎪 Event Campaign", callback_data="gate:event", style="primary")],
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_objective():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("👍 تفاعل المنشور", callback_data="obj:POST_ENGAGEMENT", style="success")],
        [_btn("👁 الوصول", callback_data="obj:REACH", style="success")],
        [_btn("👥 زيارات الصفحة", callback_data="obj:PAGE_LIKES", style="success")],
        [_btn("🔗 النقرات على الرابط", callback_data="obj:LINK_CLICKS", style="success")],
        [_btn("📹 مشاهدات الفيديو", callback_data="obj:VIDEO_VIEWS", style="success")],
        [_btn("💬 رسائل", callback_data="obj:CONVERSATIONS", style="success")],
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_proxy_choice():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔄 تلقائي من البوت", callback_data="proxy:auto", style="primary")],
        [_btn("✋ إدخال يدوي", callback_data="proxy:manual", style="primary")],
        [_btn("❌ بدون بروكسي", callback_data="proxy:none")],   # بدون style
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_ad_status():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("▶️ نشط (ACTIVE)", callback_data="status:ACTIVE", style="success")],
        [_btn("⏸ متوقف (PAUSED)", callback_data="status:PAUSED")],  # بدون style
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_gender():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("👨 ذكر", callback_data="gender:male", style="primary"),
         _btn("👩 أنثى", callback_data="gender:female", style="primary")],
        [_btn("👫 الكل", callback_data="gender:all", style="primary")],
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ تأكيد", callback_data="confirm:yes", style="success"),
         _btn("❌ إلغاء", callback_data="confirm:no", style="danger")],
        [_btn("🏠 الرئيسية", callback_data="home")]   # بدون style
    ])

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔙 رجوع", callback_data="back")],      # بدون style
        [_btn("🏠 الرئيسية", callback_data="home", style="danger")]
    ])

def kb_home():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🏠 الرئيسية", callback_data="home")]   # بدون style
    ])

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🎟 توليد كود", callback_data="admin:gen_code", style="primary"),
         _btn("👤 تمديد مشترك", callback_data="admin:set_user", style="primary")],
        [_btn("🗑 حذف مشترك", callback_data="admin:remove_user", style="primary"),
         _btn("📢 رسالة جماعية", callback_data="admin:broadcast", style="primary")],
        [_btn("🌐 إضافة بروكسيات", callback_data="admin:add_proxies", style="primary"),
         _btn("📊 الإحصائيات", callback_data="admin:stats", style="primary")],
        [_btn("🏠 خروج", callback_data="home", style="danger")]
    ])

# ─── Facebook API ────────────────────────────────────────
def fb_error_detail(result: dict) -> str:
    """يرجع أوضح رسالة خطأ ممكنة من رد فيسبوك (فيسبوك بيدي تفاصيل أكتر في
    error_user_msg/error_subcode غالبًا بيتجاهلها لو اعتمدنا على message بس)."""
    err = result.get("error", {})
    if isinstance(err, str):
        return err if err else "Unknown error"
    if not isinstance(err, dict):
        return str(err) if err else "Unknown error"
    parts = []
    if err.get("message"):
        parts.append(err["message"])
    if err.get("error_user_title"):
        parts.append(f"({err['error_user_title']})")
    if err.get("error_user_msg"):
        parts.append(err["error_user_msg"])
    if err.get("error_subcode"):
        parts.append(f"[subcode: {err['error_subcode']}]")
    return " | ".join(parts) if parts else "Unknown error"

async def fb_request(method: str, endpoint: str, data: dict = None, proxy: dict = None) -> dict:
    url = f"{FB_API}/{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            if method == "GET":
                async with session.get(url, params=data, timeout=15, proxy=proxy.get("http") if proxy else None) as resp:
                    return await resp.json()
            else:
                async with session.post(url, data=data, timeout=30, proxy=proxy.get("http") if proxy else None) as resp:
                    return await resp.json()
        except Exception as e:
            return {"error": {"message": str(e)}}

async def fb_check_token(token: str, proxy: dict = None) -> dict:
    return await fb_request("GET", "me", {"access_token": token, "fields": "id,name"}, proxy)

async def fb_get_page_token(user_token: str, page_id: str, proxy: dict = None) -> dict:
    url = f"{FB_API}/{page_id}"
    params = {
        "fields": "access_token",
        "access_token": user_token
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=15, proxy=proxy.get("http") if proxy else None) as resp:
                result = await resp.json()
                if "access_token" in result:
                    return {"ok": True, "page_token": result["access_token"]}
                return {"ok": False, "error": result.get("error", {}).get("message", "Unknown")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

async def fb_upload_image(token: str, page_id: str, image_bytes: bytes, proxy: dict = None) -> dict:
    url = f"{FB_API}/{page_id}/photos"
    data = {"access_token": token, "published": "false"}
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("source", image_bytes, filename="image.jpg", content_type="image/jpeg")
            for k, v in data.items():
                form.add_field(k, v)
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=30),
                                     proxy=proxy.get("http") if proxy else None) as resp:
                status = resp.status
                try:
                    result = await resp.json()
                except Exception:
                    # الرد مش JSON (صفحة خطأ من البروكسي مثلاً) - نطبع الراو تيكست عشان نشوف السبب
                    raw_text = await resp.text()
                    return {"ok": False, "error": f"HTTP {status} - رد غير متوقع: {raw_text[:200]}"}

                if "id" in result:
                    return {"ok": True, "id": result["id"]}

                return {"ok": False, "error": fb_error_detail(result) if "error" in result else f"HTTP {status} - رد بدون id: {str(result)[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)}"}

async def fb_create_dark_post(token: str, page_id: str, image_id: str, message: str, link: str = "", proxy: dict = None) -> dict:
    data = {
        "access_token": token, "message": message,
        "attached_media": f'[{{"media_fbid": "{image_id}"}}]',
        "published": "false"
    }
    if link:
        data["link"] = link
    result = await fb_request("POST", f"{page_id}/feed", data, proxy)
    return {"ok": "id" in result, "id": result.get("id"), "error": fb_error_detail(result) if "error" in result else ""}

# فيسبوك أوقف قبول الـ legacy objectives على حسابات ODAX (من 2022 بيتفعل تدريجيًا
# على كل الحسابات). الماب ده بيحول كل هدف قديم لـ:
#   1) outcome objective اللي يتبعت لـ /campaigns
#   2) optimization_goal الصحيح اللي يتبعت لـ /adsets (مختلف عن الـ objective نفسه!)
OBJECTIVE_MAP = {
    "POST_ENGAGEMENT":  {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "POST_ENGAGEMENT"},
    "PAGE_LIKES":       {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "PAGE_LIKES"},
    "REACH":            {"outcome": "OUTCOME_AWARENESS",  "opt_goal": "REACH"},
    "BRAND_AWARENESS":  {"outcome": "OUTCOME_AWARENESS",  "opt_goal": "AD_RECALL_LIFT"},
    "LINK_CLICKS":      {"outcome": "OUTCOME_TRAFFIC",    "opt_goal": "LINK_CLICKS"},
    "VIDEO_VIEWS":      {"outcome": "OUTCOME_AWARENESS",  "opt_goal": "THRUPLAY"},
    "CONVERSATIONS":    {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "CONVERSATIONS"},
    "MESSAGES":         {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "CONVERSATIONS"},
    "LEAD_GENERATION":  {"outcome": "OUTCOME_LEADS",      "opt_goal": "LEAD_GENERATION"},
    "CONVERSIONS":      {"outcome": "OUTCOME_SALES",      "opt_goal": "OFFSITE_CONVERSIONS"},
    "APP_INSTALLS":     {"outcome": "OUTCOME_APP_PROMOTION", "opt_goal": "APP_INSTALLS"},
    "EVENT_RESPONSES":  {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "EVENT_RESPONSES"},
}

def resolve_objective(legacy_objective: str) -> dict:
    """يرجع dict فيه outcome objective + optimization goal الصحيحين، مع fallback أمان."""
    mapped = OBJECTIVE_MAP.get(legacy_objective)
    if mapped:
        return mapped
    return {"outcome": "OUTCOME_ENGAGEMENT", "opt_goal": "POST_ENGAGEMENT"}

async def fb_create_campaign(token: str, acc_id: str, objective: str, budget: float, proxy: dict = None,
                              special_ad_categories: list = None) -> dict:
    resolved = resolve_objective(objective)
    data = {
        "access_token": token,
        "name": f"Boost_{int(datetime.now().timestamp())}",
        "objective": resolved["outcome"],
        "status": "PAUSED",
        # daily_budget اتشالت من هنا عمدًا: لما تتحدد ميزانية على الكامبين، فيسبوك بيحوّله
        # تلقائيًا لـ Campaign Budget Optimization (CBO)، وفي الحالة دي مفيش لازمة (وممنوع)
        # تحدد bid_strategy على مستوى الأدسيت - وده اللي كان بيخلي فيسبوك يرجع لـ
        # LOWEST_COST_WITH_BID_CAP الافتراضي ويطلب bid_amount. الميزانية والـ bid_strategy
        # دلوقتي على مستوى الأدسيت بس (Ad Set Budget Optimization - ABO).
        "special_ad_categories": json.dumps(special_ad_categories if special_ad_categories else []),
        # مطلوب صراحة لما الميزانية على مستوى الأدسيت (ABO) مش الكامبين. False يعني كل
        # أدسيت بميزانيته المحددة بدون مشاركة 20% بين الأدسيتس.
        "is_adset_budget_sharing_enabled": "false"
    }
    result = await fb_request("POST", f"act_{acc_id}/campaigns", data, proxy)
    return {"ok": "id" in result, "id": result.get("id"), "error": fb_error_detail(result) if "error" in result else ""}

async def fb_create_adset(token: str, acc_id: str, camp_id: str, budget: float, targeting: dict, opt_goal: str = "REACH", proxy: dict = None) -> dict:
    data = {
        "access_token": token,
        "name": f"AdSet_{int(datetime.now().timestamp())}",
        "campaign_id": camp_id, "daily_budget": int(budget * 100),
        "targeting": json.dumps(targeting), "status": "PAUSED",
        "billing_event": "IMPRESSIONS", "optimization_goal": opt_goal,
        # من غير bid_strategy صريحة، فيسبوك بيرجع لـ LOWEST_COST_WITH_BID_CAP اللي بيطلب
        # bid_amount إلزامي. الإستراتيجية دي تخلي فيسبوك يدير المزايدة أوتوماتيك من غير سقف.
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP"
    }
    result = await fb_request("POST", f"act_{acc_id}/adsets", data, proxy)
    return {"ok": "id" in result, "id": result.get("id"), "error": fb_error_detail(result) if "error" in result else ""}

async def fb_create_ad(token: str, acc_id: str, adset_id: str, creative: dict, status: str = "ACTIVE", proxy: dict = None) -> dict:
    data = {
        "access_token": token,
        "name": f"Ad_{int(datetime.now().timestamp())}",
        "adset_id": adset_id, "creative": json.dumps(creative), "status": status
    }
    result = await fb_request("POST", f"act_{acc_id}/ads", data, proxy)
    return {"ok": "id" in result, "id": result.get("id"), "error": fb_error_detail(result) if "error" in result else ""}

async def fb_update_ad_status(token: str, ad_id: str, status: str, proxy: dict = None) -> dict:
    data = {
        "access_token": token,
        "ad_status": status
    }
    result = await fb_request("POST", ad_id, data, proxy)
    return {"ok": "id" in result, "error": result.get("error", {}).get("message", "")}

# ─── Handlers ────────────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    ensure_user(uid, username, first_name)

    subscribed = is_sub(uid)
    name = first_name or "مستخدم"
    status = "✅ مشترك" if subscribed else "❌ غير مشترك"
    text = f"⚡ <b>🚀 BESHOY BOOST BOT</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."

    await message.answer(text, reply_markup=kb_main(subscribed), parse_mode="HTML")

@router.message(Command("beshoy"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.set_state(AdStates.waiting_admin_password)
    await message.answer("🔐 أدخل كلمة المرور:", reply_markup=kb_home())

@router.message(AdStates.waiting_admin_password)
async def process_admin_password(message: Message, state: FSMContext):
    if message.text == ADMIN_PASS:
        await state.clear()
        await message.answer("✅ مرحباً مشرف!", reply_markup=kb_admin())
    else:
        await state.clear()
        await message.answer("❌ كلمة مرور خاطئة", reply_markup=kb_home())

@router.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    subscribed = is_sub(uid)
    name = callback.from_user.first_name or "مستخدم"
    status = "✅ مشترك" if subscribed else "❌ غير مشترك"
    text = f"⚡ <b>🚀 BESHOY BOOST BOT</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."

    await callback.message.edit_text(text, reply_markup=kb_main(subscribed), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 عدت للرئيسية", reply_markup=kb_home())
    await callback.answer()

@router.callback_query(F.data == "redeem")
async def cb_redeem(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdStates.waiting_redeem_code)
    await callback.message.edit_text("🎟 أرسل كود التفعيل:", reply_markup=kb_home())
    await callback.answer()

@router.message(AdStates.waiting_redeem_code)
async def process_redeem_code(message: Message, state: FSMContext):
    code = message.text.strip()
    code_data = DB["codes"].get(code)

    if not code_data or code_data.get("used_by"):
        await state.clear()
        await message.answer("❌ كود غير صالح أو مستخدم", reply_markup=kb_home())
        return

    hours = int(code_data["hours"])
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")

    uid_str = str(message.from_user.id)

    if uid_str not in DB["users"]:
        DB["users"][uid_str] = {
            "uid": message.from_user.id,
            "un": message.from_user.username or "",
            "fn": message.from_user.first_name or "",
            "joined": now_iso(),
            "removed": False,
            "sub": ""
        }
        DB["stats"]["users"] = DB["stats"].get("users", 0) + 1

    DB["users"][uid_str]["sub"] = until
    DB["users"][uid_str]["removed"] = False
    DB["codes"][code]["used_by"] = message.from_user.id
    DB["codes"][code]["used_at"] = now_iso()
    save_data()

    await state.clear()
    subscribed = is_sub(message.from_user.id)
    await message.answer(f"✅ تم التفعيل حتى: {until}", reply_markup=kb_main(subscribed))

@router.callback_query(F.data == "ad:start")
async def cb_ad_start(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_sub(uid):
        await callback.answer("❌ اشترك أولاً بكود Redeem", show_alert=True)
        return

    await callback.message.edit_text("🚀 اختر البوابة الإعلانية:", reply_markup=kb_gates())
    await callback.answer()

@router.callback_query(F.data.startswith("gate:"))
async def cb_gate(callback: CallbackQuery, state: FSMContext):
    gate = callback.data.split(":")[1]
    await state.update_data(gate=gate)
    await state.set_state(AdStates.waiting_token)
    await callback.message.edit_text("🔑 أرسل Access Token الخاص بفيسبوك:", reply_markup=kb_back())
    await callback.answer()

@router.message(AdStates.waiting_token)
async def process_token(message: Message, state: FSMContext):
    token = message.text.strip()
    data = await state.get_data()
    proxy = data.get("proxy")

    info = await fb_check_token(token, proxy)

    if "id" not in info:
        await state.clear()
        await message.answer(f"❌ التوكن غير صالح: {info.get('error', {}).get('message', '')}", reply_markup=kb_home())
        return

    await state.update_data(token=token)
    await state.set_state(AdStates.waiting_account_id)
    await message.answer("✅ تم التحقق من التوكن.\n🆔 أدخل Account ID:", reply_markup=kb_back())

@router.message(AdStates.waiting_account_id)
async def process_account_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or len(text) < 10 or len(text) > 20:
        await message.answer("❌ Account ID غير صحيح (10-20 رقم)", reply_markup=kb_back())
        return

    await state.update_data(account_id=text)
    await state.set_state(AdStates.waiting_page_id)
    await message.answer("✅ تم حفظ Account ID.\n📄 أدخل Page ID:", reply_markup=kb_back())

@router.message(AdStates.waiting_page_id)
async def process_page_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Page ID غير صحيح", reply_markup=kb_back())
        return

    await state.update_data(page_id=text)

    data = await state.get_data()
    proxy = data.get("proxy")
    user_token = data.get("token")
    page_result = await fb_get_page_token(user_token, text, proxy)

    if page_result.get("ok"):
        await state.update_data(token=page_result["page_token"])
    else:
        await message.answer(
            f"⚠️ فشل الحصول على Page Token: {page_result.get('error')}\n"
            "تأكد أن التوكن لديه صلاحية pages_manage_posts"
        )
        return

    await state.set_state(AdStates.waiting_objective)
    await message.answer("🎯 اختر هدف الإعلان:", reply_markup=kb_objective())

@router.callback_query(F.data.startswith("obj:"))
async def cb_objective(callback: CallbackQuery, state: FSMContext):
    objective = callback.data.split(":")[1]
    await state.update_data(objective=objective)

    obj_names = {
        "POST_ENGAGEMENT": "👍 تفاعل المنشور",
        "REACH": "👁 الوصول",
        "PAGE_LIKES": "👥 زيارات الصفحة",
        "LINK_CLICKS": "🔗 النقرات على الرابط",
        "VIDEO_VIEWS": "📹 مشاهدات الفيديو",
        "CONVERSATIONS": "💬 رسائل"
    }
    obj_name = obj_names.get(objective, objective)

    await state.set_state(AdStates.waiting_proxy_choice)
    await callback.message.edit_text(f"✅ الهدف: {obj_name}\n\n🌐 اختر طريقة استخدام البروكسي:", reply_markup=kb_proxy_choice())
    await callback.answer()

@router.callback_query(F.data.startswith("proxy:"))
async def cb_proxy_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]

    if choice == "auto":
        proxy = get_random_proxy()
        if proxy:
            await state.update_data(proxy=proxy)
            await callback.message.edit_text("✅ تم اختيار بروكسي تلقائي من البوت", reply_markup=kb_back())
        else:
            await callback.message.edit_text("⚠️ لا توجد بروكسيات متاحة، سيتم المتابعة بدون بروكسي", reply_markup=kb_back())
    elif choice == "manual":
        await state.set_state(AdStates.waiting_proxy_manual)
        await callback.message.edit_text("✋ أرسل البروكسي:\n\nالصيغ المدعومة:\n• ip:port\n• ip:port:user:pass\n• user:pass@ip:port\n• http://ip:port", reply_markup=kb_back())
        await callback.answer()
        return
    elif choice == "none":
        await state.update_data(proxy=None)
        await callback.message.edit_text("✅ سيتم المتابعة بدون بروكسي", reply_markup=kb_back())

    data = await state.get_data()
    gate = data.get("gate")

    if gate == "dark_post":
        await state.set_state(AdStates.waiting_image)
        await callback.message.edit_text("📸 أرسل الصورة:", reply_markup=kb_back())
    elif gate == "boost_post":
        await state.set_state(AdStates.waiting_post_id)
        await callback.message.edit_text("📝 أدخل Post ID:", reply_markup=kb_back())
    elif gate == "page_like":
        await state.set_state(AdStates.waiting_budget)
        await callback.message.edit_text("💰 أدخل الميزانية اليومية ($):", reply_markup=kb_back())
    elif gate == "event":
        await state.set_state(AdStates.waiting_event_name)
        await callback.message.edit_text("🎪 أدخل اسم الحدث:", reply_markup=kb_back())

    await callback.answer()

@router.message(AdStates.waiting_proxy_manual)
async def process_proxy_manual(message: Message, state: FSMContext):
    proxy_str = message.text.strip()
    proxy = parse_proxy(proxy_str)

    if not proxy:
        await message.answer("❌ صيغة البروكسي غير صحيحة", reply_markup=kb_back())
        return

    await state.update_data(proxy=proxy)

    data = await state.get_data()
    gate = data.get("gate")

    if gate == "dark_post":
        await state.set_state(AdStates.waiting_image)
        await message.answer("✅ تم حفظ البروكسي.\n📸 أرسل الصورة:", reply_markup=kb_back())
    elif gate == "boost_post":
        await state.set_state(AdStates.waiting_post_id)
        await message.answer("✅ تم حفظ البروكسي.\n📝 أدخل Post ID:", reply_markup=kb_back())
    elif gate == "page_like":
        await state.set_state(AdStates.waiting_budget)
        await message.answer("✅ تم حفظ البروكسي.\n💰 أدخل الميزانية اليومية ($):", reply_markup=kb_back())
    elif gate == "event":
        await state.set_state(AdStates.waiting_event_name)
        await message.answer("✅ تم حفظ البروكسي.\n🎪 أدخل اسم الحدث:", reply_markup=kb_back())

@router.message(AdStates.waiting_image)
async def process_image(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ أرسل صورة (JPG أو PNG).", reply_markup=kb_back())
        return

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                image_bytes = await resp.read()
    except Exception as e:
        await message.answer(f"❌ فشل تحميل الصورة من تيليجرام: {type(e).__name__}: {str(e)}", reply_markup=kb_home())
        return

    data = await state.get_data()
    proxy = data.get("proxy")
    result = await fb_upload_image(data["token"], data["page_id"], image_bytes, proxy)

    if not result.get("ok"):
        err_msg = result.get('error') or "خطأ غير معروف (تحقق من صلاحية التوكن أو إعدادات البروكسي)"
        await message.answer(f"❌ فشل رفع الصورة: {err_msg}", reply_markup=kb_home())
        return

    await state.update_data(image_id=result["id"])
    await state.set_state(AdStates.waiting_message)
    await message.answer("✅ تم رفع الصورة.\n💬 أرسل النص الأساسي للإعلان:", reply_markup=kb_back())

@router.message(AdStates.waiting_message)
async def process_message_text(message: Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ النص قصير جداً (على الأقل 5 أحرف)", reply_markup=kb_back())
        return

    await state.update_data(message=message.text)
    await state.update_data(link="")
    await state.set_state(AdStates.waiting_country)
    await message.answer("✅ تم حفظ النص.\n🌍 أدخل الدولة المستهدفة (مثل: EG, US, SA):", reply_markup=kb_back())

@router.message(AdStates.waiting_country)
async def process_country(message: Message, state: FSMContext):
    text = message.text.strip().upper()
    if len(text) != 2 or not text.isalpha():
        await message.answer("❌ رمز الدولة يجب أن يكون حرفين (مثل EG)", reply_markup=kb_back())
        return

    await state.update_data(country=text)
    await state.set_state(AdStates.waiting_age)
    await message.answer(f"✅ الدولة: {text}\n👤 أدخل الفئة العمرية (مثال: 18-65):", reply_markup=kb_back())

@router.message(AdStates.waiting_age)
async def process_age(message: Message, state: FSMContext):
    text = message.text.strip()
    if not re.match(r'^\d{1,2}-\d{1,2}$', text):
        await message.answer("❌ الصيغة غير صحيحة. استخدم 18-65 مثلاً.", reply_markup=kb_back())
        return

    ages = text.split("-")
    if int(ages[0]) < 13 or int(ages[1]) > 65 or int(ages[0]) >= int(ages[1]):
        await message.answer("❌ عمر غير صحيح (13-65)", reply_markup=kb_back())
        return

    await state.update_data(age=text)
    await message.answer(f"✅ العمر: {text}\n⚧ اختر الجنس:", reply_markup=kb_gender())

@router.callback_query(F.data.startswith("gender:"))
async def cb_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(AdStates.waiting_budget)
    await callback.message.edit_text(f"✅ الجنس: {gender}\n💰 أدخل الميزانية اليومية ($):", reply_markup=kb_back())
    await callback.answer()

@router.message(AdStates.waiting_post_id)
async def process_post_id(message: Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ Post ID قصير جداً", reply_markup=kb_back())
        return

    await state.update_data(post_id=message.text)
    await state.set_state(AdStates.waiting_budget)
    await message.answer("✅ تم حفظ Post ID.\n💰 أدخل الميزانية اليومية ($):", reply_markup=kb_back())

@router.message(AdStates.waiting_event_name)
async def process_event_name(message: Message, state: FSMContext):
    if len(message.text) < 3:
        await message.answer("❌ اسم الحدث قصير جداً", reply_markup=kb_back())
        return

    await state.update_data(event_name=message.text)
    await state.set_state(AdStates.waiting_event_desc)
    await message.answer("✅ تم حفظ الاسم.\n📝 أدخل وصف الحدث:", reply_markup=kb_back())

@router.message(AdStates.waiting_event_desc)
async def process_event_desc(message: Message, state: FSMContext):
    if len(message.text) < 10:
        await message.answer("❌ وصف الحدث قصير جداً (على الأقل 10 أحرف)", reply_markup=kb_back())
        return

    await state.update_data(event_desc=message.text)
    await state.set_state(AdStates.waiting_event_start)
    await message.answer("✅ تم حفظ الوصف.\n🕐 أدخل وقت البداية (YYYY-MM-DD HH:MM):", reply_markup=kb_back())

@router.message(AdStates.waiting_event_start)
async def process_event_start(message: Message, state: FSMContext):
    await state.update_data(event_start=message.text)
    await state.set_state(AdStates.waiting_event_end)
    await message.answer("✅ تم حفظ البداية.\n🕐 أدخل وقت النهاية (YYYY-MM-DD HH:MM):", reply_markup=kb_back())

@router.message(AdStates.waiting_event_end)
async def process_event_end(message: Message, state: FSMContext):
    await state.update_data(event_end=message.text)
    await state.set_state(AdStates.waiting_budget)
    await message.answer("✅ تم حفظ النهاية.\n💰 أدخل الميزانية اليومية ($):", reply_markup=kb_back())

@router.message(AdStates.waiting_budget)
async def process_budget(message: Message, state: FSMContext):
    try:
        budget = float(message.text)
        if budget < 1 or budget > 10000:
            raise ValueError
    except:
        await message.answer("❌ الميزانية يجب أن تكون رقماً بين 1 و 10000", reply_markup=kb_back())
        return

    await state.update_data(budget=budget)
    await state.set_state(AdStates.waiting_days)
    await message.answer(f"✅ الميزانية: {budget}$/يوم\n📅 أدخل عدد الأيام (1-365):", reply_markup=kb_back())

@router.message(AdStates.waiting_days)
async def process_days(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 365:
            raise ValueError
    except:
        await message.answer("❌ يجب أن يكون عدد الأيام بين 1 و 365", reply_markup=kb_back())
        return

    await state.update_data(days=days)
    await state.set_state(AdStates.waiting_ad_status)
    await message.answer("⚡ اختر حالة الإعلان عند الإنشاء:", reply_markup=kb_ad_status())

@router.callback_query(F.data.startswith("status:"))
async def cb_ad_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split(":")[1]
    await state.update_data(ad_status=status)

    data = await state.get_data()

    obj_names = {
        "POST_ENGAGEMENT": "👍 تفاعل المنشور",
        "REACH": "👁 الوصول",
        "PAGE_LIKES": "👥 زيارات الصفحة",
        "LINK_CLICKS": "🔗 النقرات على الرابط",
        "VIDEO_VIEWS": "📹 مشاهدات الفيديو",
        "CONVERSATIONS": "💬 رسائل"
    }

    status_names = {
        "ACTIVE": "▶️ نشط",
        "PAUSED": "⏸ متوقف"
    }

    summary = f"📋 <b>مراجعة البيانات</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    summary += f"🔑 التوكن: {data.get('token', '')[:10]}...\n"
    summary += f"🆔 Account: {data.get('account_id')}\n"
    summary += f"📄 Page: {data.get('page_id')}\n"
    summary += f"🎯 الهدف: {obj_names.get(data.get('objective'), data.get('objective'))}\n"
    summary += f"🌐 البروكسي: {'✅ مستخدم' if data.get('proxy') else '❌ بدون'}\n"

    gate = data.get("gate")
    if gate == "dark_post":
        summary += f"🖼 الصورة: تم رفعها\n"
        summary += f"📝 النص: {data.get('message', '')[:30]}...\n"
    elif gate == "boost_post":
        summary += f"📝 Post ID: {data.get('post_id')}\n"
    elif gate == "event":
        summary += f"🎪 الحدث: {data.get('event_name')}\n"
        summary += f"🕐 البداية: {data.get('event_start')}\n"
        summary += f"🕐 النهاية: {data.get('event_end')}\n"

    summary += f"🌍 الدولة: {data.get('country')}\n"
    summary += f"👤 العمر: {data.get('age')}\n"
    summary += f"⚧ الجنس: {data.get('gender')}\n"
    summary += f"💰 الميزانية: {data.get('budget')}$/يوم\n"
    summary += f"📅 المدة: {data.get('days')} أيام\n"
    summary += f"⚡ الحالة: {status_names.get(status, status)}\n"
    summary += f"━━━━━━━━━━━━━━━━━━━━\n"
    summary += f"هل البيانات صحيحة؟"

    await callback.message.edit_text(summary, reply_markup=kb_confirm(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "confirm:yes")
async def cb_confirm_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⏳ جاري إنشاء الإعلان...")

    data = await state.get_data()
    gate = data.get("gate")
    token = data.get("token")
    acc_id = data.get("account_id")
    budget = data.get("budget")
    objective = data.get("objective", "POST_ENGAGEMENT")
    ad_status = data.get("ad_status", "ACTIVE")
    proxy = data.get("proxy")

    DB["stats"]["requests"] = DB["stats"].get("requests", 0) + 1
    save_data()

    try:
        if gate == "dark_post":
            page_id = data.get("page_id")
            image_id = data.get("image_id")
            message = data.get("message")
            link = data.get("link", "")
            country = data.get("country")
            age = data.get("age")
            gender = data.get("gender")

            dark_post = await fb_create_dark_post(token, page_id, image_id, message, link, proxy)
            if not dark_post.get("ok"):
                raise Exception(dark_post.get("error"))

            campaign = await fb_create_campaign(token, acc_id, objective, budget, proxy)
            if not campaign.get("ok"):
                raise Exception(campaign.get("error"))

            targeting = {
                "geo_locations": {"countries": [country]},
                "age_min": int(age.split("-")[0]),
                "age_max": int(age.split("-")[1]),
                "genders": [1] if gender == "male" else [2] if gender == "female" else [1, 2],
                # مطلوب صراحة من فيسبوك دلوقتي. 0 = نلتزم بالاستهداف اليدوي اللي حدده المستخدم
                # (عمر/جنس/دولة) بدل ما فيسبوك يوسّع الجمهور تلقائيًا بميزة Advantage Audience.
                "targeting_automation": {"advantage_audience": 0}
            }

            opt_goal = resolve_objective(objective)["opt_goal"]
            adset = await fb_create_adset(token, acc_id, campaign["id"], budget, targeting, opt_goal, proxy)
            if not adset.get("ok"):
                raise Exception(adset.get("error"))

            creative = {"object_story_id": dark_post["id"]}
            ad = await fb_create_ad(token, acc_id, adset["id"], creative, ad_status, proxy)
            if not ad.get("ok"):
                raise Exception(ad.get("error"))

            await callback.message.edit_text(
                f"✅ تم إنشاء الإعلان بنجاح!\n\n🆔 Ad ID: <code>{ad['id']}</code>\n⚡ الحالة: {ad_status}",
                reply_markup=kb_home(),
                parse_mode="HTML"
            )

    except Exception as e:
        await callback.message.edit_text(f"❌ فشل إنشاء الإعلان:\n{str(e)}", reply_markup=kb_home())

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "confirm:no")
async def cb_confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ تم الإلغاء.", reply_markup=kb_home())
    await callback.answer()

# ─── Admin Handlers ──────────────────────────────────────
@router.callback_query(F.data.startswith("admin:"))
async def cb_admin(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "stats":
        users = DB["stats"].get("users", 0)
        reqs = DB["stats"].get("requests", 0)
        proxies = len(DB.get("proxies", []))
        await callback.message.edit_text(
            f"📊 <b>الإحصائيات</b>\n\n👤 المستخدمون: {users}\n📋 الطلبات: {reqs}\n🌐 البروكسيات: {proxies}",
            reply_markup=kb_admin(),
            parse_mode="HTML"
        )

    elif action == "gen_code":
        await state.set_state(AdStates.waiting_admin_gen_code)
        await callback.message.edit_text("🎟️ أدخل مدة الكود بالساعات:", reply_markup=kb_home())

    elif action == "set_user":
        await state.set_state(AdStates.waiting_admin_set_user)
        await callback.message.edit_text("👤 أدخل: uid | hours\nمثال: 123456789 | 168", reply_markup=kb_home())

    elif action == "remove_user":
        await state.set_state(AdStates.waiting_admin_remove_user)
        await callback.message.edit_text("🗑️ أدخل UID المستخدم:", reply_markup=kb_home())

    elif action == "broadcast":
        await state.set_state(AdStates.waiting_admin_broadcast)
        await callback.message.edit_text("📢 أدخل الرسالة الجماعية:", reply_markup=kb_home())

    elif action == "add_proxies":
        await state.set_state(AdStates.waiting_admin_add_proxies)
        await callback.message.edit_text("🌐 أرسل البروكسيات (كل بروكسي في سطر):", reply_markup=kb_home())

    await callback.answer()

@router.message(AdStates.waiting_admin_gen_code)
async def process_admin_gen_code(message: Message, state: FSMContext):
    try:
        hours = int(message.text)
        code = gen_code()
        DB["codes"][code] = {"hours": hours, "created_at": now_iso(), "used_by": None, "used_at": None}
        save_data()
        await message.answer(f"✅ الكود:\n<code>{code}</code>\nالمدة: {hours} ساعة", reply_markup=kb_admin(), parse_mode="HTML")
    except:
        await message.answer("❌ رقم ساعات غير صحيح", reply_markup=kb_admin())
    await state.clear()

@router.message(AdStates.waiting_admin_set_user)
async def process_admin_set_user(message: Message, state: FSMContext):
    parts = message.text.split("|")
    if len(parts) != 2:
        await message.answer("❌ الصيغة: uid | hours", reply_markup=kb_admin())
        await state.clear()
        return

    try:
        uid = int(parts[0].strip())
        hours = int(parts[1].strip())
        until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")

        uid_str = str(uid)
        if uid_str not in DB["users"]:
            DB["users"][uid_str] = {"uid": uid, "un": "", "fn": "", "joined": now_iso(), "removed": False, "sub": ""}

        DB["users"][uid_str]["sub"] = until
        DB["users"][uid_str]["removed"] = False
        save_data()

        await message.answer(f"✅ تم تمديد {uid} حتى {until}", reply_markup=kb_admin())
    except:
        await message.answer("❌ بيانات غير صحيحة", reply_markup=kb_admin())
    await state.clear()

@router.message(AdStates.waiting_admin_remove_user)
async def process_admin_remove_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
        uid_str = str(uid)
        if uid_str in DB["users"]:
            DB["users"][uid_str]["removed"] = True
            save_data()
        await message.answer("✅ تم حذف المستخدم", reply_markup=kb_admin())
    except:
        await message.answer("❌ UID غير صحيح", reply_markup=kb_admin())
    await state.clear()

@router.message(AdStates.waiting_admin_broadcast)
async def process_admin_broadcast(message: Message, state: FSMContext):
    success = 0
    for uid_str in DB["users"]:
        try:
            await bot.send_message(int(uid_str), f"📢 رسالة من الإدارة:\n\n{message.text}")
            success += 1
        except:
            pass
    await message.answer(f"✅ تم الإرسال لـ {success} مستخدم", reply_markup=kb_admin())
    await state.clear()

@router.message(AdStates.waiting_admin_add_proxies)
async def process_admin_add_proxies(message: Message, state: FSMContext):
    lines = [x.strip() for x in message.text.splitlines() if x.strip() and not x.startswith("#")]
    if "proxies" not in DB:
        DB["proxies"] = []
    DB["proxies"].extend(lines)
    save_data()
    await message.answer(f"✅ تمت إضافة {len(lines)} بروكسي", reply_markup=kb_admin())
    await state.clear()

# ─── Main ────────────────────────────────────────────────
async def main():
    logger.info("🚀 Starting BESHOY BOT (aiogram 3.20+ + JSON)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
