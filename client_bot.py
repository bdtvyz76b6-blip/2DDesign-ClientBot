import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database import init_db, add_order

TOKEN = os.getenv("CLIENT_BOT_TOKEN")
RUSLAN_ID = 6312016802
DANIIL_ID = 5222385918

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Order(StatesGroup):
    design_type = State()
    text = State()
    style = State()
    tariff = State()

type_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Логотип"), KeyboardButton(text="Баннер")],
    [KeyboardButton(text="Аватар")]
], resize_keyboard=True)

tariff_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Базовый (3 вар.) — 400₽")],
    [KeyboardButton(text="Стандартный (5 вар.) — 550₽")],
    [KeyboardButton(text="Мега (7 вар.) — 650₽")]
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Я бот студии 2D Design. Что будем делать?", reply_markup=type_kb)
    await state.set_state(Order.design_type)

@dp.message(Order.design_type)
async def get_type(message: types.Message, state: FSMContext):
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
        parse_mode="HTML"
    )

    executor_id = RUSLAN_ID if executor == "ruslan" else DANIIL_ID
    await bot.send_message(
        executor_id,
        f"📥 Новый заказ #{order_id}\n"
        f"Клиент: @{message.from_user.username}\n"
        f"Тип: {design_type}, Стиль: {style}\n"
        f"Тариф: {tariff} ({amount} ₽)\n"
        f"Текст: {text}"
    )
    await state.clear()

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())