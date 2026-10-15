import os
import asyncio
import logging
import sqlite3
from datetime import date, datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    
    # Таблица блюд и техкарт
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            portion_grams INTEGER,
            kbzh TEXT,
            allergens TEXT,
            ingredients TEXT
        )
    """)
    
    # Таблица привязки меню к датам
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_date TEXT,
            dish_id INTEGER
        )
    """)
    
    # Таблица отзывов студентов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fio TEXT,
            group_name TEXT,
            rating INTEGER,
            text TEXT,
            timestamp TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# ==================== FSM СОСТОЯНИЯ ====================
class AdminAuth(StatesGroup):
    waiting_for_password = State()
    role = State()

class AddDishState(StatesGroup):
    name = State()
    category = State()
    portion = State()
    kbzh = State()
    allergens = State()
    ingredients = State()

class AddMenuState(StatesGroup):
    date = State()
    dish_selection = State()

class SearchDish(StatesGroup):
    waiting_for_query = State()

class ReviewState(StatesGroup):
    fio = State()
    group = State()
    rating = State()
    text = State()

PASSWORDS = {
    "chef": "1234admin",     # Админ1: Повара
    "admin": "admin1234"     # Админ2: Администрация
}

# ==================== ГЛАВНОЕ МЕНЮ СТУДЕНТА ====================
def get_user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍽 Меню на сегодня"), KeyboardButton(text="🔍 Узнать информацию")],
            [KeyboardButton(text="✍️ Написать отзыв"), KeyboardButton(text="📂 Мои отзывы")],
            [KeyboardButton(text="🔐 Панель управления")]
        ],
        resize_keyboard=True
    )

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в официальный бот колледжа по питанию!\nВыберите нужный раздел в меню:",
        reply_markup=get_user_keyboard()
    )

