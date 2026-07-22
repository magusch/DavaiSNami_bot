import asyncio
import aiohttp

from config import API_URL, API_TOKEN

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

async def fetch_events(params):
    """Отправляет асинхронный запрос на API и получает список событий."""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'events/valid/', headers=HEADERS, json=params) as response:
            if response.status != 200:
                return {"error": f"Ошибка API: {response.status}"}

            response_json = await response.json()

            if "task_id" in response_json:
                return await check_status(response_json["task_id"])

            return response_json

async def fetch_exhibitions():
    """Отправляет асинхронный запрос на API и получает список выставок."""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'tasks/get-exhibitions/', headers=HEADERS) as response:
            if response.status != 200:
                return {"error": f"Ошибка API: {response.status}"}

            response_json = await response.json()

            if "task_id" in response_json:
                return await check_status(response_json["task_id"])

            return response_json


async def check_status(task_id: str):
    """Wait and return result by task_id."""
    max_retries = 15
    retries = 0

    while retries < max_retries:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}tasks/status/{task_id}", headers=HEADERS) as response:
                if response.status != 200:
                    return {"error": f"Ошибка API: {response.status}"}

                response_json = await response.json()

                if response_json.get("status") == "success":
                    return response_json
                elif response_json.get("status") == "failed":
                    return {"error": "Задача не выполнена"}
        
        retries += 1
        await asyncio.sleep(1)


async def keyword_search(query, type='event', limit=10):
    """Синхронный keyword-поиск (GET /search/). Возвращает {events, places}."""

    params = {'query': query, 'type': type, 'limit': limit}
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL + 'search/', headers=HEADERS, params=params) as response:
            if response.status != 200:
                return {"error": f"Ошибка API: {response.status}"}
            return await response.json()


async def semantic_search(message, history=None, limit=8, max_distance=None):
    """Семантический поиск (POST /search/semantic/ + поллинг tasks/status/).

    Возвращает внутренний результат задачи {status, query, result:{events,...}}
    либо {"error": ...}."""

    payload = {
        "message": message,
        "limit": limit,
        "max_distance": max_distance,
        "history": history or [],
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'search/semantic/', headers=HEADERS, json=payload) as response:
            if response.status not in (200, 202):
                return {"error": f"Ошибка API: {response.status}"}
            data = await response.json()

    task_id = data.get("task_id")
    if not task_id:
        return data

    return await poll_semantic_status(task_id)


async def poll_semantic_status(task_id: str, max_retries: int = 20, interval: float = 1.5):
    """Поллинг GET /tasks/status/{task_id} для семантической задачи."""

    for _ in range(max_retries):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}tasks/status/{task_id}", headers=HEADERS) as response:
                if response.status != 200:
                    return {"error": f"Ошибка API: {response.status}"}
                data = await response.json()

        status = data.get("status")
        if status == "success":
            return data.get("result", {})
        if status in ("failure", "failed"):
            return {"error": data.get("error", "Задача не выполнена")}

        await asyncio.sleep(interval)

    return {"error": "Превышено время ожидания семантического поиска"}


async def create_post_by_ai(event_data):
    """Send async request to API for making post."""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'create_post_by_ai/', headers=HEADERS, json=event_data) as response:
            if response.status != 200:
                return {"error": f"Ошибка API: {response.status}"}

            response_json = await response.json()

            if "task_id" in response_json:
                return await check_status(response_json["task_id"])

            return response_json
