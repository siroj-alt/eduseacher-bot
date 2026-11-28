"""Dispetcherni yig'adi: asosiy handlerlar -> qo'shimcha imkoniyatlar -> eng oxirida umumiy (fallback) handlerlar."""
from typing import Optional

from aiogram import Bot

from bot_handlers import dp, fallback  # noqa: F401
import features

dp.include_router(features.router)
dp.include_router(fallback)


def make_bot(token: str, session=None) -> Bot:
    """Barcha xabarlar standart holda HTML rejimida (aiogram 3.4 va yangi versiyalar bilan mos)."""
    try:
        from aiogram.client.default import DefaultBotProperties  # aiogram >= 3.7
        return Bot(token=token, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    except ImportError:
        return Bot(token=token, session=session, parse_mode="HTML")
