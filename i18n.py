"""Ikki tilli (uz / ru) matnlar. t("kalit", **kw) joriy foydalanuvchi tilida matn qaytaradi.
Til CtxMiddleware tomonidan har bir update uchun set_ctx() orqali o'rnatiladi."""
from contextvars import ContextVar
from typing import Optional

_LANG: ContextVar = ContextVar("lang", default="uz")
_ROLE: ContextVar = ContextVar("role", default="")


def set_ctx(lang: str, role: str = "") -> None:
    _LANG.set("ru" if lang == "ru" else "uz")
    _ROLE.set(role or "")


def lang() -> str:
    return _LANG.get()


def role() -> str:
    return _ROLE.get()


def t(key: str, **kw) -> str:
    pair = S.get(key)
    if pair is None:
        return key
    text = pair[1] if _LANG.get() == "ru" and pair[1] else pair[0]
    return text.format(**kw) if kw else text


def all_texts(key: str) -> set:
    pair = S.get(key)
    return {x for x in pair if x} if pair else set()


# ---------------------------------------------------------------- nomlar
CATS_RU = {
    "Ingliz tili": "Английский язык", "Rus tili": "Русский язык", "Dasturlash (IT)": "Программирование (IT)",
    "Matematika": "Математика", "IELTS": "IELTS", "Xitoy tili": "Китайский язык", "Koreys tili": "Корейский язык",
    "Nemis tili": "Немецкий язык", "Arab tili": "Арабский язык", "SAT": "SAT", "Kimyo": "Химия",
    "Biologiya": "Биология", "Tarix": "История", "Huquq": "Право", "Fizika": "Физика",
    "Ona tili va adabiyot": "Родной язык и литература", "Kiberxavfsizlik": "Кибербезопасность",
    "Sun'iy intellekt": "Искусственный интеллект", "Tarmoq administratorligi": "Сетевое администрирование",
    "Video montaj": "Видеомонтаж", "Grafik dizayn": "Графический дизайн", "SMM va marketing": "SMM и маркетинг",
    "Robototexnika": "Робототехника", "Buxgalteriya": "Бухгалтерия", "Mental arifmetika": "Ментальная арифметика",
    "Turk tili": "Турецкий язык", "Yapon tili": "Японский язык", "Fransuz tili": "Французский язык",
    "Kompyuter savodxonligi": "Компьютерная грамотность", "Shaxmat": "Шахматы", "Rasm chizish": "Рисование",
    "Musiqa": "Музыка", "Raqs": "Танцы", "Maktabga tayyorlov": "Подготовка к школе", "Tikuvchilik": "Шитьё",
    "Oshpazlik": "Кулинария", "Sartaroshlik va go'zallik": "Парикмахерское дело и красота",
    "O'zbek tili (chet elliklar uchun)": "Узбекский язык (для иностранцев)",
}
REGS_RU = {
    "Toshkent shahri": "г. Ташкент", "Toshkent viloyati": "Ташкентская обл.", "Samarqand": "Самарканд",
    "Buxoro": "Бухара", "Farg'ona": "Фергана", "Andijon": "Андижан", "Namangan": "Наманган", "Xorazm": "Хорезм",
    "Qashqadaryo": "Кашкадарья", "Surxondaryo": "Сурхандарья", "Navoiy": "Навои", "Jizzax": "Джизак",
    "Sirdaryo": "Сырдарья", "Qoraqalpog'iston": "Каракалпакстан",
}


def cat_name(name: Optional[str]) -> str:
    name = name or ""
    return CATS_RU.get(name, name) if _LANG.get() == "ru" else name


def reg_name(name: Optional[str]) -> str:
    name = name or ""
    return REGS_RU.get(name, name) if _LANG.get() == "ru" else name


# ---------------------------------------------------------------- matnlar: kalit -> (uz, ru)
S: dict = {}


def _a(**pairs):
    S.update(pairs)


# ---- asosiy menyu tugmalari (reply keyboard)
_a(
    btn_find=("🔍 Markaz qidirish", "🔍 Найти центр"),
    btn_near=("📍 Yaqin markazlar", "📍 Центры рядом"),
    btn_regions=("🗺 Viloyatlar", "🗺 Регионы"),
    btn_cats=("📚 Yo'nalishlar", "📚 Направления"),
    btn_fav=("⭐ Saqlanganlar", "⭐ Избранное"),
    btn_leads=("📝 Arizalarim", "📝 Мои заявки"),
    btn_test=("🧪 Daraja testi", "🧪 Тест уровня"),
    btn_family=("👨‍👩‍👧 Farzandim uchun", "👨‍👩‍👧 Для ребёнка"),
    btn_share=("🎁 Do'stlarga ulashish", "🎁 Поделиться с друзьями"),
    btn_profile=("👤 Profil", "👤 Профиль"),
    btn_owner=("🏫 Markazim", "🏫 Мой центр"),
    btn_site=("🌐 Platforma", "🌐 Платформа"),
    btn_about=("ℹ️ Bot haqida", "ℹ️ О боте"),
    btn_cancel=("❌ Bekor qilish", "❌ Отмена"),
    btn_send_loc=("📍 Joylashuvni yuborish", "📍 Отправить геолокацию"),
    btn_send_phone=("📱 Raqamni yuborish", "📱 Отправить номер"),
    placeholder=("Markaz yoki kurs nomini yozing…", "Напишите название центра или курса…"),
)

