"""Events from posts and links: post text → create_post_by_ai/, URL → ai/event-from-url/."""

import asyncio
import datetime
import itertools
import logging
import re
import time
from urllib.parse import urlsplit

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import services.external_api as external_api
from config import TIMEZONE_HOUR

logger = logging.getLogger(__name__)

URL_CALLBACK = "imp:"       # admin: parse a link
SUGGEST_CALLBACK = "sug:"   # user: suggest a link
USER_DAILY_LIMIT = 3        # suggestions per user per day
MAX_LINKS = 3               # per message
SHORT_POST_CHARS = 200      # shorter post with a link → parse the page, not the text
_LINKS_TTL = 24 * 3600

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_SKIP_HOSTS = ("t.me", "telegram.me")     # except public channel posts
# Public post; its ?embed=1 page has the full text, the plain page often doesn't.
_TG_POST_RE = re.compile(r"^https?://(?:www\.)?(?:t|telegram)\.me/(?:s/)?([A-Za-z][A-Za-z0-9_]{3,})/(\d+)",
                         re.IGNORECASE)

_links = {}                 # key -> {'ts', 'urls', 'city'}; URLs don't fit in callback_data
_keys = itertools.count(1)
_tasks = set()              # strong refs to background tasks
_user_submits = {}          # user_id -> (date, count); resets on restart


def extract_urls(message: types.Message):
    """Unique URLs from text, text_link entities and inline buttons."""
    text = message.text or message.caption or ""
    found = []
    for entity in (message.entities or message.caption_entities or []):
        if entity.type == "text_link" and entity.url:
            found.append(entity.url)
        elif entity.type == "url":
            found.append(entity.extract_from(text))
    found += _URL_RE.findall(text)
    markup = message.reply_markup
    if isinstance(markup, InlineKeyboardMarkup):
        found += [b.url for row in markup.inline_keyboard for b in row if b.url]

    result = []
    for url in found:
        url = url.strip().rstrip(".,;:!?")
        if not url.lower().startswith("http"):
            url = "https://" + url
        url = _tg_post_url(url) or url
        host = (urlsplit(url).hostname or "").lower()
        if not host or url in result:
            continue
        if host.endswith(_SKIP_HOSTS) and not is_tg_post(url):
            continue
        result.append(url)
    return result[:MAX_LINKS]


def _embed(channel, post_id):
    return f"https://t.me/{channel}/{post_id}?embed=1&mode=tme"


def _tg_post_url(url):
    m = _TG_POST_RE.match(url)
    return _embed(m.group(1), m.group(2)) if m else None


def is_tg_post(url):
    return bool(_TG_POST_RE.match(url))


def forwarded_post_url(message: types.Message):
    """Embed URL of a post forwarded from a public channel, else None."""
    origin = message.forward_origin
    chat = getattr(origin, "chat", None)
    post_id = getattr(origin, "message_id", None)
    if chat is not None and chat.username and post_id:
        return _embed(chat.username, post_id)
    return None


def suggestion_urls(message: types.Message):
    """Forwarded post first, then links from it."""
    urls = [u for u in [forwarded_post_url(message)] if u]
    urls += [u for u in extract_urls(message) if u not in urls]
    return urls[:MAX_LINKS]


def link_label(url):
    m = _TG_POST_RE.match(url)
    return f"пост @{m.group(1)}" if m else urlsplit(url).hostname


def display_url(url):
    """Post URL without ?embed=1."""
    m = _TG_POST_RE.match(url)
    return f"https://t.me/{m.group(1)}/{m.group(2)}" if m else url


def has_link(message: types.Message):
    """Any link, t.me included."""
    entities = message.entities or message.caption_entities or []
    return (any(e.type in ("url", "text_link") for e in entities)
            or bool(_URL_RE.search(message.text or message.caption or "")))


def text_without_urls(text):
    return _URL_RE.sub("", text or "").strip()


def is_short_announce(message: types.Message, urls):
    return bool(urls) and len(text_without_urls(message.text or message.caption)) < SHORT_POST_CHARS


# ---- link buttons

def _gc_links():
    now = time.time()
    for key in [k for k, v in _links.items() if now - v["ts"] > _LINKS_TTL]:
        _links.pop(key, None)


def links_keyboard(urls, city, prefix=URL_CALLBACK, label="🔗 Разобрать"):
    if not urls:
        return None
    _gc_links()
    key = str(next(_keys))
    _links[key] = {"ts": time.time(), "urls": urls, "city": city}
    rows = [[InlineKeyboardButton(text=f"{label} {link_label(u)}",
                                  callback_data=f"{prefix}{key}:{i}")]
            for i, u in enumerate(urls)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def suggest_keyboard(urls, city):
    return links_keyboard(urls, city, prefix=SUGGEST_CALLBACK, label="➕ Предложить")


def link_from_callback(data):
    """'<prefix><key>:<i>' → (url, city), None if unknown (e.g. after restart)."""
    try:
        key, idx = data.split(":", 1)[1].split(":")
        entry = _links[key]
        return entry["urls"][int(idx)], entry["city"]
    except (KeyError, ValueError, IndexError):
        return None


# ---- user quota

def _today():
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=TIMEZONE_HOUR)).date()


