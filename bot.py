import os
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

logging.basicConfig(level=logging.INFO)

# ---------- конфигурация ----------
TOKEN = os.getenv("BOT_TOKEN")                     # единый токен
ADMIN_IDS = [6312016802, 5222385918]               # Руслан, Даниил
SECRET_COMMAND = "/admin2d"                        # команда для входа в админку

# ---------- база данных ----------
DB = "orders.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT,
        design_type TEXT,
        text TEXT,
        style TEXT,
        tariff TEXT,
        amount INTEGER,
        executor TEXT,
        executor_share INTEGER,
        fund_share INTEGER,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO meta VALUES ('last_assigned', 'daniil')")
    conn.commit()
    conn.close()

def get_next_executor():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key='last_assigned'")
    last = c.fetchone()[0]
    next_exec = 'ruslan' if last == 'daniil' else 'daniil'
    c.execute("UPDATE meta SET value=? WHERE key='last_assigned'", (next_exec,))
    conn.commit()
    conn.close()
    return next_exec

def add_order(client, design_type, text, style, tariff, amount):
    executor = get_next_executor()
    executor_share = int(amount * 0.95)
    fund_share = amount - executor_share
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''INSERT INTO orders (client, design_type, text, style, tariff, amount, executor, executor_share, fund_share)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (client, design_type, text, style, tariff, amount, executor, executor_share, fund_share))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id, executor

def executor_name(executor):
    if executor == 'ruslan':
        return 'Руслан'
    elif executor == 'daniil':
        return 'Даниил'
    return 'Не назначен'

STATUS_EMOJI = {
    'new': '🆕 Новый',
    'in_progress': '⏳ В процессе',
    'done': '✅ Выполнен'
}

# ---------- инициализация бота ----------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------- клавиатуры ----------
client_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Логотип"), KeyboardButton(text="Баннер")],
    [KeyboardButton(text="Аватар")]
], resize_keyboard=True)

tariff_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Базовый (3 вар.) — 400₽")],
    [KeyboardButton(text="Стандартный (5 вар.) — 550₽")],
    [KeyboardButton(text="Мега (7 вар.) — 650₽")]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📋 Заказы")],
    [KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="👥 Админы")],
    [KeyboardButton(text="🔙 Выйти из админки")]
], resize_keyboard=True)

# ---------- FSM для заказа ----------
class Order(StatesGroup):
    design_type = State()
    text = State()
    style = State()
    tariff = State()

# ---------- общие обработчики ----------
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    # если пользователь админ – всё равно показываем клиентское меню,
    # в админку он может зайти по секретной команде
    await message.answer("Привет! Я бот студии 2D Design. Что будем делать?", reply_markup=client_kb)

