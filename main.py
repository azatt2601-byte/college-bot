import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BOT_TOKEN = "8973228847:AAHS4xepzdj5xHtf_L2zTSW8RWxffwVh5BA"
ADMIN_PASSWORD = "admin1234"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class AdminAuth(StatesGroup):
    waiting_for_password = State()


class AdminSchedule(StatesGroup):
    waiting_for_photo = State()
    waiting_for_link = State()


class AdminAddEvent(StatesGroup):
    waiting_for_date = State()
    waiting_for_text = State()
    waiting_for_cabinet = State()


LEXICON = {
    "RU": {
        "welcome_start": "Привет! Пожалуйста, выбери удобный язык для работы с ботом:\n\nСәлем! Ботпен жұмыс істеу үшін ыңғайлы тілді таңдаңыз:",
        "main_menu_title": "Главное меню:",
        "btn_menu": "🍽 Меню",
        "btn_schedule": "📅 Расписание",
        "btn_events": "🎉 Мероприятия",
        "btn_ideas": "💡 Идеи для колледжа",
        "btn_polls": "📊 Опросы",
        "btn_contact": "📞 Прямая связь",
        "btn_change_lang": "🌐 Смена языка",
        "btn_restart": "🔄 Перезапуск бота",
        "btn_admin": "⚙️ Админка",
        "btn_back": "⬅️ Назад",
        "restarted_msg": "🔄 Бот перезапущен! Чем могу помочь?",
        "lang_changed_msg": "Язык успешно изменён на Русский! 🇷🇺",
        "schedule_text": "Хорошо, вот новое расписание на эту неделю для всех групп!",
        "download_word": "📄 Скачать Word",
        "no_events": "🎉 На данный момент новых анонсов нет.",
        "ideas_title": "💡 Отправьте вашу идею или предложение для колледжа. Мы обязательно передадим её администрации!",
        "contact_title": "📞 Контакты администрации колледжа:\n\n📍 Приёмная: каб. 101\n📧 Email: info@college.edu.kz\n📱 Ватсап / Телефон: +7 (700) 000-00-00",
        "polls_title": "📊 Активные опросы на данный момент отсутствуют.",
        "pass_prompt": "🔒 Введите пароль администратора:",
        "pass_wrong": "❌ Неверный пароль! Доступ ограничен.",
        "pass_correct": "✅ Пароль верный! Добро пожаловать в панель администратора.",
    },
    "KZ": {
        "welcome_start": "Сәлем! Ботпен жұмыс істеу үшін ыңғайлы тілді таңдаңыз:\n\nПривет! Пожалуйста, выбери удобный язык для работы с ботом:",
        "main_menu_title": "Негізгі мәзір:",
        "btn_menu": "🍽 Мәзір",
        "btn_schedule": "📅 Сабақ кестесі",
        "btn_events": "🎉 Іс-шаралар",
        "btn_ideas": "💡 Колледжге арналған идеялар",
        "btn_polls": "📊 Сауалнамалар",
        "btn_contact": "📞 Тікелей байланыс",
        "btn_change_lang": "🌐 Тілді ауыстыру",
        "btn_restart": "🔄 Ботты қайта жүктеу",
        "btn_admin": "⚙️ Басқару панели",
        "btn_back": "⬅️ Артқа",
        "restarted_msg": "🔄 Бот қайта жүктелді! Қалай көмектесе аламын?",
        "lang_changed_msg": "Тіл Қазақ тіліне сәтті ауыстырылды! 🇰🇿",
        "schedule_text": "Жақсы, осы аптаға арналған жаңа сабақ кестесі!",
        "download_word": "📄 Word файлын жүктеу",
        "no_events": "🎉 Қазіргі уақытта жаңа хабарландырулар жоқ.",
        "ideas_title": "💡 Колледжге арналған идеяңызды немесе ұсынысыңызды жіберіңіз. Біз оны міндетті түрде әкімшілікке жеткіземіз!",
        "contact_title": "📞 Колледж әкімшілігінің байланыс деректері:\n\n📍 Қабылдау бөлмесі: 101 каб.\n📧 Email: info@college.edu.kz\n📱 Ватсап / Телефон: +7 (700) 000-00-00",
        "polls_title": "📊 Қазіргі уақытта белсенді сауалнамалар жоқ.",
        "pass_prompt": "🔒 Әкімші құпия сөзін енгізіңіз:",
        "pass_wrong": "❌ Құпия сөз қате! Қолжетімділік шектелді.",
        "pass_correct": "✅ Құпия сөз дұрыс! Басқару панеліне қош келдіңіз.",
    },
}

user_lang = {}


def init_db():
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, photo_id TEXT, word_link TEXT)"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS dishes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, composition TEXT, weight TEXT, calories TEXT, allergens TEXT, is_today INTEGER DEFAULT 1)"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, rating INTEGER, comment TEXT, created_at TEXT)"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, event_date TEXT, published_date TEXT, need_people_info TEXT)"""
    )
    cursor.execute("SELECT COUNT(*) FROM schedule")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO schedule (id, photo_id, word_link) VALUES (1, '', 'https://example.com/schedule.docx')"
        )
    conn.commit()
    conn.close()


init_db()


def lang_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇰🇿 Қазақша")]
        ],
        resize_keyboard=True,
    )


