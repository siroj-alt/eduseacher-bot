import asyncio
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.types import BotCommand, MenuButtonWebApp, Update, WebAppInfo  # noqa: E402

from bot_handlers import dp  # noqa: E402
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
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="cancel", description="Jarayonni bekor qilish"),
]


async def process_update(data: dict) -> None:
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        async with aiohttp.ClientSession() as http:
            update = Update.model_validate(data, context={"bot": bot})
            await dp.feed_update(bot, update, db=DB(http))
    finally:
        await bot.session.close()


async def configure(webhook_url: str) -> str:
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        me = await bot.get_me()
        await bot.set_webhook(
            url=webhook_url,
            secret_token=os.environ.get("WEBHOOK_SECRET") or None,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
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
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        me = await bot.get_me()
        info = await bot.get_webhook_info()
        tg = (f"[ OK ] Telegram: @{me.username}, webhook={info.url}, pending={info.pending_update_count}, "
              f"xato={info.last_error_message or '-'}")
    except Exception as exc:  # noqa: BLE001
        tg = f"[FAIL] Telegram: {type(exc).__name__}"
    finally:
        await bot.session.close()
    env = (f"BOT_API_SECRET={'bor' if os.environ.get('BOT_API_SECRET') else 'YO`Q'}, "
           f"ADMIN_CHAT_ID={'bor' if os.environ.get('ADMIN_CHAT_ID') else 'yo`q (ixtiyoriy)'}")
    return f"{tg}\n{env}\n{report}"


class handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, body: str = "ok") -> None:
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        key = query.get("key", [""])[0]
        if not key:
            self._reply(200, "EduSearcher bot webhook is running")
            return
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if not secret or key != secret:
            self._reply(403, "forbidden")
            return
        try:
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
