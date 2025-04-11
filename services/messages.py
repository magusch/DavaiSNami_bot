from aiogram import Bot
import services.crud as crud
from datetime import datetime


async def send_reminder(bot: Bot, user_id: int, event_title: str, event_date: datetime):
    """Send a reminder message to user about upcoming event"""
    message = f"🔔 Напоминание!\n\nСегодня пройдёт мероприятие '{event_title}' в {event_date.strftime('%H:%M')}"
    await bot.send_message(user_id, message)

async def send_weekend_guide(bot: Bot, user_id: int, events_text: str):
    """Send weekend events guide to user"""
    message = f"🌅 Гайд на выходные!\n\n{events_text}"
    await bot.send_message(user_id, message, parse_mode="Markdown", disable_web_page_preview=True)

async def check_and_send_reminders(bot: Bot):
    """Check for events that need reminders and send them"""
    reminders = crud.get_remind_events()
    for reminder in reminders:
        await send_reminder(bot, reminder.user.telegram_id, reminder.event_title, reminder.event_date)

async def send_weekend_guides(bot: Bot, events_text: str):
    """Send weekend guides to all users who enabled this feature"""
    users = crud.get_weekend_guide_users()
    for user in users:
        await send_weekend_guide(bot, user.telegram_id, events_text)
    