"""Matnlarni formatlash (aiogramga bog'liq emas)."""
import html
import math
import re
from typing import Optional

PAGE_SIZE = 6
MAX_LEN = 3900  # Telegram limiti 4096

LEVEL_CODES = {"b": "beginner", "i": "intermediate", "a": "advanced"}
LEVEL_NAMES = {
    "beginner": "Boshlang'ich", "intermediate": "O'rta", "advanced": "Yuqori",
    "b": "Boshlang'ich", "i": "O'rta", "a": "Yuqori",
}


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def clip(text: Optional[str], n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def fmt_price(value) -> Optional[str]:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n:,}".replace(",", " ") + " so'm"


def fmt_rating(value) -> str:
    try:
        r = float(value)
    except (TypeError, ValueError):
        return ""
    return f"⭐ {r:.1f}" if r > 0 else ""


def fmt_km(value) -> str:
    try:
        km = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{int(round(km * 1000))} m" if km < 1 else f"{km:.1f} km"


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- kontakt ma'lumotlarini tozalash ----------
def normalize_phone(text: Optional[str]) -> Optional[str]:
    """'+998901234567' ko'rinishiga keltiradi; noto'g'ri bo'lsa None."""
    digits = re.sub(r"\D", "", str(text or ""))
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) < 9 or len(digits) > 15:
        return None
    return "+" + digits


def _clean(value: Optional[str]) -> str:
    return str(value or "").strip()


def website_url(value: Optional[str]) -> Optional[str]:
    v = _clean(value)
    if not v or " " in v:
        return None
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    return v if re.match(r"^https?://[^/\s]+\.[^/\s]+", v, re.I) else None


def telegram_url(value: Optional[str]) -> Optional[str]:
    v = _clean(value)
    if not v or " " in v:
        return None
    if re.match(r"^https?://", v, re.I):
        return v
    if re.match(r"^(www\.)?(t\.me|telegram\.me)/", v, re.I):
        return "https://" + v
    v = v.lstrip("@")
    return f"https://t.me/{v}" if re.match(r"^[A-Za-z0-9_]{4,}$", v) else None


def instagram_url(value: Optional[str]) -> Optional[str]:
    v = _clean(value)
    if not v or " " in v:
        return None
    if re.match(r"^https?://", v, re.I):
        return v
    if re.match(r"^(www\.)?instagram\.com/", v, re.I):
        return "https://" + v
    v = v.lstrip("@")
    return f"https://instagram.com/{v}" if re.match(r"^[A-Za-z0-9._]{2,}$", v) else None


# ---------- ro'yxat ----------
def list_title(qd: dict, cat_names: dict, reg_names: dict) -> str:
    kind = qd.get("k")
    cat = cat_names.get(qd.get("cat")) if qd.get("cat") else None
    lvl = LEVEL_NAMES.get(qd.get("lvl")) if qd.get("lvl") else None
    if kind == "q":
        return f"🔎 <b>«{esc(clip(qd.get('q'), 40))}»</b> bo'yicha natijalar"
    if kind == "reg":
        return f"🏢 <b>{esc(reg_names.get(qd.get('reg'), 'Barcha viloyatlar'))}</b> markazlari"
    if kind == "near":
        extra = f" · {esc(cat)}" if cat else ""
        return f"📍 <b>Sizga eng yaqin markazlar</b>{extra}"
    # find
    place = ("📍 sizga yaqin" if qd.get("near")
             else esc(reg_names.get(qd.get("reg"))) if qd.get("reg") else "Butun O'zbekiston")
    cat_label = cat or "Barcha yo'nalishlar"
    parts = [f"<b>{esc(cat_label)}</b>", esc(lvl or "har qanday daraja"), place]
    return "🔍 " + " · ".join(parts)


def render_list(qd: dict, data: dict, page: int, cat_names: dict, reg_names: dict) -> str:
    total = int(data.get("total") or 0)
    items = data.get("items") or []
    pages = max(1, math.ceil(total / PAGE_SIZE))
    lines = [list_title(qd, cat_names, reg_names), ""]
    if not items:
        lines.append("Hech narsa topilmadi. Boshqa yo'nalish, daraja yoki hududni sinab ko'ring "
                     "yoki markaz nomini yozing.")
        return "\n".join(lines)
    lines.append(f"Jami: <b>{total}</b> ta markaz · {page + 1}/{pages}-sahifa\n")
    for i, it in enumerate(items, start=page * PAGE_SIZE + 1):
        head = f"<b>{i}. {esc(clip(it.get('name'), 60))}</b>"
        if it.get("is_verified"):
            head += " ✅"
        rating = fmt_rating(it.get("rating"))
        if rating:
            head += f"  {rating}"
        lines.append(head)
        where = ", ".join(x for x in [esc(it.get("rname")), esc(clip(it.get("address"), 60))] if x)
        km = fmt_km(it.get("km")) if it.get("km") is not None else ""
        if where or km:
            lines.append("📍 " + where + (f" · <b>{km}</b>" if km else ""))
        if it.get("cname"):
            n = int(it.get("courses_n") or 0)
            more = f" (+{n - 1} kurs)" if n > 1 else ""
            price = fmt_price(it.get("minp"))
            lines.append(f"📚 {esc(clip(it['cname'], 50))}{more}" + (f" · 💰 {price}dan" if price else ""))
        if int(it.get("branches_n") or 0) > 1:
            lines.append(f"🏢 {int(it['branches_n'])} ta filial")
        lines.append("")
    return "\n".join(lines).strip()[:MAX_LEN]


