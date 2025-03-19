import asyncio
import os
import random

from telethon import functions, TelegramClient
from telethon.errors import SessionPasswordNeededError

from CONFIG.config_manager import load_config
from state_manager import state_manager
from utils.logger import logger
from utils.two_fa_passwords_manager import save_two_fa_passwords, load_two_fa_passwords

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    exit(1)


async def connect_account(account, proxy_manager):
    account_folder = account['account_folder']
    account_data = account.get('account_data', {})
    api_id = account_data.get('app_id')
    api_hash = account_data.get('app_hash')
    proxy = proxy_manager.get_proxy_for_account(account_folder)

    if not api_id or not api_hash:
        logger.error(f"В аккаунте {account_folder} отсутствуют app_id или app_hash.")
        return None

    if not proxy:
        logger.error(f"Нет доступного прокси для аккаунта {account_folder}.")
        return None


    delay = random.randint(int(config['min_delay']), int(config['max_delay'])) // 4
    logger.info(f"Ожидание {delay} секунд перед подключением к аккаунту {account_folder}...")
    await asyncio.sleep(delay)


    session_files = [f for f in os.listdir(account_folder) if f.endswith('.session')]
    if not session_files:
        logger.error(f"Файл сессии не найден в папке {account_folder}.")
        return None


    session_name = os.path.join(account_folder, session_files[0])
    logger.info(f"Используем файл сессии: {session_name}")


    client = TelegramClient(
        session=session_name,
        api_id=api_id,
        api_hash=api_hash,
        proxy=proxy
    )

    try:
        logger.info(f"Попытка подключения к аккаунту {account_folder}...")
        await asyncio.wait_for(client.connect(),
                               timeout=(random.randint(int(config['min_delay']), int(config['max_delay'])) // 4))

        if not client.is_connected():
            logger.error(f"Не удалось подключиться к аккаунту {account_folder}.")
            return None


        if not await client.is_user_authorized():
            logger.error(f"Аккаунт {account_folder} не авторизован.")
            return None


        try:

            me = await client.get_me()


            try:
                password_info = await client(functions.account.GetPasswordRequest())
                if password_info is None:
                    logger.info(f"2FA не требуется для аккаунта {account_folder}.")
                else:

                    account_name = os.path.basename(account_folder)
                    logger.info(f"Имя аккаунта: {account_name}")


                    two_fa_passwords = load_two_fa_passwords()


                    if account_name in two_fa_passwords:
                        password = two_fa_passwords[account_name]
                        logger.info(f"Используем сохраненный пароль для 2FA аккаунта {account_name}.")
                    else:

                        password = input(f"Введите пароль для 2FA аккаунта {account_name}: ")

                        two_fa_passwords[account_name] = password
                        save_two_fa_passwords(two_fa_passwords)
                        logger.info(f"Пароль для аккаунта {account_name} успешно сохранен.")

                    await client.sign_in(password=password)
                    logger.info(f"2FA пароль успешно введен для аккаунта {account_name}.")
            except SessionPasswordNeededError:
                logger.error(f"Требуется пароль для 2FA, но он не был предоставлен.")
                return None
        except Exception as e:
            logger.error(f"Ошибка при проверке 2FA для аккаунта {account_folder}: {e}")
            return None

        logger.info(f"Аккаунт {account_folder} успешно подключен и авторизован.")
        return client
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при подключении к аккаунту {account_folder}. Проверьте интернет или прокси.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при подключении к аккаунту {account_folder}: {e}")
        return None


async def check_account_status(client):
    try:
        if not await client.is_user_authorized():
            logger.warning(f"Аккаунт {client.session.filename} не авторизован.")
            return False, None

        me = await client.get_me()
        if me and me.username:
            logger.info(f"Аккаунт {client.session.filename} активен. Username: @{me.username}")
            return True, me.username
        else:
            logger.warning(f"Аккаунт {client.session.filename} не имеет username.")
            return True, None
    except Exception as e:
        logger.error(f"Аккаунт {client.session.filename} заблокирован или неактивен: {e}")
        return False, None