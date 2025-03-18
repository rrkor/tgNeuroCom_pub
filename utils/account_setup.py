import os
import random
import re
import sqlite3

from openai import AsyncOpenAI, OpenAI
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, CheckUsernameRequest

from CONFIG.config_manager import load_config
from utils.account_manager import connect_account
from utils.logger import logger

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    exit(1)


DB_PATH = 'cache/channels.db'
AVATARS_FOLDER = 'avatars'
openai_api_key = config['openai_api_key']
model = config['modelapi']
USERNAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$')
bio = config['bio']

def initialize_accounts_table():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Accounts (
                    account_name TEXT PRIMARY KEY,
                    avatar_file TEXT
                )
            ''')
            conn.commit()
            logger.info("Таблица Accounts создана или уже существует.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы Accounts: {e}")

# Аватары
def get_available_avatars():
    if not os.path.exists(AVATARS_FOLDER):
        logger.error(f"Папка с аватарками {AVATARS_FOLDER} не найдена.")
        return []

    avatars = [f for f in os.listdir(AVATARS_FOLDER) if f.endswith(('.jpeg', '.jpg', '.png', '.mp4'))]
    if not avatars:
        logger.error(f"В папке {AVATARS_FOLDER} нет подходящих файлов для аватарок.")
    else:
        logger.info(f"Найдено {len(avatars)} аватарок в папке {AVATARS_FOLDER}.")
    return avatars
def get_random_avatar(account_name):
    avatars = get_available_avatars()
    if not avatars:
        logger.error(f"Нет доступных аватарок для аккаунта {account_name}.")
        return None

    try:
        with sqlite3.connect('cache/channels.db') as conn:
            cursor = conn.cursor()

            # Получаем список уже использованных аватарок
            cursor.execute('SELECT avatar_file FROM Accounts')
            used_avatars = {row[0] for row in cursor.fetchall()}  # Создаем множество использованных аватарок

            # Фильтруем доступные аватарки, исключая уже использованные
            available_avatars = [avatar for avatar in avatars if avatar not in used_avatars]

            if not available_avatars:
                logger.error(f"Нет доступных аватарок для аккаунта {account_name}. Все аватарки уже используются.")
                return None

            # Выбираем случайную аватарку из доступных
            avatar_file = random.choice(available_avatars)

            # Сохраняем выбранную аватарку в базу данных
            cursor.execute('INSERT OR IGNORE INTO Accounts (account_name, avatar_file) VALUES (?, ?)', (account_name, avatar_file))
            conn.commit()

            logger.info(f"Для аккаунта {account_name} выбрана новая аватарка: {avatar_file}.")
            return avatar_file
    except Exception as e:
        logger.error(f"Ошибка при выборе аватарки для аккаунта {account_name}: {e}")
        return None
async def set_account_avatar(client, avatar_path):
    try:
        logger.info(f"Попытка удаления старых аватарок для аккаунта.")
        await client(DeletePhotosRequest(await client.get_profile_photos('me')))
        logger.info(f"Старые аватарки успешно удалены.")

        if avatar_path.endswith(('.jpeg', '.jpg', '.png')):
            logger.info(f"Загрузка изображения в качестве аватарки: {avatar_path}.")
            # Убедитесь, что файл существует и доступен
            if not os.path.exists(avatar_path):
                logger.error(f"Файл аватарки {avatar_path} не найден.")
                return

            # Загружаем файл
            with open(avatar_path, 'rb') as file:
                uploaded_file = await client.upload_file(file)
                await client(UploadProfilePhotoRequest(file=uploaded_file))
            logger.info(f"Аватарка успешно установлена: {avatar_path}.")
        elif avatar_path.endswith('.mp4'):
            logger.info(f"Загрузка видео в качестве аватарки: {avatar_path}.")
            # Убедитесь, что файл существует и доступен
            if not os.path.exists(avatar_path):
                logger.error(f"Файл аватарки {avatar_path} не найден.")
                return

            # Загружаем файл
            with open(avatar_path, 'rb') as file:
                uploaded_file = await client.upload_file(file)
                await client(UploadProfilePhotoRequest(video=uploaded_file))
            logger.info(f"Аватарка успешно установлена: {avatar_path}.")
        else:
            logger.error(f"Неподдерживаемый формат файла: {avatar_path}.")
    except Exception as e:
        logger.error(f"Ошибка при установке аватарки: {e}")

# first name) и био
async def update_account_profile(client, first_name, bio):
    try:
        logger.info(f"Попытка обновления профиля: first_name={first_name}, bio={bio}.")
        await client(UpdateProfileRequest(
            first_name=first_name,
            about=bio
        ))
        logger.info(f"Профиль успешно обновлен: first_name={first_name}, bio={bio}.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
def generate_firstname():
    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": """ 
Придумай уникальный никнейм для поклонника криптовалют. Учитывай:  
1. Смешение стилей: технические термины (HODL, DeFi, NFT), мемы, абсурд, поп-культура.  
2. Визуальный креатив: необычные символы (Ξ, ₿, Ð), регистры (𝕮𝖗𝖞𝖕𝖙𝖔_𝕲𝖔𝖉), ASCII-арт, зачеркивания, пробелы внутри слов.  
3. Языковую игру: каламбуры, перевод на другие языки, ребусы (например, 暗号の騎士 = Crypto Knight).  
4. Длину: от минимализма (Ξ) до эпичных предложений (TheGhostOfSatoshiHauntingFiatBanks).  
5. Иронию и провокацию: самоирония сообщества (NFTCollectorOfUselessJPEGsSince2021).  
Примеры для вдохновения: Ðapposaurus_Rex, HowToLoseMoneyIn10Coins, ༒S̾h̾i̾l̾l̾i̾n̾g̾༒.  
Сгенерируй ОДИН никнейм, избегая шаблонов. Чем абсурднее и многограннее — тем лучше!  
"""},
            ],
            max_tokens=10,
            n=1,
            stop=None,
            temperature=0.7,
        )
        username = response.choices[0].message.content.strip()
        logger.info(f"Сгенерирован юзернейм с помощью ChatGPT: {username}")
        return username
    except Exception as e:
        logger.error(f"Ошибка при генерации юзернейма с помощью ChatGPT: {e}")
        return None





def is_valid_username(username):
    if not username:
        return False
    return bool(USERNAME_REGEX.match(username))
async def is_username_available(client, username):
    try:
        result = await client(CheckUsernameRequest(username))
        return result
    except Exception as e:
        logger.error(f"Ошибка при проверке уникальности юзернейма {username}: {e}")
        return False
def generate_username():
    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": """Generate a unique and creative Telegram username (without the @ symbol).
                 It should be 6-12 characters long, start with a letter, and contain only letters (not capital), 
                 numbers, or underscores. Moreover, it can be relates on cryptocurrency or blockchain. 
                 But make it creative and various please. As an answer just write one username."""},
            ],
            max_tokens=12,
            n=1,
            stop=None,
            temperature=0.7,
        )
        username = response.choices[0].message.content.strip()
        logger.info(f"Сгенерирован юзернейм с помощью ChatGPT: {username}")
        return username
    except Exception as e:
        logger.error(f"Ошибка при генерации юзернейма с помощью ChatGPT: {e}")
        return None
async def generate_unique_username(client):
    max_attempts = 20
    for _ in range(max_attempts):
        username = generate_username()
        if not username:
            logger.warning("Не удалось сгенерировать юзернейм. Повторная попытка...")
            continue

        if not is_valid_username(username):
            logger.warning(f"Юзернейм {username} не соответствует синтаксису Telegram.")
            continue

        if await is_username_available(client, username):
            logger.info(f"Юзернейм {username} доступен для использования.")
            return username
        else:
            logger.warning(f"Юзернейм {username} уже занят.")

    logger.error("Не удалось сгенерировать уникальный юзернейм после нескольких попыток.")
    return None
async def update_account_username(client, new_username):
    try:
        logger.info(f"Попытка обновления юзернейма на: @{new_username}.")
        await client(UpdateUsernameRequest(new_username))
        logger.info(f"Юзернейм успешно обновлен: @{new_username}.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении юзернейма: {e}")






async def setup_account(account, proxy_manager):
    account_folder = account['account_folder']
    account_name = os.path.basename(account_folder)

    logger.info(f"Начало настройки аккаунта: {account_name}.")

    # Получаем случайную аватарку для аккаунта
    avatar_file = get_random_avatar(account_name)
    if not avatar_file:
        logger.error(f"Не удалось выбрать аватарку для аккаунта {account_name}.")
        return

    avatar_path = os.path.join(AVATARS_FOLDER, avatar_file)
    logger.info(f"Аватарка для аккаунта {account_name}: {avatar_path}.")

    # Подключаемся к аккаунту
    client = await connect_account(account, proxy_manager)
    if not client:
        logger.error(f"Не удалось подключиться к аккаунту {account_name}.")
        return

    # Устанавливаем аватарку
    await set_account_avatar(client, avatar_path)

    #first name и био
    new_first_name = generate_username()

    new_bio = config['bio']
    await update_account_profile(client, new_first_name, new_bio)

    # Генерация и установка уникального юзернейма
    new_username = await generate_unique_username(client)
    if new_username:  # Проверка на None
        await update_account_username(client, new_username)
    else:
        logger.error(f"Не удалось установить юзернейм для аккаунта {account_name}.")

    # Добавляем аккаунт в базу данных
    with sqlite3.connect('cache/channels.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO Accounts (account_name, avatar_file) VALUES (?, ?)', (account_name, avatar_file))
        conn.commit()

    # Закрываем соединение
    await client.disconnect()
    logger.info(f"Настройка аккаунта {account_name} завершена.")