# ---- inline tugmalar (umumiy)
_a(
    b_menu=("🏠 Menyu", "🏠 Меню"), b_back=("⬅️ Orqaga", "⬅️ Назад"),
    b_prev=("⬅️", "⬅️"), b_next=("➡️", "➡️"),
    b_goto_channel=("📢 Kanalga o'tish", "📢 Перейти в канал"),
    b_check_sub=("✅ Obunani tekshirish", "✅ Проверить подписку"),
    b_price=("Narx", "Цена"), b_sort=("Saralash", "Сортировка"),
    b_by_cat=("📚 Yo'nalish bo'yicha", "📚 По направлению"),
    b_upd_loc=("📍 Joylashuvni yangilash", "📍 Обновить геолокацию"),
    b_new_search=("🔍 Yangi qidiruv", "🔍 Новый поиск"),
    b_compare_n=("⚖️ Taqqoslash ({n})", "⚖️ Сравнить ({n})"),
    b_price_all=("Hammasi", "Любая"), b_price_500=("500 ming gacha", "до 500 тыс."),
    b_price_1m=("1 mln gacha", "до 1 млн"), b_price_2m=("2 mln gacha", "до 2 млн"),
    b_price_3m=("3 mln gacha", "до 3 млн"),
    b_sort_smart=("🎯 Mos kelishi bo'yicha", "🎯 По релевантности"),
    b_sort_cheap=("💸 Avval arzonlari", "💸 Сначала дешёвые"),
    b_sort_rating=("🏆 Yuqori reytingli", "🏆 С высоким рейтингом"),
    b_apply=("📝 Ariza qoldirish", "📝 Оставить заявку"),
    b_saved=("⭐ Saqlangan", "⭐ В избранном"), b_save=("☆ Saqlash", "☆ В избранное"),
    b_trial=("🎁 Sinov darsi", "🎁 Пробный урок"),
    b_route=("🗺 Yo'nalish", "🗺 Маршрут"), b_review=("✍️ Sharh", "✍️ Отзыв"),
    b_cmp_add=("⚖️ Taqqoslashga qo'shish", "⚖️ Добавить к сравнению"),
    b_cmp_remove=("➖ Taqqoslashdan olish", "➖ Убрать из сравнения"),
    b_cmp_clear=("🗑 Tozalash", "🗑 Очистить"),
    b_website=("🌐 Sayt", "🌐 Сайт"), b_share=("📤 Ulashish", "📤 Поделиться"),
    b_to_results=("⬅️ Natijalarga", "⬅️ К результатам"),
    b_general_app=("📝 Umumiy ariza", "📝 Общая заявка"),
    b_cancel_i=("❌ Bekor qilish", "❌ Отмена"), b_skip=("⏭ O'tkazib yuborish", "⏭ Пропустить"),
    b_any_course=("Farqi yo'q", "Не важно"),
    b_use_name=("✅ Shu ism", "✅ Это имя"),
    b_back_center=("🏫 Markaz sahifasiga", "🏫 К странице центра"),
    b_cats_back=("⬅️ Yo'nalishlar", "⬅️ Направления"), b_by_loc=("📍 Yaqin atrofda", "📍 Рядом со мной"),
    b_all_uz=("🇺🇿 Butun O'zbekiston", "🇺🇿 Весь Узбекистан"),
    b_all_regions=("🌍 Barcha viloyatlar", "🌍 Все регионы"), b_all_cats=("📚 Barcha yo'nalishlar", "📚 Все направления"),
    b_test_start=("▶️ Testni boshlash", "▶️ Начать тест"), b_test_stop=("⏹ To'xtatish", "⏹ Остановить"),
    b_test_centers=("🏫 Mos markazlarni ko'rish", "🏫 Подходящие центры"),
    b_test_ielts=("🎓 IELTS markazlari", "🎓 Центры IELTS"), b_test_again=("🔁 Qayta topshirish", "🔁 Пройти заново"),
    b_link_child=("➕ Farzandni ulash", "➕ Привязать ребёнка"),
    b_owner_new=("🆕 Yangi arizalar ({n})", "🆕 Новые заявки ({n})"), b_owner_all=("📋 Barcha arizalar", "📋 Все заявки"),
    b_rep_today=("📊 Bugun", "📊 Сегодня"), b_rep_week=("📊 Hafta", "📊 Неделя"), b_rep_month=("📊 Oy", "📊 Месяц"),
    b_open_cabinet=("🖥 Kabinetni ochish", "🖥 Открыть кабинет"),
    b_open_cabinet_site=("🖥 Kabinetni ochish (sayt)", "🖥 Открыть кабинет (сайт)"),
    b_accept=("✅ Qabul qilish", "✅ Принять"), b_reject=("❌ Rad etish", "❌ Отклонить"),
    b_contacted=("📞 Bog'landim", "📞 Связался"),
    b_edit_name=("✏️ Ismni o'zgartirish", "✏️ Изменить имя"), b_edit_phone=("📱 Raqamni o'zgartirish", "📱 Изменить номер"),
    b_upd_loc2=("📍 Joylashuv", "📍 Геолокация"), b_del_loc=("🗑 Joylashuvni o'chirish", "🗑 Удалить геолокацию"),
    b_lang=("🌐 Til / Язык", "🌐 Til / Язык"), b_my_study=("🎓 Mening o'qishim", "🎓 Моё обучение"),
    b_unlink=("🔓 Kabinetni uzish", "🔓 Отвязать кабинет"), b_link_cabinet=("🔗 Kabinetni ulash", "🔗 Привязать кабинет"),
    b_yes_unlink=("✅ Ha", "✅ Да"), b_no=("❌ Yo'q", "❌ Нет"),
    b_send_friend=("📨 Do'stga yuborish", "📨 Отправить другу"), b_enter_code=("🔑 Kodni kiritish", "🔑 Ввести код"),
    b_open_platform=("🌐 Platformani ochish", "🌐 Открыть платформу"),
    b_inline_open_bot=("🤖 Botda ochish", "🤖 Открыть в боте"), b_inline_site=("🌐 Sayt", "🌐 Сайт"),
    lvl_b_btn=("🌱 Boshlang'ich", "🌱 Начальный"), lvl_i_btn=("🌿 O'rta", "🌿 Средний"),
    lvl_a_btn=("🌳 Yuqori", "🌳 Продвинутый"), lvl_x_btn=("🔀 Farqi yo'q", "🔀 Не важно"),
    dow_1=("Du", "Пн"), dow_2=("Se", "Вт"), dow_3=("Chor", "Ср"), dow_4=("Pay", "Чт"),
    dow_5=("Ju", "Пт"), dow_6=("Sha", "Сб"), dow_7=("Yak", "Вс"),
)

