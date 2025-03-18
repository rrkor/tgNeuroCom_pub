
from cryptography.fernet import Fernet
import os
from utils.logger import logger
import json

def generate_key(key_file='FILES/config_key.key'):
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, 'wb') as key_file:
            key_file.write(key)
        logger.info("Ключ шифрования сгенерирован и сохранен.")
    else:
        with open(key_file, 'rb') as key_file:
            key = key_file.read()
    return key

def encrypt_config(config, key):
    fernet = Fernet(key)
    encrypted_config = fernet.encrypt(json.dumps(config).encode())
    return encrypted_config

def decrypt_config(encrypted_config, key):
    fernet = Fernet(key)
    decrypted_config = json.loads(fernet.decrypt(encrypted_config).decode())
    return decrypted_config

def save_encrypted_config(config, key, config_file='FILES/config_encrypted.yaml'):
    encrypted_config = encrypt_config(config, key)
    with open(config_file, 'wb') as f:
        f.write(encrypted_config)
    logger.info("Конфигурация зашифрована и сохранена.")

def load_encrypted_config(key, config_file='FILES/config_encrypted.yaml'):
    if not os.path.exists(config_file):
        return {}
    with open(config_file, 'rb') as f:
        encrypted_config = f.read()
    return decrypt_config(encrypted_config, key)
