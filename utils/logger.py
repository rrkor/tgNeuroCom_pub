
import logging
import os
from colorlog import ColoredFormatter

TEMP_FOLDER = 'cache'
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)-8s%(reset)s %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_cyan',
        }
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler("cache/neurocommenting.log")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

logger = setup_logging()