# ---- umumiy so'zlar
_a(
    som=("so'm", "сум"), unit_m=("m", "м"), unit_km=("km", "км"), friend=("do'st", "друг"),
    user_word=("Foydalanuvchi", "Пользователь"), center_word=("markaz", "центр"),
    direction=("Yo'nalish", "Направление"), continue_word=("Davom etish:", "Продолжить:"),
    no_word=("yo'q", "нет"), saved_yes=("saqlangan ✅", "сохранена ✅"),
    lvl_b=("Boshlang'ich", "Начальный"), lvl_i=("O'rta", "Средний"), lvl_a=("Yuqori", "Продвинутый"),
    lvl_any=("Barcha daraja", "Любой уровень"), lvl_any_l=("barcha daraja", "любой уровень"),
    all_cats=("Barcha yo'nalish", "Все направления"), all_regions=("Barcha viloyatlar", "Все регионы"),
    place_near=("📍 yaqin atrofda", "📍 рядом со мной"), place_all=("🇺🇿 butun O'zbekiston", "🇺🇿 весь Узбекистан"),
    sort_cheap_l=("💸 arzonlari avval", "💸 сначала дешёвые"), sort_rating_l=("🏆 reyting bo'yicha", "🏆 по рейтингу"),
    price_from=("{price} dan", "от {price}"),
    st_new=("🆕 Yangi", "🆕 Новая"), st_contacted=("📞 Bog'lanildi", "📞 Связались"),
    st_accepted=("✅ Qabul qilindi", "✅ Принята"), st_rejected=("❌ Rad etildi", "❌ Отклонена"),
    st_cancelled=("🚫 Bekor qilindi", "🚫 Отменена"), st_done=("🎓 Yakunlandi", "🎓 Завершена"),
)

# ---- majburiy obuna
_a(
    gate_text=("📢 <b>Botdan foydalanish uchun kanalga obuna bo'ling</b>\n\nYangi markazlar, chegirmalar va foydali maslahatlar — "
               "<b>@edusearcher</b> kanalida. Obuna bo'lgach, «Obunani tekshirish» tugmasini bosing.",
               "📢 <b>Чтобы пользоваться ботом, подпишитесь на канал</b>\n\nНовые центры, скидки и полезные советы — "
               "в канале <b>@edusearcher</b>. После подписки нажмите «Проверить подписку»."),
    sub_first=("Avval kanalga obuna bo'ling 👇", "Сначала подпишитесь на канал 👇"),
    sub_ok=("✅ Obuna tasdiqlandi!", "✅ Подписка подтверждена!"),
    sub_not_yet=("Obuna topilmadi. Kanalga obuna bo'lib, qayta urinib ko'ring.", "Подписка не найдена. Подпишитесь на канал и попробуйте снова."),
    sub_cant_check=("Hozir tekshirib bo'lmadi, birozdan so'ng urinib ko'ring.", "Сейчас не удаётся проверить, попробуйте чуть позже."),
)

