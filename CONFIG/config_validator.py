from pydantic import ValidationError
from CONFIG.config_manager import ConfigSchema
from utils.logger import logger


def validate_config(config):
    try:
        validated_config = ConfigSchema(**config)
        return validated_config.dict()
    except ValidationError as e:
        logger.error(f"Ошибка валидации конфигурации: {e}")
        return None