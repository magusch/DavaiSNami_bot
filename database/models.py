from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'bot_user'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    is_admin = Column(Boolean, default=False)
    balance = Column(Integer, default=50)
    weekend_guide = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    events = relationship('SavedUserEvent', back_populates='user')
    monitor = relationship('TelegramMonitor', back_populates='user')


class TelegramMonitor(Base):
    __tablename__ = 'bot_telegram_monitor'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger)
    user_id = Column(Integer, ForeignKey('bot_user.id'))
    user = relationship('User', back_populates='monitor')
    telegram_info = Column(String)
    message = Column(String)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.now)


class SavedUserEvent(Base):
    __tablename__ = 'bot_user_events'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('bot_user.id'))
    user = relationship('User', back_populates='events')
    telegram_id = Column(Integer)
    post_id = Column(Integer)
    event_title = Column(DateTime)
    event_date = Column(DateTime)
    event_id = Column(Integer, ForeignKey('events_events2post.id'))
    is_remind = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class Events2Post(Base):
    __tablename__ = 'events_events2post'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    prepared_text = Column(String)
    post_url = Column(String)
    price = Column(String)