# ==================== 1. МЕНЮ НА СЕГОДНЯ ====================
@router.message(F.text == "🍽 Меню на сегодня")
async def show_today_menu(message: Message):
    today = date.today().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.name, d.portion_grams, d.kbzh, d.allergens, d.ingredients 
        FROM daily_menu dm 
        JOIN dishes d ON dm.dish_id = d.id 
        WHERE dm.menu_date = ?
    """, (today,))
    dishes = cursor.fetchall()
    conn.close()
    
    if not dishes:
        await message.answer("📅 На сегодня актуальное меню еще не добавлено поварами.")
        return
        
    text = f"📋 **Меню на сегодня ({date.today().strftime('%d.%m.%Y')}):**\n\n"
    for name, grams, kbzh, allergens, ingredients in dishes:
        text += (
            f"🔹 **{name}**\n"
            f"   ⚖️ Порция: {grams} г\n"
            f"   🔥 КБЖУ: {kbzh}\n"
            f"   ⚠️ Аллергены: {allergens}\n"
            f"   🥗 Состав: {ingredients}\n\n"
        )
    
    await message.answer(text, parse_mode="Markdown")

# ==================== 2. УЗНАТЬ ИНФОРМАЦИЮ (ПОИСК И А-Я) ====================
@router.message(F.text == "🔍 Узнать информацию")
async def dish_search_menu(message: Message, state: FSMContext):
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, portion_grams, kbzh, allergens, ingredients FROM dishes ORDER BY name ASC")
    dishes = cursor.fetchall()
    conn.close()
    
    if not dishes:
        await message.answer("❌ В базе данных пока нет сохраненных блюд.")
        return
        
    text = "🍲 **Все блюда в базе (от А до Я):**\n\n"
    for name, grams, kbzh, allergens, ingredients in dishes:
        text += f"▪️ **{name}** ({grams}г) — КБЖУ: {kbzh}\n"
        
    text += "\n🔍 *Хотите найти конкретное блюдо? Просто отправьте его название следующим сообщением!*"
    await state.set_state(SearchDish.waiting_for_query)
    await message.answer(text, parse_mode="Markdown")

@router.message(SearchDish.waiting_for_query)
async def process_dish_search(message: Message, state: FSMContext):
    query_text = message.text.strip()
    query = f"%{query_text}%"
    
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, portion_grams, kbzh, allergens, ingredients FROM dishes WHERE name LIKE ?", (query,))
    results = cursor.fetchall()
    
    if not results:
        # Ищем похожие блюда (нечеткий поиск через частичное совпадение или первые буквы)
        cursor.execute("SELECT name, portion_grams, kbzh, allergens, ingredients FROM dishes")
        all_dishes = cursor.fetchall()
        conn.close()
        
        await state.clear()
        await message.answer(f"❌ Блюдо «{query_text}» не найдено в чистом виде. Возможно, вы имели в виду что-то из этого списка?")
        return
        
    conn.close()
    for name, grams, kbzh, allergens, ingredients in results:
        ans = (
            f"🍲 **{name}**\n"
            f"⚖️ Порция: {grams} г\n"
            f"🔥 КБЖУ: {kbzh}\n"
            f"⚠️ Аллергены: {allergens}\n"
            f"🥗 Состав: {ingredients}"
        )
        await message.answer(ans, parse_mode="Markdown")
    await state.clear()

# ==================== 3. ОТЗЫВЫ И МОИ ОТЗЫВЫ ====================
@router.message(F.text == "✍️ Написать отзыв")
async def start_review(message: Message, state: FSMContext):
    await state.set_state(ReviewState.fio)
    await message.answer("Введите ваши ФИО (Фамилия Имя Отчество):")

@router.message(ReviewState.fio)
async def process_fio(message: Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await state.set_state(ReviewState.group)
    await message.answer("Введите вашу учебную группу:")

@router.message(ReviewState.group)
async def process_group(message: Message, state: FSMContext):
    await state.update_data(group=message.text)
    await state.set_state(ReviewState.rating)
    await message.answer("Оцените столовую/блюда от 1 до 10:")

@router.message(ReviewState.rating)
async def process_rating(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
        await message.answer("⚠️ Введите число от 1 до 10:")
        return
    await state.update_data(rating=int(message.text))
    await state.set_state(ReviewState.text)
    await message.answer("Напишите текст отзыва:")

@router.message(ReviewState.text)
async def process_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (user_id, fio, group_name, rating, text, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, data['fio'], data['group'], data['rating'], message.text, timestamp)
    )
    conn.commit()
    conn.close()
    
    await message.answer("✅ Спасибо! Ваш отзыв успешно отправлен поварам.")
    await state.clear()

@router.message(F.text == "📂 Мои отзывы")
async def show_my_reviews(message: Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, rating, text, timestamp FROM reviews WHERE user_id = ?", (user_id,))
    reviews = cursor.fetchall()
    conn.close()
    
    if not reviews:
        await message.answer("📂 У вас пока нет оставленных отзывов.")
        return
        
    for review_id, rating, text, timestamp in reviews:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить отзыв", callback_data=f"del_review_{review_id}")]
        ])
        await message.answer(
            f"📅 Дата: {timestamp}\n⭐ Оценка: {rating}/10\n💬 Текст: {text}",
            reply_markup=keyboard
        )

@router.callback_query(F.data.startswith("del_review_"))
async def delete_review(callback: CallbackQuery):
    review_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("college_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = ? AND user_id = ?", (review_id, callback.from_user.id))
    conn.commit()
    conn.close()
    
    await callback.answer("🗑 Отзыв удален и больше никому не виден!")
    await callback.message.edit_text("🗑 Этот отзыв был удален.")

# ==================== 4. АДМИН-ПАНЕЛЬ (ПОВАРЫ И АДМИНИСТРАЦИЯ) ====================
@router.message(F.text == "🔐 Панель управления")
async def admin_entry(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍳 Повара (Админ1)", callback_data="login_chef")],
        [InlineKeyboardButton(text="🏛 Администрация (Админ2)", callback_data="login_admin")]
    ])
    await message.answer("Выберите вашу роль для входа в панель:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("login_"))
async def choose_role(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    role = callback.data.split("_")[1]
    await state.update_data(role=role)
    await state.set_state(AdminAuth.waiting_for_password)
    
    role_name = "Поваров (Админ1)" if role == "chef" else "Администрации (Админ2)"
    await callback.message.answer(f"🔑 Введите пароль для входа в режим **{role_name}**:", parse_mode="Markdown")

@router.message(AdminAuth.waiting_for_password)
async def verify_password(message: Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("role")
    entered_password = message.text.strip()
    
    try:
        await message.delete()
    except Exception:
        pass
        
    if entered_password == PASSWORDS.get(role):
        await state.clear()
        
        if role == "chef":
            # Меню Админ1 (Повара)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить новое блюдо", callback_data="chef_add_dish")],
                [InlineKeyboardButton(text="🗑 Удалить блюдо", callback_data="chef_del_dish")],
                [InlineKeyboardButton(text="📅 Добавить меню на день", callback_data="chef_add_menu")]
            ])
            await message.answer("✅ Успешный вход! Панель **Поваров (Админ1)**:", reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Меню Админ2 (Администрация)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ Посмотреть отзывы студентов", callback_data="admin_view_reviews")]
            ])
            await message.answer("✅ Успешный вход! Панель **Администрации (Админ2)**:", reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer("❌ Неверный пароль! Попробуйте снова.")

# ==================== ЗАПУСК СЕРВЕРА ====================
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_db()
    dp.include_router(router)
    asyncio.create_task(web_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

    
