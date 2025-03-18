

def get_start_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ввести пароль главного админа")],
            [KeyboardButton(text="Подключиться к сессии")],
            [KeyboardButton(text="О боте")],
        ],
        resize_keyboard=True
    )
    return keyboard

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu(is_program_running=False):
    """
    Возвращает главное меню в зависимости от состояния программы.
    :param is_program_running: True, если программа запущена, иначе False.
    """
    if is_program_running:
        # Меню, когда программа запущена
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Остановка")],
               # [KeyboardButton(text="Перезапуск")],
                [KeyboardButton(text="Настройки")]
            ],
            resize_keyboard=True
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Запуск")],
                [KeyboardButton(text="Настройки")],
                [KeyboardButton(text="Выйти")]
            ],
            resize_keyboard=True
        )
    return keyboard

def get_back_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Вернуться назад")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_settings_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ТГ-Каналы"), KeyboardButton(text="Прокси")],
            [KeyboardButton(text="Админы"), KeyboardButton(text="Аккаунты")],
            [KeyboardButton(text="Вернуться назад")]
        ],
        resize_keyboard=True
    )



def get_admins_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить админа")],
            [KeyboardButton(text="Удалить админа")],
            [KeyboardButton(text="Список админов")],
            [KeyboardButton(text="Вернуться назад")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_accounts_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список аккаунтов"), KeyboardButton(text="Обновить инфу")],
            [KeyboardButton(text="Подписаться на переходник")],
            [KeyboardButton(text="Вернуться назад")]
        ],
        resize_keyboard=True
    )
    return keyboard