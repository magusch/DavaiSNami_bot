import asyncio
import sys
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram import types

from aiogram.types import CallbackQuery

import config
from handlers import callbacks, commands, messages#, photos

dp = Dispatcher()


# @dp.message(CommandStart())
# async def command_start_handler(message: types.Message, command: CommandObject) -> None:
#     await commands.start_message(message, command)


@dp.message(Command(commands=['start', 'help', 'paysupport', 'support', 'terms']))
async def command_help_handler(message: types.Message, command: CommandObject) -> None:
    await commands.process_command_handler(message, command)

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message()
async def command_text_handler(message: types.Message) -> None:
    await messages.handle_message(message)


@dp.callback_query(F.data.startswith("save_event:"))
async def save_post_callback(callback: CallbackQuery):
    if await callbacks.process_save_event(callback):
        await callback.answer(f"Пост с event_id={callback.data.split(':')[-1]} сохранён!")
    else:
        await callback.answer("Пост не сохранён!", show_alert=True)


@dp.callback_query(F.data.startswith("referral:"))
async def save_post_callback(callback: CallbackQuery):
    if await callbacks.process_referral_start(callback):
        await callback.answer(f"Добро пожеловать, рефералка от юзера активирована")
    else:
        await callback.answer("Пост не сохранён!", show_alert=True)


@dp.callback_query()
async def process_menu_callback(callback_query: types.CallbackQuery) -> None:
    await callbacks.process_menu_callback(callback_query)
    if callback_query.data == "reminders":
        await callback_query.message.answer('hey напоминалка', parse_mode="Markdown")
        pass


async def main() -> None:
    bot = Bot(token=config.TOKEN)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())