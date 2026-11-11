import asyncio
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402
from aiogram.types import BotCommand, Update  # noqa: E402

from bot_handlers import dp  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")


async def process_update(data: dict) -> None:
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()


async def configure(webhook_url: str) -> str:
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=os.environ.get("WEBHOOK_SECRET") or None,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Botni ishga tushirish"),
                BotCommand(command="help", description="Yordam"),
                BotCommand(command="about", description="EduSearcher haqida"),
            ]
        )
        info = await bot.get_webhook_info()
        return f"Webhook o'rnatildi: {info.url} (pending: {info.pending_update_count})"
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
        key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        if not key:
            self._reply(200, "EduSearcher bot webhook is running")
            return
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if not secret or key != secret:
            self._reply(403, "forbidden")
            return
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        try:
            self._reply(200, asyncio.run(configure(f"https://{host}/api/webhook")))
        except Exception as exc:
            log.exception("Webhook o'rnatishda xatolik")
            self._reply(500, f"xatolik: {type(exc).__name__}")

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
