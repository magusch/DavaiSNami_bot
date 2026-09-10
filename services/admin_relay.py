"""Пересылка админу того, на что бот сам не отвечает.

Троттлинг in-memory, как в history: один спамер не должен завалить админа.
"""

import logging
import time

from config import ID_ADMIN

logger = logging.getLogger(__name__)

_SEEN = {}                  # chat_id -> {'ts': float, 'count': int}
_WINDOW = 60 * 60           # окно троттлинга
_MAX_PER_WINDOW = 10        # больше не пересылаем, только пишем в лог


def _allow(chat_id):
    entry = _SEEN.get(chat_id)
    now = time.time()
    if not entry or now - entry['ts'] > _WINDOW:
        _SEEN[chat_id] = {'ts': now, 'count': 1}
        return True
    entry['count'] += 1
    return entry['count'] <= _MAX_PER_WINDOW


def _header(message, reason):
    chat = message.chat
    lines = [f"📨 {reason}"]
    if chat.type != 'private':
        lines.append(f"Чат: {chat.title or chat.type} ({chat.id})")
    user = message.from_user
    if user:
        username = f" @{user.username}" if user.username else ""
        lines.append(f"От: {user.full_name}{username} ({user.id})")
    return "\n".join(lines)


async def relay_to_admin(message, reason):
    """Показать сообщение админу. True — переслали, False — некому/тротлим/упало."""
    if not ID_ADMIN:
        return False
    if not _allow(message.chat.id):
        logger.info("Admin relay throttled for chat %s (%s)", message.chat.id, reason)
        return False
    try:
        # без parse_mode: в имени и названии чата может быть что угодно
        await message.bot.send_message(ID_ADMIN, _header(message, reason))
        await message.forward(ID_ADMIN)
        return True
    except Exception:
        logger.exception("Failed to relay message to admin (%s)", reason)
        return False
