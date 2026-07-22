"""Лёгкое in-memory хранилище истории диалога по chat_id для уточняющих
семантических запросов («а подешевле», «а в субботу?»).

Без БД: история живёт в памяти процесса и сбрасывается по таймауту бездействия.
Сервер всё равно берёт только последние 6 реплик, поэтому больше не храним.
"""

import time

_HISTORY = {}  # chat_id -> {'ts': float, 'items': [str, ...]}
_TTL = 20 * 60  # сбрасываем историю после 20 минут бездействия
_MAX = 6


def get_history(chat_id):
    """Вернуть последние реплики (старые → новые) или [] если истёк TTL."""
    entry = _HISTORY.get(chat_id)
    if not entry:
        return []
    if time.time() - entry['ts'] > _TTL:
        _HISTORY.pop(chat_id, None)
        return []
    return list(entry['items'][-_MAX:])


def add_message(chat_id, text):
    """Дописать реплику пользователя в историю."""
    entry = _HISTORY.get(chat_id)
    if not entry or time.time() - entry['ts'] > _TTL:
        entry = {'items': []}
    entry['items'].append(text)
    entry['items'] = entry['items'][-_MAX:]
    entry['ts'] = time.time()
    _HISTORY[chat_id] = entry


def clear(chat_id):
    """Сбросить историю (новая тема)."""
    _HISTORY.pop(chat_id, None)
