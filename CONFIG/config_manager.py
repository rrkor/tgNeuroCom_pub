# Файл: config_manager.py
import signal
import yaml
from utils.logger import logger
from cryptography.fernet import Fernet
import json
import os
from pydantic import BaseModel, ValidationError

ENCRYPTED_CONFIG_FILE = 'CONFIG/config_encrypted.yaml'
KEY_FILE = 'CONFIG/config_key.key'

class ConfigSchema(BaseModel):
    min_delay: int
    max_delay: int
    maxtokensfromgpt: int
    modelapi: str
    openai_api_key: str
    bot_token: str
    main_admin: str
    main_password: str
    MAIN_ADMIN_CHAT_ID: str
    geo_api: str
    max_bots_for_comment: int
    average_delay_between_comments: int
    bio: str

def generate_key(key_file=KEY_FILE):
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, 'wb') as key_file:
            key_file.write(key)
        logger.info("Ключ шифрования сгенерирован и сохранен.")
    else:
        with open(key_file, 'rb') as key_file:
            key = key_file.read()
    return key

def encrypt_config(config, key):
    fernet = Fernet(key)
    encrypted_config = fernet.encrypt(json.dumps(config).encode())
    return encrypted_config

def decrypt_config(encrypted_config, key):
    fernet = Fernet(key)
    decrypted_config = json.loads(fernet.decrypt(encrypted_config).decode())
    return decrypted_config

def save_encrypted_config(config, key, config_file=ENCRYPTED_CONFIG_FILE):
    encrypted_config = encrypt_config(config, key)
    with open(config_file, 'wb') as f:
        f.write(encrypted_config)
    logger.info("Конфигурация зашифрована и сохранена.")

def load_encrypted_config(key, config_file=ENCRYPTED_CONFIG_FILE):
    if not os.path.exists(config_file):
        logger.error("Зашифрованный конфиг отсутствует. Пожалуйста, купите ключ.")
        return None
    with open(config_file, 'rb') as f:
        encrypted_config = f.read()
    return decrypt_config(encrypted_config, key)

def validate_config(config):
    try:
        validated_config = ConfigSchema(**config)
        return validated_config.dict()
    except ValidationError as e:
        logger.error(f"Ошибка валидации конфигурации: {e}")
        return None

def load_config():
    try:
        key = generate_key()
        encrypted_config = load_encrypted_config(key)
        if encrypted_config is None:
            return None
        validated_config = validate_config(encrypted_config)
        if validated_config:
            logger.info("Конфигурация успешно загружена и валидирована.")
            return validated_config
        else:
            logger.error("Конфигурация не прошла валидацию.")
            return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке конфигурации: {e}")
        return None

def reload_config(signum, frame):
    global config
    logger.info("Получен сигнал для перезагрузки конфигурации.")
    config = load_config()
    logger.info("Конфигурация успешно перезагружена.")

signal.signal(signal.SIGUSR1, reload_config)