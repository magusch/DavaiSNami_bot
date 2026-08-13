import logging
from datetime import datetime, timedelta, timezone

from keyboards import show_menu, feed_more_keyboard, exhibitions_more_keyboard, categories_menu
from aiogram import types

from services.utils import send_chunked
from handlers.billing import open_billing

logger = logging.getLogger(__name__)

from services.process import process_day_events, process_weekday_events, process_exhibitions, \
    process_lucky_event, process_weekend_events
from services import crud
from services import process
from services import external_api
from config import MENU, CHANNEL_LINK, BOT_LINK, ACTION_COST, STARS_RATE, TOPUP_STARS
from states import ReminderState

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


async def process_menu_callback(callback_query: types.CallbackQuery, state=None):
    try:
        await callback_query.answer()
    except Exception:
        # callback мог устареть (бэклог после рестарта) — не валим обработку
        logger.warning("Failed to answer callback query (likely too old)")
    data = callback_query.data
    wait_text = 'подождите чуток...'
    if (not callback_query.message.text
            or wait_text == callback_query.message.text or data in ['balance']
            or data.startswith('more:') or data.startswith('exmore:')):
        wait_message = await callback_query.message.answer(wait_text, reply_markup=await show_menu('back'))
    else:
        try:
            wait_message = await callback_query.message.edit_text(wait_text, reply_markup=await show_menu('back'))
        except Exception:
            logger.exception("Failed to edit message, falling back to answer")
            wait_message = await callback_query.message.answer(wait_text, reply_markup=await show_menu('back'))

    telegram_user_id = callback_query.from_user.id
    cost = _action_cost(data)
    try:
        billing = await open_billing(callback_query.message, telegram_user_id, cost)
        if billing is None:
            return                      # not enough gems, top-up offer already sent
        if data == 'weekday':
            await callback_query.message.answer('Выберите день недели', reply_markup=await show_menu('weekday'))
        elif data == 'events':
            await callback_query.message.answer('Когда?', reply_markup=await show_menu('events'))
        elif data == 'settings':
            await callback_query.message.answer('Настройки', reply_markup=await show_menu('settings'))
        elif data in MENU['settings'].keys() or data in ['saved_events_old']:
            await process_settings_callback(callback_query)
        elif data in MENU['events'].keys():
            not_minus_balance = await process_events_callback(callback_query, billing)
            if not not_minus_balance:
                await crud.charge_balance(telegram_user_id, cost)
        elif data.startswith('more:'):
            not_minus_balance = await process_more_callback(callback_query, billing)
            if not not_minus_balance:
                await crud.charge_balance(telegram_user_id, cost)
        elif data.startswith('exmore:'):
            not_minus_balance = await process_exhibitions_more_callback(callback_query, billing)
            if not not_minus_balance:
                await crud.charge_balance(telegram_user_id, cost)
        elif data in MENU['weekday'].keys():
            not_minus_balance = await process_weekday_callback(callback_query, billing)
            if not not_minus_balance:
                await crud.charge_balance(telegram_user_id, cost)
        elif data in MENU['balance'].keys():
            await process_balance_callback(callback_query)
        elif data.startswith('sevent_'):
            if await process_saved_events(callback_query, state=state):
                await process_settings_callback(callback_query)
        else:
            callback_message = f'{data} не найдено, обратитесь к разработчику! \n\n/start'
            await callback_query.message.answer(callback_message, reply_markup=await show_menu('events'))
    finally:
        try:
            user_monitor_dict = {
                'telegram_id': telegram_user_id,
                'telegram_info': f"{callback_query.from_user.username} ({callback_query.from_user.first_name} {callback_query.from_user.last_name})",
                'message': data,
                'type': 'data'
            }
            await crud.create_telegram_monitor(user_monitor_dict)
        except Exception:
            logger.exception("Failed to log telegram monitor")
        if wait_message:
            try:
                await wait_message.delete()
            except Exception:
                pass

# Paid callbacks are the ones that actually hit the API for listings. Menus,
# categories, settings, "lucky" and "similar" are free.
_FREE_CALLBACKS = ('events', 'settings', 'weekday', 'categories', 'lucky')


def _action_cost(data):
    """Gem price of a callback."""
    if data in _FREE_CALLBACKS:
        return 0
    if (data in MENU['events'] or data in MENU['weekday']
            or data.startswith(('more:', 'exmore:'))):
        return ACTION_COST['feed']
    return 0


async def _send_feed(message, title, result, menu_key='events', billing=None):
    answer = await process.feed_answer(result, title, billing)
    keyboard = await feed_more_keyboard(result, menu_key)
    await send_chunked(message, answer, parse_mode="Markdown",
                       reply_markup=keyboard, disable_web_page_preview=True)


