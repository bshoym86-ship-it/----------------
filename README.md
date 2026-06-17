# 🚀 دليل رفع البوت على Railway (خطوة بخطوة)

## 📋 الملفات اللي عندك دلوقتي

| الملف | وظيفته |
|------|--------|
| `beshoy_bot.py` | الكود الرئيسي (مظبوط ومصلّح) |
| `requirements.txt` | مكتبات بايثون |
| `Procfile` | بيقول لـ Railway إزاي يشغّل البوت |
| `Dockerfile` | لو Railway اختار Docker mode |
| `railway.json` | إعدادات Railway (healthcheck + restart) |
| `.dockerignore` | منع رفع ملفات حساسة للـ image |
| `.env.example` | قالب المتغيرات — نسخة للمرجعية |

---

## ✅ الخطوات على Railway

### 1) اعمل حساب
- ادخل [railway.app](https://railway.app)
- اعمل تسجيل دخول بـ GitHub

### 2) ارفع الكود على GitHub
- اعمل repository جديد على GitHub (مثلاً `beshoy-bot`)
- ارفع **كل** ملفات المشروع (بدون `dump.rdb` وبدون `.env`)

### 3) اعمل مشروع جديد على Railway
- على Railway اضغط **New Project**
- اختار **Deploy from GitHub repo**
- اختار الـ repo بتاعك

### 4) ضيف Redis
- في صفحة المشروع، اضغط **+ New** (يسار فوق)
- اختار **Database** → **Add Redis**
- Railway هيضيف Redis ويديك رابط تلقائي

### 5) ظبط المتغيرات (Variables)
- ادخل على خدمة الـ bot (مش Redis)
- روح على tab **Variables**
- ضيف المتغيرات دي:

```
TELEGRAM_BOT_TOKEN = (التوكن من BotFather)
ADMIN_PASS = (كلمة مرور قوية جديدة، مش Nemo@1986)
SUPPORT_URL = https://t.me/username_الدعم
WEBHOOK_URL = (هتاخده من الخطوة 7)
WEBHOOK_SECRET = (32 حرف عشوائي — استخدم generator زي: https://generate-random.org/api-key-generator)
REDIS_URL = (انسخه من خدمة Redis على Railway → Connect → Redis Connection URL)
```

### 6) أول Deploy
- Railway هيبدأ deploy أوتوماتيك
- استنى 2-3 دقايق
- لما يخلّص، اضغط على خدمة الـ bot → **Settings** → **Networking** → **Generate Domain**
- هيديك رابط زي: `https://beshoy-bot-production.up.railway.app`
- ده هو الـ `WEBHOOK_URL`

### 7) رجع ظبط WEBHOOK_URL
- ارجع لـ **Variables** على خدمة الـ bot
- ضيف `WEBHOOK_URL = https://beshoy-bot-production.up.railway.app` (الرابط اللي أخدته)
- Railway هيعمل redeploy أوتوماتيك

### 8) فعّل الـ webhook على تيليجرام (تلقائي!)
- البوت دلوقتي هيـسجّل الـ webhook أوتوماتيك لما يشتغل
- لو عايز تتأكد، افتح في المتصفح:
  ```
  https://beshoy-bot-production.up.railway.app/health
  ```
  لازم يرجّع: `{"status":"healthy", ...}`

### 9) جرّب البوت
- افتح تيليجرام وبعت `/start` للبوت
- لو ردّ عليك بالأزرار → مبروك، البوت شغّال 🎉

---

## 🧪 جرّب إعلان فيسبوك (الاختبار الحقيقي)

1. كبّ `/start` ثم **🎟 تفعيل كود**
2. لازم يكون عندك كود — اعمل أدمن:
   - ابعت `/beshoy` للبوت
   - اكتب كلمة المرور (اللي في `ADMIN_PASS`)
   - اختار **🎟 توليد كود** واكتب عدد الساعات (مثلاً `24`)
   - البوت هيديك كود — انسخه
3. ارجع كبّ `/start` ثم **🎟 تفعيل كود** والصق الكود
4. دلوقتي زرار **🚀 إعلان جديد** هيظهر
5. جرّب أي بوابة (مثلاً Dark Post)
6. لو وصلت لرسالة "✅ تم إنشاء الإعلان" → البوت شغّال 100%

---

## ⚠️ لو فيه مشاكل

### البوت مبيردّش على `/start`
- على Railway → خدمة الـ bot → **Logs**
- ادوّر على `🔔 Webhook registered: {'ok': True...}`
- لو `WEBHOOK_URL` فاضي → اتبع الخطوة 7

### إعلان فيسبوك بيرجّع error
- على Railway → **Logs**
- ادوّر على `Callback error` أو `Facebook API`
- لو الخطأ في التوكن → التوكن غلط أو منتهي
- لو الخطأ `proxies=` → ميزبطش الـ deploy (نزّل أحدث نسخة)

### Redis مبي respond-ش
- على Railway → خدمة Redis → **Logs**
- تأكد إن `REDIS_URL` في Variables الـ bot مطابق لـ Redis Connection URL

---

## 🔒 نصائح أمنية مهمة

1. **غيّر `ADMIN_PASS`** فوراً — متسيّبهوش `Nemo@1986`
2. **`WEBHOOK_SECRET`** مهم جداً — بدونه أي حد يقدر يبعت updates مزيفة لبوتك
3. **متشاركش `TELEGRAM_BOT_TOKEN`** مع حد
4. لو حسّيت إن التوكن اتسرق → من BotFather اكتب `/revoke` وضمّن توكن جديد
5. راجع Redis Logs من فترة لفترة — يفترض ميكونش فيه اتصالات غريبة

---

## 📦 لو عايز تشغّله محلياً (اختياري)

```bash
# 1. ثبت Redis محلياً (أو استخدم Docker)
docker run -d -p 6379:6379 redis:7-alpine

# 2. ظبط .env
cp .env.example .env
# عدّل القيم

# 3. شغّل
pip install -r requirements.txt
python beshoy_bot.py
```

وللاختبار بدون webhook (polling mode مؤقت):
```bash
python -c "import asyncio; from beshoy_bot import polling_loop; asyncio.run(polling_loop())"
```

---

## ✅ خلاصة اللي اتعمل

- ✅ اتصلّح bug الـ httpx (`proxies=` → `proxy=`) → **كل بوابات فيسبوك الـ 5 هتشتغل**
- ✅ اتفصل polling (مفيش duplicate execution)
- ✅ اتضاف Redis retry في الـ startup
- ✅ اتضاف auto-registration للـ webhook
- ✅ اتضاف `WEBHOOK_SECRET` verification
- ✅ اتضاف TTL=30min على state (مفيش توكنات تفضل لالأبد في Redis)
- ✅ اتضاف `PORT` env (Railway بيطلبه)
- ✅ اتضاف `railway.json` + `Procfile` + `.dockerignore` + `.env.example`
- ✅ اتضاف healthcheck endpoint

البوت جاهز للرفع. لو احتجت مساعدة في أي خطوة قولي.
