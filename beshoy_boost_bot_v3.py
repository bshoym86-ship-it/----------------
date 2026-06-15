# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "aiogram==3.17.*",
#   "httpx==0.28.*",
#   "beautifulsoup4==4.15.*",
# ]
# ///
"""
BESHOY BOOST BOT V3 — Telegram Bot
aiogram · Proxy Support · Colored Buttons · 5 Facebook Ad Gates
Dark Post Gate (Primary) + Partner Ship + Boost Post + Page Like + Event Campaign
"""
import os, re, json, secrets, string, random, asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

import httpx
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Message, WebAppInfo
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set!")

ADMIN_PASS = "Nemo@1986"
ADMIN_CMD = "beshoy"
SUPPORT_URL = "https://t.me/your_support_username"
BOT_NAME = "🚀 BESHOY BOOST BOT V3"

# Colors for buttons (aiogram supports emoji-based colored buttons)
COLORS = {
    "primary": "🔵",
    "success": "🟢",
    "danger": "🔴",
    "warning": "🟡",
    "info": "🟣",
    "dark": "⚫",
    "white": "⚪",
}

# Facebook Graph API
FB_API = "https://graph.facebook.com/v18.0"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Objective names in Arabic
OBJ_NAMES = {
    "CONVERSATIONS": "💬 محادثات",
    "MESSAGES_MESSENGER": "📨 رسائل ماسنجر",
    "MESSAGES_WHATSAPP": "📱 رسائل واتساب",
    "LINK_CLICKS": "🔗 نقرات رابط",
    "POST_ENGAGEMENT": "📌 تفاعل بوست",
    "VIDEO_VIEWS": "🎬 مشاهدات فيديو",
}

# ═══════════════════════════════════════════════════════
# AIOGRAM SETUP
# ═══════════════════════════════════════════════════════
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# ═══════════════════════════════════════════════════════
# IN-MEMORY DB (for simplicity, no Redis dependency)
# ═══════════════════════════════════════════════════════
class MemoryDB:
    def __init__(self):
        self.users: dict[int, dict] = {}
        self.states: dict[int, dict] = {}
        self.codes: dict[str, dict] = {}
        self.proxies: list[str] = []
        self.stats: dict[str, int] = {"requests": 0, "users": 0}

    def get_user(self, uid: int) -> Optional[dict]:
        return self.users.get(uid)

    def save_user(self, uid: int, data: dict):
        self.users[uid] = data

    def ensure_user(self, uid: int, un: str = "", fn: str = ""):
        u = self.get_user(uid)
        if not u:
            u = {
                "uid": uid, "un": un, "fn": fn, "cn": "",
                "joined": self.now_iso(), "removed": False, "sub": ""
            }
        u["un"], u["fn"] = un, fn
        self.save_user(uid, u)
        return u

    def is_sub(self, uid: int) -> bool:
        u = self.get_user(uid)
        if not u or u.get("removed"): return False
        s = u.get("sub", "")
        if not s: return False
        try: return datetime.fromisoformat(s) > datetime.now(timezone.utc)
        except: return False

    def set_sub(self, uid: int, hours: int) -> str:
        u = self.get_user(uid)
        if not u:
            u = {"uid": uid, "un": "", "fn": "", "cn": "", "joined": self.now_iso(), "removed": False, "sub": ""}
        until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
        u["sub"] = until
        u["removed"] = False
        self.save_user(uid, u)
        return until

    def get_state(self, uid: int) -> dict:
        return self.states.get(uid, {"st": ""})

    def set_state(self, uid: int, data: dict):
        self.states[uid] = data

    def clear_state(self, uid: int):
        self.states.pop(uid, None)

    def gen_code(self, prefix: str = "BM", length: int = 12) -> str:
        a = string.ascii_uppercase + string.digits
        code = f"{prefix}-{''.join(secrets.choice(a) for _ in range(length))}"
        return code

    def create_code(self, code: str, hours: int):
        self.codes[code] = {"h": hours, "ca": self.now_iso(), "ub": None, "ua": None}

    def use_code(self, code: str, uid: int) -> Optional[int]:
        c = self.codes.get(code)
        if not c or c.get("ub"): return None
        c["ub"] = uid
        c["ua"] = self.now_iso()
        return c["h"]

    def add_proxies(self, text: str) -> int:
        lines = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
        self.proxies.extend(lines)
        return len(lines)

    def get_random_proxy(self) -> Optional[str]:
        if not self.proxies: return None
        return random.choice(self.proxies)

    def inc_stat(self, key: str, amount: int = 1):
        self.stats[key] = self.stats.get(key, 0) + amount

    def get_stat(self, key: str) -> int:
        return self.stats.get(key, 0)

    @staticmethod
    def now_iso():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

db = MemoryDB()

# ═══════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════
class AdStates(StatesGroup):
    # Login / Auth
    admin_pass = State()
    
    # Generic ad states (shared across gates)
    proxy_choice = State()
    proxy_custom = State()
    cookies_input = State()
    account_id = State()
    ad_code = State()
    objective = State()
    budget = State()
    days = State()
    confirm = State()
    
    # Additional states
    page_id = State()
    post_url = State()
    page_name = State()
    event_name = State()
    event_description = State()
    event_start = State()
    event_end = State()
    
    # Admin states
    admin_gen_code = State()
    admin_set_user = State()
    admin_remove_user = State()
    admin_broadcast = State()
    admin_add_proxies = State()

# ═══════════════════════════════════════════════════════
# COLORED KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════
def mkbtn(text: str, callback: str = "", url: str = "", web_app: str = "", color: str = "primary") -> InlineKeyboardButton:
    """Create colored inline button with emoji prefix based on color."""
    color_map = {
        "primary": "🔵 ", "success": "🟢 ", "danger": "🔴 ",
        "warning": "🟡 ", "info": "🟣 ", "dark": "⚫ ",
        "white": "⚪ ", "red": "🔴 ", "green": "🟢 ",
        "blue": "🔵 ", "yellow": "🟡 ", "purple": "🟣 ",
        "pink": "🩷 ", "orange": "🟠 ",
    }
    prefix = color_map.get(color, "🔵 ")
    full_text = f"{prefix}{text}"
    
    if url:
        return InlineKeyboardButton(text=full_text, url=url)
    if web_app:
        return InlineKeyboardButton(text=full_text, web_app=WebAppInfo(url=web_app))
    return InlineKeyboardButton(text=full_text, callback_data=callback)

def row(*buttons) -> list:
    return list(buttons)

