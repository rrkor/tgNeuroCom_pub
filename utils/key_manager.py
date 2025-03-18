
import json
import os
from utils.logger import logger

KEYS_FILE = 'FILES/one_time_keys.json'

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    try:
        with open(KEYS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке one_time_keys.json: {e}")
        return {}

def save_keys(keys: dict):
    try:
        with open(KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(keys, f, ensure_ascii=False, indent=4)
        logger.info("Одноразовые ключи успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении one_time_keys.json: {e}")

def generate_key(username: str) -> str:
    import uuid
    key = str(uuid.uuid4())
    keys = load_keys()
    normalized_username = username.lstrip('@').lower()
    keys[key] = normalized_username
    save_keys(keys)
    logger.info(f"Одноразовый ключ для {normalized_username} сгенерирован.")
    return key

def verify_key(key: str) -> None:
    keys = load_keys()
    if key in keys:
        username = keys[key]
        del keys[key]
        save_keys(keys)
        logger.info(f"Одноразовый ключ для {username} успешно использован.")
        return username
    return None