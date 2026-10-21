import re

from aiogram import types
from config import CHANNEL_LINK, ACTION_COST, STARS_RATE, TOPUP_STARS, REFERRAL_BONUS
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import show_menu, selection_picker_keyboard, city_menu
from services.utils import webapp_link

import services.crud as crud
from services import city as city_service
from services.process import process_user_event
from services import process

# /start payloads, always <kind>-<id> with a hyphen:
# pick-<selection_id> — pick events from a digest post,
# save-<event_id> — save one event (also where a channel ⭐ leads before /start),
# referral-<telegram_id>,
# city-<code> — set the user's city (bot link from a city channel).
START_PAYLOAD = re.compile(r'(pick|save|referral)-(\d+)|city-([a-z]+)')


async def process_command_handler(message: types.Message, command):
    if command.command == 'start':
        await start_command(message, command)
    elif command.command == 'help':
        await help_command(message)
    elif command.command == 'paysupport':
        await paysupport_command(message)
    elif command.command == 'support':
        await support_command(message)
    elif command.command == 'terms':
        await terms_command(message)

    user_monitor_dict = {
        'telegram_id': message.from_user.id,
        'telegram_info': f"{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})",
        'message': f"{command.command}" + (f" {command.args}" if command.args else ""),
        'type': 'command'
    }
    await crud.create_telegram_monitor(user_monitor_dict)


async def start_command(message: types.Message, command):
    user = await crud.get_user_by_telegram(message.from_user.id)
    new_user = False
    if not user:
        await process.new_user(message)
        user = await crud.get_user_by_telegram(message.from_user.id)
        new_user = True

    payload = START_PAYLOAD.fullmatch(command.args.strip()) if command.args else None
    if not payload:
        await help_command(message)
        await ask_city_if_unset(message)
        return

    events_menu = await show_menu('events')
    if payload.group(3):
        await city_start(message, payload.group(3))
        return

    kind, object_id = payload.group(1), int(payload.group(2))
    if kind == 'pick':
        await selection_picker(message, user, object_id)
    elif kind == 'save':
        event = await process_user_event({'user_id': user.id, 'event_id': object_id})
        if event:
            await city_service.adopt_city(message.from_user.id, event.city_id)
            text = f"⭐ Сохранил «{event.title}».\n{process.remind_note(event)}".strip()
            await message.answer(text, reply_markup=events_menu)
        else:
            await message.answer("Не нашёл это мероприятие.", reply_markup=events_menu)
    elif kind == 'referral':
        if new_user:
            await process.referral_click(object_id, message.from_user.id)
            await message.answer(
                "Вы успешно зарегистрировались по реферальной ссылке!",
                reply_markup=events_menu,
            )
        else:
            await message.answer("Вы уже были зарегистрированы!", reply_markup=events_menu)
        await ask_city_if_unset(message)


async def ask_city_if_unset(message: types.Message):
    """Ask for the city on /start while dsn_user.city_id is NULL."""
    if await city_service.get_user_city(message.from_user.id, default=None) is not None:
        return
    cities = await city_service.active_cities()
    if len(cities) < 2:
        return
    await message.answer("🏙 Из какого вы города? Афиша и поиск будут по нему, "
                         "поменять можно в ⚙️ Настройках.",
                         reply_markup=await city_menu(cities, back=False))


async def selection_picker(message: types.Message, user, selection_id: int):
    """/start pick-<selection_id>: events of a digest post, a ⭐ for each."""
    picker = await process.process_selection_picker(selection_id, user.id)
    if picker.status == 'ok':
        await city_service.adopt_city(message.from_user.id, picker.city)
        keyboard = await selection_picker_keyboard(selection_id, picker.events,
                                                   picker.webapp_url, picker.saved_ids)
        await message.answer(picker.text, parse_mode="HTML", disable_web_page_preview=True,
                             reply_markup=keyboard)
    elif picker.status == 'empty':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Актуальные мероприятия", url=webapp_link())],
            *(await show_menu('events')).inline_keyboard,
        ])
        await message.answer("Все мероприятия из этого поста уже прошли.", reply_markup=keyboard)
    elif picker.status == 'not_found':
        await message.answer("Эта подборка уже недоступна.", reply_markup=await show_menu('events'))
    else:
        await message.answer("Не получилось загрузить подборку, попробуйте чуть позже.",
                             reply_markup=await show_menu('events'))


async def city_start(message: types.Message, code: str):
    """/start city-<code>: set the city, then the usual greeting."""
    if await city_service.set_user_city(message.from_user.id, code):
        await message.answer(f"🏙 Город: *{city_service.city_name(code)}*", parse_mode="Markdown")
    await help_command(message)


def _price_note():
    """One-line price list for /start and /help — computed from config, never hardcoded,
    so the texts follow whenever the rates change."""
    return (
        f"\n\n💎 *Самоцветы*: афиша — {ACTION_COST['feed']} 💎, "
        f"поиск по слову — {ACTION_COST['search_keyword']} 💎, "
        f"умный поиск текстом — {ACTION_COST['search_semantic']} 💎.\n"
        f"Баланс и пополнение — в ⚙️ Настройках ({TOPUP_STARS} ⭐ → {TOPUP_STARS * STARS_RATE} 💎), "
        f"или позовите друга: по {REFERRAL_BONUS} 💎 обоим."
    )

async def send_welcome(message: types.Message):
    text = (f"Привет! Это бот канала {CHANNEL_LINK}. С моей помощью можно получить краткий гид мероприятий "
            "на определённый день, на выходные или по проходящим выставкам в городе.\n\n"
            "Чтобы начать, укажите дату или нажмите на кнопку в меню." + _price_note())
    
    keyboard = await show_menu('events')
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await process.new_user(message)


async def help_command(message: types.Message):
    text = (f"Привет! Это бот канала {CHANNEL_LINK}. С моей помощью можно получить краткий гид мероприятий "
            "на определённый день, на выходные или по проходящим выставкам в городе.\n\n"
            "Чтобы начать, укажите дату или нажмите на кнопку в меню." + _price_note())
    await message.answer(text,  parse_mode="Markdown", reply_markup= await show_menu('events'))


async def paysupport_command(message: types.Message):
    await message.answer(
        "💸 *Вопросы по оплате*\n\n"
        "Если у вас возникли проблемы с оплатой или Stars, можете написать нам: @magusch\n"
        "Мы поможем вам в кратчайшие сроки!",
        parse_mode="Markdown", reply_markup=await show_menu('settings')
    )


async def support_command(message: types.Message):
    await message.answer(
        "🛠 *Поддержка*\n\n"
        "По любым вопросам пишите: @magusch",
        parse_mode="Markdown", reply_markup=await show_menu('settings')
    )


async def terms_command(message: types.Message):
    await message.answer(
        "📄 *Пользовательское соглашение*\n\n"
        "Используя этого бота, вы соглашаетесь с правилами сервиса. "
        "Использование бота подразумевает согласие с условиями, "
        "описанными в пользовательском соглашении. ",
        parse_mode="Markdown", reply_markup=await show_menu('settings')
    )