"""User city: which city the feed, search and web app links are built for."""
import logging
import time

from config import DEFAULT_CITY, CITY_NAMES
from . import crud

logger = logging.getLogger(__name__)

CITIES_TTL = 600

_cities_cache = (0.0, None)
_names = dict(CITY_NAMES)   # refreshed from city_city.name


def city_name(code):
    return _names.get(code, code)


async def active_cities():
    """Active city codes, the default one first. Falls back to [DEFAULT_CITY]
    when city_city cannot be read."""
    global _cities_cache
    cached_at, cities = _cities_cache
    if cities and time.monotonic() - cached_at < CITIES_TTL:
        return cities
    try:
        rows = await crud.get_active_cities()
    except Exception:
        logger.warning("Failed to read city_city, using the default city only")
        rows = []
    _names.update({city.code: city.name for city in rows if city.name})
    cities = [DEFAULT_CITY] + [city.code for city in rows if city.code != DEFAULT_CITY]
    _cities_cache = (time.monotonic(), cities)
    return cities


async def get_user_city(telegram_id, default=DEFAULT_CITY):
    """The user's city (dsn_user.city_id); `default` when it is NULL or the user
    is not in the DB. default=None tells "not chosen" apart from a choice."""
    try:
        city = await crud.get_user_city(telegram_id)
    except Exception:
        # a listing in the default city beats an error message
        logger.exception("Failed to read the user city")
        city = None
    return city or default


async def set_user_city(telegram_id, city):
    """Set the user's city. Returns False for an unknown/inactive code or when
    the user is not in dsn_user yet."""
    if city not in await active_cities():
        return False
    return await crud.set_user_city(telegram_id, city)


async def adopt_city(telegram_id, city):
    """Set the city from a deep link target (event/selection) only when the user
    has not chosen one yet."""
    if city and await get_user_city(telegram_id, default=None) is None:
        await set_user_city(telegram_id, city)
