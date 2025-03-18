import json
import os
from utils.logger import logger

TEMP_FOLDER = 'cache'
TWO_FA_PASSWORDS_FILE = os.path.join(TEMP_FOLDER, 'two_fa_passwords.json')

def initialize_two_fa_storage():
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)
        logger.info(f"Папка {TEMP_FOLDER} успешно создана.")

    if not os.path.exists(TWO_FA_PASSWORDS_FILE):
        with open(TWO_FA_PASSWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)  # Создаем пустой словарь
        logger.info(f"Файл {TWO_FA_PASSWORDS_FILE} успешно создан.")

# Вызов функции инициализации при запуске программы
initialize_two_fa_storage()


def load_two_fa_passwords():
    """Загружает пароли 2FA из файла two_fa_passwords.json."""
    if not os.path.exists(TWO_FA_PASSWORDS_FILE):
        return {}

    try:
        with open(TWO_FA_PASSWORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке паролей 2FA: {e}")
        return {}

def save_two_fa_passwords(two_fa_passwords):
    """Сохраняет пароли 2FA в файл two_fa_passwords.json."""
    try:
        with open(TWO_FA_PASSWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(two_fa_passwords, f, ensure_ascii=False, indent=4)
        logger.info("Пароли 2FA успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении паролей 2FA: {e}")