def main_keyboard(user_id):
    lang = user_lang.get(user_id, "RU")
    lex = LEXICON[lang]
    kb = [
        [
            KeyboardButton(text=lex["btn_menu"]),
            KeyboardButton(text=lex["btn_schedule"]),
        ],
        [
            KeyboardButton(text=lex["btn_events"]),
            KeyboardButton(text=lex["btn_ideas"]),
        ],
        [
            KeyboardButton(text=lex["btn_polls"]),
            KeyboardButton(text=lex["btn_contact"]),
        ],
        [
            KeyboardButton(text=lex["btn_change_lang"]),
            KeyboardButton(text=lex["btn_restart"]),
        ],
        [KeyboardButton(text=lex["btn_admin"])],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_keyboard():
    kb = [
        [
            KeyboardButton(text="📢 Добавить анонс"),
            KeyboardButton(text="🔄 Обновить расписание"),
        ],
        [
            KeyboardButton(text="➕ Добавить блюдо"),
            KeyboardButton(text="❌ Удалить блюдо"),
        ],
        [
            KeyboardButton(text="💬 Посмотреть отзывы"),
            KeyboardButton(text="⬅️ Главное меню"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        LEXICON["RU"]["welcome_start"], reply_markup=lang_keyboard()
    )


@dp.message(F.text.in_(["🇷🇺 Русский", "🇰🇿 Қазақша"]))
async def set_language(message: types.Message):
    lang = "RU" if "Русский" in message.text else "KZ"
    user_lang[message.from_user.id] = lang
    lex = LEXICON[lang]
    await message.answer(
        lex["lang_changed_msg"], reply_markup=main_keyboard(message.from_user.id)
    )


@dp.message(
    F.text.in_(
        [LEXICON["RU"]["btn_change_lang"], LEXICON["KZ"]["btn_change_lang"]]
    )
)
async def change_language(message: types.Message):
    await message.answer(
        "Тебе надо выбрать два языка: русский или казахский / Тілді таңдаңыз:",
        reply_markup=lang_keyboard(),
    )


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_restart"], LEXICON["KZ"]["btn_restart"]])
)
async def restart_bot(message: types.Message, state: FSMContext):
    await state.clear()
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await message.answer(
        lex["restarted_msg"], reply_markup=main_keyboard(message.from_user.id)
    )


@dp.message(F.text.in_(["⬅️ Назад", "⬅️ Артқа", "⬅️ Главное меню"]))
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await message.answer(
        lex["main_menu_title"], reply_markup=main_keyboard(message.from_user.id)
    )


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_admin"], LEXICON["KZ"]["btn_admin"]])
)
async def request_admin_password(message: types.Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await state.set_state(AdminAuth.waiting_for_password)
    await message.answer(lex["pass_prompt"])


@dp.message(AdminAuth.waiting_for_password)
async def check_admin_password(message: types.Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer(lex["pass_correct"], reply_markup=admin_keyboard())
    else:
        await state.clear()
        await message.answer(
            lex["pass_wrong"], reply_markup=main_keyboard(message.from_user.id)
        )


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_menu"], LEXICON["KZ"]["btn_menu"]])
)
async def canteen_section(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title, weight, calories, composition, allergens FROM dishes WHERE is_today=1"
    )
    dishes = cursor.fetchall()
    conn.close()
    if not dishes:
        await message.answer(f"🍽 **{lex['btn_menu']}**\n\nИнформация обновляется...")
        return
    res = f"🍽 **{lex['btn_menu']}:**\n\n"
    for d in dishes:
        res += f"🔹 **{d[0]}** ({d[1]})\n▫️ КБЖУ: {d[2]}\n▫️ Состав: {d[3]}\n⚠️ Аллергены: {d[4]}\n\n"
    await message.answer(res, parse_mode="Markdown")


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_schedule"], LEXICON["KZ"]["btn_schedule"]])
)
async def show_schedule(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT photo_id, word_link FROM schedule WHERE id=1")
    data = cursor.fetchone()
    conn.close()
    word_link = data[1] if data else "#"
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lex["download_word"], url=word_link)]
        ]
    )
    if data and data[0]:
        await message.answer_photo(
            photo=data[0], caption=lex["schedule_text"], reply_markup=inline_kb
        )
    else:
        await message.answer(lex["schedule_text"], reply_markup=inline_kb)


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_events"], LEXICON["KZ"]["btn_events"]])
)
async def show_events(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT title, event_date, published_date, need_people_info FROM events ORDER BY id DESC LIMIT 5"
    )
    events = cursor.fetchall()
    conn.close()
    if not events:
        await message.answer(lex["no_events"])
        return
    for ev in events:
        title, event_date, pub_date, need_info = ev
        text = f"🎉 **Дата проведения: {event_date}**\n"
        text += f"🗓 *Опубликовано: {pub_date}*\n\n"
        text += f"{title}\n"
        if need_info:
            text += f"\n📍 **Нужны люди:** подходите в кабинет **{need_info}**"
        await message.answer(text, parse_mode="Markdown")


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_ideas"], LEXICON["KZ"]["btn_ideas"]])
)
async def college_ideas(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await message.answer(lex["ideas_title"])


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_polls"], LEXICON["KZ"]["btn_polls"]])
)
async def show_polls(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await message.answer(lex["polls_title"])


@dp.message(
    F.text.in_([LEXICON["RU"]["btn_contact"], LEXICON["KZ"]["btn_contact"]])
)
async def contact_info(message: types.Message):
    lang = user_lang.get(message.from_user.id, "RU")
    lex = LEXICON[lang]
    await message.answer(lex["contact_title"])


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
  