# ---------- секретная команда ----------
@dp.message(Command("admin2d"))
async def admin_login(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("🔐 Админ-панель активирована.", reply_markup=admin_kb)

# ---------- выход из админки ----------
@dp.message(lambda msg: msg.text == "🔙 Выйти из админки")
async def admin_logout(message: types.Message):
    await message.answer("Вы вернулись в обычный режим.", reply_markup=client_kb)

# ---------- клиентский сценарий ----------
@dp.message(lambda msg: msg.text in ["Логотип", "Баннер", "Аватар"])
async def choose_type(message: types.Message, state: FSMContext):
    await state.update_data(design_type=message.text)
    await message.answer("Введи текст (название, слоган):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Order.text)

@dp.message(Order.text)
async def get_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer(
        "Опиши желаемый стиль (например: строгий чёрно-белый, яркий с градиентом, рукописный каллиграфический):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Order.style)

@dp.message(Order.style)
async def get_style(message: types.Message, state: FSMContext):
    await state.update_data(style=message.text)
    await message.answer("Выбери тариф:", reply_markup=tariff_kb)
    await state.set_state(Order.tariff)

@dp.message(Order.tariff)
async def process_tariff(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = data["text"]
    style = data["style"]
    design_type = data["design_type"]
    tariff_text = message.text

    if "Базовый" in tariff_text:
        amount = 400
        tariff = "Базовый"
    elif "Стандартный" in tariff_text:
        amount = 550
        tariff = "Стандартный"
    else:
        amount = 650
        tariff = "Мега"

    order_id, executor = add_order(
        client=message.from_user.username or str(message.from_user.id),
        design_type=design_type,
        text=text,
        style=style,
        tariff=tariff,
        amount=amount
    )

    exec_name = "Руслан" if executor == "ruslan" else "Даниил"
    await message.answer(
        f"✅ Ваш заказ принят!\n"
        f"Номер заказа: <b>#{order_id}</b>\n"
        f"Тариф: {tariff} ({amount} ₽)\n"
        f"С вами свяжется специалист <b>{exec_name}</b>.\n\n"
        f"Оплата: перевод на карту по договорённости.",
        parse_mode="HTML",
        reply_markup=client_kb   # возвращаем обычную клавиатуру
    )

    # уведомление исполнителю
    executor_id = ADMIN_IDS[0] if executor == "ruslan" else ADMIN_IDS[1]
    await bot.send_message(
        executor_id,
        f"📥 Новый заказ #{order_id}\n"
        f"Клиент: @{message.from_user.username}\n"
        f"Тип: {design_type}, Стиль: {style}\n"
        f"Тариф: {tariff} ({amount} ₽)\n"
        f"Текст: {text}"
    )
    await state.clear()

# ---------- админские кнопки ----------
@dp.message(lambda msg: msg.text == "📋 Заказы")
async def show_orders(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, client, tariff, amount, executor, status, created_at FROM orders ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("Заказов пока нет.")
        return
    for row in rows:
        order_id, client, tariff, amount, executor, status, created_at = row
        status_text = STATUS_EMOJI.get(status, status)
        exec_text = executor_name(executor) if executor else "не назначен"
        date_str = created_at[:16] if created_at else "?"
        text = (
            f"<b>#{order_id}</b> {status_text}\n"
            f"Тариф: {tariff} ({amount}₽)\n"
            f"Клиент: @{client}\n"
            f"Исполнитель: {exec_text}\n"
            f"Создан: {date_str}"
        )
        btns = []
        if status == "new" and executor is None:
            btns.append(InlineKeyboardButton(text="Взять", callback_data=f"take_{order_id}"))
        if status == "in_progress" or (status == "new" and executor is not None):
            btns.append(InlineKeyboardButton(text="✅ Выполнен", callback_data=f"done_{order_id}"))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[btns]) if btns else None
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(lambda msg: msg.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT SUM(executor_share) FROM orders WHERE executor='ruslan'")
    ruslan = c.fetchone()[0] or 0
    c.execute("SELECT SUM(executor_share) FROM orders WHERE executor='daniil'")
    daniil = c.fetchone()[0] or 0
    c.execute("SELECT SUM(fund_share) FROM orders")
    fund = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM orders WHERE status='done'")
    done = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status!='done'")
    active = c.fetchone()[0]
    conn.close()
    await message.answer(
        f"📊 <b>2D Design — статистика</b>\n\n"
        f"👤 Руслан заработал: {ruslan} ₽\n"
        f"👤 Даниил заработал: {daniil} ₽\n"
        f"💰 Фонд развития: {fund} ₽\n"
        f"✅ Выполнено заказов: {done}\n"
        f"⏳ Активных: {active}",
        parse_mode="HTML"
    )

@dp.message(lambda msg: msg.text == "👥 Админы")
async def show_admins(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer(
        "<b>Администраторы 2D Design:</b>\n"
        "👤 Руслан (основатель)\n"
        "👤 Даниил (специалист)",
        parse_mode="HTML"
    )

# ---------- обработка inline-кнопок (взять/выполнить) ----------
@dp.callback_query(lambda c: c.data.startswith("take_"))
async def take_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    executor = 'ruslan' if user_id == ADMIN_IDS[0] else 'daniil'
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT executor, status FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    if not row:
        await callback.answer("Заказ не найден", show_alert=True)
        conn.close()
        return
    current_executor, _ = row
    if current_executor is not None:
        await callback.answer(f"Уже назначен на {executor_name(current_executor)}", show_alert=True)
        conn.close()
        return
    c.execute("UPDATE orders SET executor=?, status='in_progress' WHERE id=?", (executor, order_id))
    conn.commit()
    conn.close()
    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ Взял: {executor_name(executor)}",
        parse_mode="HTML"
    )
    await callback.answer("Заказ взят!")

@dp.callback_query(lambda c: c.data.startswith("done_"))
async def done_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    executor = 'ruslan' if user_id == ADMIN_IDS[0] else 'daniil'
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT executor, status FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    if not row:
        await callback.answer("Заказ не найден", show_alert=True)
        conn.close()
        return
    current_executor, status = row
    if current_executor != executor:
        await callback.answer("Вы не назначены на этот заказ", show_alert=True)
        conn.close()
        return
    c.execute("UPDATE orders SET status='done' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Выполнен!",
        parse_mode="HTML"
    )
    await callback.answer("Отмечено как выполненное")

# ---------- запуск ----------
async def main():
    logging.info("Starting unified bot...")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())