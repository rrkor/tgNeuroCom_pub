import asyncio
import signal
import os
import sys

from CONFIG.config_manager import load_config
from state_manager import state_manager
from utils.account_manager import connect_account, check_account_status
from utils.file_checker import check_file_integrity
from utils.logger import logger
from utils.proxy import load_proxies_from_file
from utils.proxy_manager import ProxyManager
from utils.utils import load_accounts_from_folder, load_channels_from_database, initialize_database

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    sys.exit(1)

LOCK_FILE = "bot.lock"



async def shutdown():
    state_manager.is_running = False
    for client in state_manager.active_accounts:
        try:
            if client and client.is_connected():
                await client.disconnect()
                logger.info(f"Клиент {client.session.filename} успешно отключен.")
        except Exception as e:
            logger.error(f"Ошибка при отключении клиента {client.session.filename}: {e}")

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Все задачи завершены.")

async def start_program():
    """Запускает основную логику программы."""
    initialize_database()

    accounts = []
    accounts = load_accounts_from_folder(accounts=accounts)

    state_manager.is_running = True
    try:
        is_integrity_ok, message = check_file_integrity()
        if not is_integrity_ok:
            logger.error(message)
            from telegram_bot import bot
            await bot.send_message(chat_id=config['MAIN_ADMIN_CHAT_ID'], text=message)
            return

        proxies = load_proxies_from_file()
        if not proxies:
            logger.error("Список прокси пуст. Программа не может быть запущена.")
            return

        proxy_manager = ProxyManager(proxies)
        await proxy_manager.test_all_proxies()

        accounts = load_accounts_from_folder()
        if not accounts:
            logger.error("Нет доступных аккаунтов. Программа не может быть запущена.")
            return

        state_manager.active_accounts = []
        for account in accounts:
            session_files = [f for f in os.listdir(account['account_folder']) if f.endswith('.session')]
            if not session_files:
                logger.error(f"Файл сессии не найден для аккаунта {account['account_folder']}.")
                continue

            client = await connect_account(account, proxy_manager)
            if client:
                is_active, username = await check_account_status(client)
                account['is_active'] = is_active
                account['username'] = username
                logger.info(f"Аккаунт {account['account_folder']} инициализирован. Username: @{username}")
                if is_active:
                    state_manager.active_accounts.append(client)
                    logger.info(f"Аккаунт {account['account_folder']} успешно инициализирован и добавлен в активные.")

        if not state_manager.active_accounts:
            logger.error("Нет активных аккаунтов. Программа не может быть запущена.")
            return

        channels = load_channels_from_database()
        logger.info(f"Загружены каналы из базы данных: {channels}")
        if not channels:
            logger.error("Список каналов пуст. Программа не может быть запущена.")
            return

        for client in state_manager.active_accounts:
            from tg import subscribe_and_disable_notifications
            await subscribe_and_disable_notifications(client, channels)

        for client in state_manager.active_accounts:
            from tg import scan_posts_periodically
            task = asyncio.create_task(scan_posts_periodically(client, proxy_manager))

        while state_manager.is_running:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Ошибка при запуске программы: {e}")
    finally:
        state_manager.is_running = False

async def main():
    from telegram_bot import start_bot
    bot_task = asyncio.create_task(start_bot())
    await bot_task

if __name__ == "__main__":
    if os.path.exists(LOCK_FILE):
        logger.error("Другой экземпляр программы уже запущен.")
        print("Ошибка: другой экземпляр программы уже запущен.")
        sys.exit(1)

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
        logger.info(f"Файл блокировки создан: {LOCK_FILE}")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении программы: {e}")
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.info(f"Файл блокировки удалён: {LOCK_FILE}")
        asyncio.run(shutdown())