# ---- start / menyu / yordam
_a(
    welcome=("👋 Assalomu alaykum, <b>{name}</b>!\n\nMen <b>EduSearcher</b> botiman — O'zbekistondagi o'quv markazlarini "
             "topishda yordam beraman: narx, reyting, manzil, sinov darsi va ariza — hammasi shu yerda.\n\n"
             "Quyidagi menyudan boshlang 👇",
             "👋 Здравствуйте, <b>{name}</b>!\n\nЯ бот <b>EduSearcher</b> — помогаю находить учебные центры Узбекистана: "
             "цены, рейтинг, адрес, пробный урок и заявка — всё здесь.\n\nНачните с меню ниже 👇"),
    welcome_short=("👋 Xush kelibsiz! Menyudan tanlang 👇", "👋 Добро пожаловать! Выберите в меню 👇"),
    welcome_ref=("🎁 Siz do'stingiz taklifi orqali keldingiz — rahmat!", "🎁 Вы пришли по приглашению друга — спасибо!"),
    ref_joined=("🎉 <b>{name}</b> sizning taklifingiz orqali botga qo'shildi!", "🎉 <b>{name}</b> присоединился к боту по вашему приглашению!"),
    menu_text=("🏠 Asosiy menyu. Nima qilamiz?", "🏠 Главное меню. Что делаем?"),
    help_text=("<b>Yordam</b>\n\n"
               "🔍 <b>Qidirish</b> — markaz yoki kurs nomini yozing. Masalan: <i>ingliz tili</i>, <i>IELTS 1 mln gacha</i>, <i>arzon matematika</i>.\n"
               "📍 <b>Yaqin markazlar</b> — joylashuvingizni yuboring.\n"
               "⚖️ <b>Taqqoslash</b> — kartochkadan 2–3 markazni tanlang.\n"
               "🎁 <b>Sinov darsi</b> — kartochkadagi tugma orqali kun va vaqtni tanlang.\n"
               "🧪 <b>Daraja testi</b> — ingliz tili A1–C1 darajangizni aniqlang.\n"
               "👨‍👩‍👧 <b>Farzandim uchun</b> — farzandning davomati va uy vazifasi.\n"
               "🌐 Tilni /lang buyrug'i bilan almashtiring.\n"
               "💬 Istalgan vaqtda /menu — bosh menyu, /cancel — bekor qilish.",
               "<b>Помощь</b>\n\n"
               "🔍 <b>Поиск</b> — напишите название центра или курса. Например: <i>английский</i>, <i>IELTS до 1 млн</i>, <i>дешёвая математика</i>.\n"
               "📍 <b>Центры рядом</b> — отправьте геолокацию.\n"
               "⚖️ <b>Сравнение</b> — выберите 2–3 центра в карточке.\n"
               "🎁 <b>Пробный урок</b> — кнопка в карточке: выберите день и время.\n"
               "🧪 <b>Тест уровня</b> — определите уровень английского A1–C1.\n"
               "👨‍👩‍👧 <b>Для ребёнка</b> — посещаемость и домашние задания.\n"
               "🌐 Язык меняется командой /lang.\n"
               "💬 В любой момент /menu — главное меню, /cancel — отмена."),
    about_head=("ℹ️ <b>EduSearcher</b> — O'zbekiston o'quv markazlari katalogi", "ℹ️ <b>EduSearcher</b> — каталог учебных центров Узбекистана"),
    about_stats=("📊 Bazada: <b>{centers}</b> markaz, <b>{branches}</b> filial, <b>{courses}</b> kurs, {categories} yo'nalish, {regions} viloyat.",
                 "📊 В базе: <b>{centers}</b> центров, <b>{branches}</b> филиалов, <b>{courses}</b> курсов, {categories} направлений, {regions} регионов."),
    about_tail=("Bot sayt bilan bir xil ma'lumotlar bazasida ishlaydi: sayt va botdagi arizalar markaz egasiga bir joyda keladi.",
                "Бот работает на одной базе с сайтом: заявки из сайта и бота попадают владельцу центра в одно место."),
    find_prompt=("🔍 Yo'nalishni tanlang yoki to'g'ridan-to'g'ri markaz/kurs nomini yozing:", "🔍 Выберите направление или просто напишите название центра/курса:"),
    regions_prompt=("🗺 Viloyatni tanlang:", "🗺 Выберите регион:"),
    cats_prompt=("📚 Yo'nalishni tanlang:", "📚 Выберите направление:"),
    cat_level_prompt=("📚 <b>{name}</b>\n\nDarajani tanlang:", "📚 <b>{name}</b>\n\nВыберите уровень:"),
    cat_where_prompt=("📚 <b>{name}</b>\n\nQayerdan qidiramiz?", "📚 <b>{name}</b>\n\nГде ищем?"),
    lvl_where_prompt=("📚 <b>{name}</b> · {level}\n\nQayerdan qidiramiz?", "📚 <b>{name}</b> · {level}\n\nГде ищем?"),
    near_cat_prompt=("📍 Qaysi yo'nalish bo'yicha yaqin markazlarni ko'rsataylik?", "📍 По какому направлению показать ближайшие центры?"),
    ask_location=("📍 Yaqin markazlarni topish uchun joylashuvingizni yuboring:", "📍 Отправьте геолокацию, чтобы найти ближайшие центры:"),
    loc_saved=("📍 Joylashuv saqlandi ✅", "📍 Геолокация сохранена ✅"),
    list_empty=("😕 Hech narsa topilmadi. Boshqa so'z yoki filtr bilan urinib ko'ring.", "😕 Ничего не найдено. Попробуйте другое слово или фильтр."),
    list_total=("Topildi: <b>{total}</b> · sahifa {page}/{pages}", "Найдено: <b>{total}</b> · стр. {page}/{pages}"),
    title_q=("🔎 «<b>{q}</b>»", "🔎 «<b>{q}</b>»"),
    title_reg=("🗺 <b>{name}</b>", "🗺 <b>{name}</b>"),
    title_near=("📍 <b>Yaqin markazlar</b>{extra}", "📍 <b>Центры рядом</b>{extra}"),
    title_lvltest=("🧪 <b>{level}</b> darajasi uchun markazlar", "🧪 Центры для уровня <b>{level}</b>"),
    more_courses=(" +{n} kurs", " +{n} курс."), branches_n=("🏢 {n} ta filial", "🏢 Филиалов: {n}"),
    reviews_n=("{n} sharh", "отзывов: {n}"),
    search_short=("Kamida 2 ta belgi yozing 🙂", "Напишите хотя бы 2 символа 🙂"),
    search_expired=("Qidiruv eskirdi. Qaytadan qidiring.", "Поиск устарел. Повторите поиск."),
    dont_understand=("Tushunmadim 🤔 Menyudan tanlang yoki markaz nomini yozing.", "Не понял 🤔 Выберите в меню или напишите название центра."),
    use_buttons=("Iltimos, pastdagi tugmalardan foydalaning 👇", "Пожалуйста, используйте кнопки ниже 👇"),
    stale_button=("Bu tugma eskirgan. /menu ni bosing.", "Эта кнопка устарела. Нажмите /menu."),
    step_expired=("Jarayon eskirdi. Qaytadan boshlang.", "Сессия устарела. Начните заново."),
    cancelled=("Bekor qilindi", "Отменено"), cancelled_home=("Bekor qilindi. Bosh menyu 👇", "Отменено. Главное меню 👇"),
    error_retry=("⚠️ Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.", "⚠️ Произошла ошибка. Попробуйте чуть позже."),
    error_retry_short=("Xatolik. Qayta urinib ko'ring.", "Ошибка. Попробуйте снова."),
    error_alert=("Xatolik yuz berdi", "Произошла ошибка"),
    error_msg=("⚠️ Kutilmagan xatolik. /menu ni bosib qayta urinib ko'ring.", "⚠️ Непредвиденная ошибка. Нажмите /menu и попробуйте снова."),
    save_fail_alert=("Saqlab bo'lmadi", "Не удалось сохранить"),
    center_not_found=("Markaz topilmadi", "Центр не найден"), center_nf_short=("Markaz topilmadi", "Центр не найден"),
    no_map_address=("Bu markaz uchun xarita manzili kiritilmagan.", "Для этого центра не указан адрес на карте."),
    fav_saved=("⭐ Saqlandi", "⭐ Сохранено"), fav_removed=("Saqlanganlardan olindi", "Убрано из избранного"),
    fav_empty=("⭐ Hali saqlangan markaz yo'q. Kartochkadagi «Saqlash» tugmasini bosing.", "⭐ В избранном пока пусто. Нажмите «В избранное» в карточке."),
    fav_title=("⭐ <b>Saqlanganlar</b> ({n})", "⭐ <b>Избранное</b> ({n})"),
    leads_empty=("📝 Hali ariza yubormagansiz.", "📝 Вы ещё не отправляли заявок."),
    leads_title=("📝 <b>Arizalarim</b>", "📝 <b>Мои заявки</b>"),
    leads_footer=("Markaz arizangizni ko'rib chiqib, siz bilan bog'lanadi.", "Центр рассмотрит заявку и свяжется с вами."),
    card_branches=("🏢 <b>Filiallar ({n})</b>", "🏢 <b>Филиалы ({n})</b>"), more_branches=("… yana {n} ta filial", "… ещё филиалов: {n}"),
    card_courses=("📚 <b>Kurslar ({n})</b>", "📚 <b>Курсы ({n})</b>"), more_courses_card=("… yana {n} ta kurs", "… ещё курсов: {n}"),
    months_n=("{n} oy", "{n} мес."), card_reviews=("💬 <b>Sharhlar</b>", "💬 <b>Отзывы</b>"),
)