# ---------- markaz kartochkasi ----------
def nearest_branch(card: dict, lat, lng) -> Optional[dict]:
    best, best_km = None, None
    for b in card.get("branches") or []:
        if b.get("lat") is None or b.get("lng") is None or lat is None or lng is None:
            continue
        km = haversine_km(lat, lng, b["lat"], b["lng"])
        if best_km is None or km < best_km:
            best, best_km = b, km
    return best


def render_card(card: dict, lat=None, lng=None) -> str:
    out = []
    head = f"<b>{esc(card.get('name'))}</b>" + (" ✅" if card.get("verified") else "")
    out.append(head)
    rev = card.get("reviews") or {}
    rating = fmt_rating(card.get("rating")) or (fmt_rating(rev.get("avg")) if rev.get("count") else "")
    meta = []
    if rating:
        meta.append(rating)
    if rev.get("count"):
        meta.append(f"{int(rev['count'])} ta sharh")
    if meta:
        out.append(" · ".join(meta))
    if card.get("description"):
        out.append(f"\n<i>{esc(clip(card['description'], 350))}</i>")

    branches = card.get("branches") or []
    if branches:
        out.append(f"\n📍 <b>Filiallar</b> ({len(branches)})")
        for b in branches[:5]:
            line = "• " + ", ".join(x for x in [esc(b.get("region")), esc(clip(b.get("address"), 70))] if x)
            if lat is not None and lng is not None and b.get("lat") is not None and b.get("lng") is not None:
                line += f" · <b>{fmt_km(haversine_km(lat, lng, b['lat'], b['lng']))}</b>"
            if b.get("phone") and b.get("phone") != card.get("phone"):
                line += f" · ☎ {esc(b['phone'])}"
            out.append(line)
        if len(branches) > 5:
            out.append(f"… va yana {len(branches) - 5} ta filial")

    courses = card.get("courses") or []
    if courses:
        out.append(f"\n📚 <b>Kurslar</b> ({len(courses)})")
        for c in courses[:10]:
            bits = [esc(clip(c.get("name"), 50))]
            price = fmt_price(c.get("price"))
            if price:
                bits.append(f"💰 {price}")
            if c.get("months"):
                bits.append(f"{int(c['months'])} oy")
            if c.get("schedule"):
                bits.append(esc(clip(c["schedule"], 30)))
            out.append("• " + " · ".join(bits))
        if len(courses) > 10:
            out.append(f"… va yana {len(courses) - 10} ta kurs")

    contacts = []
    if card.get("phone"):
        contacts.append(f"📞 {esc(card['phone'])}")
    if telegram_url(card.get("telegram")):
        contacts.append(f"✈️ {esc(clip(card['telegram'], 50))}")
    if website_url(card.get("website")):
        contacts.append(f"🌐 {esc(clip(card['website'], 50))}")
    if instagram_url(card.get("instagram")):
        contacts.append(f"📷 {esc(clip(card['instagram'], 50))}")
    if contacts:
        out.append("\n" + "\n".join(contacts))

    items = rev.get("items") or []
    if items:
        out.append("\n💬 <b>Sharhlar</b>")
        for r in items:
            s = int(r.get("stars") or 0)
            txt = f" — {esc(clip(r.get('comment'), 120))}" if r.get("comment") else ""
            out.append(f"{'★' * s}{'☆' * (5 - s)} <b>{esc(clip(r.get('name'), 30))}</b>{txt}")
    return "\n".join(out)[:MAX_LEN]


def lead_status(status: str) -> str:
    return {
        "new": "🕓 Yuborildi",
        "contacted": "📞 Markaz bog'landi",
        "done": "✅ Bajarildi",
    }.get(status, "🕓 Yuborildi")


def short_date(iso: Optional[str]) -> str:
    s = str(iso or "")
    return s[:10] if len(s) >= 10 else s
