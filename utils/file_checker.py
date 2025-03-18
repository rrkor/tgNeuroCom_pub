

import os
from utils.logger import logger

def check_file_integrity():
    config_files = ["config_encrypted.yaml"]
    config_dir = "CONFIG"

    for file in config_files:
        file_path = os.path.join(config_dir, file)
        if not os.path.exists(file_path):
            logger.critical(f"Файл {file} отсутствует в папке {config_dir}.")
            return False, f"Файл {file} отсутствует. Пожалуйста, купите ключ -> @rrkorobov"

    required_files = [
        "FILES/admin_key.key",
        "FILES/proxy.txt",
        "prompt.txt",
        "FILES/config_key.key",
        "FILES/role.txt"
    ]

    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"Файл {file} отсутствует.")
            return False, f"Файл {file} отсутствует. Пожалуйста, восстановите его."

    return True, "Все файлы на месте."