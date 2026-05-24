from typing import Optional, Union, List


class SteamConfig:
    """Steam插件配置类"""
    
    def __init__(self, config: dict):
        self.steam_api_key: List[str] = self._ensure_list(config.get("steam_api_key", []))
        self.proxy: Optional[str] = config.get("proxy")
        self.steam_request_interval: int = config.get("steam_request_interval", 300)
        self.steam_broadcast_type: str = config.get("steam_broadcast_type", "part")
        self.steam_disable_broadcast_on_startup: bool = config.get("steam_disable_broadcast_on_startup", False)
        self.steam_font_regular_path: str = config.get("steam_font_regular_path", "fonts/MiSans-Regular.ttf")
        self.steam_font_light_path: str = config.get("steam_font_light_path", "fonts/MiSans-Light.ttf")
        self.steam_font_bold_path: str = config.get("steam_font_bold_path", "fonts/MiSans-Bold.ttf")
    
    def _ensure_list(self, v: Union[str, List[str]]) -> List[str]:
        """确保API密钥是列表格式"""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v
