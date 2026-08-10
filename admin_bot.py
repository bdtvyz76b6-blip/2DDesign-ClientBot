import os
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from database import DB, executor_name, STATUS_EMOJI, init_db  # <-- теперь импортируем init_db

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("ADMIN_BOT_TOKEN")
if not TOKEN:
    raise ValueError("ADMIN_BOT_TOKEN не задан!")

ALLOWED_USERS = [6312016802, 5222385918]  # Руслан, Даниил

bot = Bot(token=TOKEN)
dp = Dispatcher()

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📋 Заказы")],
    [KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="👥 Админы")]
], resize_keyboard=True)

def auth(user_id):
    return user_id in ALLOWED_USERS

@dp.message(Command("start"))
async def start(message: types.Message):
    if not auth(message.from_user.id):
        logging.warning(f"Unauthorized access from {message.from_user.id}")
        return
    await message.answer("Админ-бот 2D Design. Выберите действие:", reply_markup=main_kb)

@dp.message(lambda msg: msg.text == "📋 Заказы")
async def orders_menu(message: types.Message):
    if not auth(message.from_user.id):
        return
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
async def stats_menu(message: types.Message):
    if not auth(message.from_user.id):
        return
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
async def admins_menu(message: types.Message):
    if not auth(message.from_user.id):
        return
    await message.answer(
        "<b>Администраторы 2D Design:</b>\n"
        "👤 Руслан (основатель)\n"
        "👤 Даниил (специалист)",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("take_"))
async def take_callback(callback: types.CallbackQuery):
    if not auth(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    executor = 'ruslan' if user_id == ALLOWED_USERS[0] else 'daniil'
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
    if not auth(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    executor = 'ruslan' if user_id == ALLOWED_USERS[0] else 'daniil'
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

async def main():
    logging.info("Admin bot starting (v2 with buttons)...")
    init_db()   # <-- создаёт таблицы, если их нет
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())