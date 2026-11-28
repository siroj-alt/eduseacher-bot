import asyncio
import hmac
import json
import time
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter  # noqa: E402
from aiogram.types import (  # noqa: E402
    BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Update, WebAppInfo,
)

from app import dp, make_bot  # noqa: E402
from db import DB  # noqa: E402
from kb import WEB_APP_URL  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="menu", description="Bosh menyu"),
    BotCommand(command="find", description="Markaz topish"),
    BotCommand(command="near", description="Yaqin markazlar"),
    BotCommand(command="saved", description="Saqlanganlar"),
    BotCommand(command="applications", description="Arizalarim"),
    BotCommand(command="share", description="Do'stlarga ulashish"),
    BotCommand(command="profile", description="Profil"),
    BotCommand(command="test", description="Ingliz tili daraja testi"),
    BotCommand(command="family", description="Farzandim uchun"),
    BotCommand(command="owner", description="Markaz egasi paneli"),
    BotCommand(command="lang", description="Til / Язык"),
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="cancel", description="Jarayonni bekor qilish"),
]


async def process_update(data: dict) -> None:
    bot = make_bot(os.environ["BOT_TOKEN"])
    try:
        async with aiohttp.ClientSession() as http:
            update = Update.model_validate(data, context={"bot": bot})
            await dp.feed_update(bot, update, db=DB(http))
    finally:
        await bot.session.close()


async def configure(webhook_url: str) -> str:
    bot = make_bot(os.environ["BOT_TOKEN"])
    try:
        me = await bot.get_me()
        await bot.set_webhook(
            url=webhook_url,
            secret_token=os.environ.get("WEBHOOK_SECRET") or None,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"],
        )
        await bot.set_my_commands(COMMANDS)
        # Chat yonidagi menyu tugmasi ham Web App (edusearcher.uz) ni ochadi
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="EduSearcher", web_app=WebAppInfo(url=WEB_APP_URL))
        )
        info = await bot.get_webhook_info()
        return (f"Webhook o'rnatildi: {info.url} (pending: {info.pending_update_count}, "
                f"bot: @{me.username}, buyruqlar: {len(COMMANDS)})")
    finally:
        await bot.session.close()


async def selftest() -> str:
    from selftest import run_selftest

    async with aiohttp.ClientSession() as http:
        report = await run_selftest(DB(http))
    # Haqiqiy Telegram tokenini ham tekshiramiz (xabar yubormaydi)
    bot = make_bot(os.environ["BOT_TOKEN"])
    try:
        me = await bot.get_me()
        info = await bot.get_webhook_info()
        tg = (f"[ OK ] Telegram: @{me.username}, webhook={info.url}, pending={info.pending_update_count}, "
              f"xato={info.last_error_message or '-'}")
        try:
            from bot_handlers import CHANNEL
            chat = await bot.get_chat(CHANNEL)
            mem = await bot.get_chat_member(CHANNEL, me.id)
            if mem.status in ("administrator", "creator"):
                tg += f"\n[ OK ] Kanal {CHANNEL} ({chat.title}): bot admin — majburiy obuna ISHLAYDI"
            else:
                tg += f"\n[WARN] Kanal {CHANNEL}: bot admin EMAS (status={mem.status}) — majburiy obuna ishlamaydi, botni kanalga ADMIN qiling"
        except Exception as exc:  # noqa: BLE001
            tg += f"\n[WARN] Kanal tekshiruvi: {type(exc).__name__}: {exc} — botni kanalga ADMIN qiling"
    except Exception as exc:  # noqa: BLE001
        tg = f"[FAIL] Telegram: {type(exc).__name__}"
    finally:
        await bot.session.close()
    env = (f"BOT_API_SECRET={'bor' if os.environ.get('BOT_API_SECRET') else 'YO`Q'}, "
           f"ADMIN_CHAT_ID={'bor' if os.environ.get('ADMIN_CHAT_ID') else 'yo`q (ixtiyoriy)'}")
    return f"{tg}\n{env}\n{report}"


