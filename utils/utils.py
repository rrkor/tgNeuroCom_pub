import os
import json
import zipfile
import sqlite3
from utils.logger import logger

TEMP_FOLDER = 'cache'
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)
    logger.info(f"Папка {TEMP_FOLDER} успешно создана.")


def load_accounts_from_folder(accounts_folder='ACCOUNTS', accounts=None):
    if accounts is None:
        accounts = []

    for account_folder in os.listdir(accounts_folder):
        account_path = os.path.join(accounts_folder, account_folder)
        if not os.path.isdir(account_path):
            logger.warning(f"{account_path} не является папкой и будет проигнорирован.")
            continue

        tdata_zip_file = None
        tdata_folder = None
        session_file = None
        json_file = None

        for file_name in os.listdir(account_path):
            if file_name.endswith('_tdata.zip'):
                tdata_zip_file = os.path.join(account_path, file_name)
            elif file_name == 'tdata' and os.path.isdir(os.path.join(account_path, file_name)):
                tdata_folder = os.path.join(account_path, file_name)
            elif file_name.endswith('.session'):
                session_file = os.path.join(account_path, file_name)
            elif file_name.endswith('.json'):
                json_file = os.path.join(account_path, file_name)

        if json_file and (tdata_zip_file or tdata_folder or session_file):
            try:
                with open(json_file, 'r') as f:
                    account_data = json.load(f)
                if tdata_zip_file:
                    tdata_folder = os.path.join(account_path, "tdata")
                    if not os.path.exists(tdata_folder):
                        os.makedirs(tdata_folder)
                        with zipfile.ZipFile(tdata_zip_file, 'r') as zip_ref:
                            zip_ref.extractall(tdata_folder)
                    os.remove(tdata_zip_file)
                    logger.info(f"ZIP-архив {tdata_zip_file} удален после распаковки.")

                accounts.append({
                    'account_folder': account_path,
                    'tdata_folder': tdata_folder,
                    'session_file': session_file,
                    'account_data': account_data
                })
                logger.info(f"Данные аккаунта {account_folder} успешно загружены.")
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных аккаунта {account_folder}: {e}")
        else:
            logger.warning(f"Не найдены необходимые файлы для аккаунта {account_folder}.")

    logger.info(f"Всего загружено аккаунтов: {len(accounts)}")
    return accounts

def initialize_database():
    with sqlite3.connect('cache/channels.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel TEXT PRIMARY KEY,
                last_message_id INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Accounts (
                account_name TEXT PRIMARY KEY,
                avatar_file TEXT,
                pin_channel TEXT
            )
        ''')
        conn.commit()

initialize_database()




def load_channels_from_database():
    try:
        conn = sqlite3.connect('cache/channels.db')
        cursor = conn.cursor()
        cursor.execute('SELECT channel FROM channels')
        channels = [row[0] for row in cursor.fetchall()]
        conn.close()
        return channels
    except Exception as e:
        logger.error(f"Ошибка при загрузке каналов из базы данных: {e}")
        return []

def save_channels_to_database(channel):
    try:
        conn = sqlite3.connect('cache/channels.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO channels (channel) VALUES (?)', (channel,))
        conn.commit()
        conn.close()
        logger.info(f"Канал {channel} успешно добавлен в базу данных.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении канала в базу данных: {e}")

def remove_channel_from_database(channel):
    try:
        conn = sqlite3.connect('cache/channels.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE channel = ?', (channel,))
        conn.commit()
        conn.close()
        logger.info(f"Канал {channel} успешно удален из базы данных.")
    except Exception as e:
        logger.error(f"Ошибка при удалении канала из базы данных: {e}")