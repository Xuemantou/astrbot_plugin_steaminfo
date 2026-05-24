import time
from PIL import Image
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

from .models import Player, ProcessedPlayer


class SteamDataStore:
    """Steam数据存储类，使用astrbot的KV存储"""
    
    def __init__(self, star):
        self.star = star
    
    # 绑定数据操作
    async def get_bind_data(self) -> Dict[str, List[Dict[str, str]]]:
        """获取绑定数据"""
        return await self.star.get_kv_data("bind_data", {})
    
    async def save_bind_data(self, data: Dict[str, List[Dict[str, str]]]):
        """保存绑定数据"""
        await self.star.put_kv_data("bind_data", data)
    
    async def add_bind(self, parent_id: str, content: Dict[str, str]):
        """添加绑定"""
        data = await self.get_bind_data()
        if parent_id not in data:
            data[parent_id] = [content]
        else:
            data[parent_id].append(content)
        await self.save_bind_data(data)
    
    async def remove_bind(self, parent_id: str, user_id: str):
        """移除绑定"""
        data = await self.get_bind_data()
        if parent_id in data:
            data[parent_id] = [d for d in data[parent_id] if d.get("user_id") != user_id]
            await self.save_bind_data(data)
    
    async def update_bind(self, parent_id: str, user_id: str, content: Dict[str, str]):
        """更新绑定"""
        data = await self.get_bind_data()
        if parent_id in data:
            for i, d in enumerate(data[parent_id]):
                if d.get("user_id") == user_id:
                    data[parent_id][i] = content
                    break
            await self.save_bind_data(data)
    
    async def get_bind(self, parent_id: str, user_id: str) -> Optional[Dict[str, str]]:
        """获取绑定信息"""
        data = await self.get_bind_data()
        if parent_id in data:
            for d in data[parent_id]:
                if d.get("user_id") == user_id:
                    if not d.get("nickname"):
                        d["nickname"] = None
                    return d
        return None
    
    async def get_bind_by_steam_id(self, parent_id: str, steam_id: str) -> Optional[Dict[str, str]]:
        """通过Steam ID获取绑定信息"""
        data = await self.get_bind_data()
        if parent_id in data:
            for d in data[parent_id]:
                if d.get("steam_id") == steam_id:
                    if not d.get("nickname"):
                        d["nickname"] = None
                    return d
        return None
    
    async def get_all_binds(self, parent_id: str) -> List[str]:
        """获取所有绑定的Steam ID"""
        data = await self.get_bind_data()
        if parent_id not in data:
            return []
        result = []
        for d in data[parent_id]:
            if d.get("steam_id") and d["steam_id"] not in result:
                result.append(d["steam_id"])
        return result
    
    async def get_all_steam_ids(self) -> List[str]:
        """获取所有Steam ID"""
        data = await self.get_bind_data()
        result = []
        for parent_id in data:
            for d in data[parent_id]:
                if d.get("steam_id") and d["steam_id"] not in result:
                    result.append(d["steam_id"])
        return result
    
    async def get_unified_msg_origins(self) -> Dict[str, str]:
        """获取所有 parent_id 对应的 unified_msg_origin
        
        Returns:
            字典，key 为 parent_id，value 为 unified_msg_origin
        """
        data = await self.get_bind_data()
        result = {}
        for parent_id in data:
            for d in data[parent_id]:
                if d.get("unified_msg_origin"):
                    result[parent_id] = d["unified_msg_origin"]
                    break
        return result
    
    # Steam信息数据操作
    async def get_steam_info_data(self) -> List[ProcessedPlayer]:
        """获取Steam信息数据"""
        return await self.star.get_kv_data("steam_info_data", [])
    
    async def save_steam_info_data(self, data: List[ProcessedPlayer]):
        """保存Steam信息数据"""
        await self.star.put_kv_data("steam_info_data", data)
    
    async def update_steam_info_by_players(self, players: List[Player]):
        """更新Steam信息数据"""
        data = await self.get_steam_info_data()
        processed_players = []
        
        for player in players:
            old_player = None
            for p in data:
                if p.get("steamid") == player.get("steamid"):
                    old_player = p
                    break
            
            if old_player is None:
                if player.get("gameextrainfo") is not None:
                    player["game_start_time"] = int(time.time())
                else:
                    player["game_start_time"] = None
                processed_players.append(player)
            else:
                if (player.get("gameextrainfo") is not None and 
                    old_player.get("gameextrainfo") is None):
                    player["game_start_time"] = int(time.time())
                elif (player.get("gameextrainfo") is None and 
                      old_player.get("gameextrainfo") is not None):
                    player["game_start_time"] = None
                elif (player.get("gameextrainfo") is not None and 
                      old_player.get("gameextrainfo") is not None):
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        player["game_start_time"] = int(time.time())
                    else:
                        player["game_start_time"] = old_player.get("game_start_time")
                else:
                    player["game_start_time"] = None
                processed_players.append(player)
        
        await self.save_steam_info_data(processed_players)
    
    async def get_players_by_steam_ids(self, steam_ids: List[str]) -> List[ProcessedPlayer]:
        """通过Steam ID获取玩家列表"""
        data = await self.get_steam_info_data()
        return [p for p in data if p.get("steamid") in steam_ids]
    
    async def compare_players(self, old_players: List[Player], new_players: List[Player]) -> List[Dict[str, Any]]:
        """比较新旧玩家数据"""
        result = []
        for player in new_players:
            for old_player in old_players:
                if player.get("steamid") == old_player.get("steamid"):
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        if (player.get("gameextrainfo") is not None and 
                            old_player.get("gameextrainfo") is not None):
                            result.append({
                                "type": "change",
                                "player": player,
                                "old_player": old_player,
                            })
                        elif old_player.get("gameextrainfo") is not None:
                            result.append({
                                "type": "stop",
                                "player": player,
                                "old_player": old_player,
                            })
                        elif player.get("gameextrainfo") is not None:
                            result.append({
                                "type": "start",
                                "player": player,
                                "old_player": old_player,
                            })
                        else:
                            result.append({
                                "type": "error",
                                "player": player,
                                "old_player": old_player,
                            })
        return result
    
    # 群组数据操作
    async def get_parent_data(self) -> Dict[str, str]:
        """获取群组数据"""
        return await self.star.get_kv_data("parent_data", {})
    
    async def save_parent_data(self, data: Dict[str, str]):
        """保存群组数据"""
        await self.star.put_kv_data("parent_data", data)
    
    async def update_parent(self, parent_id: str, name: str):
        """更新群组信息"""
        data = await self.get_parent_data()
        data[parent_id] = name
        await self.save_parent_data(data)
    
    async def get_parent(self, parent_id: str) -> Tuple[Image.Image, str]:
        """获取群组信息"""
        data = await self.get_parent_data()
        # 默认头像路径
        default_avatar = Image.open(Path(__file__).parent / "res/unknown_avatar.jpg")
        if parent_id not in data:
            return default_avatar, parent_id
        return default_avatar, data[parent_id]
    
    # 禁用播报数据操作
    async def get_disabled_parents(self) -> List[str]:
        """获取禁用播报的群组"""
        return await self.star.get_kv_data("disabled_parents", [])
    
    async def save_disabled_parents(self, data: List[str]):
        """保存禁用播报的群组"""
        await self.star.put_kv_data("disabled_parents", data)
    
    async def disable_parent(self, parent_id: str):
        """禁用群组播报"""
        data = await self.get_disabled_parents()
        if parent_id not in data:
            data.append(parent_id)
            await self.save_disabled_parents(data)
    
    async def enable_parent(self, parent_id: str):
        """启用群组播报"""
        data = await self.get_disabled_parents()
        if parent_id in data:
            data.remove(parent_id)
            await self.save_disabled_parents(data)
    
    async def is_parent_disabled(self, parent_id: str) -> bool:
        """检查群组是否禁用播报"""
        data = await self.get_disabled_parents()
        return parent_id in data