async def notify() -> str:
    """Bazadagi navbatdagi bildirishnomalarni yuboradi (yangi so'rov, 24 soatlik eslatma,
    haftalik hisobot, 14 kundan keyin o'quvchiga savol). Har soatda pg_cron chaqiradi."""
    async with aiohttp.ClientSession() as http:
        items = await DB(http).collect_notifications()
    if not items:
        return "sent=0"
    bot = make_bot(os.environ["BOT_TOKEN"])
    sent = failed = 0
    started = time.monotonic()
    unsent: list = []
    try:
        for idx, it in enumerate(items):
            if time.monotonic() - started > 45:
                unsent = items[idx:]
                log.warning("Vaqt tugadi, %s ta xabar keyingi safarga qoldirildi", len(unsent))
                break
            chat_id, text = it.get("chat_id"), it.get("text")
            if not chat_id or not text:
                continue
            markup = None
            rows = []
            for row in it.get("buttons") or []:
                btns = []
                for b in row:
                    if not b.get("text"):
                        continue
                    if b.get("url"):
                        btns.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
                    elif b.get("data"):
                        btns.append(InlineKeyboardButton(text=b["text"], callback_data=b["data"]))
                if btns:
                    rows.append(btns)
            if rows:
                markup = InlineKeyboardMarkup(inline_keyboard=rows)
            for attempt in (1, 2):
                try:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML",
                                           reply_markup=markup, disable_web_page_preview=True)
                    sent += 1
                    break
                except TelegramRetryAfter as exc:
                    if attempt == 2:
                        failed += 1
                        break
                    await asyncio.sleep(min(exc.retry_after, 10))
                except TelegramForbiddenError:
                    failed += 1  # foydalanuvchi botni bloklagan
                    break
                except Exception:  # noqa: BLE001
                    log.exception("Bildirishnoma yuborilmadi (chat %s)", chat_id)
                    failed += 1
                    break
            await asyncio.sleep(0.05)
    finally:
        await bot.session.close()
    if unsent:
        try:
            async with aiohttp.ClientSession() as http:
                await DB(http).requeue(unsent)
        except Exception:  # noqa: BLE001
            log.exception("Yuborilmay qolgan xabarlarni qayta navbatga qo'yib bo'lmadi")
    return f"sent={sent} failed={failed} total={len(items)} requeued={len(unsent)}"


async def daily(dry: bool = False) -> str:
    """Kanalga kunlik post (pg_cron har kuni 09:00 Toshkent vaqti)."""
    from daily import run_daily

    bot = make_bot(os.environ["BOT_TOKEN"])
    try:
        async with aiohttp.ClientSession() as http:
            return await run_daily(bot, DB(http), dry=dry)
    finally:
        await bot.session.close()


class handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, body: str = "ok") -> None:
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path in ("/api/notify", "/api/daily") or self.headers.get("X-Notify-Key"):
            secret = os.environ.get("BOT_API_SECRET", "")
            given = self.headers.get("X-Notify-Key", "")
            if not secret or not hmac.compare_digest(given, secret):
                self._reply(403, "forbidden")
                return
            try:
                if path == "/api/daily":
                    self._reply(200, asyncio.run(daily()))
                else:
                    self._reply(200, asyncio.run(notify()))
            except Exception as exc:  # noqa: BLE001
                log.exception("Bildirishnomalar xatoligi")
                self._reply(500, f"xatolik: {type(exc).__name__}")
            return
        query = parse_qs(parsed.query)
        key = query.get("key", [""])[0]
        if not key:
            self._reply(200, "EduSearcher bot webhook is running")
            return
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if not secret or key != secret:
            self._reply(403, "forbidden")
            return
        try:
            if query.get("daily", [""])[0] == "dry":
                self._reply(200, asyncio.run(daily(dry=True)))
                return
            if query.get("selftest", [""])[0] == "1":
                self._reply(200, asyncio.run(selftest()))
                return
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
            self._reply(200, asyncio.run(configure(f"https://{host}/api/webhook")))
        except Exception as exc:
            log.exception("Setup/selftest xatoligi")
            self._reply(500, f"xatolik: {type(exc).__name__}: {exc}")

    def do_POST(self):
        secret = os.environ.get("WEBHOOK_SECRET")
        if secret and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
            self._reply(403, "forbidden")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            asyncio.run(process_update(data))
        except Exception:
            # Telegram qayta-qayta yubormasligi uchun baribir 200 qaytaramiz
            log.exception("Update qayta ishlashda xatolik")
        self._reply(200)
