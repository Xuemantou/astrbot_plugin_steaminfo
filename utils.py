import time
import pytz
import httpx
import datetime
import calendar
from PIL import Image
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional
from astrbot.api import logger

from .models import Player
from .data_source import SteamDataStore


def normalize_proxy(proxy: str = None) -> Optional[str]:
    """将空字符串代理转换为 None
    
    Args:
        proxy: 代理地址字符串，可能为空字符串或 None
        
    Returns:
        有效的代理地址或 None
    """
    if proxy is not None and proxy.strip() == "":
        return None
    return proxy


async def _fetch_avatar(avatar_url: str, proxy: str = None) -> Image.Image:
    """获取头像图片
    
    Args:
        avatar_url: 头像图片的 URL
        proxy: 代理地址
        
    Returns:
        PIL Image 对象
    """
    proxy = normalize_proxy(proxy)
    
    async with httpx.AsyncClient(proxy=proxy, timeout=30.0) as client:
        response = await client.get(avatar_url)
        if response.status_code != 200:
            return Image.open(Path(__file__).parent / "res/unknown_avatar.jpg")
        return Image.open(BytesIO(response.content))


async def fetch_avatar(
    player: Player, avatar_dir: Optional[Path], proxy: str = None
) -> Image.Image:
    """获取玩家头像
    
    Args:
        player: Steam 玩家数据
        avatar_dir: 头像缓存目录
        proxy: 代理地址
        
    Returns:
        PIL Image 对象
    """
    if avatar_dir is not None:
        avatar_path = (
            avatar_dir / f"avatar_{player['steamid']}_{player['avatarhash']}.png"
        )
        
        if avatar_path.exists():
            avatar = Image.open(avatar_path)
        else:
            avatar = await _fetch_avatar(player["avatarfull"], proxy)
            avatar.save(avatar_path)
    else:
        avatar = await _fetch_avatar(player["avatarfull"], proxy)
    
    return avatar


async def convert_player_name_to_nickname(
    data: Dict[str, str], parent_id: str, data_store: SteamDataStore
) -> Dict[str, str]:
    """将玩家名称转换为昵称
    
    Args:
        data: 玩家数据字典
        parent_id: 群组 ID
        data_store: 数据存储实例
        
    Returns:
        添加了昵称的玩家数据字典
    """
    bind_info = await data_store.get_bind_by_steam_id(parent_id, data["steamid"])
    if bind_info:
        data["nickname"] = bind_info.get("nickname")
    else:
        data["nickname"] = None
    return data


async def simplize_steam_player_data(
    player: Player, proxy: str = None, avatar_dir: Path = None
) -> Dict[str, str]:
    """简化Steam玩家数据
    
    Args:
        player: Steam 玩家原始数据
        proxy: 代理地址
        avatar_dir: 头像缓存目录
        
    Returns:
        简化后的玩家数据字典，包含 steamid, avatar, name, status, personastate
    """
    avatar = await fetch_avatar(player, avatar_dir, proxy)
    
    if player["personastate"] == 0:
        if not player.get("lastlogoff"):
            status = "离线"
        else:
            time_logged_off = player["lastlogoff"]
            time_to_now = calendar.timegm(time.gmtime()) - time_logged_off
            
            if time_to_now < 60:
                status = "上次在线 刚刚"
            elif time_to_now < 3600:
                status = f"上次在线 {time_to_now // 60} 分钟前"
            elif time_to_now < 86400:
                status = f"上次在线 {time_to_now // 3600} 小时前"
            elif time_to_now < 2592000:
                status = f"上次在线 {time_to_now // 86400} 天前"
            elif time_to_now < 31536000:
                status = f"上次在线 {time_to_now // 2592000} 个月前"
            else:
                status = f"上次在线 {time_to_now // 31536000} 年前"
    elif player["personastate"] in [1, 2, 4]:
        status = (
            "在线" if player.get("gameextrainfo") is None else player["gameextrainfo"]
        )
    elif player["personastate"] == 3:
        status = (
            "离开" if player.get("gameextrainfo") is None else player["gameextrainfo"]
        )
    elif player["personastate"] in [5, 6]:
        status = "在线"
    else:
        status = "未知"
    
    return {
        "steamid": player["steamid"],
        "avatar": avatar,
        "name": player["personaname"],
        "status": status,
        "personastate": player["personastate"],
    }


def image_to_bytes(image: Image.Image) -> bytes:
    """将 PIL Image 转换为 PNG 字节数据
    
    Args:
        image: PIL Image 对象
        
    Returns:
        PNG 格式的字节数据
    """
    with BytesIO() as bio:
        image.save(bio, format="PNG")
        return bio.getvalue()


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """将十六进制颜色字符串转换为 RGB 元组
    
    Args:
        hex_color: 十六进制颜色字符串（如 "FF0000"）
        
    Returns:
        RGB 元组 (r, g, b)
    """
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def convert_timestamp_to_beijing_time(timestamp: int) -> str:
    """将 Unix 时间戳转换为北京时间字符串
    
    Args:
        timestamp: Unix 时间戳
        
    Returns:
        格式化的北京时间字符串 (YYYY-MM-DD HH:MM:SS)
    """
    beijing_timezone = pytz.timezone("Asia/Shanghai")
    date_utc = datetime.datetime.fromtimestamp(timestamp, pytz.utc)
    date_beijing = date_utc.astimezone(beijing_timezone)
    return date_beijing.strftime("%Y-%m-%d %H:%M:%S")
