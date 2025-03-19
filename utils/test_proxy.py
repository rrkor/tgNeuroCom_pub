import aiohttp
from aiohttp_socks import ProxyConnector
import asyncio
from utils.logger import logger


async def test_socks5_proxy(proxy):
	proxy_url = f"socks5://{proxy['username']}:{proxy['password']}@{proxy['addr']}:{proxy['port']}"
	logger.info(f"Используемый URL для тестирования SOCKS5 прокси: {proxy_url}")
	connector = ProxyConnector.from_url(proxy_url)

	try:
		async with aiohttp.ClientSession(connector=connector) as session:
			async with session.get("http://httpbin.org/ip", timeout=5) as response:
				if response.status == 200:
					data = await response.json()
					logger.info(f"Прокси {proxy['addr']}:{proxy['port']} работает. IP: {data['origin']}")
					return True
				else:
					logger.warning(f"Прокси {proxy['addr']}:{proxy['port']} вернул статус {response.status}")
					return False
	except Exception as e:
		logger.error(f"Ошибка при тестировании прокси {proxy['addr']}:{proxy['port']}: {e}")
		return False


async def test_http_proxy(proxy):
	proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['addr']}:{proxy['port']}"
	try:
		async with aiohttp.ClientSession() as session:
			async with session.get("http://httpbin.org/ip", proxy=proxy_url, timeout=5) as response:
				if response.status == 200:
					data = await response.json()
					logger.info(f"Прокси {proxy['addr']}:{proxy['port']} работает. Ваш IP: {data['origin']}")
					return True
				else:
					logger.warning(f"Прокси {proxy['addr']}:{proxy['port']} вернул статус {response.status}")
					return False
	except Exception as e:
		logger.error(f"Ошибка при тестировании прокси {proxy['addr']}:{proxy['port']}: {e}")
		return False


async def test_proxy(proxy):
	logger.info(f"Тестирование прокси: {proxy['addr']}:{proxy['port']}")
	if proxy.get('proxy_type') == 'socks5':
		return await test_socks5_proxy(proxy)
	elif proxy.get('proxy_type') == 'http':
		return await test_http_proxy(proxy)
	else:
		logger.warning(f"Неизвестный тип прокси: {proxy.get('proxy_type')}")
		return False


async def test_all_proxies(proxies):
	tasks = [test_proxy(proxy) for proxy in proxies]
	results = await asyncio.gather(*tasks)
	return results
