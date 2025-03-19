from CONFIG.config_manager import load_config
from state_manager import state_manager
from datetime import datetime, timedelta
import aiohttp
from utils.logger import logger

config = load_config()
if not config:
	logger.error("Не удалось загрузить конфигурацию. Программа завершена.")
	exit(1)


async def get_country_flag(ip_address):
	if ip_address in state_manager.geoip_cache and datetime.now() - state_manager.geoip_cache[ip_address][
		"timestamp"] < state_manager.geo_ip_CACHE_DURATION:
		return state_manager.geoip_cache[ip_address]["flag"]

	api_key = config['geo_api']
	url = f"http://api.ipgeolocation.io/ipgeo?apiKey={api_key}&ip={ip_address}"

	async with aiohttp.ClientSession() as session:
		async with session.get(url) as response:
			data = await response.json()
			logger.info(f"Ответ от IPGeolocation для IP {ip_address}: {data}")

			if "country_code2" in data:
				country_code = data["country_code2"].lower()
				flag = "".join(chr(ord(c) + 127397) for c in country_code.upper())
			else:
				flag = "🏳️"

			state_manager.geoip_cache[ip_address] = {
				"flag": flag,
				"timestamp": datetime.now()
			}
			return flag


def load_proxies_from_file(proxy_file='FILES/proxy.txt'):
	proxies = []
	try:
		with open(proxy_file, 'r', encoding='utf-8') as f:
			for line in f:
				if '###' in line:
					break
				line = line.strip()
				if not line:
					continue
				proxy_data = line.split(':')
				if len(proxy_data) == 4:
					proxies.append({
						'proxy_type': 'socks5',
						'addr': proxy_data[0],
						'port': int(proxy_data[1]),
						'username': proxy_data[2],
						'password': proxy_data[3]
					})
				else:
					logger.warning(f"Некорректный формат прокси: {line}")
		logger.info(f"Загружено прокси: {len(proxies)}")
	except Exception as e:
		logger.error(f"Ошибка при загрузке прокси: {e}")
	return proxies
