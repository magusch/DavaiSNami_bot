import re

from aiogram import types
from datetime import datetime, timedelta, timezone

from config import WEEK_MENU, MENU, MONTHES, LANG, ID_ADMIN, ID_CHANNEL, waiting_for_time
from keyboards import show_menu

from services import process
import services.crud as crud
import services.external_api as external_api

date_menu = {
    MENU['events']['today']: lambda daynow: process.process_day_events(0, daynow),
    MENU['events']['tomorrow']: lambda daynow: process.process_day_events(1, daynow),
    MENU['events']['weekend']: lambda daynow: process.process_weekend_events(daynow),
    MENU['events']['lucky']: lambda daynow: process.process_lucky_event(daynow),
    MENU['events']['exhibitions']: lambda daynow: process.process_exhibitions(daynow),
    #DATE_MENU['weekday']: lambda daynow: process.process_weekday_events(daynow.weekday(), daynow),
}


async def handle_message(message: types.Message):
    if message.successful_payment:
        if message.successful_payment.invoice_payload == "balance_topup":
            user_id = message.from_user.id
            stars_amount = message.successful_payment.total_amount*10
            await crud.change_balance(user_id, stars_amount)
            await message.answer(f"Баланс пополнен на {stars_amount} ⭐️!")
    elif message.forward_date:
        if message.forward_from_chat.id == ID_CHANNEL:
            if await process_forwarded_event(message):
                answer = "Мероприятие успешно сохранено! Также было запланировано напоминание! " \
                         "Отредактировать напоминание можно в настройках."
            else:
                answer = "Мероприятие не добавлено! Возможно это не мероприятие или оно истекло. " \
                         "Если это не так напишите в поддержку"

            await message.answer(answer, parse_mode="Markdown", reply_markup=await show_menu('events'),
                                 disable_web_page_preview=True)
        elif message.from_user.id == ID_ADMIN:
            await process_forwarded_admin_message(message)
    elif message.from_user.id in waiting_for_time:
        await handle_time_for_event(message)

        result = await process.process_saved_user_event(telegram_id=message.from_user.id)

        if result is not None:
            answer, sevent_menu = result
        else:
            answer = f"У вас нет сохранённых событий. Пересылайте события из канала"
            sevent_menu = None

        if sevent_menu:
            await message.answer(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                 reply_markup=sevent_menu)
        else:
            await message.answer(answer, parse_mode="Markdown", disable_web_page_preview=True,
                                 reply_markup=await show_menu('settings'))

    else:
        wait_message = await message.answer('Немного подождите...', reply_markup=types.ReplyKeyboardRemove())
        message_text = message.text.lower().capitalize()
        if message_text in [MENU['events']['weekday']]:
            answer = MENU['events']['weekday']
            await message.reply(answer, parse_mode="Markdown",
                                reply_markup=await show_menu('weekday'), disable_web_page_preview=True)
        elif message_text in MENU['events'].values():
            answer = await handle_date_command(message_text)
            await message.reply(answer, parse_mode="Markdown",
                                reply_markup=await show_menu('events'), disable_web_page_preview=True)
        elif message_text in MENU['settings'].values():
            await handle_setting(message_text)
            await message.answer("⚙️ Настройки", parse_mode="Markdown", reply_markup=await show_menu('settings'),
                                 disable_web_page_preview=True)
        elif message_text in MENU['weekday'].values():
            answer = await handle_weekday_text(message_text)
            await message.reply(answer, parse_mode="Markdown", reply_markup=await show_menu('events'),
                                disable_web_page_preview=True)
        else:
            answer = await handle_date_text(message_text)
            await message.reply(answer, parse_mode="Markdown", reply_markup=await show_menu('events'),
                                disable_web_page_preview=True)

            if 'не найдено' not in answer:
                await crud.change_balance(message.from_user.id, -2)

        await wait_message.delete()
    user_monitor_dict = {
        'telegram_id': message.from_user.id,
        'telegram_info': f"{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})",
        'message': message.text,
        'type': 'message'
    }
    await crud.create_telegram_monitor(user_monitor_dict)


