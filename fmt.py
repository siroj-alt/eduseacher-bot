"""Matnlarni formatlash (aiogramga bog'liq emas). Matnlar i18n orqali uz/ru tillarida."""
import html
import math
import re
from typing import Optional

import i18n
from i18n import t

PAGE_SIZE = 6
MAX_LEN = 3900  # Telegram limiti 4096

LEVEL_CODES = {"b": "beginner", "i": "intermediate", "a": "advanced"}
_LEVEL_KEYS = {"beginner": "lvl_b", "intermediate": "lvl_i", "advanced": "lvl_a",
               "b": "lvl_b", "i": "lvl_i", "a": "lvl_a"}


def level_name(code: Optional[str]) -> str:
    key = _LEVEL_KEYS.get(code or "")
    return t(key) if key else t("lvl_any")


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
    return f"{n:,}".replace(",", " ") + " " + t("som")


def fmt_money(n: int) -> str:
    return f"{int(n):,}".replace(",", " ") + " " + t("som")


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
    unit_m, unit_km = t("unit_m"), t("unit_km")
    return f"{int(round(km * 1000))} {unit_m}" if km < 1 else f"{km:.1f} {unit_km}"


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- qidiruv so'rovidan narx va saralashni ajratish ----------
_UNIT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mln|млн|million|milliyon|ming|тыс|k)\b\.?", re.I)
_PLAIN_RE = re.compile(r"\b(\d{5,9})\b\s*(?:so'?m|сум)?", re.I)
_FILLER_RE = re.compile(r"\b(gacha|dan\s+kam|до|дешевле)\b", re.I)
_CHEAP_RE = re.compile(r"\b(arzon|arzonroq|дешев\w*)\b", re.I)
_RATING_RE = re.compile(r"\b(reyting\w*|рейтинг\w*)\b", re.I)


def parse_query(text: str):
    """'ingliz tili 1 mln gacha arzon' -> ('ingliz tili', 1000000, 'cheap')."""
    s = " " + (text or "") + " "
    maxp, sort = None, None
    m = _UNIT_RE.search(s)
    if m:
        val = float(m.group(1).replace(",", "."))
        mult = 1_000_000 if m.group(2).lower() in ("mln", "млн", "million", "milliyon") else 1000
        maxp = int(val * mult)
        s = s[:m.start()] + " " + s[m.end():]
    else:
        m = _PLAIN_RE.search(s)
        if m:
            maxp = int(m.group(1))
            s = s[:m.start()] + " " + s[m.end():]
    if maxp is not None:
        s = _FILLER_RE.sub(" ", s)
    if _CHEAP_RE.search(s):
        sort = "cheap"
        s = _CHEAP_RE.sub(" ", s)
    elif _RATING_RE.search(s):
        sort = "rating"
        s = _RATING_RE.sub(" ", s)
    s = " ".join(s.split())
    return s, maxp, sort


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
def filter_line(qd: dict) -> str:
    bits = []
    if qd.get("maxp"):
        bits.append("💰 ≤ " + fmt_money(int(qd["maxp"])))
    sort = qd.get("sort")
    if sort == "cheap":
        bits.append(t("sort_cheap_l"))
    elif sort == "rating":
        bits.append(t("sort_rating_l"))
    return " · ".join(bits)


def list_title(qd: dict, cat_names: dict, reg_names: dict) -> str:
    kind = qd.get("k")
    cat = i18n.cat_name(cat_names.get(qd.get("cat"))) if qd.get("cat") else None
    lvl = level_name(qd.get("lvl")) if qd.get("lvl") else None
    if kind == "q":
        head = t("title_q", q=esc(clip(qd.get("q"), 40)))
    elif kind == "reg":
        head = t("title_reg", name=esc(i18n.reg_name(reg_names.get(qd.get("reg"))) if qd.get("reg") else t("all_regions")))
    elif kind == "near":
        head = t("title_near", extra=(f" · {esc(cat)}" if cat else ""))
    elif kind == "lvltest":
        head = t("title_lvltest", level=esc(qd.get("clabel") or ""))
    else:
        place = (t("place_near") if qd.get("near")
                 else esc(i18n.reg_name(reg_names.get(qd.get("reg")))) if qd.get("reg") else t("place_all"))
        parts = [f"<b>{esc(cat or t('all_cats'))}</b>", esc(lvl or t("lvl_any_l")), place]
        head = "🔍 " + " · ".join(parts)
    f = filter_line(qd)
    return head + (f"\n{f}" if f else "")