async def process_events_callback(callback_query: types.CallbackQuery, billing=None):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)
    data_command = callback_query.data
    events_menu = await show_menu('events')
    title = f"*{MENU['events'].get(data_command, '')}:*"

    if data_command == 'categories':
        await callback_query.message.answer('Выберите категорию',
                                            reply_markup=await categories_menu())
        return 1

    if data_command == 'exhibitions':
        result = await process_exhibitions(daynow)
        answer = await process.feed_answer(result, title, billing)
        keyboard = await exhibitions_more_keyboard(result)
        await send_chunked(callback_query.message, answer, parse_mode="Markdown",
                           reply_markup=keyboard, disable_web_page_preview=True)
        return 1 if not result.found else None

    if data_command == 'lucky':
        result = await process_lucky_event(daynow, with_similar=True)
        answer = await process.footer_message(f"{title}\n{result.text}")
        sent_photo = False
        # photo captions are capped at 1024 chars — send long text as its own message
        if result.image and len(answer) <= 1024:
            img_bytes = await external_api.download_image(result.image)
            if img_bytes:
                try:
                    await callback_query.message.answer_photo(
                        types.BufferedInputFile(img_bytes, filename="event.jpg"),
                        caption=answer, parse_mode="Markdown",
                        reply_markup=events_menu,
                    )
                    sent_photo = True
                except Exception:
                    logger.exception("Failed to send lucky event photo, falling back to text")
            else:
                logger.info("Lucky photo unavailable, url=%s", result.image)
        if not sent_photo:
            await send_chunked(callback_query.message, answer, parse_mode="Markdown",
                               reply_markup=events_menu, disable_web_page_preview=True)
        return 1

    # diversified feed: today / tomorrow / weekend
    if data_command == 'today':
        result = await process_day_events(0, daynow)
    elif data_command == 'tomorrow':
        result = await process_day_events(1, daynow)
    elif data_command == 'weekend':
        result = await process_weekend_events(daynow)
    else:
        await callback_query.message.answer('Неверная команда', reply_markup=events_menu)
        return 1

    await _send_feed(callback_query.message, title, result, billing=billing)
    return 1 if not result.found else None


async def process_more_callback(callback_query: types.CallbackQuery, billing=None):
    """"More" button — the next feed page for the same period."""
    try:
        _, date_from, date_to, page = callback_query.data.split(':')
        page = int(page)
    except (ValueError, IndexError):
        await callback_query.message.answer('Неверная команда', reply_markup=await show_menu('events'))
        return 1

    result = await process.process_feed(date_from, date_to, page=page)
    await _send_feed(callback_query.message, '*Ещё мероприятия:*', result, billing=billing)
    return 1 if not result.found else None


async def process_exhibitions_more_callback(callback_query: types.CallbackQuery, billing=None):
    """"More exhibitions" button — the next page of exhibitions."""
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)
    try:
        page = int(callback_query.data.split(':')[1])
    except (ValueError, IndexError):
        await callback_query.message.answer('Неверная команда', reply_markup=await show_menu('events'))
        return 1

    result = await process_exhibitions(daynow, page=page)
    answer = await process.feed_answer(result, '*Ещё выставки:*', billing)
    keyboard = await exhibitions_more_keyboard(result)
    await send_chunked(callback_query.message, answer, parse_mode="Markdown",
                       reply_markup=keyboard, disable_web_page_preview=True)
    return 1 if not result.found else None


async def process_weekday_callback(callback_query: types.CallbackQuery, billing=None):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    data_command = callback_query.data
    weekday = list(MENU['weekday'].keys()).index(data_command)

    result = await process_weekday_events(weekday, daynow)
    answer = await process.feed_answer(result, billing=billing)
    keyboard = await feed_more_keyboard(result, 'weekday')
    await send_chunked(callback_query.message, answer, reply_first=True, parse_mode="Markdown",
                       disable_web_page_preview=True, reply_markup=keyboard)

    if not result.found:
        return 1


async def process_settings_callback(callback_query: types.CallbackQuery):
    data_command = callback_query.data
    if data_command == 'city':
        await callback_query.message.answer('Выберите город', reply_markup=await show_menu('city'))
    elif data_command == 'weekend_guide':
        is_enabled = await crud.toggle_weekend_guide(callback_query.from_user.id)
        status = "включен" if is_enabled else "выключен"
        await callback_query.message.answer(
            f'Гайд на выходные {status}', parse_mode="Markdown",
            reply_markup=await show_menu('settings')
        )
    elif data_command == 'balance':
        # get_balance returns None for "no such user" — the old toggle_balance
        # mixed that up with a real negative balance and re-created the user
        balance = await crud.get_balance(callback_query.from_user.id)
        if balance is None:
            await process.new_user(callback_query)
            balance = await crud.get_balance(callback_query.from_user.id)
        await callback_query.message.answer(
            process.balance_message(balance), parse_mode="Markdown",
            reply_markup=await show_menu('balance')
        )

    elif data_command == 'saved_events' or data_command.startswith('sevent_'):
        await process_message_saved_event(callback_query, answer_message=None, old=0)

    elif data_command == 'saved_events_old':
        await process_message_saved_event(callback_query, old=1)