# ---- ariza (lead) va sharh
_a(
    lead_course_prompt=("📝 <b>{name}</b>\n\nQaysi kurs bo'yicha ariza qoldirasiz?", "📝 <b>{name}</b>\n\nПо какому курсу оставить заявку?"),
    ask_name=("👤 Ismingizni yozing:", "👤 Напишите ваше имя:"),
    ask_name_saved=("👤 Ismingizni yozing yoki saqlanganini tanlang:", "👤 Напишите имя или выберите сохранённое:"),
    ask_phone=("📱 Telefon raqamingizni yuboring (tugma yoki +998901234567 ko'rinishida yozing):",
               "📱 Отправьте номер телефона (кнопкой или в формате +998901234567):"),
    ask_note=("💬 Izoh qoldiring (ixtiyoriy):", "💬 Оставьте комментарий (необязательно):"),
    phone_bad=("Raqam noto'g'ri. Namuna: +998901234567", "Неверный номер. Пример: +998901234567"),
    phone_saved=("📱 Raqam saqlandi: {phone}", "📱 Номер сохранён: {phone}"),
    phone_saved2=("📱 Raqam saqlandi ✅", "📱 Номер сохранён ✅"),
    only_own_number=("Iltimos, o'zingizning raqamingizni yuboring.", "Пожалуйста, отправьте свой собственный номер."),
    name_len=("Ism 2–80 belgi bo'lishi kerak.", "Имя должно быть от 2 до 80 символов."),
    name_saved=("✅ Ism saqlandi", "✅ Имя сохранено"),
    lead_expired=("Ariza jarayoni eskirdi. Markazni qaytadan oching.", "Заявка устарела. Откройте центр заново."),
    lead_fail=("⚠️ Arizani yuborib bo'lmadi. Keyinroq urinib ko'ring.", "⚠️ Не удалось отправить заявку. Попробуйте позже."),
    lead_sent=("✅ <b>Ariza yuborildi!</b>\n\n🏢 {center}\n{course}👤 {name}\n📞 {phone}\n\nMarkaz tez orada siz bilan bog'lanadi.",
               "✅ <b>Заявка отправлена!</b>\n\n🏢 {center}\n{course}👤 {name}\n📞 {phone}\n\nЦентр скоро свяжется с вами."),
    rv_stars_prompt=("⭐ Markazni baholang:", "⭐ Оцените центр:"),
    rv_comment_prompt=("{stars}\n\n💬 Sharh yozing yoki o'tkazib yuboring:", "{stars}\n\n💬 Напишите отзыв или пропустите:"),
    rv_expired=("Sharh jarayoni eskirdi.", "Отзыв устарел."),
    rv_fail=("⚠️ Sharhni yuborib bo'lmadi.", "⚠️ Не удалось отправить отзыв."),
    rv_thanks=("🙏 Sharhingiz uchun rahmat!", "🙏 Спасибо за отзыв!"),
    enc_yes=("🎉 Zo'r! <b>{center}</b> markaziga o'qishga qabul qilinganingiz tasdiqlandi.", "🎉 Отлично! Ваше зачисление в <b>{center}</b> подтверждено."),
    enc_no=("Tushunarli. <b>{center}</b> uchun javobingiz qayd etildi.", "Понятно. Ваш ответ для <b>{center}</b> записан."),
    thanks_saved=("Rahmat, saqlandi", "Спасибо, сохранено"),
    req_not_found=("So'rov topilmadi", "Запрос не найден"),
)

