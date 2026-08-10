import asyncio
from client_bot import dp as client_dp, bot as client_bot
from admin_bot import dp as admin_dp, bot as admin_bot

async def main():
    await asyncio.gather(
        client_dp.start_polling(client_bot),
        admin_dp.start_polling(admin_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())