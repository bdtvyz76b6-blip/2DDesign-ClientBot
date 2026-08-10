import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from database import DB, executor_name, STATUS_EMOJI

TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ALLOWED_USERS = [123456789, 987654321]  # твой Telegram ID и Даниила

bot = Bot(token=TOKEN)
dp = Dispatcher()

def auth(user_id):
    return user_id in ALLOWED_USERS

@dp.message(Command("start"))
async def start(message: types.Message):
    if not auth(message.from_user.id):
        return
    await message.answer("Админ-бот 2D Design. Команды:\n/orders, /my, /take, /done, /stats")

@dp.message(Command("orders"))
async def list_orders(message: types.Message):
    if not auth(message.from_user.id):
        return
    args = message.text.split()
    active_only = len(args) > 1 and args[1] == 'active'

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if active_only:
        c.execute("SELECT id, client, tariff, amount, executor, status, created_at FROM orders WHERE status != 'done' ORDER BY id DESC LIMIT 20")
    else:
        c.execute("SELECT id, client, tariff, amount, executor, status, created_at FROM orders ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await message.answer("Заказов нет.")
        return

    text = "<b>Список заказов:</b>\n\n"
    for row in rows:
        order_id, client, tariff, amount, executor, status, created_at = row
        status_text = STATUS_EMOJI.get(status, status)
        exec_text = executor_name(executor)
        date_str = created_at[:16] if created_at else "?"
        text += f"<b>#{order_id}</b> {status_text}\n"
        text += f"Тариф: {tariff} ({amount}₽)\n"
        text += f"Клиент: @{client}\n"
        text += f"Исполнитель: {exec_text}\n"
        text += f"Создан: {date_str}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("my"))
async def my_orders(message: types.Message):
    if not auth(message.from_user.id):
        return
    user_id = message.from_user.id
    executor = 'ruslan' if user_id == ALLOWED_USERS[0] else 'daniil'
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, client, tariff, amount, status, created_at FROM orders WHERE executor=? AND status != 'done' ORDER BY id DESC", (executor,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await message.answer("У вас нет активных заказов.")
        return
    text = "<b>Мои заказы:</b>\n\n"
    for row in rows:
        order_id, client, tariff, amount, status, created_at = row
        status_text = STATUS_EMOJI.get(status, status)
        text += f"<b>#{order_id}</b> {status_text} | {tariff} ({amount}₽) | @{client} | {created_at[:16]}\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("take"))
async def take_order(message: types.Message):
    if not auth(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите номер заказа: /take 5")
        return
    order_id = int(args[1])
    user_id = message.from_user.id
    executor = 'ruslan' if user_id == ALLOWED_USERS[0] else 'daniil'

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT executor, status FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    if not row:
        await message.answer("Заказ не найден.")
        conn.close()
        return
    current_executor, status = row
    if current_executor is not None:
        await message.answer(f"Заказ уже назначен на {executor_name(current_executor)}.")
        conn.close()
        return
    c.execute("UPDATE orders SET executor=?, status='in_progress' WHERE id=?", (executor, order_id))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Заказ #{order_id} теперь ваш. Статус: в процессе.")

@dp.message(Command("done"))
async def done_order(message: types.Message):
    if not auth(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите номер заказа: /done 5")
        return
    order_id = int(args[1])
    user_id = message.from_user.id
    executor = 'ruslan' if user_id == ALLOWED_USERS[0] else 'daniil'

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT executor, status FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    if not row:
        await message.answer("Заказ не найден.")
        conn.close()
        return
    current_executor, status = row
    if current_executor != executor:
        await message.answer(f"Этот заказ выполняет {executor_name(current_executor)}, вы не можете его закрыть.")
        conn.close()
        return
    c.execute("UPDATE orders SET status='done' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Заказ #{order_id} отмечен как выполненный.")

@dp.message(Command("stats"))
async def stats_admin(message: types.Message):
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())