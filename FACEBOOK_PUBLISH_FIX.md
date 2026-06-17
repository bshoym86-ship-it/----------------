# 🔧 حل مشكلة Publish Permissions (#200)

## ❌ المشكلة:
```
فشل رفع الصورة: (#200) This app is not allowed to publish to other users' timelines.
```

---

## 🎯 السبب:

Access Token لا يملك الصلاحيات الكافية لنشر على صفحات Facebook.

### الصلاحيات المطلوبة:
- ✅ `publish_pages` - لإنشاء منشورات Dark Post
- ✅ `pages_read_engagement` - لقراءة بيانات الصفحات
- ✅ `ads_management` - لإدارة الإعلانات

---

## ✅ الحل (خطوة بخطوة):

### 1️⃣ اطلب صلاحيات جديدة
```
https://developers.facebook.com/docs/permissions/reference
```

### 2️⃣ استخدم Facebook Login مع الصلاحيات الصحيحة:
```
https://www.facebook.com/v18.0/dialog/oauth?
client_id=YOUR_APP_ID
&redirect_uri=https://your-domain.com/callback
&scope=publish_pages,pages_read_engagement,ads_management,pages_manage_posts
&response_type=code
```

### 3️⃣ جدّد Access Token:
```bash
# مثال على الحصول على long-lived token
curl -X GET "https://graph.facebook.com/v18.0/oauth/access_token?
client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&
grant_type=fb_exchange_token&
fb_exchange_token=SHORT_LIVED_TOKEN"
```

### 4️⃣ تحقق من الصلاحيات:
```bash
# تحقق من الصلاحيات المتوفرة
curl "https://graph.facebook.com/me/permissions?access_token=YOUR_TOKEN"
```

---

## 🛡️ التحسينات في الكود:

### ✨ ما تم تحسينه:

1. **معالجة أفضل للأخطاء**:
   - الكود يكتشف الآن خطأ #200 ويعطيك رسالة واضحة

2. **التحقق من الصلاحيات**:
   - عند التحقق من التوكن، يتم عرض تحذير إذا كانت `publish_pages` غير موجودة

3. **رسائل توجيهية**:
   - عند الفشل، تظهر تعليمات واضحة للحل

---

## 📝 مثال على الاستخدام:

```python
# التوكن يجب أن يحتوي على الصلاحيات التالية:
# - publish_pages
# - pages_read_engagement  
# - ads_management

# ثم استخدمه في البوت:
# /start
# اختر Dark Post
# أرسل التوكن الجديد
```

---

## 🔗 مراجع مفيدة:

- [Facebook Graph API - Permissions](https://developers.facebook.com/docs/permissions)
- [Publish Pages Permission](https://developers.facebook.com/docs/permissions/reference/publish_pages)
- [Access Tokens](https://developers.facebook.com/docs/facebook-login/access-tokens)
- [Long-Lived Access Tokens](https://developers.facebook.com/docs/facebook-login/access-tokens/refreshing)

---

## 🆘 إذا استمرت المشكلة:

1. ✅ تأكد من أن الصفحة تابعة لحسابك
2. ✅ تأكد من أن التطبيق موافق عليه من Facebook
3. ✅ جرّب في مرحلة التطوير أولاً (Development)
4. ✅ تحقق من أن الصفحة لا محظورة

---

**آخر تحديث**: 2026-06-17
