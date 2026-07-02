# 📚 Ingliz tili Online Kurslar Bot

Aiogram v3 + PostgreSQL asosida qurilgan to'liq avtomatlashtirilgan kurs sotish bot tizimi.

---

## 🚀 Railway ga Deploy qilish

### 1. GitHub ga push qiling
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/SIZNING_USERNAME/SIZNING_REPO.git
git push -u origin main
```

### 2. Railway da yangi loyiha yarating
1. [railway.app](https://railway.app) ga kiring
2. **New Project** → **Deploy from GitHub repo** → repo ni tanlang
3. **Add Plugin** → **PostgreSQL** qo'shing

### 3. Environment Variables qo'shing
Railway dashboard → Variables bo'limiga quyidagilarni kiriting:

| Kalit | Qiymat |
|-------|--------|
| `BOT_TOKEN` | Botning token raqami |
| `SUPER_ADMIN_IDS` | Admin Telegram IDlari (vergul bilan) |
| `REFERRAL_BONUS` | Referal bonus (masalan: 20000) |
| `MIN_WITHDRAWAL` | Minimal yechish (masalan: 50000) |
| `WEBHOOK_URL` | Ixtiyoriy. Agar bo'sh bo'lsa, Railway avtomatik `RAILWAY_PUBLIC_DOMAIN` dan oladi |
| `WEBHOOK_PATH` | Webhook yo'li (masalan: `/webhook`) |
| `WEBHOOK_SECRET` | Webhook secret token (ixtiyoriy, lekin tavsiya etiladi) |

> **`DATABASE_URL`** ni yozmang — Railway PostgreSQL qo'shganda avtomatik to'ldiriladi!

### 4. Deploy
Variables kiritilgandan keyin Railway avtomatik deploy qiladi.

---

## 💻 Lokal ishga tushirish

```bash
pip install -r requirements.txt
cp .env.example .env
# .env faylni to'ldiring
python main.py
```

---

## 📱 Bot funksionalligi

### Foydalanuvchi uchun:
- 📚 Bir yoki bir nechta kurs tanlash (chegirma tizimi bilan)
- 💳 To'lov kartalari orqali to'lash
- 🎓 Mening kurslarim — tasdiqlangan kurslar + kanal havolasi
- 👥 Referal tizim — do'st taklif qilish va bonus yig'ish

### Admin uchun:
- 📊 Statistika (foydalanuvchilar, sotuvlar, daromad)
- ✅ To'lovlarni tasdiqlash/rad etish
- 💸 Pul yechish so'rovlari (chek rasm bilan)
- 📚 Kurslar CRUD
- 💳 To'lov kartalari boshqaruvi
- 🎁 Chegirma qoidalari (bundle)
- 📢 Homiy kanallar
- 📣 Broadcast xabar yuborish
- 👮 Admin qo'shish/o'chirish
- ⚙️ Sozlamalar (bonus, yechish, FAQ, kurs sahifasi matni)

---

## ⚙️ Sozlamalar (.env)

```env
BOT_TOKEN=bot_token
DATABASE_URL=postgresql+asyncpg://...   # Railway avtomatik beradi
SUPER_ADMIN_IDS=123456789,987654321      # Vergul bilan ajrating
REFERRAL_BONUS=20000                     # So'mda
MIN_WITHDRAWAL=50000                     # So'mda
```
