import json
import os
from utils.logger import logger
from cryptography.fernet import Fernet
from CONFIG.config_manager import load_config


ADMIN_FILE = 'FILES/admins.json'
KEY_FILE = 'FILES/admin_key.key'


def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        logger.info("Ключ шифрования для админов сгенерирован.")
    else:
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
    return key

def encrypt_password(password: str, key: bytes) -> str:
    fernet = Fernet(key)
    encrypted_password = fernet.encrypt(password.encode())
    return encrypted_password.decode()

def decrypt_password(encrypted_password: str, key: bytes) -> str:
    fernet = Fernet(key)
    decrypted_password = fernet.decrypt(encrypted_password.encode())
    return decrypted_password.decode()

def load_admins():
    if not os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    try:
        with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при загрузке admins.json: файл содержит некорректный JSON. Создаю новый файл.")
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке admins.json: {e}")
        return {}

def save_admins(admins: dict):
    try:
        os.makedirs(os.path.dirname(ADMIN_FILE), exist_ok=True)
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, ensure_ascii=False, indent=4)
        logger.info("Список админов успешно сохранен.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении admins.json: {e}")

def add_admin(username: str, password: str):
    key = generate_key()
    admins = load_admins()
    if not username.startswith('@'):
        username = f"@{username}"
    admins[username] = encrypt_password(password, key)
    save_admins(admins)
    logger.info(f"Админ {username} успешно добавлен.")

def verify_admin(username: str, password: str) -> bool:
    config = load_config()
    if not username.startswith('@'):
        username = f"@{username}"
    if is_main_admin(username):
        main_password = config.get('main_password')
        if not main_password:
            logger.error("Пароль главного администратора не найден в конфигурации.")
            return False
        return password == main_password
    admins = load_admins()
    if username not in admins:
        return False
    key = generate_key()
    try:
        decrypted_password = decrypt_password(admins[username], key)
        return decrypted_password == password
    except Exception as e:
        logger.error(f"Ошибка при проверке пароля админа {username}: {e}")
        return False

def is_main_admin(username: str) -> bool:
    config = load_config()
    main_admin = config.get('main_admin')
    if not main_admin:
        logger.error("Главный администратор не указан в конфигурации.")
        return False
    normalized_username = f"@{username.lstrip('@')}"
    normalized_main_admin = f"@{main_admin}"
    return normalized_username == normalized_main_admin

def remove_admin(username: str):
    admins = load_admins()
    if not username.startswith('@'):
        username = f"@{username}"
    if username in admins:
        del admins[username]
        save_admins(admins)
        logger.info(f"Админ {username} успешно удален.")
    else:
        logger.warning(f"Админ {username} не найден.")