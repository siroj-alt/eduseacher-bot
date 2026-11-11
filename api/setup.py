import asyncio
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402
from aiogram.types import BotCommand  # noqa: E402

log = logging.getLogger("setup")


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
    def _reply(self, code: int, body: str) -> None:
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        secret = os.environ.get("WEBHOOK_SECRET", "")
        key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        if not secret or key != secret:
            self._reply(403, "forbidden")
            return
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        try:
            result = asyncio.run(configure(f"https://{host}/api/webhook"))
            self._reply(200, result)
        except Exception as exc:
            log.exception("Webhook o'rnatishda xatolik")
            self._reply(500, f"xatolik: {type(exc).__name__}")
