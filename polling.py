"""Lokal ishga tushirish (polling). Vercel'da esa api/index.py ishlaydi.

Ishlatish:
    BOT_TOKEN=... BOT_API_SECRET=... python polling.py
"""
import asyncio
import logging
import os

import aiohttp
from aiogram import Bot

from bot_handlers import dp
from db import DB


async def main():
    logging.basicConfig(level=logging.INFO)
    token = os.environ["BOT_TOKEN"]
    bot = Bot(token=token)
    # Webhook o'rnatilgan bo'lsa, polling ishlashi uchun uni o'chirib qo'yamiz
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi (polling)...")
    async with aiohttp.ClientSession() as http:
        await dp.start_polling(bot, db=DB(http))


if __name__ == "__main__":
    asyncio.run(main())
