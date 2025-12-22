from database.session import db_session
from database.models import DsnUser, DsnUserEvent, TelegramMonitor, Events2Post # SavedUserEvent, User,
from sqlalchemy import select, or_


@db_session
async def save_event_for_user(db, **saved_user_event):
    result = await db.execute(
        select(DsnUserEvent).filter(
            DsnUserEvent.user_id  == saved_user_event['user_id'],
            DsnUserEvent.event_id == saved_user_event['event_id'],
        ))
    existing_event = result.scalar_one_or_none()

    if existing_event:
        return existing_event.__dict__

    user_event = DsnUserEvent(**saved_user_event)
    db.add(user_event)
    await db.commit()


@db_session
async def get_saved_user_event(db, user_id: int, old: int = 0):
    if old == 0:
        result = await db.execute(
            select(DsnUserEvent).filter(
                DsnUserEvent.user_id == user_id,
                DsnUserEvent.remind_sent == False
            )
        )
    else:
        result = await db.execute(
            select(DsnUserEvent).filter(
                DsnUserEvent.user_id == user_id,
                DsnUserEvent.remind_sent == True
            )
        )

    return result.scalars().all()


@db_session
async def toggle_remind_events(db, user_id, event_id, opt):
    user_event = \
        await db.scalar(select(DsnUserEvent).filter(
            DsnUserEvent.user_id == user_id,
            DsnUserEvent.event_id == int(event_id)
        ))
    if user_event:
        if opt == 0:
            user_event.remind_datetime = None
        elif opt == -1:
            await db.delete(user_event)

        await db.commit()


@db_session
async def edit_time_reminder(db, user_id, event_id, remind_datetime):
    user_event = \
        await db.scalar(select(DsnUserEvent).filter(
            DsnUserEvent.user_id == user_id,
            DsnUserEvent.event_id == int(event_id)
        ))

    if user_event:
        user_event.remind_datetime = remind_datetime
        user_event.remind_sent = False
        await db.commit()


@db_session
async def get_weekend_guide_users(db):
    users = await db.execute(
        select(DsnUser).filter(DsnUser.weekend_guide==1)
    )
    return users


@db_session
async def toggle_weekend_guide(db, telegram_id: int) -> bool:
    """Toggle weekend guide setting for user. Returns new state."""
    result = await db.execute(
        select(DsnUser).filter(DsnUser.telegram_id == telegram_id)
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
        select(DsnUser).filter(DsnUser.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user.balance
    return -1


@db_session
async def change_balance(db, telegram_id: int, stars: int):
    user = await db.scalar(select(DsnUser).filter(DsnUser.telegram_id == telegram_id))
    if user:
        user.balance += stars
        await db.commit()
        return user.balance
    return -1


@db_session
async def make_new_user(db, user_dict: dict):
    # Check if user with this telegram_id already exists
    user = await get_user_by_telegram(user_dict['telegram_id'])

    # If user already exists, return the existing user
    if not user:
        user = DsnUser(**user_dict)
        db.add(user)
        await db.commit()
    return user


@db_session
async def get_user_by_telegram(db, telegram_id: int):
    result = await db.execute(
        select(DsnUser).filter(DsnUser.telegram_id == telegram_id)
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

