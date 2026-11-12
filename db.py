"""Supabase (edusearcher.uz bazasi) bilan ishlash qatlami.

Bot faqat ochiq (anon/publishable) kalit bilan ishlaydi:
- ommaviy ma'lumotlar (markazlar, kurslar, yo'nalishlar, viloyatlar) RLS orqali o'qiladi;
- yozish/shaxsiy amallar `bot_*` funksiyalari orqali, BOT_API_SECRET bilan himoyalangan;
- ariza/sharh/statistika uchun saytning o'z funksiyalari (submit_lead, submit_review, track_event).
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

import aiohttp

log = logging.getLogger("bot.db")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xmdxmfvrzbfjursksfhv.supabase.co").rstrip("/")
# Bu kalit ochiq (saytning brauzer kodida ham bor), shuning uchun standart qiymat sifatida qoldirildi.
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_BVrfkdIa6RfE2vCD761KUg_YG4Rn51u")

# Baza bo'sh turgan paytda ham ishlashi uchun zaxira ro'yxatlar
FALLBACK_REGIONS = [
    (1, "Toshkent shahri"), (2, "Toshkent viloyati"), (3, "Samarqand"), (4, "Buxoro"),
    (5, "Farg'ona"), (6, "Andijon"), (7, "Namangan"), (8, "Xorazm"), (9, "Qashqadaryo"),
    (10, "Surxondaryo"), (11, "Navoiy"), (12, "Jizzax"), (13, "Sirdaryo"), (14, "Qoraqalpog'iston"),
]
FALLBACK_CATEGORIES = [
    (1, "Ingliz tili"), (2, "Rus tili"), (3, "Dasturlash (IT)"), (4, "Matematika"), (5, "IELTS"),
    (6, "Xitoy tili"), (7, "Koreys tili"), (8, "Nemis tili"), (9, "Arab tili"), (10, "SAT"),
    (11, "Kimyo"), (12, "Biologiya"), (13, "Tarix"), (14, "Huquq"), (15, "Fizika"),
    (16, "Ona tili va adabiyot"), (17, "Kiberxavfsizlik"), (18, "Sun'iy intellekt"),
    (19, "Tarmoq administratorligi"), (20, "Video montaj"), (21, "Grafik dizayn"),
    (22, "SMM va marketing"), (23, "Robototexnika"), (24, "Buxgalteriya"), (25, "Mental arifmetika"),
    (26, "Turk tili"), (27, "Yapon tili"), (28, "Fransuz tili"), (29, "Kompyuter savodxonligi"),
]

_CACHE: dict = {}
_CACHE_TTL = 600  # soniya


class DBError(Exception):
    """Baza xatosi. user_visible=True bo'lsa, xabar foydalanuvchiga ko'rsatilishi mumkin."""

    def __init__(self, message: str, user_visible: bool = False):
        super().__init__(message)
        self.user_visible = user_visible


def _secret() -> str:
    return os.environ.get("BOT_API_SECRET", "")


class DB:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    # ---------- past darajadagi so'rovlar ----------
    async def _request(self, method: str, path: str, *, json_body: Any = None, params: Optional[dict] = None) -> Any:
        url = f"{SUPABASE_URL}/rest/v1/{path}"
        headers = {"apikey": SUPABASE_KEY, "Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        last_exc: Optional[Exception] = None
        for attempt in (1, 2):
            try:
                async with self.session.request(
                    method, url, json=json_body, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 500 and attempt == 1:
                        continue
                    if resp.status >= 400:
                        message, code = text[:200], ""
                        try:
                            err = json.loads(text)
                            message = err.get("message") or message
                            code = err.get("code") or ""
                        except ValueError:
                            pass
                        # RAISE EXCEPTION (P0001) — saytdagidek foydalanuvchiga ko'rsatiladigan xabarlar
                        raise DBError(message, user_visible=(code == "P0001"))
                    return json.loads(text) if text else None
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt == 2:
                    break
        log.error("Baza bilan aloqa xatosi: %r", last_exc)
        raise DBError("Baza bilan aloqa o'rnatilmadi")

    async def rpc(self, fn: str, params: Optional[dict] = None) -> Any:
        return await self._request("POST", f"rpc/{fn}", json_body=params or {})

    async def _srpc(self, fn: str, params: dict) -> Any:
        """Maxfiy kalit bilan himoyalangan funksiya."""
        return await self.rpc(fn, {"p_secret": _secret(), **params})

    # ---------- ma'lumotnomalar (kesh bilan) ----------
    async def _cached(self, key: str, path: str, params: dict, fallback: list) -> list:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return hit[1]
        try:
            rows = await self._request("GET", path, params=params)
            data = [(int(r["id"]), r["name"]) for r in rows or []]
            if data:
                _CACHE[key] = (time.time(), data)
                return data
        except DBError:
            log.warning("%s ro'yxatini olib bo'lmadi, zaxira ishlatildi", key)
        return hit[1] if hit else fallback

    async def categories(self) -> list:
        return await self._cached("cats", "categories", {"select": "id,name", "order": "id"}, FALLBACK_CATEGORIES)

    async def regions(self) -> list:
        return await self._cached("regs", "regions", {"select": "id,name", "order": "id"}, FALLBACK_REGIONS)

    # ---------- foydalanuvchi ----------
    async def ctx(self, tg: int, name: Optional[str], username: Optional[str], ref: Optional[int] = None) -> dict:
        res = await self._srpc("bot_ctx", {"p_tg": tg, "p_name": name, "p_username": username, "p_ref": ref})
        if not isinstance(res, dict):
            raise DBError("bot_ctx javobi noto'g'ri")
        if not isinstance(res.get("session"), dict):
            res["session"] = {}
        return res

    async def patch_user(self, tg: int, patch: dict) -> None:
        await self._srpc("bot_patch_user", {"p_tg": tg, "p_patch": patch})

    async def set_session(self, tg: int, session: dict) -> None:
        await self._srpc("bot_set_session", {"p_tg": tg, "p_session": session})

    # ---------- markazlar ----------
    async def list_centers(self, *, region=None, category=None, level=None, q=None,
                           lat=None, lng=None, limit=6, offset=0) -> dict:
        res = await self.rpc("bot_list_centers", {
            "p_region": region, "p_category": category, "p_level": level, "p_q": q,
            "p_lat": lat, "p_lng": lng, "p_limit": limit, "p_offset": offset,
        })
        if not isinstance(res, dict):
            return {"total": 0, "items": []}
        res.setdefault("items", [])
        res["total"] = int(res.get("total") or 0)
        return res

    async def center_card(self, tg: int, center_id: str) -> Optional[dict]:
        res = await self._srpc("bot_center_card", {"p_tg": tg, "p_center": center_id})
        return res if isinstance(res, dict) else None

    async def stats(self) -> dict:
        res = await self.rpc("bot_stats")
        return res if isinstance(res, dict) else {}

    # ---------- saqlanganlar, arizalar, sharhlar ----------
    async def toggle_favorite(self, tg: int, center_id: str) -> bool:
        return bool(await self._srpc("bot_toggle_favorite", {"p_tg": tg, "p_center": center_id}))

    async def favorites(self, tg: int) -> list:
        res = await self._srpc("bot_favorites", {"p_tg": tg})
        return res if isinstance(res, list) else []

    async def my_leads(self, tg: int) -> list:
        res = await self._srpc("bot_my_leads", {"p_tg": tg})
        return res if isinstance(res, list) else []

    async def submit_lead(self, tg: int, center_id: str, name: str, phone: str,
                          course: Optional[str], note: Optional[str], tg_name: Optional[str] = None) -> Any:
        # Saytdagi "O'qishga ariza" bilan bir xil jadvalga (applications) yoziladi:
        # bosh admin paneli va markaz paneli "Arizalar" bo'limida (manba: Telegram bot) ko'rinadi.
        return await self._srpc("bot_submit_application", {
            "p_tg": tg, "p_center": center_id, "p_name": name, "p_phone": phone,
            "p_course_name": course, "p_note": note,
        })

    async def submit_review(self, tg: int, center_id: str, name: str, stars: int, comment: Optional[str]) -> Any:
        return await self.rpc("submit_review", {
            "p_center": center_id, "p_name": name, "p_stars": stars,
            "p_comment": comment, "p_visitor": f"tg:{tg}",
        })

    async def track(self, kind: str, center_id: Optional[str], tg: int) -> None:
        try:
            await self.rpc("track_event", {
                "p_kind": kind, "p_center": center_id, "p_visitor": f"tg:{tg}", "p_path": "/bot",
            })
        except DBError:
            log.warning("track_event yozilmadi")