async def handle_date_command(text_message):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)
    handler = date_menu.get(text_message)
    if handler:
        answer = f"*{text_message.capitalize()}:*\n"
        if text_message == MENU['events']['weekend']:
            saturday_events, sunday_events = await handler(daynow)
            answer = f"_Выходные:_\n{saturday_events}\n{sunday_events}"
        else:
            answer = answer + await handler(daynow)
    else:
        answer = 'Неверная команда'

    return answer


async def handle_setting(message_text):
    pass


async def handle_date_text(message_text):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    parts = re.split(r'[.,\-/ ]', message_text)
    parts = [part for part in parts if part]  # Удаляем пустые строки
    
    try:
        day = int(parts[0])  # Пытаемся получить день из первой части
        
        # Определяем месяц
        if len(parts) == 1:  # Если указан только день
            # Если день уже прошел в текущем месяце, берем следующий месяц
            if day < daynow.day:
                month = daynow.month % 12 + 1
            else:
                month = daynow.month
        elif len(parts) >= 2:
            # Пытаемся определить месяц из второй части
            if parts[1].isdigit():  # Если вторая часть - число (например, 31.01)
                month = int(parts[1])
            else:  # Если вторая часть - название месяца (например, 31 января)
                month_name = parts[1].lower()
                # Ищем месяц в списке месяцев
                for i, month_str in enumerate(MONTHES[LANG]):
                    if month_str.startswith(month_name) or month_name.startswith(month_str[:3]):
                        month = i + 1
                        break
                else:  # Если месяц не найден
                    month = daynow.month
                    if day < daynow.day:
                        month = month % 12 + 1
        
        # Определяем год
        year = daynow.year
        if month < daynow.month or (month == daynow.month and day < daynow.day):
            year += 1
            
        # Создаем объект даты
        date_with_events = datetime(day=day, month=month, year=year)
        
        # Получаем события на указанную дату
        answer = f"События на {day} {MONTHES[LANG][month-1]} {year}:\n"
        answer += await process.process_events(date_with_events)
        # Здесь должен быть код для получения событий на указанную дату
        
    except (ValueError, IndexError):
        answer = "Не удалось распознать дату. Пожалуйста, укажите дату в формате 'ДД.ММ', 'ДД месяц' или просто 'ДД'."

    return answer


async def handle_weekday_text(message_text):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    weekday = WEEK_MENU[LANG].index(message_text.capitalize())

    answer = f"_{message_text.capitalize()}:_\n"
    answer += await process.process_weekday_events(weekday, daynow)
    return answer


async def process_forwarded_event(message: types.Message):
    """
    Process forwarded events from admin and send to API service for post creation.
    
    Args:
        message (types.Message): The forwarded message from user
        """
    event_post_id = message.forward_origin.message_id
    user_id = message.from_user.id
    return await process.process_user_event({'telegram_id': user_id, 'post_id': event_post_id})


async def process_forwarded_admin_message(message: types.Message):
    """
    Process forwarded messages from admin and send to API service for post creation.
    
    Args:
        message (types.Message): The forwarded message from admin
        """
    content = message.text or message.caption or ""
        
    post_data = {
        "content": content,
        "message_id": message.message_id,
        "forward_from": message.forward_from.id if message.forward_from else None,
        "forward_date": message.forward_date.isoformat() if message.forward_date else None,
    }

    await external_api.create_post_by_ai(post_data)

    await message.reply("Пост отправлен на обработку!", reply_markup=await show_menu('events'))


async def handle_time_for_event(message):
    telegram_id = message.from_user.id
    event_id = waiting_for_time.pop(telegram_id)
    remind_datetime = await process.edit_remind_time(telegram_id, event_id, message.text)
    if remind_datetime:
        await message.reply(f"Поставлено новое время для напоминания о мероприятии: {remind_datetime}")
    else:
        await message.reply(f"Ошибка с определением времени, напоминалка не установлена.")