# ---- profil, til, kabinet
_a(
    profile_text=("👤 <b>Profil</b>\n\nIsm: {name}\nTelefon: {phone}\nJoylashuv: {loc}\n⭐ Saqlangan: {favs}\n🎁 Takliflar: {refs}\n🌐 Til: {lang}\n\n{cabinet}",
                  "👤 <b>Профиль</b>\n\nИмя: {name}\nТелефон: {phone}\nГеолокация: {loc}\n⭐ В избранном: {favs}\n🎁 Приглашений: {refs}\n🌐 Язык: {lang}\n\n{cabinet}"),
    cabinet_linked=("🔗 Sayt kabineti ulangan", "🔗 Кабинет на сайте привязан"), cabinet_not_linked=("🔗 Sayt kabineti ulanmagan", "🔗 Кабинет на сайте не привязан"),
    pf_name_prompt=("✏️ Yangi ismingizni yozing:", "✏️ Напишите новое имя:"),
    pf_phone_prompt=("📱 Yangi raqamingizni yuboring:", "📱 Отправьте новый номер:"),
    lang_prompt=("🌐 Tilni tanlang / Выберите язык:", "🌐 Tilni tanlang / Выберите язык:"),
    lang_changed=("✅ Til o'zgartirildi: O'zbekcha", "✅ Язык изменён: Русский"),
    link_how=("🔗 <b>Kabinetni ulash</b>\n\nedusearcher.uz saytida kabinetingizga kiring → «Telegram bot» bo'limidan ulanish havolasini oling va shu yerda oching.",
              "🔗 <b>Привязка кабинета</b>\n\nВойдите в кабинет на edusearcher.uz → в разделе «Telegram-бот» получите ссылку для привязки и откройте её здесь."),
    link_fail=("⚠️ Ulab bo'lmadi. Havola noto'g'ri.", "⚠️ Не удалось привязать. Ссылка неверна."),
    link_expired=("⏳ Havola eskirgan. Saytdan yangisini oling.", "⏳ Ссылка устарела. Получите новую на сайте."),
    link_ok_owner=("✅ <b>Kabinet ulandi</b>{who}\n\n{centers}Endi yangi arizalar shu yerga keladi. Boshqarish: «🏫 Markazim».",
                   "✅ <b>Кабинет привязан</b>{who}\n\n{centers}Теперь новые заявки приходят сюда. Управление: «🏫 Мой центр»."),
    link_ok_user=("✅ <b>Kabinet ulandi</b>{who}\n\nEndi to'lov, davomat va uy vazifalari haqida bildirishnomalar shu yerga keladi.",
                  "✅ <b>Кабинет привязан</b>{who}\n\nТеперь уведомления об оплате, посещаемости и домашних заданиях приходят сюда."),
    unlink_confirm=("Kabinetni botdan uzamizmi? Bildirishnomalar to'xtaydi.", "Отвязать кабинет от бота? Уведомления прекратятся."),
    unlinked=("🔓 Kabinet uzildi.", "🔓 Кабинет отвязан."),
    my_study_title=("🎓 <b>Mening o'qishim</b>", "🎓 <b>Моё обучение</b>"),
)

# ---- taklif (referal)
_a(
    share_announcement=("🎓 EduSearcher — O'zbekistondagi o'quv markazlarini narx, reyting va manzil bo'yicha tez toping. Sinov darsiga yoziling!",
                        "🎓 EduSearcher — быстро находите учебные центры Узбекистана по цене, рейтингу и адресу. Записывайтесь на пробный урок!"),
    share_howto=("🎁 <b>Do'stlarga ulashish</b>\n\nHavolani do'stlaringizga yuboring — ular botga qo'shilganda sizga xabar keladi.",
                 "🎁 <b>Поделиться с друзьями</b>\n\nОтправьте ссылку друзьям — когда они присоединятся к боту, вы получите сообщение."),
    share_count=("👥 Taklif qilinganlar: <b>{n}</b>", "👥 Приглашено: <b>{n}</b>"),
    share_more=("… va yana {n} ta", "… и ещё {n}"),
    share_legend=("✅ — ariza qoldirgan", "✅ — оставил заявку"),
    share_site_code=("🔑 Sayt taklif kodingiz: <b>{code}</b>\nTaklif qilingan: {invited} · o'qishga yozilgan: {enrolled}",
                     "🔑 Ваш код приглашения на сайте: <b>{code}</b>\nПриглашено: {invited} · записались: {enrolled}"),
    share_site_hint=("💡 Sayt kabinetini ulasangiz, taklif kodingiz va statistikangiz shu yerda ko'rinadi.",
                     "💡 Привяжите кабинет на сайте — здесь появятся ваш код и статистика."),
    ref_code_prompt=("🔑 Do'stingiz taklif kodini yozing:", "🔑 Введите код приглашения друга:"),
    ref_code_bad=("Kod noto'g'ri formatda. Faqat harf va raqamlar (4–12 belgi).", "Неверный формат кода. Только буквы и цифры (4–12 символов)."),
    ref_code_ok=("✅ Kod qabul qilindi! Rahmat.", "✅ Код принят! Спасибо."),
    ref_err_not_linked=("Avval sayt kabinetini ulang (Profil → Kabinetni ulash).", "Сначала привяжите кабинет на сайте (Профиль → Привязать кабинет)."),
    ref_err_code=("Bunday kod topilmadi.", "Такой код не найден."),
    ref_err_self=("O'zingizning kodingizni kiritib bo'lmaydi.", "Нельзя ввести свой собственный код."),
    ref_err_already=("Siz allaqachon kod kiritgansiz.", "Вы уже вводили код."),
    ref_err_old=("Kod faqat yangi foydalanuvchilar uchun.", "Код действует только для новых пользователей."),
)