def render_list(qd: dict, data: dict, page: int, cat_names: dict, reg_names: dict) -> str:
    total = int(data.get("total") or 0)
    items = data.get("items") or []
    pages = max(1, math.ceil(total / PAGE_SIZE))
    lines = [list_title(qd, cat_names, reg_names), ""]
    if not items:
        lines.append(t("list_empty"))
        return "\n".join(lines)
    lines.append(t("list_total", total=total, page=page + 1, pages=pages))
    for i, it in enumerate(items, start=page * PAGE_SIZE + 1):
        head = f"<b>{i}. {esc(clip(it.get('name'), 60))}</b>"
        if it.get("is_verified"):
            head += " ✅"
        rating = fmt_rating(it.get("rating"))
        if rating:
            head += f"  {rating}"
        if it.get("app_discount"):
            head += f"  🏷 −{int(it['app_discount'])}%"
        lines.append(head)
        where = ", ".join(x for x in [esc(i18n.reg_name(it.get("rname"))), esc(clip(it.get("address"), 60))] if x)
        km = fmt_km(it.get("km")) if it.get("km") is not None else ""
        if where or km:
            lines.append("📍 " + where + (f" · <b>{km}</b>" if km else ""))
        if it.get("cname"):
            n = int(it.get("courses_n") or 0)
            more = t("more_courses", n=n - 1) if n > 1 else ""
            price = fmt_price(it.get("minp"))
            lines.append(f"📚 {esc(clip(it['cname'], 50))}{more}" + (f" · 💰 {t('price_from', price=price)}" if price else ""))
        if int(it.get("branches_n") or 0) > 1:
            lines.append(t("branches_n", n=int(it["branches_n"])))
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
        meta.append(t("reviews_n", n=int(rev["count"])))
    if meta:
        out.append(" · ".join(meta))
    if card.get("description"):
        out.append(f"\n<i>{esc(clip(card['description'], 350))}</i>")

    branches = card.get("branches") or []
    if branches:
        out.append("\n" + t("card_branches", n=len(branches)))
        for b in branches[:5]:
            line = "• " + ", ".join(x for x in [esc(i18n.reg_name(b.get("region"))), esc(clip(b.get("address"), 70))] if x)
            if lat is not None and lng is not None and b.get("lat") is not None and b.get("lng") is not None:
                line += f" · <b>{fmt_km(haversine_km(lat, lng, b['lat'], b['lng']))}</b>"
            if b.get("phone") and b.get("phone") != card.get("phone"):
                line += f" · ☎ {esc(b['phone'])}"
            out.append(line)
        if len(branches) > 5:
            out.append(t("more_branches", n=len(branches) - 5))

    courses = card.get("courses") or []
    if courses:
        out.append("\n" + t("card_courses", n=len(courses)))
        for c in courses[:10]:
            bits = [esc(clip(c.get("name"), 50))]
            price = fmt_price(c.get("price"))
            if price:
                bits.append(f"💰 {price}")
            if c.get("months"):
                bits.append(t("months_n", n=int(c["months"])))
            if c.get("schedule"):
                bits.append(esc(clip(c["schedule"], 30)))
            out.append("• " + " · ".join(bits))
        if len(courses) > 10:
            out.append(t("more_courses_card", n=len(courses) - 10))

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
        out.append("\n" + t("card_reviews"))
        for r in items:
            s = int(r.get("stars") or 0)
            txt = f" — {esc(clip(r.get('comment'), 120))}" if r.get("comment") else ""
            out.append(f"{'★' * s}{'☆' * (5 - s)} <b>{esc(clip(r.get('name'), 30))}</b>{txt}")
    return "\n".join(out)[:MAX_LEN]


def lead_status(status: str) -> str:
    return t("st_" + status) if status in ("new", "contacted", "accepted", "rejected", "cancelled", "done") else t("st_new")


def short_date(iso: Optional[str]) -> str:
    s = str(iso or "")
    return s[:10] if len(s) >= 10 else s


