"""Who triggered an API request: sent to the API as the X-Client-Context header
so its request log can tie a call to a Telegram user.

An outer update middleware stores the context in a contextvar, external_api
reads it when building headers — so the call chain doesn't have to pass tg_id
around. asyncio.create_task copies the context, background tasks keep it.

Keys are shared with the web app: app, user_id, tg_id, ip, session. The bot
knows no ip (Telegram doesn't give it) and no session; extra keys are ours.
No names or phones — the id is enough."""

from __future__ import annotations

import json
from contextvars import ContextVar

from aiogram import BaseMiddleware
from aiogram.types import Update

_MAX_HEADER = 2048
_MAX_ACTION = 64

_context = ContextVar('client_context', default=None)


def header_value() -> str:
    """JSON for X-Client-Context. json.dumps escapes non-ASCII as \\uXXXX by default."""
    ctx = {'app': 'bot', **(_context.get() or {})}
    value = json.dumps(ctx, separators=(',', ':'))
    if len(value) > _MAX_HEADER:   # can't really happen, but the API caps it at 2 KB
        value = json.dumps({k: ctx[k] for k in ('app', 'tg_id') if k in ctx})
    return value


def _action(update: Update) -> str | None:
    """Short tag of what the user did: a command or a callback_data prefix.
    Free text isn't sent — it may hold personal data."""
    if update.message:
        text = update.message.text or ''
        if text.startswith('/'):
            return text.split(maxsplit=1)[0][:_MAX_ACTION]
        return 'text' if text else update.message.content_type
    if update.callback_query and update.callback_query.data:
        return 'cb:' + update.callback_query.data[:_MAX_ACTION]
    return None


class ClientContextMiddleware(BaseMiddleware):
    """Outer middleware for dp.update. Runs after aiogram's own
    UserContextMiddleware, so event_from_user / event_chat are already set."""

    async def __call__(self, handler, event: Update, data):
        user = data.get('event_from_user')
        chat = data.get('event_chat')
        ctx = {
            'tg_id': user.id if user else None,
            'chat_id': chat.id if chat and (not user or chat.id != user.id) else None,
            'lang': user.language_code if user else None,
            'update': event.event_type,
            'update_id': event.update_id,
            'action': _action(event),
        }
        token = _context.set({k: v for k, v in ctx.items() if v is not None})
        try:
            return await handler(event, data)
        finally:
            _context.reset(token)
