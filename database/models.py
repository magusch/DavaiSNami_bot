from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Boolean, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase

from datetime import datetime


class Base(DeclarativeBase):
    pass

class TelegramMonitor(Base):
    __tablename__ = 'bot_telegram_monitor'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger)
    telegram_info = Column(String)
    message = Column(String)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.now)


class Events2Post(Base):
    __tablename__ = 'events_events2post'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    prepared_text = Column(String)
    post_url = Column(String)
    price = Column(String)
    from_date = Column(DateTime(timezone=True))
    #dsn_user_events = relationship("DsnUserEvent", back_populates="event")


class DsnUser(Base):
    __tablename__ = "dsn_user"

    id = Column(Integer, primary_key=True)
    nickname = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    balance = Column(Integer, default=100, nullable=True)
    weekend_guide = Column(Boolean, default=False, nullable=True)

    full_name = Column(String, nullable=True)

    dsn_user_events = relationship("DsnUserEvent", back_populates="user")

    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)


class DsnUserEvent(Base):
    __tablename__ = 'dsn_user_event'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('dsn_user.id'), index=True)
    event_id = Column(Integer, ForeignKey('events_events2post.id'), index=True)
    remind_datetime = Column(DateTime(timezone=True), default=None, nullable=True)
    remind_sent = Column(Boolean, nullable=True)

    user = relationship("DsnUser", back_populates="dsn_user_events")
    #event = relationship("Events2Posts", back_populates="dsn_user_events")
