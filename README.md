# eduseacher-bot

EduSearcher.uz Telegram boti (aiogram 3), Vercel'da webhook orqali ishlaydi.

## Vercel Environment Variables
- `BOT_TOKEN` — BotFather'dan olingan token
- `WEBHOOK_SECRET` — tasodifiy maxfiy qator (Telegram so'rovlarini tekshirish va `/api/setup` himoyasi uchun)
- `WEB_APP_URL` — (ixtiyoriy) standart: `https://edusearcher.uz`

## Deploydan keyin
Bir marta `https://<domen>/api/setup?key=<WEBHOOK_SECRET>` manzilini oching — webhook va bot buyruqlari o'rnatiladi.

## Lokal ishga tushirish
```
pip install -r requirements.txt
BOT_TOKEN=... python main.py
```
