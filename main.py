import asyncio
import sys
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram import types


import config
from handlers import callbacks, commands, messages#, photos

dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    await commands.send_welcome(message)

# @dp.message(CommandHelp())
# async def command_help_handler(message: types.Message) -> None:
#     await commands.send_help(message)

@dp.message()
async def command_text_handler(message: types.Message) -> None:
    await messages.handle_message(message)

#from database import get_user_settings, get_events_by_date, save_event


@dp.callback_query()
async def process_menu_callback(callback_query: types.CallbackQuery) -> None:
    await callbacks.proccess_menu_callback(callback_query)
    if callback_query.data == "reminders":
        await callback_query.message.answer('hey напоминалка', parse_mode="Markdown")
        pass


async def main() -> None:
    bot = Bot(token=config.TOKEN)
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())