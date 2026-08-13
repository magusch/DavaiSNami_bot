from aiogram import types
from config import CHANNEL_LINK, ACTION_COST, STARS_RATE, TOPUP_STARS, REFERRAL_BONUS
from keyboards import show_menu

import services.crud as crud
from services.process import process_user_event
from services import process


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

    if command.args:
        events_menu = await show_menu('events')
        if "save-" in command.args and user:
            event_id = command.args.split('-')[1].strip()
            if await process_user_event({'user_id': user.id, 'event_id': int(event_id), 'telegram_id': message.from_user.id}):
                await message.answer(f"Пост сохранён! {command.args}", reply_markup=events_menu)
        elif 'referral-' in command.args:  # and new_user
            referral_id = int(command.args.split("-")[1].strip())
            if new_user:
                await process.referral_click(referral_id, message.from_user.id)
                await message.answer(
                    "Вы успешно зарегистрировались по реферальной ссылке!",
                    reply_markup=events_menu,
                )
            else:
                await message.answer("Вы уже были зарегистрированы!", reply_markup=events_menu)
    else:
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