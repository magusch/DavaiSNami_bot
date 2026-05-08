import re
from datetime import datetime, timedelta, timezone

from config import MONTHES, LANG, TIMEZONE_HOUR

USER_TZ = timezone(timedelta(hours=TIMEZONE_HOUR))

TELEGRAM_MESSAGE_LIMIT = 4096
SAFE_MESSAGE_LIMIT = 4000  # запас на разметку/футер


def split_message(text: str, limit: int = SAFE_MESSAGE_LIMIT) -> list[str]:
    """Разрезать длинный текст на куски <= limit. Режем по \\n\\n, потом \\n, потом пробелу."""
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind('\n\n', 0, limit)
        if split_at == -1:
            split_at = remaining.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(' ', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def send_chunked(message, text, *, reply_first=False, **kwargs):
    """Отправить текст одной или несколькими порциями.
    reply_markup и footer-ссылки прикрепляются только к последнему сообщению,
    чтобы не дублировать клавиатуру/ссылки. reply_first=True — первый чанк через reply()."""
    chunks = split_message(text)
    reply_markup = kwargs.pop('reply_markup', None)
    for i, chunk in enumerate(chunks):
        last = (i == len(chunks) - 1)
        chunk_kwargs = dict(kwargs)
        if last and reply_markup is not None:
            chunk_kwargs['reply_markup'] = reply_markup
        if i == 0 and reply_first:
            await message.reply(chunk, **chunk_kwargs)
        else:
            await message.answer(chunk, **chunk_kwargs)


def parse_user_datetime(text):
    """
    Parse string with date and time. It consists different format of dates
    If year is not in string it will put current year or next year (for past date)
    Return datetime or None.
    """
    now = datetime.now()
    text = text.strip()

    # Popular formats: 05.06 18:00, 5.6 18:00, 05.06.2025 18:00, 2025-06-05 18:00, 5/6 18:00, 5 июня 18:00
    patterns = [
        (r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})?\s+(\d{1,2}):(\d{2})$", "%d.%m.%Y %H:%M"),
        (r"^(\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})$", "%d.%m %H:%M"),
        (r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})$", "%Y-%m-%d %H:%M"),
        (r"^(\d{1,2})\s+([а-яА-Я]+)\s+(\d{1,2}):(\d{2})$", None),  # 5 июня 18:00
        (r"^(\d{1,2})[.\-/](\d{1,2})$", "%d.%m"),
    ]

    for pattern, dt_format in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                # With year: 05.06.2025 18:00
                if dt_format == "%d.%m.%Y %H:%M":
                    day, month, year, hour, minute = groups
                    year = int(year) if year else now.year
                    dt = datetime(year, int(month), int(day), int(hour), int(minute))
                # Without year: 05.06 18:00
                elif dt_format == "%d.%m %H:%M":
                    day, month, hour, minute = groups
                    year = now.year
                    dt = datetime(year, int(month), int(day), int(hour), int(minute))
                # ISO format: 2025-06-05 18:00
                elif dt_format == "%Y-%m-%d %H:%M":
                    year, month, day, hour, minute = groups
                    dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
                # 5 июня 18:00
                elif dt_format is None and len(groups) == 4:
                    day, month_str, hour, minute = groups
                    try:
                        month = MONTHES[LANG].index(month_str.lower()) + 1
                    except ValueError:
                        return None
                    year = now.year
                    dt = datetime(year, month, int(day), int(hour), int(minute))
                # 05.06 (without time)
                elif dt_format == "%d.%m":
                    day, month = groups
                    year = now.year
                    dt = datetime(year, int(month), int(day), 12, 0)
                else:
                    continue

                if dt < now:
                    if not (dt_format and "%Y" in dt_format):
                        dt = dt.replace(year=dt.year + 1)
                return dt
            except (ValueError, IndexError):
                return None

    return None


def dt_local_to_utc(local_dt) -> datetime:
    local_dt = local_dt.replace(tzinfo=USER_TZ)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt


def dt_utc_to_user(utc_dt: datetime) -> str:
    return utc_dt.astimezone(USER_TZ)

