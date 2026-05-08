import logging
import re

from aiogram import types
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from config import WEEK_MENU, MENU, MONTHES, LANG, ID_ADMIN, ID_CHANNEL
from keyboards import show_menu

from services import process
import services.crud as crud
import services.external_api as external_api
from services.utils import send_chunked

date_menu = {
    MENU['events']['today']: lambda daynow: process.process_day_events(0, daynow),
    MENU['events']['tomorrow']: lambda daynow: process.process_day_events(1, daynow),
    MENU['events']['weekend']: lambda daynow: process.process_weekend_events(daynow),
    MENU['events']['lucky']: lambda daynow: process.process_lucky_event(daynow),
    MENU['events']['exhibitions']: lambda daynow: process.process_exhibitions(daynow),
    #DATE_MENU['weekday']: lambda daynow: process.process_weekday_events(daynow.weekday(), daynow),
}


async def handle_message(message: types.Message):
    message_text = message.text
    if message.successful_payment:
        if message.successful_payment.invoice_payload == "balance_topup":
            user_id = message.from_user.id
            stars_amount = message.successful_payment.total_amount*10
            await crud.change_balance(user_id, stars_amount)
            await message.answer(
                f"Баланс пополнен на {stars_amount} ⭐️!",
                reply_markup=await show_menu('events'),
            )
            if message_text is None:
                message_text = ''
            message_text += f"; Баланс пополнен на {stars_amount} ⭐️!"

    elif message.forward_date:
        forward_chat = message.forward_from_chat
        if forward_chat and forward_chat.id == ID_CHANNEL:
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
        else:
            await message.answer(
                "Это не похоже на мероприятие из нашего канала. "
                "Чтобы сохранить событие, пересылайте пост из канала с мероприятиями.",
                reply_markup=await show_menu('events'),
            )
    else:
        if not message_text:
            await message.answer(
                "Я понимаю только текстовые сообщения. Пожалуйста, выберите пункт меню или введите дату.",
                reply_markup=await show_menu('events'),
            )
            return
        wait_message = await message.answer('Немного подождите...', reply_markup=types.ReplyKeyboardRemove())
        try:
            message_text = message_text.lower().capitalize()
            if message_text in [MENU['events']['weekday']]:
                answer = MENU['events']['weekday']
                await message.reply(answer, parse_mode="Markdown",
                                    reply_markup=await show_menu('weekday'), disable_web_page_preview=True)
            elif message_text in MENU['events'].values():
                answer = await handle_date_command(message_text)
                await send_chunked(message, answer, reply_first=True, parse_mode="Markdown",
                                   reply_markup=await show_menu('events'), disable_web_page_preview=True)
            elif message_text in MENU['settings'].values():
                await handle_setting(message_text)
                await message.answer("⚙️ Настройки", parse_mode="Markdown", reply_markup=await show_menu('settings'),
                                     disable_web_page_preview=True)
            elif message_text in MENU['weekday'].values():
                answer = await handle_weekday_text(message_text)
                await send_chunked(message, answer, reply_first=True, parse_mode="Markdown",
                                   reply_markup=await show_menu('events'), disable_web_page_preview=True)
            else:
                answer, found = await handle_date_text(message_text)
                await send_chunked(message, answer, reply_first=True, parse_mode="Markdown",
                                   reply_markup=await show_menu('events'), disable_web_page_preview=True)

                if found:
                    await crud.change_balance(message.from_user.id, -2)
        finally:
            try:
                await wait_message.delete()
            except Exception:
                logger.exception("Failed to delete wait message")
    user_monitor_dict = {
        'telegram_id': message.from_user.id,
        'telegram_info': f"{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})",
        'message': message_text,
        'type': 'message'
    }
    await crud.create_telegram_monitor(user_monitor_dict)


async def handle_date_command(text_message):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)
    handler = date_menu.get(text_message)
    if handler:
        if text_message == MENU['events']['weekend']:
            sat, sun = await handler(daynow)
            answer = f"_Выходные:_\n{sat.text}\n{sun.text}"
        else:
            result = await handler(daynow)
            answer = f"*{text_message.capitalize()}:*\n{result.text}"
        answer = await process.footer_message(answer)
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
        result = await process.process_events(date_with_events)
        answer = await process.footer_message(result.text)
        return answer, result.found

    except (ValueError, IndexError):
        answer = "Возникла ошибка, вероятно нам не удалось распознать дату.\n Пожалуйста, укажите дату в формате 'ДД.ММ', 'ДД месяц' или просто 'ДД'."
        return answer, False


async def handle_weekday_text(message_text):
    daynow = datetime.now(timezone.utc) + timedelta(hours=3)

    weekday = WEEK_MENU[LANG].index(message_text.capitalize())

    result = await process.process_weekday_events(weekday, daynow)
    return await process.footer_message(result.text)


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


async def handle_time_for_event(message, state):
    data = await state.get_data()
    event_id = data.get('event_id')
    await state.clear()

    telegram_id = message.from_user.id
    remind_datetime = await process.edit_remind_time(telegram_id, event_id, message.text)
    if remind_datetime:
        await message.reply(f"Установлено напоминание: {remind_datetime}")
    else:
        await message.reply(
            "Не удалось распознать дату, напоминание не установлено.\n\n"
            "Попробуйте формат:\n"
            "• `12.05 18:30`\n"
            "• `12 мая 18:30`\n"
            "• `12.05` (без времени — в 12:00)",
            parse_mode="Markdown",
        )

    result = await process.process_saved_user_event(telegram_id=telegram_id)
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
