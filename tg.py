import os
import random
import asyncio
import re
import sqlite3
from telethon.tl.types import Channel, Chat, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.errors import (
    ChatWriteForbiddenError,
    ChannelPrivateError,
    ChannelInvalidError,
    FloodWaitError,
    PeerFloodError,
    UserBannedInChannelError
)

from telethon.tl.types import InputPeerNotifySettings
from telethon.tl.functions.account import UpdateNotifySettingsRequest, UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest, LeaveChannelRequest, \
    GetParticipantRequest
from CONFIG.config_manager import load_config
from state_manager import state_manager
from utils.logger import logger
from gpt import generate_comment, clean_text
from utils.utils import load_channels_from_database

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    exit(1)


min_delay = config['min_delay']
max_delay = config['max_delay']
max_bots_for_comment = config.get('max_bots_for_comment')
average_delay_between_comments = config.get('average_delay_between_comments')


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


def update_last_message_id(channel_identifier, message_id):
    with sqlite3.connect('cache/channels.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO channels (channel, last_message_id)
            VALUES (?, ?)
        ''', (channel_identifier, message_id))
        conn.commit()
        logger.info(f"Обновлен last_message_id для канала {channel_identifier}: {message_id}")


def is_post_commented(channel_identifier, message_id):
    with sqlite3.connect('cache/channels.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_message_id FROM channels WHERE channel = ?', (channel_identifier,))
        result = cursor.fetchone()
        return result and result[0] >= message_id


def select_random_accounts(active_accounts, max_bots):
    if not active_accounts:
        logger.warning("Нет активных аккаунтов для выбора.")
        return []
    num_bots = random.randint(1, max_bots)
    selected_accounts = random.sample(active_accounts, min(num_bots, len(active_accounts)))
    logger.info(f"Выбрано {len(selected_accounts)} аккаунтов для комментирования: "
                f"{[acc.session.filename for acc in selected_accounts]}")
    return selected_accounts


def get_random_delay(average_delay):
    lower_bound = max(25, int(average_delay) - 20)
    upper_bound = int(average_delay) + 20
    return random.randint(lower_bound, upper_bound)




async def send_top_level_comment(client, channel_identifier, post_id, post_text):
    try:
        channel_entity = await client.get_entity(channel_identifier)

        is_broadcast = False
        is_mega = False

        if isinstance(channel_entity, Channel):
            is_broadcast = channel_entity.broadcast
            is_mega = channel_entity.megagroup
        elif isinstance(channel_entity, Chat):
            is_broadcast = False
            is_mega = True


        comment = await generate_comment(post_text)
        if not comment:
            logger.warning("Сгенерированный комментарий пуст, пропускаем отправку.")
            return None

        await asyncio.sleep(3)

        if is_broadcast:
            try:
                channel_full = await client(GetFullChannelRequest(channel_entity))
                linked_id = getattr(channel_full.full_chat, 'linked_chat_id', None)
            except Exception as e:
                logger.error(f"Не удалось получить FullChannel для {channel_identifier}: {e}")
                linked_id = None

            if linked_id:
                discussion_entity = await client.get_entity(linked_id)
                dialogs = await client.get_dialogs()
                is_subscribed = any(dialog.id == discussion_entity.id for dialog in dialogs)

                if not is_subscribed:
                    logger.info(
                        f"Аккаунт {client.session.filename}: присоединяемся к обсуждению '{discussion_entity.title}'...")
                    try:
                        await client(JoinChannelRequest(discussion_entity))
                        logger.info(f"Успешно присоединились к обсуждению: {discussion_entity.title}")
                    except Exception as e:
                        logger.error(f"Ошибка при присоединении к обсуждению {discussion_entity.title}: {e}")
                        return None

                sent_message = await client.send_message(
                    entity=channel_entity,
                    message=comment,
                    comment_to=post_id
                )
                logger.info(f"Комментарий отправлен в '{channel_entity.title}'.")
                return sent_message
            else:
                logger.warning(f"Канал '{channel_entity.title}' не имеет связанного обсуждения (linked_chat_id). "
                               "Невозможно прокомментировать пост.")
                return None
        else:
            sent_message = await client.send_message(
                entity=channel_entity,
                message=comment,
                reply_to=post_id
            )
            logger.info(f"Комментарий отправлен в '{channel_entity.title}'.")
            return sent_message

    except (ChannelPrivateError, ChannelInvalidError) as e:
        logger.error(f"Канал {channel_identifier} приватный/недействителен: {e}")
    except ChatWriteForbiddenError:
        logger.error(f"Нет прав писать комментарии в канале/обсуждении '{channel_identifier}'.")
    except FloodWaitError as e:
        logger.error(f"FloodWait при отправке комментария: нужно подождать {e.seconds} секунд.")
        await asyncio.sleep(e.seconds)
    except PeerFloodError:
        logger.error(f"PeerFlood: Телеграм ограничил частоту действий аккаунта {client.session.filename}.")
    except UserBannedInChannelError:
        logger.error(f"Аккаунт забанен в канале '{channel_identifier}'.")
    except Exception as e:
        logger.error(f"Ошибка при отправке комментария в '{channel_identifier}': {e}")

    return None

async def handle_new_post(event, account_manager):
    if not event.chat:
        logger.error("Событие не содержит информации о чате.")
        return

    session_name = event.client.session.filename
    account_name = os.path.basename(os.path.dirname(session_name))
    logger.info(f"Аккаунт {account_name} получил пост в канале {event.chat.title} (ID поста: {event.id}).")

    try:
        try:
            channel_entity = await event.client.get_entity(event.chat)
        except (ChannelPrivateError, ChannelInvalidError) as e:
            logger.error(f"Канал {event.chat.title} приватный/недействителен: {e}")
            return
        except Exception as e:
            logger.error(f"Не удалось получить информацию о канале {event.chat.title}: {e}")
            return

        if getattr(channel_entity, 'username', None):
            channel_identifier = f"@{channel_entity.username}"
        else:
            channel_identifier = str(channel_entity.id)

        if is_post_commented(channel_identifier, event.message.id):
            logger.info(f"Пост {event.message.id} в канале '{event.chat.title}' уже прокомментирован, пропускаем.")
            return

        update_last_message_id(channel_identifier, event.message.id)

        post_text = clean_text(event.message.message)
        if not post_text:
            logger.warning(f"Пост в канале {event.chat.title} не содержит текста или пуст после очистки.")
            return

        logger.info(f"Текст поста: {post_text}")

        selected_accounts = select_random_accounts(state_manager.active_accounts, max_bots_for_comment)
        if not selected_accounts:
            logger.warning("Не удалось выбрать аккаунты для комментирования.")
            return

        random.shuffle(selected_accounts)

        for i, client_acc in enumerate(selected_accounts):
            await send_top_level_comment(client_acc, channel_identifier, event.id, post_text)

            if i < len(selected_accounts) - 1:
                delay = get_random_delay(average_delay_between_comments)
                logger.info(f"Ожидание {delay} секунд перед следующим комментарием...")
                await asyncio.sleep(delay)

    except Exception as e:
        logger.error(f"Ошибка при обработке нового поста: {e}")

async def disable_notifications(client, channel):
    try:
        channel_entity = await client.get_entity(channel)
        await client(UpdateNotifySettingsRequest(
            peer=channel_entity,
            settings=InputPeerNotifySettings(mute_until=2 ** 31 - 1)
        ))
        logger.info(f"Уведомления отключены для канала: {channel}")
    except Exception as e:
        logger.error(f"Не удалось отключить уведомления для канала {channel}: {e}")


async def is_user_subscribed(client, channel_identifier):
    try:
        channel_entity = await client.get_entity(channel_identifier)
        await client.get_messages(channel_entity, limit=1)
        return True
    except (ChannelPrivateError, ChannelInvalidError) as e:
        logger.error(f"Канал {channel_identifier} приватный/недействителен: {e}")
        return False
    except FloodWaitError as e:
        logger.error(f"FloodWait при проверке подписки: нужно подождать {e.seconds} секунд.")
        await asyncio.sleep(e.seconds)
        return False
    except PeerFloodError:
        logger.error(f"PeerFlood: Telegram ограничил частоту действий аккаунта {client.session.filename}.")
        return False
    except UserBannedInChannelError:
        logger.error(f"Аккаунт {client.session.filename} забанен в канале {channel_identifier}.")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки на канал {channel_identifier}: {e}")
        return False


async def subscribe_and_disable_notifications(client, channels):
    try:
        current_channels = set(channels)
        if not current_channels:
            logger.warning(f"Список каналов пуст для аккаунта {client.session.filename}.")
            return

        for channel in current_channels:
            channel_name = channel.lstrip('@').lower()
            try:
                try:
                    channel_entity = await client.get_entity(channel)
                except ChannelPrivateError:
                    logger.error(f"Канал {channel} приватный/закрытый, пропускаем.")
                    continue
                except ChannelInvalidError:
                    logger.error(f"Канал {channel} недействителен или не существует. Пропускаем.")
                    continue
                except Exception as e:
                    logger.error(f"Не удалось получить информацию о канале {channel}: {e}")
                    continue

                if await is_user_subscribed(client, channel):
                    logger.info(f"Аккаунт {client.session.filename} уже подписан на канал: {channel}")
                else:
                    delay = random.randint(10, 30)
                    logger.info(
                        f"Аккаунт {client.session.filename} ожидает {delay} сек перед подпиской на {channel}...")
                    await asyncio.sleep(delay)

                    try:
                        await client(JoinChannelRequest(channel))
                        logger.info(f"Аккаунт {client.session.filename} успешно подписался на канал: {channel}")
                    except Exception as e:
                        logger.error(f"Ошибка при подписке на канал {channel}: {e}")
                        continue

                await disable_notifications(client, channel)

            except Exception as e:
                logger.error(
                    f"Неизвестная ошибка при подписке/обработке канала {channel} для {client.session.filename}: {e}")
                continue

    except Exception as e:
        logger.error(f"Ошибка при обработке подписок для {client.session.filename}: {e}")
        await asyncio.sleep(60)


async def scan_channels_on_startup(client, channels):
    for channel in channels:
        try:
            channel_entity = await client.get_entity(channel)
            messages = await client.get_messages(channel_entity, limit=2)
            last_post_id = None

            for message in messages:
                if getattr(message, 'message', None):
                    last_post_id = message.id
                    break

            if last_post_id:
                update_last_message_id(channel, last_post_id)
            else:
                logger.warning(f"Не удалось найти недавние посты в канале {channel}.")
        except ChannelPrivateError:
            logger.error(f"Канал {channel} приватный или недоступен. Пропускаем.")
        except Exception as e:
            logger.error(f"Ошибка при сканировании канала {channel}: {e}")


async def scan_posts_periodically(client, account_manager):
    while state_manager.is_running:
        try:
            channels = load_channels_from_database()
            if not channels:
                logger.warning("Список каналов пуст. Ожидание 20 сек...")
                await asyncio.sleep(20)
                continue

            for channel in channels:
                try:
                    channel_entity = await client.get_entity(channel)
                    messages = await client.get_messages(channel_entity, limit=10)
                    if not messages:
                        logger.info(f"В канале {channel} нет новых сообщений.")
                        continue

                    last_post = None
                    for message in messages:
                        if getattr(message, 'message', None):
                            last_post = message
                            break

                    if not last_post:
                        logger.info(f"В канале {channel} нет текстовых постов.")
                        continue

                    if is_post_commented(channel, last_post.id):
                        continue

                    logger.info(f"Найден новый пост в канале {channel}. ID: {last_post.id}")
                    update_last_message_id(channel, last_post.id)

                    post_text = clean_text(last_post.message)
                    if not post_text:
                        logger.warning(
                            f"Пост {last_post.id} в {channel} пустой после очистки, пропускаем комментирование.")
                        continue

                    selected_accounts = select_random_accounts(state_manager.active_accounts, max_bots_for_comment)
                    random.shuffle(selected_accounts)

                    for i, client_acc in enumerate(selected_accounts):
                        await send_top_level_comment(client_acc, channel_entity, last_post.id, post_text)
                        if i < len(selected_accounts) - 1:
                            delay = get_random_delay(average_delay_between_comments)
                            logger.info(f"Ожидание {delay} секунд перед следующим комментарием...")
                            await asyncio.sleep(delay)

                except ChannelPrivateError:
                    logger.error(f"Канал {channel} приватный/закрытый, пропускаем.")
                except Exception as e:
                    logger.error(f"Ошибка при сканировании канала {channel}: {e}")

            await asyncio.sleep(20)

        except Exception as e:
            logger.error(f"Ошибка при сканировании постов: {e}")
            await asyncio.sleep(20)









async def unsubscribe_from_channel(client, channel):
    try:
        entity = await client.get_entity(channel)
        await client(LeaveChannelRequest(entity))
        logger.info(f"Успешная отписка от {channel}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отписки от {channel}: {str(e)}")
        return False

def normalize_channel_input(input_str):
    input_str = input_str.strip().lower()
    patterns = [
        r"@([a-z0-9_]{5,32})",
        r"t.me/([a-z0-9_]{5,32})",
        r"https://t.me/([a-z0-9_]{5,32})"
    ]
    for pattern in patterns:
        match = re.match(pattern, input_str)
        if match:
            return match.group(1)
    return None




async def start_all_accounts(account_manager):
    for client in state_manager.active_accounts:
        channels = load_channels_from_database()
        await subscribe_and_disable_notifications(client, channels)
        await scan_channels_on_startup(client, channels)
        asyncio.create_task(scan_posts_periodically(client, account_manager))
    logger.info("Все аккаунты инициализированы.")



async def is_channel_admin(client, channel_username: str) -> bool:
    try:
        channel = await client.get_entity(channel_username)
        participant = await client(GetParticipantRequest(
            channel=channel,
            participant=await client.get_me()
        ))
        return isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False


async def unpin_channel(client):
    try:
        await client(UpdateProfileRequest(
            first_name=await client.get_me().first_name,
            about=config['bio'],
            channel=None
        ))
        return True
    except Exception as e:
        logger.error(f"Ошибка открепления: {str(e)}")
        return False

async def get_current_pinned_channel(client):
    try:
        me = await client.get_me()
        return me.channel if hasattr(me, 'channel') else None
    except Exception as e:
        logger.error(f"Ошибка получения текущего канала: {str(e)}")
        return None