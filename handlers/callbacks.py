from datetime import datetime, timedelta, timezone

from keyboards import show_menu
from aiogram import types

from services.process import process_day_events, process_weekday_events, process_exhibitions, process_lucky_event, process_weekend_events
from services import crud
from services import process
from config import MENU, CHANNEL_LINK


async def process_menu_callback(callback_query: types.CallbackQuery):
    message = await callback_query.message.edit_text('wait a minute...')
    data = callback_query.data

    if data == 'weekday':
        await callback_query.message.edit_text('Выберите день недели', reply_markup=await show_menu('weekday'))
    elif data == 'events':
        await callback_query.message.edit_text('Когда?', reply_markup=await show_menu('events'))
    elif data == 'settings':
        await callback_query.message.edit_text('Настройки', reply_markup=await show_menu('settings'))
    elif data in MENU['settings'].keys():
        await process_settings_callback(callback_query)
    elif data in MENU['events'].keys():
        await process_events_callback(callback_query)
    elif data in MENU['weekday'].keys():
        await process_weekday_callback(callback_query)
    elif data in MENU['balance'].keys():
        await process_balance_callback(callback_query)
    else:
        callback_message = f'{data} не найдено, обратитесь к разработчику! \n\n/start'
        await callback_query.message.answer(callback_message, reply_markup=await show_menu('events'))

    user_monitor_dict = {
        'telegram_id': callback_query.from_user.id,
        'telegram_info': f"{callback_query.from_user.username} ({callback_query.from_user.first_name} {callback_query.from_user.last_name})",
        'message': data,
        'type': 'data'
    }
    await crud.create_telegram_monitor(user_monitor_dict)
    #await message.delete()

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
        await callback_query.message.reply(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    elif data_command == 'exhibitions':
        answer = answer + await handler(daynow)
        await callback_query.message.reply(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    elif data_command == 'lucky':
        answer = answer + await handler(daynow)
        await callback_query.message.reply(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    elif data_command == 'weekday':
        await callback_query.message.edit_text('Выберите день недели', reply_markup=await show_menu('weekday'))
    elif handler:
        answer = answer + await handler(daynow)
        await callback_query.message.reply(answer, parse_mode="Markdown",
                                           reply_markup=await show_menu('events'), disable_web_page_preview=True)
    else:
        await callback_query.message.reply('Неверная команда', reply_markup=await show_menu('events'))


async def process_weekday_callback(callback_query: types.CallbackQuery):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    data_command = callback_query.data
    weekday = list(MENU['weekday'].keys()).index(data_command)

    answer = f"_{MENU['weekday'][data_command]}:_\n"
    answer = answer + await process_weekday_events(weekday, daynow)
    await callback_query.message.reply(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                       reply_markup=await show_menu('weekday'))

async def process_settings_callback(callback_query: types.CallbackQuery):
    data_command = callback_query.data
    if data_command == 'city':
        await callback_query.message.edit_text('Выберите город', reply_markup=await show_menu('city'))
    elif data_command == 'weekend_guide':
        is_enabled = await crud.toggle_weekend_guide(callback_query.from_user.id)
        status = "включен" if is_enabled else "выключен"
        await callback_query.message.edit_text(
            f'Гайд на выходные {status}', parse_mode="Markdown",
            reply_markup=await show_menu('settings')
        )
    elif data_command == 'balance':
        balance = await crud.toggle_balance(callback_query.from_user.id)
        await callback_query.message.edit_text(
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

    elif data_command == 'saved_events':

        saved_events_fast = await process.get_saved_user_event_fast(callback_query.from_user.id)
        if saved_events_fast:
            answer_fast = f"Ваши сохранённые события:\n{saved_events_fast}"
            await callback_query.message.edit_text(answer_fast, parse_mode="Markdown", disable_web_page_preview=True,
                                                   reply_markup=await show_menu('settings'))

        saved_events = await process.get_saved_user_event(telegram_id=callback_query.from_user.id)
        if saved_events:
            answer = f"Ваши сохранённые события:\n{saved_events}"
        else:
            answer = f"У вас нет сохранённых событий. Пересылайте события из канала {CHANNEL_LINK}"
        await callback_query.message.edit_text(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                               reply_markup=await show_menu('settings'))


async def process_balance_callback(callback_query: types.CallbackQuery):
    data_command = callback_query.data
    if data_command == 'balance_add':
        await callback_query.message.answer_invoice(
            title="Пополнение баланса",
            description="Пополни баланс через Telegram Stars",
            payload="balance_topup",
            currency="XTR",
            prices=[types.LabeledPrice(label="1 звёзд", amount=1)],  # 100 Stars
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
    elif data_command == 'referal_url':
        link = "https://t.me/your_bot?start=referral: " + str(callback_query.from_user.id)
        await callback_query.message.edit_text(
            'Пусть друзья зайдут по вашей ссылке и вы получите по 100 даснов:\n' + link,
            parse_mode="Markdown",
            reply_markup=await show_menu('balance')
        )


async def process_save_event(callback):
    event_id = int(callback.data.split(":")[1])
    user_event_dict = {'telegram_id': callback.from_user.id, 'event_id': event_id}
    return await process.process_user_event(user_event_dict)