# ---- taqqoslash, narx, saralash
_a(
    cmp_added=("Taqqoslashga qo'shildi ({n}/3)", "Добавлено к сравнению ({n}/3)"), cmp_removed=("Olib tashlandi", "Убрано"),
    cmp_max=("Eng ko'pi bilan 3 ta markazni taqqoslash mumkin.", "Можно сравнивать не более 3 центров."),
    cmp_need_two=("Kamida 2 ta markaz tanlang.", "Выберите минимум 2 центра."), cmp_cleared=("Tozalandi", "Очищено"),
    cmp_empty=("Taqqoslash uchun markaz tanlanmagan.", "Для сравнения ничего не выбрано."),
    cmp_title=("⚖️ <b>Markazlarni taqqoslash</b>", "⚖️ <b>Сравнение центров</b>"),
    cmp_no_rating=("⭐ reyting yo'q", "⭐ нет рейтинга"), cmp_no_price=("narx ko'rsatilmagan", "цена не указана"),
    cmp_counts=("📚 {courses} kurs · 🏢 {branches} filial", "📚 курсов: {courses} · 🏢 филиалов: {branches}"),
    cmp_legend=("🏆 — eng yuqori reyting · 💚 — eng arzon", "🏆 — лучший рейтинг · 💚 — самая низкая цена"),
    price_prompt=("💰 Narx chegarasini tanlang (eng arzon kurs bo'yicha):", "💰 Выберите ценовой лимит (по самому дешёвому курсу):"),
    sort_prompt=("↕️ Saralash usulini tanlang:", "↕️ Выберите сортировку:"),
)

# ---- sinov darsi
_a(
    tr_no_slots=("Bu markaz uchun hozircha bo'sh vaqt yo'q.", "Для этого центра пока нет свободного времени."),
    tr_pick_day=("🎁 <b>Bepul sinov darsi</b>\n🏢 {name}\n\nKunni tanlang:", "🎁 <b>Бесплатный пробный урок</b>\n🏢 {name}\n\nВыберите день:"),
    tr_pick_time=("🗓 {day}\n\nVaqtni tanlang:", "🗓 {day}\n\nВыберите время:"),
    tr_pick_course=("📚 Qaysi kurs bo'yicha sinov darsi?", "📚 На какой курс пробный урок?"),
    tr_expired=("Sinov darsi jarayoni eskirdi. Markazni qaytadan oching.", "Запись на пробный урок устарела. Откройте центр заново."),
    tr_done=("🎁 <b>Sinov darsiga yozildingiz!</b>\n\n🏢 {center}\n🕒 {when}\n{course}👤 {name}\n📞 {phone}\n\nEslatma darsdan 3 soat oldin keladi.",
             "🎁 <b>Вы записаны на пробный урок!</b>\n\n🏢 {center}\n🕒 {when}\n{course}👤 {name}\n📞 {phone}\n\nНапоминание придёт за 3 часа до урока."),
)

# ---- daraja testi
_a(
    lt_intro=("🧪 <b>Ingliz tili daraja testi</b>\n\n{n} ta savol (A1 dan C1 gacha). Har savolga bitta to'g'ri javob bor. Natijada darajangiz va mos markazlar ko'rsatiladi.",
              "🧪 <b>Тест уровня английского</b>\n\n{n} вопросов (от A1 до C1). В каждом один правильный ответ. В конце — ваш уровень и подходящие центры."),
    lt_q_head=("❓ Savol {i}/{n} · <i>{level}</i>", "❓ Вопрос {i}/{n} · <i>{level}</i>"),
    lt_right=("✅ To'g'ri!", "✅ Верно!"), lt_wrong=("❌ To'g'ri javob: {ans}", "❌ Правильный ответ: {ans}"),
    lt_stopped=("Test to'xtatildi.", "Тест остановлен."),
    lt_result=("🏁 <b>Test yakunlandi</b>\n\nDarajangiz: <b>{level}</b>\nNatija: {score}/{n}\n{breakdown}\n\n{desc}",
               "🏁 <b>Тест завершён</b>\n\nВаш уровень: <b>{level}</b>\nРезультат: {score}/{n}\n{breakdown}\n\n{desc}"),
    lt_desc_A1=("Boshlang'ich daraja: oddiy iboralar va asosiy so'zlar. Noldan boshlovchi guruhlar mos.", "Начальный уровень: простые фразы и базовые слова. Подойдут группы с нуля."),
    lt_desc_A2=("Elementar daraja: kundalik mavzularda oddiy suhbat. Elementary guruhlar mos.", "Элементарный уровень: простое общение на бытовые темы. Подойдут группы Elementary."),
    lt_desc_B1=("O'rta daraja: ko'p mavzularda erkin gaplasha olasiz. Pre-Intermediate/Intermediate guruhlar mos.", "Средний уровень: вы свободно общаетесь на многие темы. Подойдут Pre-Intermediate/Intermediate."),
    lt_desc_B2=("O'rta-yuqori daraja: murakkab matnlarni tushunasiz. Upper-Intermediate yoki IELTS tayyorlov mos.", "Выше среднего: вы понимаете сложные тексты. Подойдут Upper-Intermediate или подготовка к IELTS."),
    lt_desc_C1=("Yuqori daraja: ravon va aniq ifodalanasiz. Advanced yoki IELTS 7+ guruhlar mos.", "Продвинутый уровень: вы говорите свободно и точно. Подойдут Advanced или IELTS 7+."),
)

