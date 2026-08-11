import asyncio
import uvicorn
from bot import dp, bot, init_db
from app import app

async def start_bot():
    """Запуск Telegram-бота"""
    init_db()
    await dp.start_polling(bot)

async def start_web():
    """Запуск веб-сервера с сайтом"""
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Запускаем бота и веб-сайт параллельно
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == "__main__":
    asyncio.run(main())

