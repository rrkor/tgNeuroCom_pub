import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import html

from telethon.tl.functions.account import UpdateProfileRequest

from state_manager import state_manager
from utils.account_manager import connect_account
from utils.account_setup import setup_account, initialize_accounts_table
from utils.logger import logger
import asyncio
from CONFIG.config_manager import load_config
from utils.admin_manager import add_admin, verify_admin, load_admins, is_main_admin, remove_admin
from utils.key_manager import generate_key, verify_key
from utils.button_manager import get_main_menu, get_start_menu, get_back_menu, get_settings_menu, get_admins_menu, \
    get_accounts_menu
from utils.proxy import load_proxies_from_file, get_country_flag
from utils.proxy_manager import ProxyManager
from utils.utils import load_channels_from_database, save_channels_to_database, remove_channel_from_database

from utils.proxy import load_proxies_from_file
from utils.utils import load_accounts_from_folder
from functools import partial


accounts = []
proxies = load_proxies_from_file()
accounts = load_accounts_from_folder(accounts=accounts)
proxy_manager = ProxyManager(proxies)


state_manager.program_running = False
proxy_cache = {}
CACHE_DURATION = timedelta(hours=1)
state_manager.is_running = False
def set_account_manager(manager):
    state_manager.account_manager = manager

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    exit(1)


bot_token = config.get("bot_token")
if not bot_token:
    logger.error("Токен Telegram-бота не найден.")
    exit(1)

try:
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    logger.info("Бот успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка при инициализации бота: {e}")
    exit(1)

dp = Dispatcher()
account_manager = None


class Form(StatesGroup):
    waiting_for_admin_password = State()
    waiting_for_2fa_password = State()
    waiting_for_admin_key = State()
    waiting_for_new_admin_username = State()
    waiting_for_admin_password_confirmation = State()
    waiting_for_new_channel = State()
    waiting_for_channel_to_remove = State()
    waiting_for_admin_to_remove = State()
    waiting_for_pin_channel = State()

password_attempts = {}