# ---- ota-ona rejimi
_a(
    fam_intro=("👨‍👩‍👧 <b>Farzandim uchun</b>\n\nFarzandingizning davomati va uy vazifalarini shu yerda kuzating, kechiksa yoki kelmasa darhol xabar oling.\n\n"
               "Ulash uchun: farzandingiz sayt kabinetida «Ota-ona kodi» (6 raqam) ni oladi — uni shu yerga kiriting.",
               "👨‍👩‍👧 <b>Для ребёнка</b>\n\nСледите за посещаемостью и домашними заданиями ребёнка и сразу получайте сообщение, если он опоздал или отсутствует.\n\n"
               "Для привязки: ребёнок получает в кабинете на сайте «Код родителя» (6 цифр) — введите его здесь."),
    fam_title=("👨‍👩‍👧 <b>Farzandlarim</b>", "👨‍👩‍👧 <b>Мои дети</b>"),
    fam_no_courses=("Hozircha kurs yo'q", "Курсов пока нет"),
    fam_hint=("Batafsil ko'rish uchun farzand ismini bosing.", "Нажмите на имя ребёнка для подробностей."),
    fam_code_prompt=("🔑 Farzandingizning 6 xonali kodini yozing:", "🔑 Введите 6-значный код ребёнка:"),
    fam_code_bad=("Kod 6 ta raqamdan iborat bo'lishi kerak.", "Код должен состоять из 6 цифр."),
    fam_err_code=("Kod noto'g'ri yoki eskirgan. Qayta kiriting yoki ❌ Bekor qilish.", "Код неверен или устарел. Введите снова или ❌ Отмена."),
    fam_err_self=("O'zingizni farzand sifatida ulab bo'lmaydi.", "Нельзя привязать самого себя."),
    fam_err_limit=("Farzandlar soni chegarasiga yetdingiz.", "Достигнут лимит числа детей."),
    fam_err_throttle=("Juda ko'p urinish. 15 daqiqadan so'ng qayta urinib ko'ring.", "Слишком много попыток. Попробуйте через 15 минут."),
    fam_linked=("✅ <b>{name}</b> ulandi. Endi davomat va uy vazifalari haqida xabar olasiz.", "✅ <b>{name}</b> привязан(а). Теперь вы будете получать уведомления о посещаемости и домашних заданиях."),
    fam_unlink_confirm=("Farzandni ro'yxatdan olib tashlaymizmi?", "Убрать ребёнка из списка?"),
    diary_none=("Hozircha faol kurs yo'q.", "Активных курсов пока нет."),
    diary_30=("📊 30 kun: ✅ {p} · ⏰ {l} · ❌ {a}", "📊 30 дней: ✅ {p} · ⏰ {l} · ❌ {a}"),
    diary_paid=("To'langan", "Оплачено"), diary_unpaid=("To'lanmagan", "Не оплачено"),
    diary_last=("Oxirgi darslar:", "Последние занятия:"), diary_hw=("Uy vazifalari:", "Домашние задания:"),
)

# ---- markaz egasi
_a(
    owner_not_linked=("🏫 Markaz egasi paneli uchun sayt kabinetini ulang.", "🏫 Для панели владельца привяжите кабинет на сайте."),
    owner_title=("🏫 <b>Markazim</b>\n\n{centers}\n\n🆕 Yangi arizalar: <b>{n}</b>", "🏫 <b>Мой центр</b>\n\n{centers}\n\n🆕 Новых заявок: <b>{n}</b>"),
    owner_no_new=("Yangi ariza yo'q 👌", "Новых заявок нет 👌"), owner_no_apps=("Hali arizalar yo'q.", "Заявок пока нет."),
    owner_all_title=("📋 <b>So'nggi arizalar</b>", "📋 <b>Последние заявки</b>"),
    owner_no_centers=("Sizda bog'langan markaz yo'q.", "У вас нет привязанных центров."),
    app_already=("Bu ariza allaqachon ko'rib chiqilgan: {status}", "Эта заявка уже обработана: {status}"),
    app_not_yours=("Bu ariza sizniki emas yoki topilmadi.", "Эта заявка вам не принадлежит или не найдена."),
    app_done_toast=("Saqlandi ✅", "Сохранено ✅"), app_result=("Holat: <b>{status}</b>", "Статус: <b>{status}</b>"),
    report_today=("bugun", "сегодня"), report_days=("{n} kun", "{n} дн."),
    report_title=("📊 <b>Hisobot</b> · {label}", "📊 <b>Отчёт</b> · {label}"),
    report_row1=("👁 Ko'rishlar: {views} · 📞 Aloqa: {contacts}", "👁 Просмотры: {views} · 📞 Контакты: {contacts}"),
    report_row2=("📝 Arizalar: {apps} · ✅ Qabul: {accepted}", "📝 Заявки: {apps} · ✅ Принято: {accepted}"),
    report_row3=("⏳ Kutayotgan: {waiting} · ⭐ Saqlagan: {saved}", "⏳ Ожидают: {waiting} · ⭐ В избранном: {saved}"),
)

# ---- inline rejim
_a(inline_button=("🎓 EduSearcher botini ochish", "🎓 Открыть бот EduSearcher"))
