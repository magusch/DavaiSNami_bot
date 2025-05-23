from database.session import db_session
from database.models import SavedUserEvent, User, TelegramMonitor, Events2Post
from sqlalchemy import select, or_

from datetime import datetime, timedelta


@db_session
async def save_event_for_user(db, **saved_user_event):
   user_event = SavedUserEvent(**saved_user_event)
   db.add(user_event)
   await db.commit()


@db_session
async def get_saved_user_event(db, user_id: int):
    # get Event id from SavedUserEvent
   result = await db.execute(
      select(SavedUserEvent).filter(
         SavedUserEvent.user_id == user_id
      )
   )
   return result.scalars().all()

@db_session
async def get_saved_user_event_by_teleram(db, telegram_id: int):
    # get Event id from SavedUserEvent
   result = await db.execute(
      select(SavedUserEvent).filter(
         SavedUserEvent.telegram_id == telegram_id
      )
   )
   return result.scalars().all()


@db_session
async def get_remind_events(db, now):
   result = await db.execute(
      select(SavedUserEvent).filter(
         SavedUserEvent.is_remind == True,
         SavedUserEvent.event_date >= now + timedelta(hours=10),
         SavedUserEvent.event_date < now
      )
   )
   return result.scalars().all()


@db_session
async def get_weekend_guide_users(db):
   users = await db.execute(
      select(User).filter(User.weekend_guide==1)
   )
   return users


@db_session
async def toggle_weekend_guide(db, telegram_id: int) -> bool:
    """Toggle weekend guide setting for user. Returns new state."""
    result = await db.execute(
        select(User).filter(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.weekend_guide = not user.weekend_guide
        await db.commit()
        return user.weekend_guide
    return False


@db_session
async def toggle_balance(db, telegram_id: int) -> bool:
    result = await db.execute(
        select(User).filter(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user.balance
    return -1


@db_session
async def increase_balance(db, telegram_id: int, stars: int):
    user = await db.scalar(select(User).filter(User.telegram_id == telegram_id))
    if user:
        user.balance += stars*10
        await db.commit()
        return user.balance
    return -1


@db_session
async def make_new_user(db, user_dict: dict):
    # Check if user with this telegram_id already exists
    result = await db.execute(
        select(User).filter(User.telegram_id == user_dict['telegram_id'])
    )
    user = result.scalar_one_or_none()
    
    # If user already exists, return the existing user
    if not user:
        user = User(**user_dict)
        db.add(user)
        await db.commit()
    return user


@db_session
async def get_user_by_telegram(db, telegram_id: int):
    result = await db.execute(
        select(User).filter(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    return user


@db_session
async def get_event_by_telegram(db, event_post_id: int):
    result = await db.execute(
        select(Events2Post).filter(or_(
            Events2Post.post_url.like(f'%{event_post_id}'),
            Events2Post.post_url == str(event_post_id)
        ))
    )

    return result.scalar_one_or_none()

@db_session
async def get_event_by_ids(db, event_ids: list[int]):
    result = await db.execute(
        select(Events2Post).filter(Events2Post.id.in_(event_ids)))

    return result.scalars().all()


@db_session
async def create_telegram_monitor(db, monitor_dict: dict):
    monitor = TelegramMonitor(**monitor_dict)
    db.add(monitor)
    await db.commit()
    return monitor