async def process_balance_callback(callback_query: types.CallbackQuery):
    data_command = callback_query.data
    if data_command == 'balance_add':
        await callback_query.message.answer_invoice(
            title="Пополнение баланса",
            description=f"{TOPUP_STARS} ⭐ Telegram Stars → {TOPUP_STARS * STARS_RATE} 💎 на баланс",
            payload="balance_topup",
            currency="XTR",
            prices=[types.LabeledPrice(label=f"{TOPUP_STARS} ⭐", amount=TOPUP_STARS)],
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌟 Пополнить", pay=True),
                 InlineKeyboardButton(text="◀️ Назад", callback_data="balance")]
            ]),
        )
    elif data_command == 'referral_url':
        link = f"https://t.me/{BOT_LINK}?start=referral-{str(callback_query.from_user.id)}"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📤 Поделиться",
                                      switch_inline_query=f"Попробуй гид-бот по поиску мероприятий: {link}. Давай с нами!")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="balance")]
            ]
        )

        await callback_query.message.answer(
            f"Пусть друзья зайдут по вашей ссылке и вы получите по 100 звёзд:\n `{link}` \n\(щёлкни по ссылке чтобы скопировать\)",
            parse_mode="MarkdownV2",
            reply_markup=keyboard #await show_menu('referral_url')
        )


async def process_save_event(callback):
    event_id = int(callback.data.split(":")[1])
    user_event_dict = {'telegram_id': callback.from_user.id, 'event_id': event_id}
    return await process.process_user_event(user_event_dict)


async def process_referral_start(callback):
    referral_id = int(callback.data.split(':')[-1].strip())
    return await process.referral_click(referral_id, callback.from_user.id)


async def process_saved_events(callback_query, state=None):
    callback_data = callback_query.data
    telegram_id = callback_query.from_user.id
    _, mod, event_id = callback_data.split('_')
    if mod in ['edit', 'enbl']:
        if not state:
            await callback_query.message.answer(
                'Не удалось установить напоминание, попробуйте позже.',
                reply_markup=await show_menu('settings')
            )
            return
        await state.update_data(event_id=event_id)
        await state.set_state(ReminderState.waiting_for_time)
        await callback_query.message.answer(
            "Введите дату и время для напоминания.\n\n"
            "Например:\n"
            "• `12.05 18:30`\n"
            "• `12 мая 18:30`\n"
            "• `12.05` (без времени — в 12:00)",
            parse_mode="Markdown",
            reply_markup=await show_menu('cancel_saved_events')
        )
    elif mod == 'sim':
        # similar events go out as their own message; the saved list is redrawn by the
        # caller afterwards (the "please wait" edit consumes the original one)
        answer = await process.process_similar_message(event_id)
        await callback_query.message.answer(answer, parse_mode="Markdown",
                                            disable_web_page_preview=True)
        return 1
    elif mod in ['dis', 'del']:
        answer = await process.toggle_saved_event(telegram_id, event_id, mod)
        if answer == 0:
            answer = f'Напоминание отключено'
        elif answer == -1:
            answer = f'Ваше мероприятие удалено из списка сохраненных'
        else:
            answer = f'Произошла ошибка с доступом, попробуйте попозже'

        await callback_query.message.answer(
            answer, parse_mode="Markdown",
            reply_markup=await show_menu('settings'),
        )
        return 1


async def process_message_saved_event(callback_query, answer_message=None, old=0):
    result = await process.process_saved_user_event(telegram_id=callback_query.from_user.id, old=old)
    if result is not None:
        answer, sevent_menu = result
    else:
        if old==0:
            answer = f"У вас нет сохранённых событий. Пересылайте события из канала {CHANNEL_LINK}"
        else:
            answer = f"У вас нет сохранённых событий в истории."
        sevent_menu = None

    if sevent_menu:
        if answer_message:
            await answer_message.edit_text(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                           reply_markup=sevent_menu)
        else:
            await callback_query.message.answer(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                                reply_markup=sevent_menu)
    else:
        await callback_query.message.answer(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                            reply_markup=await show_menu('settings'))