def ikb(rows: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Keyboard factories ───────────────────────────────
def kb_main(is_sub: bool) -> InlineKeyboardMarkup:
    rows = []
    # Colored gate buttons
    rows.append(row(
        mkbtn("🌑 Dark Post", "gate:dark_post", color="purple"),
        mkbtn("🤝 Partner Ship", "gate:partner_ship", color="blue"),
    ))
    rows.append(row(
        mkbtn("🚀 Boost Post", "gate:boost_post", color="orange"),
        mkbtn("👍 Page Like", "gate:page_like", color="green"),
    ))
    rows.append(row(
        mkbtn("🎪 Event Campaign", "gate:event_campaign", color="pink"),
    ))
    rows.append(row(
        mkbtn("🎟️ Redeem Code", "redeem", color="yellow"),
        mkbtn("🆘 Support", "", url=SUPPORT_URL, color="info"),
    ))
    return ikb(rows)

def kb_back_home(text: str = "🏠 الرئيسية") -> InlineKeyboardMarkup:
    return ikb([row(mkbtn(text, "home", color="dark"))])

def kb_home() -> InlineKeyboardMarkup:
    return ikb([row(mkbtn("🏠 الرئيسية", "home", color="primary"))])

def kb_proxy() -> InlineKeyboardMarkup:
    return ikb([
        row(mkbtn("🎲 تلقائي", "proxy:auto", color="success")),
        row(mkbtn("✏️ يدوي", "proxy:custom", color="warning")),
        row(mkbtn("⏭️ تخطي", "proxy:skip", color="dark")),
        row(mkbtn("🏠 الرئيسية", "home", color="primary")),
    ])

def kb_objectives() -> InlineKeyboardMarkup:
    rows = []
    for k, n in OBJ_NAMES.items():
        rows.append(row(mkbtn(n, f"obj:{k}", color="info")))
    rows.append(row(mkbtn("🏠 الرئيسية", "home", color="dark")))
    return ikb(rows)

def kb_confirm() -> InlineKeyboardMarkup:
    return ikb([
        row(mkbtn("✅ تأكيد", "confirm:yes", color="success")),
        row(mkbtn("❌ إلغاء", "confirm:no", color="danger")),
        row(mkbtn("🏠 الرئيسية", "home", color="dark")),
    ])

def kb_back_proxy() -> InlineKeyboardMarkup:
    return ikb([row(mkbtn("🔙 رجوع", "proxy:back", color="warning"))])

def kb_admin() -> InlineKeyboardMarkup:
    return ikb([
        row(mkbtn("🎟️ توليد كود", "admin:gen_code", color="success")),
        row(mkbtn("👤 تمديد مشترك", "admin:set_user", color="blue")),
        row(mkbtn("🗑️ حذف مشترك", "admin:remove_user", color="danger")),
        row(mkbtn("📢 رسالة جماعية", "admin:broadcast", color="purple")),
        row(mkbtn("🌐 إضافة بروكسيات", "admin:add_proxies", color="orange")),
        row(mkbtn("📊 الإحصائيات", "admin:stats", color="info")),
        row(mkbtn("🚪 خروج", "home", color="dark")),
    ])

# ═══════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════
def v_proxy(p: str) -> bool:
    return bool(re.match(r'^[\w.:@/\-]+$', p.strip()) and ":" in p)

def v_cookies(c: str) -> bool:
    return len(c) >= 50 and all(k in c for k in ["c_user", "xs", "datr"])

def v_id(v: str, mn: int = 10, mx: int = 20) -> bool:
    return bool(re.match(rf'^\d{{{mn},{mx}}}$', v.strip()))

def v_budget(v: str) -> tuple[bool, Optional[float]]:
    try:
        a = float(v)
        return (True, round(a, 2)) if 1 <= a <= 10000 else (False, None)
    except:
        return (False, None)

def v_days(v: str) -> tuple[bool, Optional[int]]:
    try:
        a = int(v)
        return (True, a) if 1 <= a <= 365 else (False, None)
    except:
        return (False, None)

def v_url(v: str) -> bool:
    return bool(re.match(r'^https?://[\w./\-]+', v.strip()))

# ═══════════════════════════════════════════════════════
# FACEBOOK API FUNCTIONS
# ═══════════════════════════════════════════════════════
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

async def fb_api_post(path: str, cookies_str: str, json_data: dict, proxy: str = None) -> dict:
    """Generic Facebook Graph API POST."""
    hdrs, proxies = fb_headers(cookies_str, proxy)
    try:
        async with httpx.AsyncClient(timeout=60, proxies=proxies, follow_redirects=True) as c:
            resp = await c.post(f"{FB_API}/{path}", headers=hdrs, json=json_data)
            data = resp.json()
            if resp.status_code == 200 and data.get("id"):
                return {"ok": True, "id": data["id"], "msg": "Success", "raw": data}
            return {"ok": False, "error": data.get("error", {}).get("message", resp.text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def fb_api_get(path: str, cookies_str: str, proxy: str = None) -> dict:
    """Generic Facebook Graph API GET."""
    hdrs, proxies = fb_headers(cookies_str, proxy)
    try:
        async with httpx.AsyncClient(timeout=60, proxies=proxies, follow_redirects=True) as c:
            resp = await c.get(f"{FB_API}/{path}", headers=hdrs)
            data = resp.json()
            return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Gate 1: Dark Post (Create unpublished page post) ─────────
async def fb_dark_post(
    page_id: str, cookies_str: str, message: str,
    link: str = "", image_url: str = "", proxy: str = None
) -> dict:
    """
    Create a Dark Post (unpublished page post) that appears only in Ads Manager.
    This is the most powerful gate for stealth advertising.
    """
    data = {
        "message": message,
        "published": False,  # ← THIS makes it a Dark Post
    }
    if link:
        data["link"] = link
    if image_url:
        data["attached_media"] = [{"media_fbid": image_url}]
    
    return await fb_api_post(f"{page_id}/feed", cookies_str, data, proxy)

# ── Gate 2: Partner Ship (existing code, improved) ───────────
async def fb_create_campaign(
    account_id: str, cookies_str: str, objective: str,
    daily_budget: float, days: int, ad_code: str,
    proxy: str = None
) -> dict:
    """Create a Facebook ad campaign via Graph API using cookies auth."""
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
    
    # Step 1: Create Campaign
    result = await fb_api_post(f"act_{account_id}/campaigns", cookies_str, {
        "name": f"Partner Ship - {ad_code[:20]}",
        "objective": fb_objective,
        "status": "ACTIVE",
        "special_ad_categories": [],
        "daily_budget": budget_cents,
    }, proxy)
    
    if not result.get("ok"):
        return result
    
    campaign_id = result["id"]
    
    # Step 2: Create Ad Set
    result2 = await fb_api_post(f"act_{account_id}/adsets", cookies_str, {
        "name": f"AdSet - {ad_code[:15]}",
        "campaign_id": campaign_id,
        "daily_budget": budget_cents,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": fb_objective,
        "targeting": {"geo_locations": {"countries": ["US"]}},
        "status": "ACTIVE",
        "start_time": datetime.now(timezone.utc).isoformat(),
    }, proxy)
    
    if not result2.get("ok"):
        return {"ok": True, "campaign_id": campaign_id, "msg": f"Campaign created but AdSet failed: {result2.get('error', '')}"}
    
    adset_id = result2["id"]
    
    # Step 3: Create Ad Creative
    result3 = await fb_api_post(f"act_{account_id}/adcreatives", cookies_str, {
        "name": f"Creative - {ad_code[:15]}",
        "object_story_spec": {
            "page_id": "YOUR_PAGE_ID",
            "link_data": {
                "link": "https://www.facebook.com",
                "message": f"Boost Ad - {ad_code[:30]}",
            }
        }
    }, proxy)
    
    creative_id = result3.get("id", "")
    creative_ok = result3.get("ok", False)
    
    # Step 4: Create Ad
    ad_data = {
        "name": f"Ad - {ad_code[:15]}",
        "adset_id": adset_id,
        "status": "ACTIVE",
    }
    if creative_ok and creative_id:
        ad_data["creative"] = {"creative_id": creative_id}
    
    result4 = await fb_api_post(f"act_{account_id}/ads", cookies_str, ad_data, proxy)
    
    return {
        "ok": True,
        "campaign_id": campaign_id,
        "adset_id": adset_id,
        "ad_id": result4.get("id", ""),
        "msg": "Full campaign created" if result4.get("ok") else f"Partial: {result4.get('error', '')}"
    }

# ── Gate 3: Boost Post ──────────────────────────────────────
async def fb_boost_post(
    page_id: str, post_id: str, cookies_str: str,
    budget: float, days: int, proxy: str = None
) -> dict:
    """
    Boost an existing post via the promotions endpoint.
    """
    budget_cents = str(int(budget * 100))
    now = datetime.now(timezone.utc)
    end_time = (now + timedelta(days=days)).isoformat()
    
    return await fb_api_post(f"{page_id}/promotions", cookies_str, {
        "post_id": post_id,
        "budget": budget_cents,
        "duration": days * 86400,  # seconds
        "target_spec": json.dumps({
            "geo_locations": {"countries": ["US"]},
            "age_min": 18,
            "age_max": 65,
        }),
        "end_time": end_time,
        "pacing_type": "standard",
    }, proxy)

# ── Gate 4: Page Like Campaign ──────────────────────────────
async def fb_page_like_campaign(
    account_id: str, page_id: str, cookies_str: str,
    budget: float, days: int, proxy: str = None
) -> dict:
    """
    Create a Page Like campaign (Page Engagement).
    """
    budget_cents = str(int(budget * 100))
    
    # Create campaign with PAGE_ENGAGEMENT objective (actually POST_ENGAGEMENT in v18+)
    result = await fb_api_post(f"act_{account_id}/campaigns", cookies_str, {
        "name": f"Page Like - {page_id[:15]}",
        "objective": "OUTCOME_ENGAGEMENT",
        "status": "ACTIVE",
        "special_ad_categories": [],
        "daily_budget": budget_cents,
    }, proxy)
    
    if not result.get("ok"):
        return result
    
    campaign_id = result["id"]
    
    # Create AdSet targeting fans
    result2 = await fb_api_post(f"act_{account_id}/adsets", cookies_str, {
        "name": f"Like AdSet - {page_id[:10]}",
        "campaign_id": campaign_id,
        "daily_budget": budget_cents,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "PAGE_ENGAGEMENT",
        "targeting": {
            "geo_locations": {"countries": ["US"]},
            "page_ids": [page_id],
        },
        "status": "ACTIVE",
    }, proxy)
    
    return {
        "ok": result2.get("ok", False),
        "campaign_id": campaign_id,
        "adset_id": result2.get("id", ""),
        "msg": "Page Like campaign running" if result2.get("ok") else f"AdSet failed: {result2.get('error', '')}"
    }

# ── Gate 5: Event Campaign ─────────────────────────────────
async def fb_event_campaign(
    account_id: str, cookies_str: str,
    event_name: str, event_description: str,
    start_time: str, end_time: str,
    budget: float, proxy: str = None
) -> dict:
    """
    Create an Event campaign to promote a Facebook event.
    """
    budget_cents = str(int(budget * 100))
    
    # First create the event
    event_result = await fb_api_post(f"act_{account_id}/events", cookies_str, {
        "name": event_name,
        "description": event_description,
        "start_time": start_time,
        "end_time": end_time,
    }, proxy)
    
    event_id = event_result.get("id", "")
    if not event_id:
        return {"ok": False, "error": event_result.get("error", "Failed to create event")}
    
    # Then create campaign to promote it
    result = await fb_api_post(f"act_{account_id}/campaigns", cookies_str, {
        "name": f"Event - {event_name[:20]}",
        "objective": "OUTCOME_ENGAGEMENT",
        "status": "ACTIVE",
        "special_ad_categories": [],
        "daily_budget": budget_cents,
    }, proxy)
    
    return {
        "ok": result.get("ok", False),
        "event_id": event_id,
        "campaign_id": result.get("id", ""),
        "msg": "Event + Campaign created" if result.get("ok") else f"Campaign failed: {result.get('error', '')}"
    }

# ═══════════════════════════════════════════════════════
# DELETE WEBHOOK (for polling mode)
# ═══════════════════════════════════════════════════════
async def on_startup():
    """Delete webhook and use polling."""
    await bot.delete_webhook(drop_pending_updates=True)
    print(f"{BOT_NAME} started in polling mode!")

# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

# ── /start ────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    db.ensure_user(uid, message.from_user.username or "", message.from_user.first_name or "")
    existing = db.get_user(uid)
    if not existing or not existing.get("joined"):
        db.inc_stat("users")
    db.clear_state(uid)
    
    sub = db.is_sub(uid)
    name = (existing.get("cn") or existing.get("fn") or "مستخدم") if existing else "مستخدم"
    status = "✅ مشترك" if sub else "❌ غير مشترك"
    txt = (
        f"⚡ <b>{BOT_NAME}</b>\n\n"
        f"مرحبًا {name}\n"
        f"الحالة: {status}\n\n"
        f"<b>البوابات المتاحة:</b>\n"
        f"🌑 <b>Dark Post</b> - إعلانات مخفية (غير منشورة)\n"
        f"🤝 <b>Partner Ship</b> - إعلانات الشراكة\n"
        f"🚀 <b>Boost Post</b> - تدعيم المنشورات\n"
        f"👍 <b>Page Like</b> - إعلانات إعجاب الصفحة\n"
        f"🎪 <b>Event Campaign</b> - إعلانات الأحداث\n\n"
        f"اختر البوابة المناسبة 👇"
    )
    await message.answer(txt, reply_markup=kb_main(sub))

# ── /beshoy admin ─────────────────────────────────────
@dp.message(Command(ADMIN_CMD))
async def cmd_admin(message: Message, state: FSMContext):
    await state.set_state(AdStates.admin_pass)
    await message.answer("🔐 اكتب باسورد لوحة التحكم:", reply_markup=kb_back_home())

# ── Password check ────────────────────────────────────
@dp.message(AdStates.admin_pass)
async def admin_pass_handler(message: Message, state: FSMContext):
    if message.text == ADMIN_PASS:
        await state.clear()
        db.clear_state(message.from_user.id)
        reqs = db.get_stat("requests")
        users = db.get_stat("users")
        await message.answer(
            f"✅ <b>لوحة التحكم</b>\n\n"
            f"📊 الطلبات: {reqs}\n"
            f"👤 المستخدمون: {users}",
            reply_markup=kb_admin()
        )
    else:
        await message.answer("❌ باسورد خطأ.", reply_markup=kb_home())
        await state.clear()

# ── Callback Query Handler ────────────────────────────
@dp.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    uid = callback.from_user.id
    cid = callback.message.chat.id
    mid = callback.message.message_id
    
    try:
        # ── HOME ──
        if data == "home":
            db.clear_state(uid)
            await state.clear()
            sub = db.is_sub(uid)
            u = db.get_user(uid)
            name = (u.get("cn") or u.get("fn") or "مستخدم") if u else "مستخدم"
            status = "✅ مشترك" if sub else "❌ غير مشترك"
            txt = f"⚡ <b>{BOT_NAME}</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."
            await bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb_main(sub))
            await callback.answer()
            return
        
        # ── REDEEM ──
        if data == "redeem":
            db.set_state(uid, {"st": "redeem"})
            await bot.edit_message_text("🎟️ أرسل كود التفعيل الآن:", cid, mid, parse_mode="HTML", reply_markup=kb_home())
            await callback.answer()
            return
        
        # ── GATES ──
        if data.startswith("gate:"):
            gate = data.split(":", 1)[1]
            u = db.get_user(uid)
            if not db.is_sub(uid):
                await callback.answer("اشترك أولًا بكود Redeem.", show_alert=True)
                return
            
            db.inc_stat("requests")
            
            gate_names = {
                "dark_post": "🌑 Dark Post",
                "partner_ship": "🤝 Partner Ship",
                "boost_post": "🚀 Boost Post",
                "page_like": "👍 Page Like",
                "event_campaign": "🎪 Event Campaign",
            }
            gate_name = gate_names.get(gate, gate)
            gate_states = {
                "dark_post": "dp_proxy",
                "partner_ship": "ps_proxy",
                "boost_post": "bp_proxy",
                "page_like": "pl_proxy",
                "event_campaign": "ec_proxy",
            }
            db.set_state(uid, {"st": gate_states.get(gate, "ps_proxy"), "gate": gate})
            
            steps_info = {
                "dark_post": "1️⃣ البروكسي\n2️⃣ الكوكيز\n3️⃣ Page ID\n4️⃣ نص المنشور\n5️⃣ رابط (اختياري)\n6️⃣ مراجعة",
                "partner_ship": "1️⃣ البروكسي\n2️⃣ الكوكيز\n3️⃣ Account ID\n4️⃣ Ad Code\n5️⃣ الهدف\n6️⃣ الميزانية\n7️⃣ المدة\n8️⃣ مراجعة",
                "boost_post": "1️⃣ البروكسي\n2️⃣ الكوكيز\n3️⃣ Page ID\n4️⃣ Post ID\n5️⃣ الميزانية\n6️⃣ المدة\n7️⃣ مراجعة",
                "page_like": "1️⃣ البروكسي\n2️⃣ الكوكيز\n3️⃣ Account ID\n4️⃣ Page ID\n5️⃣ الميزانية\n6️⃣ المدة\n7️⃣ مراجعة",
                "event_campaign": "1️⃣ البروكسي\n2️⃣ الكوكيز\n3️⃣ Account ID\n4️⃣ اسم الحدث\n5️⃣ وصف الحدث\n6️⃣ وقت البداية\n7️⃣ وقت النهاية\n8️⃣ الميزانية\n9️⃣ مراجعة",
            }
            
            txt = (
                f"<b>{gate_name}</b>\n\n"
                f"───────────────\n"
                f"📋 <b>الخطوات:</b>\n{steps_info.get(gate, '')}\n\n"
                f"───────────────\n"
                f"🔽 <b>خطوة 1:</b> اختر البروكسي"
            )
            await bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb_proxy())
            await callback.answer()
            return
        
        # ── PROXY CHOICE ──
        if data.startswith("proxy:"):
            action = data.split(":", 1)[1]
            st = db.get_state(uid)
            current_state = st.get("st", "")
            gate = st.get("gate", "partner_ship")
            
            # Determine next state after proxy
            next_states = {
                "dp_proxy": "dp_cook",
                "ps_proxy": "ps_cook",
                "bp_proxy": "bp_cook",
                "pl_proxy": "pl_cook",
                "ec_proxy": "ec_cook",
                "dp_cook": "dp_page",
                "ps_cook": "ps_acc",
                "bp_cook": "bp_page",
                "pl_cook": "pl_acc",
                "ec_cook": "ec_acc",
            }
            
            if action == "auto":
                p = db.get_random_proxy()
                if not p:
                    await callback.answer("لا توجد بروكسيات متاحة.", show_alert=True)
                    return
                st["px"] = p
                next_s = next_states.get(current_state, "ps_cook")
                st["st"] = next_s
                db.set_state(uid, st)
                await bot.edit_message_text(
                    f"✅ <b>بروكسي:</b> {p}\n\n🔽 <b>خطوة 2:</b> أدخل الكوكيز",
                    cid, mid, parse_mode="HTML", reply_markup=kb_back_proxy()
                )
            elif action == "skip":
                st["px"] = None
                next_s = next_states.get(current_state, "ps_cook")
                st["st"] = next_s
                db.set_state(uid, st)
                await bot.edit_message_text(
                    "⏭️ بدون بروكسي\n\n🔽 <b>خطوة 2:</b> أدخل الكوكيز",
                    cid, mid, parse_mode="HTML", reply_markup=kb_back_proxy()
                )
            elif action == "custom":
                st["st"] = current_state.replace("proxy", "px_in")
                db.set_state(uid, st)
                await bot.edit_message_text(
                    "✏️ أدخل البروكسي يدويًا (username:password@ip:port):",
                    cid, mid, parse_mode="HTML", reply_markup=kb_home()
                )
            elif action == "back":
                # Go back to proxy selection
                st["st"] = current_state.replace("cook", "proxy").replace("page", "proxy").replace("acc", "proxy")
                db.set_state(uid, st)
                await bot.edit_message_text(
                    "🔽 <b>خطوة 1:</b> اختر البروكسي",
                    cid, mid, parse_mode="HTML", reply_markup=kb_proxy()
                )
            
            await callback.answer()
            return
        
        # ── OBJECTIVE ──
        if data.startswith("obj:"):
            obj = data.split(":", 1)[1]
            st = db.get_state(uid)
            st["obj"] = obj
            st["st"] = st["st"].replace("obj", "budget")
            db.set_state(uid, st)
            await bot.edit_message_text(
                f"✅ <b>الهدف:</b> {OBJ_NAMES.get(obj, obj)}\n\n🔽 <b>الخطوة التالية:</b> أرسل الميزانية اليومية ($)\n(1 - 10,000)",
                cid, mid, parse_mode="HTML", reply_markup=kb_home()
            )
            await callback.answer()
            return
        
        # ── CONFIRM ──
        if data.startswith("confirm:"):
            action = data.split(":", 1)[1]
            st = db.get_state(uid)
            if action == "no":
                db.clear_state(uid)
                await bot.edit_message_text("❌ تم الإلغاء.", cid, mid, parse_mode="HTML", reply_markup=kb_home())
            elif action == "yes":
                gate = st.get("gate", "partner_ship")
                # Build confirmation summary
                summary_lines = [
                    "📋 <b>مراجعة البيانات:</b>",
                    "───────────────",
                    f"🌐 بروكسي: {st.get('px') or 'بدون'}",
                ]
                
                if gate == "dark_post":
                    summary_lines.append(f"📄 Page ID: {st.get('page_id', '')}")
                    summary_lines.append(f"💬 النص: {st.get('message', '')[:50]}...")
                elif gate == "partner_ship":
                    summary_lines.append(f"🔑 Account: {st.get('acc', '')}")
                    summary_lines.append(f"🎯 Ad Code: {st.get('acode', '')}")
                    summary_lines.append(f"🎯 الهدف: {OBJ_NAMES.get(st.get('obj', ''), '')}")
                    summary_lines.append(f"💰 الميزانية: {st.get('bgt', 10)}$/يوم")
                    summary_lines.append(f"📅 المدة: {st.get('days', 7)} أيام")
                elif gate == "boost_post":
                    summary_lines.append(f"📄 Page ID: {st.get('page_id', '')}")
                    summary_lines.append(f"📝 Post ID: {st.get('post_id', '')}")
                    summary_lines.append(f"💰 الميزانية: {st.get('bgt', 10)}$")
                elif gate == "page_like":
                    summary_lines.append(f"🔑 Account: {st.get('acc', '')}")
                    summary_lines.append(f"📄 Page ID: {st.get('page_id', '')}")
                    summary_lines.append(f"💰 الميزانية: {st.get('bgt', 10)}$/يوم")
                elif gate == "event_campaign":
                    summary_lines.append(f"🔑 Account: {st.get('acc', '')}")
                    summary_lines.append(f"🎪 الحدث: {st.get('event_name', '')}")
                    summary_lines.append(f"💰 الميزانية: {st.get('bgt', 10)}$/يوم")
                
                summary_lines.append("───────────────")
                summary_lines.append("🟢 اضغط للتشغيل!")
                
                st["st"] = f"{gate}_activate"
                db.set_state(uid, st)
                await bot.edit_message_text(
                    "\n".join(summary_lines),
                    cid, mid, parse_mode="HTML",
                    reply_markup=ikb([row(mkbtn("🚀 تشغيل الإعلان", "activate:run", color="success")),
                                     row(mkbtn("🏠 الرئيسية", "home", color="dark"))])
                )
            await callback.answer()
            return
        
        # ── ACTIVATE ──
        if data == "activate:run":
            st = db.get_state(uid)
            gate = st.get("gate", "partner_ship")
            
            await bot.edit_message_text("⏳ <b>جاري تشغيل الإعلان...</b>", cid, mid, parse_mode="HTML")
            await callback.answer()
            
            full_cookies = st.get("full_cook", "")
            proxy = st.get("px")
            result = {"ok": False, "error": "Unknown gate"}
            
            if gate == "dark_post":
                result = await fb_dark_post(
                    page_id=st.get("page_id", ""),
                    cookies_str=full_cookies,
                    message=st.get("message", "Dark Post"),
                    link=st.get("link", ""),
                    proxy=proxy
                )
            elif gate == "partner_ship":
                result = await fb_create_campaign(
                    account_id=st.get("acc", ""),
                    cookies_str=full_cookies,
                    objective=st.get("obj", "CONVERSATIONS"),
                    daily_budget=st.get("bgt", 10),
                    days=st.get("days", 7),
                    ad_code=st.get("acode", ""),
                    proxy=proxy
                )
            elif gate == "boost_post":
                result = await fb_boost_post(
                    page_id=st.get("page_id", ""),
                    post_id=st.get("post_id", ""),
                    cookies_str=full_cookies,
                    budget=st.get("bgt", 10),
                    days=st.get("days", 7),
                    proxy=proxy
                )
            elif gate == "page_like":
                result = await fb_page_like_campaign(
                    account_id=st.get("acc", ""),
                    page_id=st.get("page_id", ""),
                    cookies_str=full_cookies,
                    budget=st.get("bgt", 10),
                    days=st.get("days", 7),
                    proxy=proxy
                )
            elif gate == "event_campaign":
                result = await fb_event_campaign(
                    account_id=st.get("acc", ""),
                    cookies_str=full_cookies,
                    event_name=st.get("event_name", "Event"),
                    event_description=st.get("event_desc", ""),
                    start_time=st.get("event_start", ""),
                    end_time=st.get("event_end", ""),
                    budget=st.get("bgt", 10),
                    proxy=proxy
                )
            
            if result.get("ok"):
                success_msg = f"✅ <b>تم تشغيل الإعلان بنجاح!</b>\n\n───────────────\n"
                for k, v in result.items():
                    if k != "ok":
                        success_msg += f"• <b>{k}:</b> {v}\n"
                success_msg += "\n🎉 <b>مبروك! الإعلان يعمل الآن</b>"
                await bot.edit_message_text(success_msg, cid, mid, parse_mode="HTML", reply_markup=kb_home())
            else:
                err = result.get("error", "Unknown error")
                await bot.edit_message_text(
                    f"❌ <b>فشل تشغيل الإعلان</b>\n\nالخطأ: {err}\n\n💡 تأكد من صحة الكوكيز والبيانات",
                    cid, mid, parse_mode="HTML", reply_markup=kb_home()
                )
            
            db.clear_state(uid)
            return
        
        # ── ADMIN ──
        if data.startswith("admin:"):
            await admin_callback_handler(callback, state)
            return
        
        await callback.answer()
    
    except Exception as e:
        print(f"Callback error: {e}")
        try:
            await callback.answer("حدث خطأ، حاول مرة أخرى.", show_alert=True)
        except:
            pass

async def admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    uid = callback.from_user.id
    cid = callback.message.chat.id
    mid = callback.message.message_id
    
    if data == "admin:stats":
        reqs = db.get_stat("requests")
        users = db.get_stat("users")
        proxies = len(db.proxies)
        codes = len([c for c in db.codes.values() if not c.get("ub")])
        await bot.edit_message_text(
            f"📊 <b>الإحصائيات</b>\n\n"
            f"👤 المستخدمون: {users}\n"
            f"📋 الطلبات: {reqs}\n"
            f"🌐 البروكسيات: {proxies}\n"
            f"🎟️ الأكواد المتاحة: {codes}",
            cid, mid, parse_mode="HTML", reply_markup=kb_admin()
        )
    elif data == "admin:gen_code":
        db.set_state(uid, {"st": "a_gen"})
        await bot.edit_message_text(
            "🎟️ اكتب مدة الكود بالساعات (مثال: 24):",
            cid, mid, parse_mode="HTML",
            reply_markup=ikb([row(mkbtn("🔙 رجوع", "admin:stats", color="warning"))])
        )
    elif data == "admin:set_user":
        db.set_state(uid, {"st": "a_set"})
        await bot.edit_message_text(
            "👤 اكتب: user_id | الاسم | ساعات\nمثال: <code>123456789 | VIP | 168</code>",
            cid, mid, parse_mode="HTML",
            reply_markup=ikb([row(mkbtn("🔙 رجوع", "admin:stats", color="warning"))])
        )
    elif data == "admin:remove_user":
        db.set_state(uid, {"st": "a_rm"})
        await bot.edit_message_text(
            "🗑️ اكتب user_id المراد حذفه:",
            cid, mid, parse_mode="HTML",
            reply_markup=ikb([row(mkbtn("🔙 رجوع", "admin:stats", color="warning"))])
        )
    elif data == "admin:broadcast":
        db.set_state(uid, {"st": "a_bc"})
        await bot.edit_message_text(
            "📢 اكتب الرسالة الجماعية:",
            cid, mid, parse_mode="HTML",
            reply_markup=ikb([row(mkbtn("🔙 رجوع", "admin:stats", color="warning"))])
        )
    elif data == "admin:add_proxies":
        db.set_state(uid, {"st": "a_px"})
        await bot.edit_message_text(
            "🌐 أرسل البروكسيات، كل بروكسي في سطر:\n<code>user:pass@ip:port</code>",
            cid, mid, parse_mode="HTML",
            reply_markup=ikb([row(mkbtn("🔙 رجوع", "admin:stats", color="warning"))])
        )
    
    await callback.answer()

# ── Message Handler ──────────────────────────────────
@dp.message()
async def message_handler(message: Message, state: FSMContext):
    uid = message.from_user.id
    cid = message.chat.id
    text = message.text.strip() if message.text else ""
    
    # Ensure user exists
    db.ensure_user(uid, message.from_user.username or "", message.from_user.first_name or "")
    
    st = db.get_state(uid)
    current_state = st.get("st", "")
    
    # ── Redeem ──
    if current_state == "redeem":
        h = db.use_code(text, uid)
        if not h:
            await message.answer("❌ الكود غير صالح أو تم استخدامه.", reply_markup=kb_home())
            return
        until = db.set_sub(uid, h)
        db.clear_state(uid)
        sub = db.is_sub(uid)
        u = db.get_user(uid)
        u["sub"] = until
        db.save_user(uid, u)
        await message.answer(f"✅ تم تفعيل الاشتراك حتى:\n<code>{until}</code>", reply_markup=kb_main(sub))
        return
    
    # ── Custom Proxy Input ──
    if current_state.endswith("_px_in"):
        if not v_proxy(text):
            await message.answer("❌ صيغة بروكسي غير صحيحة. استخدم: <code>user:pass@ip:port</code>", reply_markup=kb_home())
            return
        st["px"] = text
        gate_prefix = current_state.split("_")[0]  # dp, ps, bp, pl, ec
        st["st"] = f"{gate_prefix}_cook"
        db.set_state(uid, st)
        await message.answer(
            f"✅ <b>بروكسي:</b> {text}\n\n🔽 <b>خطوة 2:</b> أدخل الكوكيز",
            reply_markup=kb_back_proxy()
        )
        return
    
    # ── COOKIES INPUT (shared across gates) ──
    if current_state.endswith("_cook"):
        if not v_cookies(text):
            await message.answer("❌ الكوكيز ناقصة (لازم تحتوي على <code>c_user</code> و <code>xs</code> و <code>datr</code>)", reply_markup=kb_home())
            return
        st["cook"] = text[:200] + "..."
        st["full_cook"] = text
        gate_prefix = current_state.split("_")[0]
        
        # Different next steps per gate
        if gate_prefix == "dp":
            st["st"] = "dp_page"
            db.set_state(uid, st)
            await message.answer("✅ تم حفظ الكوكيز\n\n🔽 <b>خطوة 3:</b> أدخل Page ID:", reply_markup=kb_home())
        elif gate_prefix == "bp":
            st["st"] = "bp_page"
            db.set_state(uid, st)
            await message.answer("✅ تم حفظ الكوكيز\n\n🔽 <b>خطوة 3:</b> أدخل Page ID:", reply_markup=kb_home())
        elif gate_prefix == "pl":
            st["st"] = "pl_acc"
            db.set_state(uid, st)
            await message.answer("✅ تم حفظ الكوكيز\n\n🔽 <b>خطوة 3:</b> أدخل Account ID (10-20 رقم):", reply_markup=kb_home())
        elif gate_prefix == "ec":
            st["st"] = "ec_acc"
            db.set_state(uid, st)
            await message.answer("✅ تم حفظ الكوكيز\n\n🔽 <b>خطوة 3:</b> أدخل Account ID (10-20 رقم):", reply_markup=kb_home())
        else:  # partner_ship default
            st["st"] = "ps_acc"
            db.set_state(uid, st)
            await message.answer("✅ تم حفظ الكوكيز\n\n🔽 <b>خطوة 3:</b> أدخل Account ID (10-20 رقم):", reply_markup=kb_home())
        return
    
    # ── DARK POST gates ──
    if current_state == "dp_page":
        if not v_id(text):
            await message.answer("❌ Page ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["page_id"] = text.strip()
        st["st"] = "dp_message"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Page ID:</b> {text.strip()}\n\n🔽 <b>خطوة 4:</b> أرسل نص المنشور:", reply_markup=kb_home())
        return
    
    if current_state == "dp_message":
        if len(text) < 5:
            await message.answer("❌ النص قصير جدًا (على الأقل 5 أحرف)", reply_markup=kb_home())
            return
        st["message"] = text
        st["st"] = "dp_link"
        db.set_state(uid, st)
        await message.answer(f"✅ تم حفظ النص\n\n🔽 <b>خطوة 5:</b> أرسل الرابط (اختياري) أو اكتب <code>تخطي</code>:", reply_markup=kb_home())
        return
    
    if current_state == "dp_link":
        if text.lower() == "تخطي" or text.lower() == "skip":
            st["link"] = ""
        elif v_url(text):
            st["link"] = text.strip()
        else:
            await message.answer("❌ رابط غير صحيح. اكتب <code>تخطي</code> أو أرسل رابط صحيح:", reply_markup=kb_home())
            return
        
        st["st"] = "dp_confirm"
        db.set_state(uid, st)
        # Show confirmation
        summary = (
            f"📋 <b>مراجعة Dark Post:</b>\n"
            f"───────────────\n"
            f"📄 Page ID: {st.get('page_id', '')}\n"
            f"💬 النص: {st.get('message', '')[:100]}\n"
            f"🔗 الرابط: {st.get('link', 'بدون')}\n"
            f"🌐 بروكسي: {st.get('px') or 'بدون'}\n"
            f"───────────────"
        )
        await message.answer(summary, reply_markup=kb_confirm())
        return
    
    # ── PARTNER SHIP gates ──
    if current_state == "ps_acc":
        if not v_id(text):
            await message.answer("❌ Account ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["acc"] = text.strip()
        st["st"] = "ps_acode"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Account:</b> {text.strip()}\n\n🔽 <b>خطوة 4:</b> أدخل Ad Code:", reply_markup=kb_home())
        return
    
    if current_state == "ps_acode":
        if len(text) < 5:
            await message.answer("❌ Ad Code قصير جدًا", reply_markup=kb_home())
            return
        st["acode"] = text.strip()
        st["st"] = "ps_obj"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ Ad Code\n\n🔽 <b>خطوة 5:</b> اختر هدف الإعلان:", reply_markup=kb_objectives())
        return
    
    if current_state == "ps_budget":
        ok, val = v_budget(text)
        if not ok:
            await message.answer("❌ الميزانية لازم رقم (1$ - 10,000$)", reply_markup=kb_home())
            return
        st["bgt"] = val
        st["st"] = "ps_days"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>الميزانية:</b> {val}$/يوم\n\n🔽 <b>خطوة التالية:</b> عدد الأيام (1-365):", reply_markup=kb_home())
        return
    
    if current_state == "ps_days":
        ok, val = v_days(text)
        if not ok:
            await message.answer("❌ عدد الأيام لازم رقم (1-365)", reply_markup=kb_home())
            return
        st["days"] = val
        st["st"] = "ps_confirm"
        db.set_state(uid, st)
        summary = (
            f"📋 <b>مراجعة البيانات:</b>\n"
            f"───────────────\n"
            f"🌐 بروكسي: {st.get('px') or 'بدون'}\n"
            f"🔑 Account: {st.get('acc','')}\n"
            f"🎯 Ad Code: {st.get('acode','')}\n"
            f"🎯 الهدف: {OBJ_NAMES.get(st.get('obj',''),'')}\n"
            f"💰 الميزانية: {st.get('bgt',10)}$/يوم\n"
            f"📅 المدة: {val} أيام\n"
            f"───────────────\n"
            f"أكّد لتشغيل الإعلان."
        )
        await message.answer(summary, reply_markup=kb_confirm())
        return
    
    # ── BOOST POST gates ──
    if current_state == "bp_page":
        if not v_id(text):
            await message.answer("❌ Page ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["page_id"] = text.strip()
        st["st"] = "bp_post"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Page ID:</b> {text.strip()}\n\n🔽 <b>خطوة 4:</b> أدخل Post ID:", reply_markup=kb_home())
        return
    
    if current_state == "bp_post":
        if len(text) < 5:
            await message.answer("❌ Post ID قصير جدًا", reply_markup=kb_home())
            return
        st["post_id"] = text.strip()
        st["st"] = "bp_budget"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ Post ID\n\n🔽 <b>خطوة 5:</b> الميزانية اليومية ($):", reply_markup=kb_home())
        return
    
    if current_state == "bp_budget":
        ok, val = v_budget(text)
        if not ok:
            await message.answer("❌ الميزانية لازم رقم (1$ - 10,000$)", reply_markup=kb_home())
            return
        st["bgt"] = val
        st["st"] = "bp_days"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>الميزانية:</b> {val}$/يوم\n\n🔽 <b>خطوة 6:</b> عدد الأيام (1-365):", reply_markup=kb_home())
        return
    
    if current_state == "bp_days":
        ok, val = v_days(text)
        if not ok:
            await message.answer("❌ عدد الأيام لازم رقم (1-365)", reply_markup=kb_home())
            return
        st["days"] = val
        st["st"] = "bp_confirm"
        db.set_state(uid, st)
        summary = (
            f"📋 <b>مراجعة Boost Post:</b>\n"
            f"───────────────\n"
            f"📄 Page ID: {st.get('page_id','')}\n"
            f"📝 Post ID: {st.get('post_id','')}\n"
            f"💰 الميزانية: {st.get('bgt',10)}$/يوم\n"
            f"📅 المدة: {val} أيام\n"
            f"───────────────\n"
            f"أكّد لتشغيل الإعلان."
        )
        await message.answer(summary, reply_markup=kb_confirm())
        return
    
    # ── PAGE LIKE gates ──
    if current_state == "pl_acc":
        if not v_id(text):
            await message.answer("❌ Account ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["acc"] = text.strip()
        st["st"] = "pl_page"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Account:</b> {text.strip()}\n\n🔽 <b>خطوة 4:</b> أدخل Page ID:", reply_markup=kb_home())
        return
    
    if current_state == "pl_page":
        if not v_id(text):
            await message.answer("❌ Page ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["page_id"] = text.strip()
        st["st"] = "pl_budget"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Page ID:</b> {text.strip()}\n\n🔽 <b>خطوة 5:</b> الميزانية اليومية ($):", reply_markup=kb_home())
        return
    
    if current_state == "pl_budget":
        ok, val = v_budget(text)
        if not ok:
            await message.answer("❌ الميزانية لازم رقم (1$ - 10,000$)", reply_markup=kb_home())
            return
        st["bgt"] = val
        st["st"] = "pl_days"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>الميزانية:</b> {val}$/يوم\n\n🔽 <b>خطوة 6:</b> عدد الأيام (1-365):", reply_markup=kb_home())
        return
    
    if current_state == "pl_days":
        ok, val = v_days(text)
        if not ok:
            await message.answer("❌ عدد الأيام لازم رقم (1-365)", reply_markup=kb_home())
            return
        st["days"] = val
        st["st"] = "pl_confirm"
        db.set_state(uid, st)
        summary = (
            f"📋 <b>مراجعة Page Like:</b>\n"
            f"───────────────\n"
            f"🔑 Account: {st.get('acc','')}\n"
            f"📄 Page ID: {st.get('page_id','')}\n"
            f"💰 الميزانية: {st.get('bgt',10)}$/يوم\n"
            f"📅 المدة: {val} أيام\n"
            f"───────────────\n"
            f"أكّد لتشغيل الإعلان."
        )
        await message.answer(summary, reply_markup=kb_confirm())
        return
    
    # ── EVENT CAMPAIGN gates ──
    if current_state == "ec_acc":
        if not v_id(text):
            await message.answer("❌ Account ID غير صحيح (10-20 رقم)", reply_markup=kb_home())
            return
        st["acc"] = text.strip()
        st["st"] = "ec_name"
        db.set_state(uid, st)
        await message.answer(f"✅ <b>Account:</b> {text.strip()}\n\n🔽 <b>خطوة 4:</b> اسم الحدث:", reply_markup=kb_home())
        return
    
    if current_state == "ec_name":
        if len(text) < 3:
            await message.answer("❌ اسم الحدث قصير جدًا", reply_markup=kb_home())
            return
        st["event_name"] = text.strip()
        st["st"] = "ec_desc"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ اسم الحدث\n\n🔽 <b>خطوة 5:</b> وصف الحدث:", reply_markup=kb_home())
        return
    
    if current_state == "ec_desc":
        if len(text) < 10:
            await message.answer("❌ وصف الحدث قصير جدًا (على الأقل 10 أحرف)", reply_markup=kb_home())
            return
        st["event_desc"] = text.strip()
        st["st"] = "ec_start"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ الوصف\n\n🔽 <b>خطوة 6:</b> وقت البداية (YYYY-MM-DD HH:MM):", reply_markup=kb_home())
        return
    
    if current_state == "ec_start":
        st["event_start"] = text.strip()
        st["st"] = "ec_end"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ وقت البداية\n\n🔽 <b>خطوة 7:</b> وقت النهاية (YYYY-MM-DD HH:MM):", reply_markup=kb_home())
        return
    
    if current_state == "ec_end":
        st["event_end"] = text.strip()
        st["st"] = "ec_budget"
        db.set_state(uid, st)
        await message.answer("✅ تم حفظ وقت النهاية\n\n🔽 <b>خطوة 8:</b> الميزانية اليومية ($):", reply_markup=kb_home())
        return
    
    if current_state == "ec_budget":
        ok, val = v_budget(text)
        if not ok:
            await message.answer("❌ الميزانية لازم رقم (1$ - 10,000$)", reply_markup=kb_home())
            return
        st["bgt"] = val
        st["st"] = "ec_confirm"
        db.set_state(uid, st)
        summary = (
            f"📋 <b>مراجعة Event Campaign:</b>\n"
            f"───────────────\n"
            f"🔑 Account: {st.get('acc','')}\n"
            f"🎪 الحدث: {st.get('event_name','')}\n"
            f"📝 الوصف: {st.get('event_desc','')[:50]}...\n"
            f"🕐 البداية: {st.get('event_start','')}\n"
            f"🕐 النهاية: {st.get('event_end','')}\n"
            f"💰 الميزانية: {st.get('bgt',10)}$/يوم\n"
            f"───────────────\n"
            f"أكّد لتشغيل الإعلان."
        )
        await message.answer(summary, reply_markup=kb_confirm())
        return
    
    # ── ADMIN INPUTS ──
    if current_state == "a_gen":
        try:
            h = int(text)
            assert h > 0
        except:
            await message.answer("❌ اكتب رقم ساعات صحيح.", reply_markup=kb_home())
            return
        code = db.gen_code()
        db.create_code(code, h)
        db.clear_state(uid)
        await message.answer(
            f"✅ تم توليد الكود:\n<code>{code}</code>\nالمدة: {h} ساعة",
            reply_markup=kb_admin()
        )
        return
    
    if current_state == "a_set":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 3:
            await message.answer("❌ الصيغة غلط. استخدم: <code>user_id | الاسم | ساعات</code>", reply_markup=kb_home())
            return
        try:
            tid = int(parts[0])
            nm = parts[1]
            h = int(parts[2])
        except:
            await message.answer("❌ user_id والساعات لازم أرقام.", reply_markup=kb_home())
            return
        db.ensure_user(tid)
        u = db.get_user(tid)
        u["cn"] = nm
        db.save_user(tid, u)
        until = db.set_sub(tid, h)
        db.clear_state(uid)
        await message.answer(f"✅ تم ضبط {nm}\nحتى: {until}", reply_markup=kb_admin())
        return
    
    if current_state == "a_rm":
        try:
            tid = int(text)
        except:
            await message.answer("❌ اكتب user_id صحيح.", reply_markup=kb_home())
            return
        u = db.get_user(tid)
        if u:
            u["removed"] = True
            db.save_user(tid, u)
        db.clear_state(uid)
        await message.answer("✅ تم حذف المستخدم.", reply_markup=kb_admin())
        return
    
    if current_state == "a_bc":
        db.clear_state(uid)
        await message.answer("📢 ميزة البث الجماعي قريبًا!", reply_markup=kb_admin())
        return
    
    if current_state == "a_px":
        c = db.add_proxies(text)
        db.clear_state(uid)
        await message.answer(f"✅ تمت إضافة {c} بروكسي.", reply_markup=kb_admin())
        return
    
    # ── Default: send home ──
    sub = db.is_sub(uid)
    u = db.get_user(uid)
    name = (u.get("cn") or u.get("fn") or "مستخدم") if u else "مستخدم"
    status = "✅ مشترك" if sub else "❌ غير مشترك"
    txt = f"⚡ <b>{BOT_NAME}</b>\n\nمرحبًا {name}\nالحالة: {status}\n\nاختر من الأزرار."
    await message.answer(txt, reply_markup=kb_main(sub))


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())