@dp.message(lambda message: message.text == "О боте")
async def about_bot(message: Message):
    try:
        text = "v0.2 tgNEUROCOM. DM for software @rrkorobov."
        escaped_text = html.escape(text)
        await message.answer(escaped_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка при обработке команды 'О боте': {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(Command("start"))
async def command_start(message: Message):
    try:
        username = message.from_user.username
        logger.info(f"Пользователь @{username} запустил бота.")
        await message.answer(
            "v0.2 tgNEUROCOM by RRKOR",
            reply_markup=get_start_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        await message.answer("Бот мертв. Пока что.")

# Обработчик ввода пароля главного админа
@dp.message(lambda message: message.text == "Ввести пароль главного админа")
async def enter_admin_password(message: Message, state: FSMContext):
    try:
        config = load_config()
        main_admin = config.get('main_admin')
        if not main_admin:
            await message.answer("Главный администратор не указан в конфигурации.")
            return
        current_username = f"@{message.from_user.username}"
        normalized_main_admin = f"@{main_admin}"
        if current_username != normalized_main_admin:
            await message.answer("Вы не являетесь главным администратором.")
            return
        await message.answer("Введите пароль главного админа:", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_admin_password)
    except Exception as e:
        logger.error(f"Ошибка при обработке ввода пароля: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

# Обработчик пароля главного админа
@dp.message(Form.waiting_for_admin_password)
async def process_admin_password(message: Message, state: FSMContext):
    try:
        username = message.from_user.username
        password = message.text
        if password == "Вернуться назад":
            await message.answer("Вы вернулись в главное меню.", reply_markup=get_start_menu())
            await state.clear()
            return
        if verify_admin(username, password):
            logger.info(f"Пользователь @{username} успешно вошел в систему.")
            await message.answer("Пароль верный. Вы авторизованы как главный админ.", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("Неверный пароль. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка при обработке пароля: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

# Обработчик подключения к сессии
@dp.message(lambda message: message.text == "Подключиться к сессии")
async def connect_to_session(message: Message, state: FSMContext):
    try:
        await message.answer("Введите одноразовый ключ для подключения к сессии:", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_admin_key)
    except Exception as e:
        logger.error(f"Ошибка при подключении к сессии: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

# Обработчик одноразового ключа
@dp.message(Form.waiting_for_admin_key)
async def process_admin_key(message: Message, state: FSMContext):
    try:
        key = message.text
        if key == "Вернуться назад":
            await message.answer("Вы вернулись в главное меню.", reply_markup=get_start_menu())
            await state.clear()
            return
        username = verify_key(key)
        if username:
            current_username = message.from_user.username.lower()
            if current_username != username:
                await message.answer(f"Этот ключ предназначен для @{username}.")
                return
            add_admin(message.from_user.username, "dummy_password")
            await message.answer(
                f"Вы успешно подключились к сессии как админ: @{message.from_user.username}",
                reply_markup=get_main_menu()
            )
            await state.clear()
        else:
            await message.answer("Неверный ключ. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка при обработке ключа: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")



# Обработчик username нового админа
@dp.message(Form.waiting_for_new_admin_username)
async def process_new_admin_username(message: Message, state: FSMContext):
    try:
        if message.text == "Вернуться назад":
            await message.answer("Добавление админа отменено.", reply_markup=get_settings_menu())
            await state.clear()
            return
        username = message.text.lstrip('@')
        if not username:
            await message.answer("Некорректный username. Попробуйте снова.")
            return
        await state.update_data(new_admin_username=username)
        await message.answer("Введите ваш пароль для подтверждения:")
        await state.set_state(Form.waiting_for_admin_password_confirmation)
    except Exception as e:
        logger.error(f"Ошибка при обработке username нового админа: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

# Обработчик подтверждения пароля для добавления админа
@dp.message(Form.waiting_for_admin_password_confirmation)
async def process_admin_password_confirmation(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        new_admin_username = data.get('new_admin_username')
        if not verify_admin(message.from_user.username, message.text):
            await message.answer("Неверный пароль. Добавление админа отменено.", reply_markup=get_start_menu())
            await state.clear()
            return
        code = generate_key(new_admin_username)
        await message.answer(
            f"Код для добавления админа:\n\n"
            f"`{code}`\n\n"
            f"Отправьте этот код будущему админу. Код действителен только для @{new_admin_username}.",
            parse_mode="Markdown",
            reply_markup=get_settings_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при подтверждении пароля: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(Form.waiting_for_admin_to_remove)
async def process_remove_admin(message: Message, state: FSMContext):
    try:
        if message.text == "Вернуться назад":
            await message.answer("Удаление админа отменено.", reply_markup=get_admins_menu())
            await state.clear()
            return

        username = message.text.strip()
        if not username.startswith("@"):
            await message.answer("Некорректный username. Попробуйте снова.", reply_markup=get_back_menu())
            return

        # Удаляем админа
        remove_admin(username)
        await message.answer(f"Админ {username} успешно удален.", reply_markup=get_admins_menu())
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при удалении админа: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_admins_menu())






@dp.message(lambda message: message.text == "Вернуться назад")
async def back_to_main_menu(message: Message, state: FSMContext):
    """
    Возвращает пользователя в главное меню в зависимости от состояния программы.
    """
    try:
        await state.clear()  # Очищаем состояние
        if state_manager.program_running:
            # Возвращаем в главное меню для запущенной программы
            await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_menu(is_program_running=True))
        else:
            # Возвращаем в главное меню для остановленной программы
            await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_menu(is_program_running=False))
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_main_menu())







@dp.message(lambda message: message.text == "Запуск")
async def start_program_handler(message: Message):
    try:
        if state_manager.is_running:
            await message.answer("Программа уже запущена.")
            return
        if not is_main_admin(message.from_user.username):
            await message.answer("Эта команда доступна только главному администратору.")
            return

        # Блокируем интерфейс
        state_manager.is_initializing = True
        await message.answer("Запуск программы... Пожалуйста, подождите.", reply_markup=get_main_menu(is_program_running=True))

        # Загрузка каналов из базы данных
        channels = load_channels_from_database()
        if not channels:
            await message.answer("Список каналов пуст. Добавьте каналы через меню 'ТГ-Каналы'.")
            logger.warning("Список каналов пуст. Программа не может быть запущена.")
            state_manager.is_initializing = False
            return

        # Загрузка прокси

        if not proxies:
            await message.answer("Список прокси пуст. Добавьте прокси через меню 'Прокси'.")
            logger.warning("Список прокси пуст. Программа не может быть запущена.")
            state_manager.is_initializing = False
            return

        # Загрузка аккаунтов
        accounts = load_accounts_from_folder()
        if not accounts:
            await message.answer("Нет доступных аккаунтов. Добавьте аккаунты в папку ACCOUNTS.")
            logger.warning("Нет доступных аккаунтов. Программа не может быть запущена.")
            state_manager.state_manager.is_initializing = False
            return

        # Запуск программы
        state_manager.program_running = True
        from main import start_program
        asyncio.create_task(start_program())
        await message.answer(
            f"Программа запущена.\n"
            f"Каналы: {len(channels)}\n"
            f"Рабочие прокси: {len(proxy_manager.working_proxies)}\n"
            f"Подключенные аккаунты: {len(accounts)}"
        )
        logger.info(f"Программа запущена. Каналы: {len(channels)}, Прокси: {len(proxy_manager.working_proxies)}, Аккаунты: {len(accounts)}")
    except Exception as e:
        logger.error(f"Ошибка при запуске программы: {e}")
        await message.answer("Произошла ошибка при запуске программы. Попробуйте снова.", reply_markup=get_main_menu())
    finally:
        state_manager.is_initializing = False  # Разблокируем интерфейс

@dp.message(lambda message: message.text == "Остановка")
async def stop_program_handler(message: Message):
    try:
        if not state_manager.is_running:
            await message.answer("Программа уже остановлена.")
            return
        if not is_main_admin(message.from_user.username):
            await message.answer("Эта команда доступна только главному администратору.")
            return
        logger.info("Начало остановки программы...")
        state_manager.is_running = False

        await message.answer("Программа остановлена.", reply_markup=get_main_menu(is_program_running=False))
        logger.info("Программа остановлена.")
    except Exception as e:
        logger.error(f"Ошибка при остановке программы: {e}")
        await message.answer("Произошла ошибка при остановке программы. Попробуйте снова.", reply_markup=get_main_menu())

"""@dp.message(lambda message: message.text == "Перезапуск")
async def restart_program_handler(message: Message):
    global program_running
    try:
        if not program_running:
            await message.answer("Программа не запущена. Используйте кнопку 'Запуск'.")
            return
        if not is_main_admin(message.from_user.username):
            await message.answer("Эта команда доступна только главному администратору.")
            return

        # Остановка программы
        await shutdown()
        await message.answer("Программа остановлена. Перезапуск...", reply_markup=get_main_menu(is_program_running=False))
        logger.info("Программа остановлена для перезапуска.")

        # Запуск программы
        program_running = True
        await message.answer("Программа перезапущена.", reply_markup=get_main_menu(is_program_running=True))
        from main import start_program
        asyncio.create_task(start_program())
        logger.info("Программа перезапущена.")
    except Exception as e:
        logger.error(f"Ошибка при перезапуске программы: {e}")
        await message.answer("Произошла ошибка при перезапуске программы. Попробуйте снова.", reply_markup=get_main_menu())"""

@dp.message(lambda message: message.text == "Выйти")
async def back_to_start_menu(message: Message, state: FSMContext):
    try:
        await message.answer("Вы вернулись в стартовое меню.", reply_markup=get_start_menu())
        await state.clear()  # Очищаем состояние
    except Exception as e:
        logger.error(f"Ошибка при возврате в стартовое меню: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_main_menu())






@dp.message(lambda message: message.text == "Аккаунты")
async def show_accounts_menu(message: types.Message):
    try:
        # Отправляем меню с кнопками
        await message.answer("Управление аккаунтами:", reply_markup=get_accounts_menu())
    except Exception as e:
        logger.error(f"Ошибка при открытии меню аккаунтов: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_main_menu())




@dp.message(lambda message: message.text == "Список аккаунтов")
async def show_accounts(message: types.Message):
    try:
        # Загружаем аккаунты
        accounts = load_accounts_from_folder()
        if not accounts:
            await message.answer("Нет доступных аккаунтов.\nДобавьте аккаунты в папку.")
            return

        # Инициализируем ProxyManager
        proxy_manager = ProxyManager(load_proxies_from_file())
        await proxy_manager.test_all_proxies()

        accounts_info = []
        for account in accounts:
            client = await connect_account(account, proxy_manager)
            if client:
                try:
                    # Получаем информацию об аккаунте
                    me = await client.get_me()
                    username = me.username if me.username else "Нет username"
                    status_icon = "✅" if await client.is_user_authorized() else "❌"
                    accounts_info.append(f"{status_icon} ID: {os.path.basename(account['account_folder'])} | @{username}")
                except Exception as e:
                    logger.error(f"Ошибка при получении информации об аккаунте: {e}")
                    accounts_info.append(f"❌ Ошибка при получении информации об аккаунте")
                finally:
                    # Закрываем соединение с аккаунтом
                    await client.disconnect()

        # Формируем сообщение с информацией об аккаунтах
        message_text = "Список аккаунтов:\n" + "\n".join(accounts_info)
        await message.answer(message_text, reply_markup=get_accounts_menu())
    except Exception as e:
        logger.error(f"Ошибка при отображении списка аккаунтов: {e}")
        await message.answer("Произошла ошибка при загрузке списка аккаунтов. Попробуйте снова.", reply_markup=get_accounts_menu())




@dp.message(lambda message: message.text == "ТГ-Каналы")
async def manage_channels(message: Message, state: FSMContext):
    try:
        channels = load_channels_from_database()
        if not channels:
            await message.answer("Список каналов пуст.")
        else:
            await message.answer(f"Текущие каналы:\n{', '.join(channels)}")
        await message.answer("Выберите действие:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Добавить канал")],
                [KeyboardButton(text="Удалить канал")],
                [KeyboardButton(text="Вернуться назад")]
            ],
            resize_keyboard=True
        ))
    except Exception as e:
        logger.error(f"Ошибка при управлении каналами: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(lambda message: message.text == "Добавить канал")
async def add_channel_start(message: Message, state: FSMContext):
    try:
        if state_manager.is_running:
            await message.answer("Программа запущена. Остановите программу перед изменением списка каналов.")
            return
        await message.answer("Введите username канала (например, @channel):", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_new_channel)
    except Exception as e:
        logger.error(f"Ошибка при начале добавления канала: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(lambda message: message.text == "Настройки")
async def settings_menu(message: Message):
    try:
        await message.answer("Настройки:", reply_markup=get_settings_menu())
    except Exception as e:
        logger.error(f"Ошибка при открытии меню настроек: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(Form.waiting_for_new_channel)
async def process_new_channel(message: Message, state: FSMContext):
    try:
        if message.text == "Вернуться назад":
            await message.answer("Добавление канала отменено.", reply_markup=get_settings_menu())
            await state.clear()
            return

        # Проверяем формат ввода
        if not validate_channel_input(message.text):
            await message.answer(
                "Некорректный формат канала. Ввод должен начинаться с @, https://t.me/ или t.me/.",
                reply_markup=get_back_menu()
            )
            return

        # Нормализуем ввод канала
        channel = normalize_channel_input(message.text.strip())

        if not channel:
            await message.answer("Некорректный username канала. Попробуйте снова.", reply_markup=get_back_menu())
            return

        # Загрузка текущих каналов из базы данных
        channels = load_channels_from_database()
        if f"@{channel}" in channels:  # Проверяем с @, так как в базе храним с @
            await message.answer("Этот канал уже добавлен.", reply_markup=get_back_menu())
            return

        # Добавление канала в базу данных
        save_channels_to_database(f"@{channel}")  # Сохраняем с @
        await message.answer(f"Канал @{channel} успешно добавлен.", reply_markup=get_settings_menu())
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при добавлении канала: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_back_menu())

@dp.message(lambda message: message.text == "Удалить канал")
async def remove_channel_start(message: Message, state: FSMContext):
    try:
        if state_manager.is_running:
            await message.answer("Программа запущена. Остановите программу перед изменением списка каналов.")
            return
        await message.answer("Введите username канала для удаления (например, @channel):", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_channel_to_remove)
    except Exception as e:
        logger.error(f"Ошибка при начале удаления канала: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

# Обработчик удаления канала
@dp.message(Form.waiting_for_channel_to_remove)
async def process_remove_channel(message: Message, state: FSMContext):
    try:
        if message.text == "Вернуться назад":
            await message.answer("Удаление канала отменено.", reply_markup=get_settings_menu())
            await state.clear()
            return

        # Проверяем формат ввода
        if not validate_channel_input(message.text):
            await message.answer(
                "Некорректный формат канала. Ввод должен начинаться с @, https://t.me/ или t.me/.",
                reply_markup=get_back_menu()
            )
            return

        # Нормализуем ввод канала
        channel = normalize_channel_input(message.text.strip())

        if not channel:
            await message.answer("Некорректный username канала. Попробуйте снова.", reply_markup=get_back_menu())
            return

        # Удаление канала из базы данных
        remove_channel_from_database(f"@{channel}")
        await message.answer(f"Канал @{channel} успешно удален.", reply_markup=get_settings_menu())
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при удалении канала: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_back_menu())

def normalize_channel_input(channel_input):
    if channel_input.startswith('@'):
        channel_input = channel_input[1:]
    channel_input = re.sub(r'^(https?:\/\/)?t\.me\/', '', channel_input)
    channel_input = channel_input.strip()
    return channel_input

def validate_channel_input(channel_input):
    if re.match(r'^(@|https?:\/\/t\.me\/|t\.me\/)', channel_input):
        return True
    return False








@dp.message(lambda message: message.text == "Прокси")
async def show_proxies(message: Message):
    try:
        global proxy_cache

        if "proxies" in proxy_cache and datetime.now() - proxy_cache["timestamp"] < CACHE_DURATION:
            proxy_statuses = proxy_cache["proxies"]
        else:
            # Загружаем прокси из файла
            proxies = load_proxies_from_file()
            if not proxies:
                await message.answer("Список прокси пуст.")
                return

            # Проверяем каждый прокси
            from utils.test_proxy import test_all_proxies  # Импорт функции
            results = await test_all_proxies(proxies)
            proxy_statuses = []
            for proxy, is_working in zip(proxies, results):
                status_icon = "✅" if is_working else "❌"
                ip_address = proxy['addr']
                country_flag = await get_country_flag(ip_address)
                proxy_statuses.append(f"{status_icon} {ip_address}:{proxy['port']} {country_flag}")

            # Обновляем кэш
            proxy_cache = {
                "proxies": proxy_statuses,
                "timestamp": datetime.now()
            }

        # Формируем сообщение
        message_text = "Список прокси:\n" + "\n".join(proxy_statuses)
        await message.answer(message_text)
    except Exception as e:
        logger.error(f"Ошибка при обработке команды 'Прокси': {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@dp.message(lambda message: message.text == "Админы")
async def manage_admins(message: Message, state: FSMContext):
    try:
        await state.clear()
        logger.info("Пользователь нажал на кнопку 'Админы'.")
        # Отправляем меню с кнопками для управления админами
        await message.answer("Управление админами:", reply_markup=get_admins_menu())
    except Exception as e:
        logger.error(f"Ошибка при открытии меню админов: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_settings_menu())

@dp.message(lambda message: message.text == "Добавить админа")
async def add_admin_start(message: Message, state: FSMContext):
    try:
        await message.answer("Введите @username нового админа:", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_new_admin_username)
    except Exception as e:
        logger.error(f"Ошибка при начале добавления админа: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_admins_menu())

@dp.message(lambda message: message.text == "Удалить админа")
async def remove_admin_start(message: Message, state: FSMContext):
    """
    Начинает процесс удаления админа.
    """
    try:
        await message.answer("Введите @username админа для удаления:", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_admin_to_remove)  # Используем новое состояние
    except Exception as e:
        logger.error(f"Ошибка при начале удаления админа: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_admins_menu())

@dp.message(lambda message: message.text == "Список админов")
async def show_admins_list(message: Message):
    try:
        admins = load_admins()
        if not admins:
            await message.answer("Вы единственный админ. Добавьте людей к себе в команду!")
            return
        admins_list = "Список админов:\n"
        for username in admins.keys():
            normalized_username = f"@{username.lstrip('@')}"
            admins_list += f"{normalized_username}\n"
        await message.answer(admins_list, reply_markup=get_admins_menu())
    except Exception as e:
        logger.error(f"Ошибка при показе списка админов: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=get_admins_menu())









@dp.message(lambda message: message.text == "Обновить инфу")
async def handle_update_accounts_info(message: types.Message):
    await update_accounts_info(message)

async def update_accounts_info(message: types.Message):
    initialize_accounts_table()

    accounts = load_accounts_from_folder()
    proxies = load_proxies_from_file()

    if not proxies:
        await message.answer("Список прокси пуст. Добавьте прокси через меню 'Прокси'.")
        return

    # Создаем ProxyManager и тестируем прокси
    proxy_manager = ProxyManager(proxies)
    await proxy_manager.test_all_proxies()

    if not proxy_manager.working_proxies:
        await message.answer("Нет рабочих прокси. Проверьте, что прокси были протестированы.")
        return

    new_accounts = []
    with sqlite3.connect('cache/channels.db') as conn:
        cursor = conn.cursor()
        for account in accounts:
            account_name = os.path.basename(account['account_folder'])
            cursor.execute('SELECT account_name FROM Accounts WHERE account_name = ?', (account_name,))
            if not cursor.fetchone():
                new_accounts.append(account)

    if not new_accounts:
        await message.answer("Новых аккаунтов для обновления не найдено.")
        return

    # Обновляем информацию для новых аккаунтов
    for account in new_accounts:
        await setup_account(account, proxy_manager)

    await message.answer("Информация для новых аккаунтов успешно обновлена.")

# Регистрация обработчика
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(update_accounts_info, text="Обновить инфу")


@dp.message(lambda message: message.text == "Подписаться на переходник")
async def subscribe_to_pin_channel(message: Message, state: FSMContext):
    try:
        global proxy_manager
        await proxy_manager.test_all_proxies()

        if state_manager.is_running:
            await message.answer("❌ Программа запущена. Остановите её перед изменением переходника.")
            return

        await message.answer("Введите @username канала-переходника:", reply_markup=get_back_menu())
        await state.set_state(Form.waiting_for_pin_channel)
    except Exception as e:
        logger.error(f"Ошибка при старте подписки: {e}")
        await message.answer("⚠️ Ошибка при старте процесса подписки")



async def process_account_subscription(client, channel):
    try:
        # Получаем имя аккаунта из пути сессии
        account_name = os.path.basename(os.path.dirname(client.session.filename))

        # Подключаемся к аккаунту
        if not client.is_connected():
            await client.connect()

            if not await client.is_user_authorized():
                logger.error(f"Аккаунт {account_name} не авторизован")
                return False

        # Проверяем текущий канал в БД
        with sqlite3.connect('cache/channels.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT pin_channel FROM Accounts WHERE account_name = ?', (account_name,))
            result = cursor.fetchone()
            current_channel = result[0] if result else None

        # Отписываемся от старого канала
        if current_channel:
            try:
                entity = await client.get_entity(current_channel)
                from telethon.tl.functions.channels import LeaveChannelRequest
                await client(LeaveChannelRequest(entity))
                logger.info(f"Отписались от {current_channel}")
            except Exception as e:
                logger.error(f"Ошибка отписки: {str(e)}")

        # Подписываемся на новый канал
        try:
            entity = await client.get_entity(channel)
            from telethon.tl.functions.channels import JoinChannelRequest
            await client(JoinChannelRequest(entity))

            # Обновляем БД
            with sqlite3.connect('cache/channels.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO Accounts 
                    (account_name, pin_channel) 
                    VALUES (?, ?)
                ''', (account_name, f"@{channel}"))
                conn.commit()

            return True
        except Exception as e:
            logger.error(f"Ошибка подписки: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        return False
    finally:
        if client.is_connected():
            await client.disconnect()


@dp.message(Form.waiting_for_pin_channel)
async def process_pin_channel(message: Message, state: FSMContext):
    try:
        progress_msg = await message.answer("🔄 Начинаю обработку...")

        await progress_msg.edit_text("🔍 Проверяю прокси...")
        await proxy_manager.test_all_proxies()

        if not proxy_manager.working_proxies:
            await message.answer("❌ Нет рабочих прокси!")
            return

        # Нормализация канала
        channel = normalize_channel_input(message.text)
        if not channel:
            await message.answer("⚠️ Неверный формат канала! Пример: @channel")
            return

        # Загрузка аккаунтов
        await progress_msg.edit_text("📂 Загружаю аккаунты...")
        accounts = load_accounts_from_folder()

        total = len(accounts)
        success = 0
        failed = 0

        # Обработка аккаунтов
        for idx, account in enumerate(accounts, 1):
            try:
                # Обновление статуса
                await progress_msg.edit_text(
                    f"⏳ Обработка {idx}/{total}\n"
                    f"✅ Успешно: {success} ❌ Ошибок: {failed}"
                )

                # Подключение
                client = await connect_account(account, proxy_manager)
                if not client:
                    failed += 1
                    continue

                # Подписка
                result = await process_account_subscription(client, channel)
                if result:
                    success += 1
                else:
                    failed += 1

                # Задержка
                await asyncio.sleep(random.randint(5, 10))

            except Exception as e:
                logger.error(f"Ошибка: {str(e)}")
                failed += 1
            finally:
                if client and client.is_connected():
                    await client.disconnect()

        # Итог
        await progress_msg.delete()
        await message.answer(
            f"📊 Готово!\nУспешно: {success}/{total}\nОшибки: {failed}/{total}",
            reply_markup=get_accounts_menu()
        )

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        await message.answer("💥 Произошла системная ошибка!")
    finally:
        await state.clear()


@dp.message(lambda message: message.text == "Закрепить переходник")
async def pin_channel_handler(message: Message):
    try:
        accounts = load_accounts_from_folder()
        await proxy_manager.test_all_proxies()

        success = 0
        failed_admin = 0
        failed_other = 0
        replaced = 0

        progress_msg = await message.answer("🔄 Начало обработки...")

        for idx, account in enumerate(accounts, 1):
            client = None
            try:
                # Обновление статуса
                await progress_msg.edit_text(
                    f"⏳ Обработка {idx}/{len(accounts)}\n"
                    f"✅ Успешно: {success} | 🔄 Заменено: {replaced} | 🛑 Не админ: {failed_admin} | ❌ Ошибки: {failed_other}"
                )

                client = await connect_account(account, proxy_manager)
                if not client:
                    failed_other += 1
                    continue

                account_name = os.path.basename(account['account_folder'])
                with sqlite3.connect('cache/channels.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT pin_channel FROM Accounts WHERE account_name = ?', (account_name,))
                    result = cursor.fetchone()
                    new_channel = result[0] if result else None

                if not new_channel:
                    failed_other += 1
                    continue

                # Получаем текущий прикрепленный канал
                me = await client.get_me()
                current_channel = me.channel if hasattr(me, 'channel') else None

                # Если есть текущий канал - проверяем права и открепляем
                if current_channel:
                    try:
                        current_entity = await client.get_entity(current_channel)
                        participant = await client.get_permissions(current_entity)
                        if not participant.is_admin:
                            raise Exception("Not admin in old channel")

                        # Открепляем старый канал
                        await client(UpdateProfileRequest(
                            first_name=me.first_name,
                            about=me.about,
                            channel=None
                        ))
                        replaced += 1
                        logger.info(f"Откреплен старый канал {current_channel}")

                    except Exception as e:
                        logger.error(f"Ошибка открепления: {str(e)}")
                        failed_admin += 1
                        continue

                # Прикрепляем новый канал
                try:
                    new_entity = await client.get_entity(new_channel)
                    participant = await client.get_permissions(new_entity)
                    if not participant.is_admin:
                        raise Exception("Not admin in new channel")

                    await client(UpdateProfileRequest(
                        first_name=me.first_name,
                        about=me.about,
                        channel=new_entity
                    ))

                    with sqlite3.connect('cache/channels.db') as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE Accounts 
                            SET pin_channel = ?
                            WHERE account_name = ?
                        ''', (new_channel, account_name))
                        conn.commit()

                    success += 1
                    logger.info(f"Прикреплен новый канал {new_channel}")

                except Exception as e:
                    logger.error(f"Ошибка прикрепления: {str(e)}")
                    failed_admin += 1

                await asyncio.sleep(random.randint(10, 20))

            except Exception as e:
                logger.error(f"Ошибка: {str(e)}")
                failed_other += 1
            finally:
                if client and client.is_connected():
                    await client.disconnect()

        # Формирование отчета
        report = (
            f"📊 Итоги закрепления:\n"
            f"• Всего аккаунтов: {len(accounts)}\n"
            f"• Успешно: {success} ✅\n"
            f"• Заменено: {replaced} 🔄\n"
            f"• Не админ: {failed_admin} 🛑\n"
            f"• Прочие ошибки: {failed_other} ❌"
        )

        await progress_msg.delete()
        await message.answer(report, reply_markup=get_accounts_menu())

    except Exception as e:
        logger.error(f"Фатальная ошибка: {str(e)}")
        await message.answer("💥 Критический сбой системы!")



async def start_bot():
    try:
        logger.info("Запуск Telegram-бота...")
        await dp.start_polling(bot)
        logger.info("Бот успешно запущен и начал работу.")
    except asyncio.CancelledError:
        logger.info("Работа бота завершена.")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()