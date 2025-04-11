import time
import aiohttp

from config import API_URL, API_TOKEN

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

async def fetch_events(params):
    """Отправляет асинхронный запрос на API и получает список событий."""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'get_valid_events/', headers=HEADERS, json=params) as response:
            if response.status != 200:
                return {"error": f"Ошибка API: {response.status}"}

            response_json = await response.json()

            if "task_id" in response_json:
                return await check_status(response_json["task_id"])

            return response_json

async def fetch_exhibitions():
    """Отправляет асинхронный запрос на API и получает список выставок."""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL + 'get_exhibitions/', headers=HEADERS) as response:
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
            async with session.get(f"{API_URL}status/{task_id}", headers=HEADERS) as response:
                if response.status != 200:
                    return {"error": f"Ошибка API: {response.status}"}

                response_json = await response.json()

                if response_json.get("status") == "success":
                    return response_json
                elif response_json.get("status") == "failed":
                    return {"error": "Задача не выполнена"}
        
        retries += 1
        time.sleep(1)


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
