from datetime import datetime, timedelta, timezone

from keyboards import show_menu
from aiogram import types

from services.process import process_day_events, process_weekday_events, process_exhibitions, process_lucky_event, process_weekend_events
from services import crud
from services import process
from config import MENU, CHANNEL_LINK, BOT_LINK, waiting_for_time

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


async def process_menu_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    wait_text = 'подождите чуток...'
    if data.startswith('sevent_') or wait_text == callback_query.message.text or data in ['balance']:
        wait_message = await callback_query.message.answer(wait_text, reply_markup=await show_menu('back'))
    else:
        wait_message = await callback_query.message.edit_text(wait_text, reply_markup=await show_menu('back'))

    telegram_user_id = callback_query.from_user.id
    if data == 'weekday':
        await callback_query.message.answer('Выберите день недели', reply_markup=await show_menu('weekday'))
    elif data == 'events':
        await callback_query.message.answer('Когда?', reply_markup=await show_menu('events'))
    elif data == 'settings':
        await callback_query.message.answer('Настройки', reply_markup=await show_menu('settings'))
    elif data in MENU['settings'].keys() or data in ['saved_events_old']:
        await process_settings_callback(callback_query)
    elif data in MENU['events'].keys():
        not_minus_balance = await process_events_callback(callback_query)
        if not not_minus_balance:
            await crud.change_balance(telegram_user_id, -2)
    elif data in MENU['weekday'].keys():
        not_minus_balance = await process_weekday_callback(callback_query)
        if not not_minus_balance:
            await crud.change_balance(telegram_user_id, -2)
    elif data in MENU['balance'].keys():
        await process_balance_callback(callback_query)
    elif data.startswith('sevent_'):
        if await process_saved_events(callback_query):
            await process_settings_callback(callback_query)
    else:
        callback_message = f'{data} не найдено, обратитесь к разработчику! \n\n/start'
        await callback_query.message.answer(callback_message, reply_markup=await show_menu('events'))
    await wait_message.delete()
    user_monitor_dict = {
        'telegram_id': telegram_user_id,
        'telegram_info': f"{callback_query.from_user.username} ({callback_query.from_user.first_name} {callback_query.from_user.last_name})",
        'message': data,
        'type': 'data'
    }
    await crud.create_telegram_monitor(user_monitor_dict)

date_menu = {
    'today': lambda daynow: process_day_events(0, daynow),
    'tomorrow': lambda daynow: process_day_events(1, daynow),
    'weekend': lambda daynow: process_weekend_events(daynow),
    'exhibitions': lambda daynow: process_exhibitions(daynow),
    'lucky': lambda daynow: process_lucky_event(daynow),
    'weekday': lambda daynow: process_weekday_events(daynow.weekday(), daynow),
}


async def process_events_callback(callback_query: types.CallbackQuery):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)
    data_command = callback_query.data
    handler = date_menu.get(data_command)

    answer = f"*{MENU['events'][data_command]}:*\n"
    if data_command == 'weekend':
        saturday_events, sunday_events = await handler(daynow)
        answer = f"{answer}{saturday_events}\n{sunday_events}"
        await callback_query.message.answer(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    elif data_command == 'exhibitions':
        answer = answer + await handler(daynow)
        await callback_query.message.answer(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    elif data_command == 'lucky':
        answer = answer + await handler(daynow)
        await callback_query.message.answer(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
        return 1
    elif data_command == 'weekday':
        await callback_query.message.answer('Выберите день недели', reply_markup=await show_menu('weekday'))
        return 1
    elif handler:
        result_text = await handler(daynow)
        answer = answer + result_text
        await callback_query.message.answer(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
        if 'не найдено' in result_text or result_text.strip=='':
            return 1
    else:
        await callback_query.message.answer('Неверная команда', reply_markup=await show_menu('events'))
        return 1


async def process_weekday_callback(callback_query: types.CallbackQuery):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    data_command = callback_query.data
    weekday = list(MENU['weekday'].keys()).index(data_command)

    answer = f"_{MENU['weekday'][data_command]}:_\n"
    result_text = await process_weekday_events(weekday, daynow)
    answer = answer + result_text
    await callback_query.message.reply(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                       reply_markup=await show_menu('weekday'))

    if 'не найдено' in result_text or result_text.strip == '':
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
        balance = await crud.toggle_balance(callback_query.from_user.id)
        await callback_query.message.answer(
            f'Баланс: {balance}', parse_mode="Markdown",
            reply_markup=await show_menu('balance')
        )
        if balance < 0:
            user_dict = {
                'telegram_id': callback_query.from_user.id,
                'username': callback_query.from_user.username,
                'first_name': callback_query.from_user.first_name,
                'last_name': callback_query.from_user.last_name,
                'balance': 100
            }
            await crud.make_new_user(user_dict)

    elif data_command == 'saved_events' or data_command.startswith('sevent_'):

        saved_events_fast = await process.get_saved_user_event_fast(callback_query.from_user.id)
        answer_message = None
        if saved_events_fast:
            answer_fast = f"Ваши сохранённые события:\n{saved_events_fast}\n(Дозагрузка..)"
            answer_message = await callback_query.message.answer(answer_fast, parse_mode="Markdown", disable_web_page_preview=True,
                                                   reply_markup=await show_menu('settings'))
        await process_message_saved_event(callback_query, answer_message=answer_message, old=0)

    elif data_command == 'saved_events_old':
        await process_message_saved_event(callback_query, old=1)


async def process_balance_callback(callback_query: types.CallbackQuery):
    data_command = callback_query.data
    if data_command == 'balance_add':
        await callback_query.message.answer_invoice(
            title="Пополнение баланса",
            description="Пополни баланс через Telegram Stars",
            payload="balance_topup",
            currency="XTR",
            prices=[types.LabeledPrice(label="10 звёзд", amount=10)],
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


async def process_saved_events(callback_query):
    callback_data = callback_query.data
    telegram_id = callback_query.from_user.id
    _, mod, event_id = callback_data.split('_')
    if mod in ['edit', 'enbl']:
        waiting_for_time[telegram_id] = event_id
        await callback_query.message.answer(
            f'Введите время для напоминания о мероприятии:', parse_mode="Markdown")
    elif mod in ['dis', 'del']:
        answer = await process.toggle_saved_event(telegram_id, event_id, mod)
        if answer == 0:
            answer = f'Напоминание отключено'
        elif answer == -1:
            answer = f'Ваше мероприятие удалено из списка сохраненных'
        else:
            answer = f'Произошла ошибка с доступом, попробуйте попозже'

        await callback_query.message.answer(answer, parse_mode="Markdown")
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