def user_quota_left(user_id):
    day, count = _user_submits.get(user_id, (None, 0))
    return USER_DAILY_LIMIT - (count if day == _today() else 0)


def take_user_quota(user_id):
    """False if today's limit is used up."""
    if user_quota_left(user_id) <= 0:
        return False
    today = _today()
    for uid in [u for u, (d, _) in _user_submits.items() if d != today]:
        _user_submits.pop(uid, None)
    _user_submits[user_id] = (today, USER_DAILY_LIMIT - user_quota_left(user_id) + 1)
    return True


def refund_user_quota(user_id):
    day, count = _user_submits.get(user_id, (None, 0))
    if day == _today() and count > 0:
        _user_submits[user_id] = (day, count - 1)


# ---- tasks and reports

async def submit_text(post_data, city):
    """→ (task_id, error)."""
    result = await external_api.create_post_by_ai(post_data, city=city)
    return result.get("task_id"), result.get("error")


async def submit_url(url, user_id, city, comment=None):
    result = await external_api.event_from_url(
        url, comment=comment or None, submitted_by=f"tg:{user_id}", city=city,
    )
    return result.get("task_id"), result.get("error")


def watch(status_message: types.Message, task_id, kind, header):
    """Wait for the task in background and append the result to status_message."""
    task = asyncio.create_task(_watch(status_message, task_id, kind, header))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _watch(status_message, task_id, kind, header):
    result = await external_api.wait_task(task_id)
    formatter = {"url": format_url_result, "user": format_user_result}.get(kind, format_text_result)
    body = formatter(result)
    try:
        await status_message.edit_text(f"{header}\n\n{body}"[:4000],
                                       reply_markup=status_message.reply_markup,
                                       disable_web_page_preview=True)
    except Exception:
        logger.exception("Failed to report import result for task %s", task_id)


def _event_line(e):
    when = str(e.get("from_date") or e.get("date") or "")[:16].replace("T", " ")
    price = e.get("price")
    parts = [e.get("title") or "без названия", when, str(price) if price else ""]
    return "• " + " — ".join(p for p in parts if p)


_URL_STATUS = {
    "created": "✅ Добавлено во входящие (pending)",
    "exists": "☑️ Уже есть в базе",
    "rejected": "🚫 Отклонено",
    "failed": "⚠️ Не удалось разобрать страницу",
    "not_found": "🤷 На странице не нашлось мероприятия",
    "rate_limited": "⏳ Дневной лимит ссылок исчерпан",
}


def format_url_result(result):
    if "error" in result and "status" not in result:
        return f"⚠️ {result['error']}"
    status = result.get("status")
    lines = [_URL_STATUS.get(status, f"Итог: {status}")]
    if result.get("method"):
        lines[0] += f" · {result['method']}" + (" · из кэша" if result.get("cached") else "")
    lines += [_event_line(e) for e in result.get("events") or []]
    lines += [f"= {r.get('title')} (id {r.get('id')}, {r.get('status')})"
              for r in result.get("existing") or []]
    lines += [f"× {r.get('title') or r.get('note') or ''} — {r.get('reason')}"
              for r in result.get("rejected") or []]
    if status == "failed" and result.get("error"):
        lines.append(str(result["error"]))
    if result.get("created_ids"):
        lines.append(f"id: {', '.join(map(str, result['created_ids']))}")
    return "\n".join(lines)


def format_text_result(result):
    if result.get("error") and not result.get("events"):
        return f"⚠️ {result['error']}"
    if not result.get("is_event"):
        return "🤷 " + (result.get("message") or "Мероприятий в тексте не нашлось")
    lines = [f"✅ Найдено мероприятий: {result.get('events_count', len(result.get('events') or []))}"]
    lines += [_event_line(e) for e in result.get("events") or []]
    if result.get("created_ids"):
        lines.append(f"Во входящих, id: {', '.join(map(str, result['created_ids']))}")
    elif result.get("error"):
        lines.append(f"⚠️ Не сохранено: {result['error']}")
    return "\n".join(lines)


_REJECT_RU = {
    "past": "оно уже прошло",
    "other_city": "оно не в вашем городе",
    "online": "это онлайн-событие",
    "too_far": "до него ещё слишком далеко",
    "no_date": "на странице нет даты",
}


def format_user_result(result):
    """User-facing: no ids or internals."""
    status = result.get("status")
    if status == "created":
        titles = [e.get("title") for e in result.get("events") or [] if e.get("title")]
        lines = ["✅ Спасибо! Мероприятие отправлено на модерацию."]
        lines += [f"• {t}" for t in titles[:5]]
        return "\n".join(lines)
    if status == "exists":
        return "☑️ Это мероприятие у нас уже есть — спасибо!"
    if status == "rejected":
        reasons = {r.get("reason") for r in result.get("rejected") or []}
        why = next((_REJECT_RU[r] for r in _REJECT_RU if r in reasons), "")
        return "🚫 Не можем добавить это мероприятие" + (f": {why}." if why else ".")
    if status == "rate_limited":
        return "⏳ На сегодня ссылок достаточно, попробуйте завтра."
    if status == "not_found":
        return "🤷 Не нашли мероприятие на этой странице."
    return "⚠️ Не получилось разобрать страницу. Попробуйте ссылку на страницу самого события."
