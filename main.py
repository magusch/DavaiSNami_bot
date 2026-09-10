import asyncio
import sys
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram import types

from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, ErrorEvent
from aiogram.fsm.context import FSMContext

import config
from handlers import callbacks, commands, messages
from keyboards import show_menu
from services import admin_relay
from states import ReminderState

logger = logging.getLogger(__name__)

dp = Dispatcher()

def _is_undeliverable(exception: Exception) -> bool:
    """Чат нам недоступен — отвечать в него и дёргать админа бессмысленно."""
    if isinstance(exception, TelegramForbiddenError):
        return True                     # юзер заблокировал бота / кикнул из чата
    if isinstance(exception, TelegramBadRequest):
        text = str(exception).lower()
        return ('topic must be specified' in text or 'chat not found' in text
                or 'user is deactivated' in text)
    return False


@dp.errors()
async def error_handler(event: ErrorEvent):
    if _is_undeliverable(event.exception):
        logger.warning("Chat is unreachable, skipping error report: %s", event.exception)
        return True

    logger.exception("Unhandled error: %s", event.exception)
    update = event.update
    error_text = "Произошла ошибка, попробуйте позже."
    try:
        if update.message:
            await update.message.answer(error_text, reply_markup=await show_menu('events'))
        elif update.callback_query:
            try:
                await update.callback_query.answer(error_text, show_alert=True)
            except Exception:
                logger.warning("Failed to answer callback query in error handler (likely too old)")
            try:
                await update.callback_query.message.answer(
                    error_text, reply_markup=await show_menu('events')
                )
            except Exception:
                logger.exception("Failed to send fallback menu after callback error")
    except Exception as send_error:
        logger.warning("Failed to send error message to user: %s", send_error)

    # Отправляем ошибку админу
    if config.ID_ADMIN:
        try:
            import traceback
            tb = traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__)
            tb_short = "".join(tb[-5:])  # последние 5 строк трейсбека
            user_info = ""
            if update.message and update.message.from_user:
                u = update.message.from_user
                user_info = f"\nUser: {u.id} (@{u.username})"
            elif update.callback_query and update.callback_query.from_user:
                u = update.callback_query.from_user
                user_info = f"\nUser: {u.id} (@{u.username})"
            admin_text = f"⚠️ Ошибка в боте:{user_info}\n\n<pre>{tb_short[:3500]}</pre>"
            bot = event.update.bot
            await bot.send_message(config.ID_ADMIN, admin_text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send error to admin")

    return True


# @dp.message(CommandStart())
# async def command_start_handler(message: types.Message, command: CommandObject) -> None:
#     await commands.start_message(message, command)


@dp.message(F.chat.type != ChatType.PRIVATE)
async def non_private_message_handler(message: types.Message) -> None:
    await admin_relay.relay_to_admin(message, "Сообщение не из лички")


@dp.message(Command(commands=['start', 'help', 'paysupport', 'support', 'terms']))
async def command_help_handler(message: types.Message, command: CommandObject) -> None:
    await commands.process_command_handler(message, command)

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(ReminderState.waiting_for_time)
async def handle_reminder_time(message: types.Message, state: FSMContext) -> None:
    await messages.handle_time_for_event(message, state)


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
async def process_menu_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callbacks.process_menu_callback(callback_query, state=state)
    if callback_query.data == "reminders":
        await callback_query.message.answer('hey напоминалка', parse_mode="Markdown")
        pass


async def main() -> None:
    bot = Bot(token=config.TOKEN)
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())