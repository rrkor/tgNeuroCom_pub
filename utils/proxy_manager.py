import asyncio
from utils.logger import logger
from utils.test_proxy import test_proxy

class ProxyManager:
    def __init__(self, proxies):
        self.proxies = proxies
        self.working_proxies = []
        self.current_proxy_index = 0

    async def test_all_proxies(self):
        tasks = [test_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)
        self.working_proxies = [proxy for proxy, result in zip(self.proxies, results) if result]
        logger.info(f"Обновлен список рабочих прокси. Рабочих прокси: {len(self.working_proxies)}/{len(self.proxies)}")

    def get_proxy_for_account(self, account_folder):
        if not self.working_proxies:
            logger.error("Нет рабочих прокси. Проверьте, что прокси были протестированы.")
            logger.info(f"Список прокси: {self.proxies}")
            return None
        account_hash = hash(account_folder)
        proxy_index = account_hash % len(self.working_proxies)
        logger.info(f"Распределение прокси для аккаунта {account_folder}: индекс {proxy_index}")
        return self.working_proxies[proxy_index]