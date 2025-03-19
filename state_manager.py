from datetime import timedelta
from CONFIG.config_manager import load_config

class StateManager:
    def __init__(self):
        self.config = load_config()

        # Глобалки
        self.program_running = False
        self.is_running = False
        self.CACHE_DURATION = timedelta(hours=1)
        self.geoip_cache = {}
        self.geo_ip_CACHE_DURATION = timedelta(days=2)
        self.proxy_manager = None
        self.bot = None
        self.dp = None
        self.is_initializing = False
        self.active_accounts = []

config = load_config()
state_manager = StateManager()