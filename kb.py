"""Tugmalar (klaviaturalar). Matnlar i18n orqali (uz/ru)."""
import os
from typing import Optional
from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

import fmt
import i18n
from i18n import t

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://edusearcher.uz")
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "edusearcherbot").lstrip("@")

# O'zbekcha qiymatlar (selftest va eski kod uchun); qaysi tilda bosilsa ham ishlaydi — i18n.all_texts
BTN_FIND = i18n.S["btn_find"][0]
BTN_NEAR = i18n.S["btn_near"][0]
BTN_REGIONS = i18n.S["btn_regions"][0]
BTN_CATS = i18n.S["btn_cats"][0]
BTN_FAV = i18n.S["btn_fav"][0]
BTN_LEADS = i18n.S["btn_leads"][0]
BTN_SHARE = i18n.S["btn_share"][0]
BTN_PROFILE = i18n.S["btn_profile"][0]
BTN_SITE = i18n.S["btn_site"][0]
BTN_ABOUT = i18n.S["btn_about"][0]
BTN_CANCEL = i18n.S["btn_cancel"][0]
BTN_TEST = i18n.S["btn_test"][0]
BTN_FAMILY = i18n.S["btn_family"][0]
BTN_OWNER = i18n.S["btn_owner"][0]


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def ub(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


def rows_of(buttons: list, per_row: int) -> list:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def markup(rows: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def home_row() -> list:
    return [ib(t("b_menu"), "home")]


def menu_only() -> InlineKeyboardMarkup:
    return markup([home_row()])


# ---------- asosiy menyu ----------
def subscribe(url: str) -> InlineKeyboardMarkup:
    return markup([
        [ub(t("b_goto_channel"), url)],
        [ib(t("b_check_sub"), "chk_sub")],
    ])


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t("btn_find")), KeyboardButton(text=t("btn_near"))],
        [KeyboardButton(text=t("btn_regions")), KeyboardButton(text=t("btn_cats"))],
        [KeyboardButton(text=t("btn_fav")), KeyboardButton(text=t("btn_leads"))],
        [KeyboardButton(text=t("btn_test")), KeyboardButton(text=t("btn_family"))],
        [KeyboardButton(text=t("btn_share")), KeyboardButton(text=t("btn_profile"))],
    ]
    if i18n.role() == "owner":
        rows.append([KeyboardButton(text=t("btn_owner"))])
    rows.append([KeyboardButton(text=t("btn_site"), web_app=WebAppInfo(url=WEB_APP_URL)),
                 KeyboardButton(text=t("btn_about"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=t("placeholder"))


def location_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_send_loc"), request_location=True)],
            [KeyboardButton(text=t("btn_cancel"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_request(saved: Optional[str] = None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t("btn_send_phone"), request_contact=True)]]
    if saved:
        rows.insert(0, [KeyboardButton(text=f"✅ {saved}")])
    rows.append([KeyboardButton(text=t("btn_cancel"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t("btn_cancel"))]], resize_keyboard=True)


# ---------- tanlash ro'yxatlari ----------
def categories(cats: list, prefix: str, all_label: Optional[str] = None) -> InlineKeyboardMarkup:
    buttons = [ib(i18n.cat_name(name), f"{prefix}:{cid}") for cid, name in cats]
    rows = [[ib(all_label, f"{prefix}:0")]] if all_label else []
    rows += rows_of(buttons, 2)
    rows.append(home_row())
    return markup(rows)


def levels(cat: int) -> InlineKeyboardMarkup:
    return markup([
        [ib(t("lvl_b_btn"), f"lvl:{cat}:b"), ib(t("lvl_i_btn"), f"lvl:{cat}:i")],
        [ib(t("lvl_a_btn"), f"lvl:{cat}:a"), ib(t("lvl_x_btn"), f"lvl:{cat}:x")],
        [ib(t("b_cats_back"), "new"), ib(t("b_menu"), "home")],
    ])


def places(cat: int, lvl: str, regs: list) -> InlineKeyboardMarkup:
    rows = [
        [ib(t("b_by_loc"), f"fl:{cat}:{lvl}")],
        [ib(t("b_all_uz"), f"fr:{cat}:{lvl}:0")],
    ]
    rows += rows_of([ib(i18n.reg_name(name), f"fr:{cat}:{lvl}:{rid}") for rid, name in regs], 2)
    rows.append([ib(t("b_back"), f"cat:{cat}"), ib(t("b_menu"), "home")])
    return markup(rows)


def regions(regs: list) -> InlineKeyboardMarkup:
    rows = [[ib(t("b_all_regions"), "rg:0")]]
    rows += rows_of([ib(i18n.reg_name(name), f"rg:{rid}") for rid, name in regs], 2)
    rows.append(home_row())
    return markup(rows)


# ---------- natijalar ro'yxati ----------
def results(items: list, page: int, total: int, qd: dict, cmp_n: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for i, it in enumerate(items, start=page * fmt.PAGE_SIZE + 1):
        label = f"{i}. {fmt.clip(it.get('name'), 36)}"
        r = fmt.fmt_rating(it.get("rating"))
        if r:
            label += f" · {r}"
        rows.append([ib(label, f"c:{it['id']}")])
    pages = max(1, -(-total // fmt.PAGE_SIZE))
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(ib(t("b_prev"), f"pg:{page - 1}"))
        nav.append(ib(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1:
            nav.append(ib(t("b_next"), f"pg:{page + 1}"))
        rows.append(nav)
    rows.append([ib(("💰 " + t("b_price")) + (" ✓" if qd.get("maxp") else ""), "prcm"),
                 ib(("↕️ " + t("b_sort")) + (" ✓" if qd.get("sort") in ("cheap", "rating") else ""), "srtm")])
    extra = []
    if qd.get("k") == "near":
        extra.append(ib(t("b_by_cat"), "nccat"))
        extra.append(ib(t("b_upd_loc"), "updloc"))
    else:
        extra.append(ib(t("b_new_search"), "new"))
    rows.append(extra)
    if cmp_n >= 2:
        rows.append([ib(t("b_compare_n", n=cmp_n), "cmps")])
    rows.append(home_row())
    return markup(rows)


PRICE_STEPS = [(0, "b_price_all"), (500_000, "b_price_500"), (1_000_000, "b_price_1m"),
               (2_000_000, "b_price_2m"), (3_000_000, "b_price_3m")]


def price_menu(current: Optional[int]) -> InlineKeyboardMarkup:
    rows = []
    for val, key in PRICE_STEPS:
        mark = "✅ " if (current or 0) == val else ""
        rows.append(ib(mark + t(key), f"prc:{val}"))
    out = rows_of(rows, 2)
    out.append([ib(t("b_back"), "bk")])
    return markup(out)


def sort_menu(current: Optional[str]) -> InlineKeyboardMarkup:
    cur = current or "smart"
    opts = [("smart", "b_sort_smart"), ("cheap", "b_sort_cheap"), ("rating", "b_sort_rating")]
    rows = [[ib(("✅ " if cur == code else "") + t(key), f"srt:{code}")] for code, key in opts]
    rows.append([ib(t("b_back"), "bk")])
    return markup(rows)


# ---------- markaz kartochkasi ----------
def card(card_data: dict, saved: bool, in_cmp: bool = False, cmp_n: int = 0) -> InlineKeyboardMarkup:
    cid = card_data["id"]
    share_link = f"https://t.me/{BOT_USERNAME}?start=c_{cid}"
    share_text = f"{card_data.get('name', t('center_word'))} — EduSearcher.uz"
    share_url = f"https://t.me/share/url?url={quote(share_link, safe='')}&text={quote(share_text, safe='')}"
    rows = [
        [ib(t("b_apply"), f"ap:{cid}"), ib(t("b_saved") if saved else t("b_save"), f"fv:{cid}")],
        [ib(t("b_trial"), f"tr:{cid}")],
        [ib(t("b_route"), f"rt:{cid}"), ib(t("b_review"), f"rv:{cid}")],
        [ib(t("b_cmp_remove") if in_cmp else t("b_cmp_add"), f"cmp:{cid}")],
    ]
    if cmp_n >= 2:
        rows.append([ib(t("b_compare_n", n=cmp_n), "cmps")])
    links = []
    tg = fmt.telegram_url(card_data.get("telegram"))
    web = fmt.website_url(card_data.get("website"))
    ig = fmt.instagram_url(card_data.get("instagram"))
    if tg:
        links.append(ub("✈️ Telegram", tg))
    if web:
        links.append(ub(t("b_website"), web))
    if ig:
        links.append(ub("📷 Instagram", ig))
    if links:
        rows.append(links)
    rows.append([ub(t("b_share"), share_url)])
    rows.append([ib(t("b_to_results"), "bk"), ib(t("b_menu"), "home")])
    return markup(rows)


def compare_view(ids: list) -> InlineKeyboardMarkup:
    rows = [[ib(f"🔎 {i}", f"c:{cid}")] for i, cid in enumerate(ids, start=1)]
    rows = [[b for r in rows for b in r]] if rows else []
    rows.append([ib(t("b_cmp_clear"), "cmpx")])
    rows.append([ib(t("b_back"), "bk"), ib(t("b_menu"), "home")])
    return markup(rows)


# ---------- ariza / sharh ----------
def lead_courses(names: list) -> InlineKeyboardMarkup:
    rows = [[ib(fmt.clip(n, 55), f"apc:{i}")] for i, n in enumerate(names)]
    rows.append([ib(t("b_general_app"), "apc:-1")])
    rows.append([ib(t("b_cancel_i"), "cancel")])
    return markup(rows)


def use_name(name: str) -> InlineKeyboardMarkup:
    return markup([
        [ib(f"✅ {fmt.clip(name, 40)}", "apn:ok")],
        [ib(t("b_cancel_i"), "cancel")],
    ])


def skip_cancel() -> InlineKeyboardMarkup:
    return markup([
        [ib(t("b_skip"), "skip")],
        [ib(t("b_cancel_i"), "cancel")],
    ])


def stars() -> InlineKeyboardMarkup:
    return markup([
        [ib("⭐" * n, f"st:{n}") for n in (1, 2, 3)],
        [ib("⭐" * n, f"st:{n}") for n in (4, 5)],
        [ib(t("b_cancel_i"), "cancel")],
    ])


# ---------- sinov darsi ----------
def trial_days(days: list) -> InlineKeyboardMarkup:
    labels = []
    for i, d in enumerate(days):
        labels.append(ib(f"{t('dow_' + str(int(d.get('dow') or 1)))} {str(d['date'])[8:10]}.{str(d['date'])[5:7]}", f"trd:{i}"))
    rows = rows_of(labels, 3)
    rows.append([ib(t("b_cancel_i"), "cancel")])
    return markup(rows)


def trial_times(times: list) -> InlineKeyboardMarkup:
    rows = rows_of([ib(f"🕒 {x}", f"trt:{i}") for i, x in enumerate(times)], 3)
    rows.append([ib(t("b_back"), "trb"), ib(t("b_cancel_i"), "cancel")])
    return markup(rows)


def trial_courses(names: list) -> InlineKeyboardMarkup:
    rows = [[ib(fmt.clip(n, 55), f"trc:{i}")] for i, n in enumerate(names)]
    rows.append([ib(t("b_any_course"), "trc:-1")])
    rows.append([ib(t("b_cancel_i"), "cancel")])
    return markup(rows)


def trial_confirm_name(name: str) -> InlineKeyboardMarkup:
    return markup([
        [ib(f"✅ {fmt.clip(name, 40)}", "trn:ok")],
        [ib(t("b_cancel_i"), "cancel")],
    ])


# ---------- daraja testi ----------
def test_start() -> InlineKeyboardMarkup:
    return markup([[ib(t("b_test_start"), "lt:s")], home_row()])


def test_options(q: int, letters: str = "ABCD") -> InlineKeyboardMarkup:
    return markup([
        [ib(ch, f"lt:a:{q}:{i}") for i, ch in enumerate(letters)],
        [ib(t("b_test_stop"), "lt:x")],
    ])


def test_result(level: str, has_loc: bool) -> InlineKeyboardMarkup:
    rows = [[ib(t("b_test_centers"), "lt:c")]]
    if level in ("B2", "C1"):
        rows.append([ib(t("b_test_ielts"), "lt:i")])
    rows.append([ib(t("b_test_again"), "lt:s"), ib(t("b_menu"), "home")])
    return markup(rows)


# ---------- ota-ona ----------
def family_empty() -> InlineKeyboardMarkup:
    return markup([[ib(t("b_link_child"), "fam:add")], home_row()])


def family_menu(children: list) -> InlineKeyboardMarkup:
    rows = []
    for i, ch in enumerate(children[:10]):
        rows.append([ib(f"👦 {fmt.clip(ch.get('name'), 28)}", f"fam:v:{i}"),
                     ib("🗑", f"fam:d:{i}")])
    rows.append([ib(t("b_link_child"), "fam:add")])
    rows.append(home_row())
    return markup(rows)


# ---------- markaz egasi ----------
def owner_menu(new_n: int) -> InlineKeyboardMarkup:
    return markup([
        [ib(t("b_owner_new", n=new_n), "own:new")],
        [ib(t("b_owner_all"), "own:all")],
        [ib(t("b_rep_today"), "own:r:1"), ib(t("b_rep_week"), "own:r:7"), ib(t("b_rep_month"), "own:r:30")],
        [ub(t("b_open_cabinet"), WEB_APP_URL.rstrip("/") + "/markaz-kabineti")],
        home_row(),
    ])


def app_actions(app_id: int) -> InlineKeyboardMarkup:
    return markup([
        [ib(t("b_accept"), f"apo:{app_id}:ok"), ib(t("b_reject"), f"apo:{app_id}:no")],
        [ib(t("b_contacted"), f"apo:{app_id}:ct")],
    ])


# ---------- profil, taklif, boshqalar ----------
def profile(linked: bool = False, role: str = "") -> InlineKeyboardMarkup:
    rows = [
        [ib(t("b_edit_name"), "pe:name"), ib(t("b_edit_phone"), "pe:phone")],
        [ib(t("b_upd_loc2"), "pe:loc"), ib(t("b_del_loc"), "pe:delloc")],
        [ib(t("b_lang"), "lang:menu")],
    ]
    if linked:
        rows.append([ib(t("b_my_study"), "my:study")])
        rows.append([ib(t("b_unlink"), "acc:unlink")])
    else:
        rows.append([ib(t("b_link_cabinet"), "acc:how")])
    rows.append(home_row())
    return markup(rows)


def lang_menu() -> InlineKeyboardMarkup:
    return markup([[ib("🇺🇿 O'zbekcha", "lang:uz"), ib("🇷🇺 Русский", "lang:ru")]])


def confirm_unlink() -> InlineKeyboardMarkup:
    return markup([[ib(t("b_yes_unlink"), "acc:unlink2"), ib(t("b_no"), "home")]])


def favorites(items: list) -> InlineKeyboardMarkup:
    rows = []
    for it in items[:30]:
        label = fmt.clip(it.get("name"), 40)
        r = fmt.fmt_rating(it.get("rating"))
        rows.append([ib(f"{label}" + (f" · {r}" if r else ""), f"c:{it['id']}")])
    rows.append(home_row())
    return markup(rows)


def my_leads(items: list) -> InlineKeyboardMarkup:
    rows = []
    seen = set()
    for it in items[:8]:
        cid = it.get("center_id")
        if cid and cid not in seen:
            seen.add(cid)
            rows.append([ib(fmt.clip(it.get("center"), 50), f"c:{cid}")])
    rows.append(home_row())
    return markup(rows)


def share(link: str, announcement: str, has_code_entry: bool = True) -> InlineKeyboardMarkup:
    url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(announcement, safe='')}"
    rows = [[ub(t("b_send_friend"), url)]]
    if has_code_entry:
        rows.append([ib(t("b_enter_code"), "ref:code")])
    rows.append(home_row())
    return markup(rows)


def open_site() -> InlineKeyboardMarkup:
    return markup([
        [InlineKeyboardButton(text=t("b_open_platform"), web_app=WebAppInfo(url=WEB_APP_URL))],
        [ib(t("btn_find"), "new")],
    ])
