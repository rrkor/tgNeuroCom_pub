# Файл: gpt.py
import re
import random
from idlelib.iomenu import encoding

from openai import AsyncOpenAI
from utils.logger import logger
from CONFIG.config_manager import load_config

config = load_config()
if not config:
    logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
    exit(1)

openai_api_key = config['openai_api_key']
client_openai = AsyncOpenAI(api_key=openai_api_key)

def clean_text(text):
    if text is None:
        return ""
    text = re.sub(r'[^\w\s]', '', text)
    return text

def read_prompt_from_file(file_path='prompt.txt'):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
            prompts = [p.strip() for p in content.split('"') if p.strip()]
            if not prompts:
                logger.error("Файл prompt.txt не содержит промптов.")
                return None
            return random.choice(prompts)
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {file_path}: {e}")
        return None

def read_role_from_file(file_path='FILES/role.txt'):

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            role1 = file.read()
        return role1
    except FileNotFoundError:
        return logger.error(f"Файл роли не найден.")
    except Exception as e:
        logger.error (f"Произошла ошибка при чтении файла: {e}")
        return None



async def generate_comment(text):
    try:
        prompt = read_prompt_from_file()
        role = read_role_from_file()
        if not prompt:
            logger.error("Не удалось загрузить текст промпта из файла.")
            return None
        prompt_plus_text = (f"{prompt} А вот и пост, к которому надо написать комментарий: {text}."
                            f" Размер комментария ни в коем случае не должен превышать {config['maxtokensfromgpt']} токенов."
                            f" И никогда не пиши букву ё, вместо нее пиши е. Никогда не используй тире или длинное тире, вместо него -."
                            f" И не используй эмодзи. Никогда. Иногда делай пунктуационные ошибки. ")
        logger.warning("Отправка запроса к OpenAI...")
        response = await client_openai.chat.completions.create(
            model=config['modelapi'],
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt_plus_text}
            ],
            max_tokens=config['maxtokensfromgpt'],
            frequency_penalty=-1
        )
        comment = response.choices[0].message.content.strip()
        logger.info(f"Ответ от OpenAI: {comment}")
        logger.info("Комментарий успешно сгенерирован.")
        return comment
    except Exception as e:
        logger.error(f"Ошибка при генерации комментария: {e}")
        return None