# ---------- taqqoslash ----------
def render_compare(items: list) -> str:
    if not items:
        return t("cmp_empty")
    prices = [i.get("min_price") for i in items if i.get("min_price")]
    ratings = [float(i["rating"]) for i in items if i.get("rating")]
    cheapest = min(prices) if prices else None
    best = max(ratings) if ratings else None
    out = [t("cmp_title"), ""]
    for n, it in enumerate(items, start=1):
        head = f"<b>{n}. {esc(clip(it.get('name'), 50))}</b>" + (" ✅" if it.get("verified") else "")
        out.append(head)
        r = fmt_rating(it.get("rating")) or t("cmp_no_rating")
        star = " 🏆" if best and it.get("rating") and float(it["rating"]) == best and len(items) > 1 else ""
        cnt = int(it.get("reviews") or 0)
        out.append(f"{r}{star}" + (" · " + t("reviews_n", n=cnt) if cnt else ""))
        mn, mx = it.get("min_price"), it.get("max_price")
        if mn:
            cheap = " 💚" if cheapest and mn == cheapest and len(items) > 1 else ""
            rng = fmt_money(mn) + (f" – {fmt_money(mx)}" if mx and mx != mn else "")
            out.append(f"💰 {rng}{cheap}")
        else:
            out.append("💰 " + t("cmp_no_price"))
        out.append(t("cmp_counts", courses=int(it.get("courses") or 0), branches=int(it.get("branches") or 0)))
        if it.get("discount"):
            out.append(f"🏷 −{int(it['discount'])}%")
        if it.get("cats"):
            out.append("📚 " + esc(clip(", ".join(i18n.cat_name(x.strip()) for x in str(it["cats"]).split(",")), 80)))
        out.append("")
    out.append(t("cmp_legend"))
    return "\n".join(out)[:MAX_LEN]


# ---------- kundalik (davomat, uy vazifasi) ----------
_ATT_ICON = {"present": "✅", "late": "⏰", "absent": "❌", "excused": "🟡"}


def render_diary(name: Optional[str], enrollments: list, parent: bool) -> str:
    head = f"👦 <b>{esc(name)}</b>" if parent else t("my_study_title")
    out = [head, ""]
    if not enrollments:
        out.append(t("diary_none"))
        return "\n".join(out)
    for e in enrollments:
        out.append(f"🏫 <b>{esc(clip(e.get('center'), 50))}</b> · {esc(clip(e.get('course'), 40))}"
                   + (f" · {esc(e['group'])}" if e.get("group") else ""))
        out.append(t("diary_30", p=int(e.get("present_30") or 0), l=int(e.get("late_30") or 0), a=int(e.get("absent_30") or 0)))
        if e.get("fee"):
            out.append(("💳 " + (t("diary_paid") if e.get("paid") else t("diary_unpaid"))) + f" · {fmt_money(e['fee'])}")
        att = e.get("attendance") or []
        if att:
            out.append(t("diary_last"))
            for a in att[:5]:
                grade = f" · {int(a['grade'])}/5" if a.get("grade") else ""
                out.append(f"{_ATT_ICON.get(a.get('status'), '•')} {str(a.get('date'))[8:10]}.{str(a.get('date'))[5:7]}{grade}"
                           + (f" — {esc(clip(a.get('note'), 40))}" if a.get("note") else ""))
        hw = e.get("homework") or []
        if hw:
            out.append(t("diary_hw"))
            for h in hw[:3]:
                due = f" ⏳ {str(h['due'])[:10]}" if h.get("due") else ""
                out.append(f"📝 {esc(clip(h.get('title'), 50))}{due}")
        out.append("")
    return "\n".join(out).strip()[:MAX_LEN]


def render_owner_report(data: dict) -> str:
    days = int(data.get("days") or 7)
    items = data.get("items") or []
    if not items:
        return t("owner_no_centers")
    label = t("report_today") if days == 1 else t("report_days", n=days)
    out = [t("report_title", label=label), ""]
    for it in items:
        out.append(f"🏫 <b>{esc(clip(it.get('name'), 50))}</b>" + (f"  {fmt_rating(it.get('rating'))}" if it.get("rating") else ""))
        out.append(t("report_row1", views=int(it.get("views") or 0), contacts=int(it.get("contacts") or 0)))
        out.append(t("report_row2", apps=int(it.get("apps") or 0), accepted=int(it.get("accepted") or 0)))
        out.append(t("report_row3", waiting=int(it.get("waiting") or 0), saved=int(it.get("saved") or 0)))
        out.append("")
    return "\n".join(out).strip()[:MAX_LEN]
