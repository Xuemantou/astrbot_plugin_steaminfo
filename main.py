import asyncio
import time
from pathlib import Path
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Image, Plain
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .config import SteamConfig
from .data_source import SteamDataStore
from .steam import get_steam_id, get_user_data, get_steam_users_info, STEAM_ID_OFFSET
from .draw import check_font, set_font_paths, draw_friends_status, draw_player_status, draw_start_gaming, vertically_concatenate_images
from .utils import fetch_avatar, image_to_bytes, simplize_steam_player_data, convert_player_name_to_nickname


@register("astrbot_plugin_steaminfo", "Xuemantou", "播报绑定的 Steam 好友状态，支持查看Steam主页、好友状态等", "1.0.0")
class SteamInfoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = SteamConfig(config)
        self.data_store = SteamDataStore(self)
        self.plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_steaminfo"
        self.plugin_data_path.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.plugin_data_path / "cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)
        
        # 设置字体路径
        set_font_paths(
            self.config.steam_font_regular_path,
            self.config.steam_font_light_path,
            self.config.steam_font_bold_path,
        )
        
        # 初始化定时任务
        self.scheduler_task = None
    
    async def initialize(self):
        """插件初始化"""
        try:
            check_font()
        except FileNotFoundError as e:
            logger.error(f"{e}, 字体文件缺失，请检查配置")
        
        # 启动定时任务
        if not self.config.steam_disable_broadcast_on_startup:
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Steam播报定时任务已启动")
    
    async def terminate(self):
        """插件销毁"""
        if self.scheduler_task:
            self.scheduler_task.cancel()
            logger.info("Steam播报定时任务已停止")
    
    async def _scheduler_loop(self):
        """定时任务循环"""
        while True:
            try:
                await self._update_and_broadcast()
            except Exception as e:
                logger.error(f"定时任务执行失败: {e}")
            await asyncio.sleep(self.config.steam_request_interval)
    
    async def _update_and_broadcast(self):
        """更新Steam状态并播报"""
        try:
            # 获取所有Steam ID
            steam_ids = await self.data_store.get_all_steam_ids()
            if not steam_ids:
                logger.debug("没有绑定的Steam ID，跳过更新")
                return
            
            logger.info(f"开始更新Steam状态，共 {len(steam_ids)} 个Steam ID")
            
            # 获取Steam用户信息
            steam_info = await get_steam_users_info(
                steam_ids, self.config.steam_api_key, self.config.proxy
            )
            
            players = steam_info.get("response", {}).get("players", [])
            if not players:
                logger.warning("Steam API 返回空的玩家列表")
                return
            
            logger.info(f"从 Steam API 获取到 {len(players)} 个玩家信息")
            
            # 获取旧数据用于比较
            old_players_dict = {}
            bind_data = await self.data_store.get_bind_data()
            for parent_id in bind_data.keys():
                parent_steam_ids = await self.data_store.get_all_binds(parent_id)
                old_players_dict[parent_id] = await self.data_store.get_players_by_steam_ids(parent_steam_ids)
            
            # 更新数据
            await self.data_store.update_steam_info_by_players(players)
            
            # 获取 unified_msg_origin 映射
            umo_dict = await self.data_store.get_unified_msg_origins()
            logger.debug(f"unified_msg_origin 映射: {umo_dict}")
            
            # 播报
            for parent_id in bind_data.keys():
                if await self.data_store.is_parent_disabled(parent_id):
                    logger.debug(f"群组 {parent_id} 已禁用播报，跳过")
                    continue
                
                # 获取 unified_msg_origin
                unified_msg_origin = umo_dict.get(parent_id)
                if not unified_msg_origin:
                    logger.warning(f"跳过播报 {parent_id}: 缺少 unified_msg_origin，请让用户重新绑定 Steam ID")
                    continue
                
                old_players = old_players_dict.get(parent_id, [])
                new_players = await self.data_store.get_players_by_steam_ids(
                    await self.data_store.get_all_binds(parent_id)
                )
                
                logger.debug(f"群组 {parent_id}: 旧数据 {len(old_players)} 条，新数据 {len(new_players)} 条")
                
                await self._broadcast_steam_info(unified_msg_origin, parent_id, old_players, new_players)
                
        except Exception as e:
            logger.error(f"更新Steam状态失败: {e}")
    
    async def _broadcast_steam_info(self, unified_msg_origin: str, parent_id: str, old_players: list, new_players: list):
        """播报Steam状态变化
        
        Args:
            unified_msg_origin: 完整的会话标识，用于发送消息
            parent_id: 群组 ID，用于获取绑定数据
            old_players: 旧的玩家数据
            new_players: 新的玩家数据
        """
        try:
            play_data = await self.data_store.compare_players(old_players, new_players)
            
            if not play_data:
                logger.debug(f"群组 {parent_id}: 没有状态变化")
                return
            
            logger.info(f"群组 {parent_id}: 检测到 {len(play_data)} 个状态变化")
            
            msg = []
            for entry in play_data:
                player = entry["player"]
                old_player = entry.get("old_player")
                
                if entry["type"] == "start":
                    msg.append(f"{player['personaname']} 开始玩 {player['gameextrainfo']} 了")
                elif entry["type"] in ["stop", "change"]:
                    time_start = old_player.get("game_start_time")
                    time_stop = time.time()
                    hours = int((time_stop - time_start) / 3600)
                    minutes = int((time_stop - time_start) % 3600 / 60)
                    time_str = (
                        f"{hours} 小时 {minutes} 分钟" if hours > 0 else f"{minutes} 分钟"
                    )
                    
                    if entry["type"] == "change":
                        msg.append(
                            f"{player['personaname']} 玩了 {time_str} {old_player['gameextrainfo']} 后，开始玩 {player['gameextrainfo']} 了"
                        )
                    else:
                        msg.append(
                            f"{player['personaname']} 玩了 {time_str} {old_player['gameextrainfo']} 后不玩了"
                        )
            
            if not msg:
                logger.debug(f"群组 {parent_id}: 没有需要播报的消息")
                return
            
            logger.info(f"群组 {parent_id}: 准备播报 {len(msg)} 条消息")
            
            # 根据播报类型生成消息
            if self.config.steam_broadcast_type == "all":
                steam_status_data = [
                    await convert_player_name_to_nickname(
                        await simplize_steam_player_data(player, self.config.proxy, self.cache_path),
                        parent_id,
                        self.data_store,
                    )
                    for player in new_players
                ]
                
                parent_avatar, parent_name = await self.data_store.get_parent(parent_id)
                image = draw_friends_status(parent_avatar, parent_name, steam_status_data)
                
                chain = [Plain("\n".join(msg)), Image.fromBytes(image_to_bytes(image))]
                await self.context.send_message(unified_msg_origin, MessageChain(chain=chain))
                logger.info(f"群组 {parent_id}: 播报完成（全部模式）")
                
            elif self.config.steam_broadcast_type == "part":
                images = []
                for entry in play_data:
                    if entry["type"] == "start":
                        bind_info = await self.data_store.get_bind_by_steam_id(parent_id, entry["player"]["steamid"])
                        nickname = bind_info.get("nickname") if bind_info else None
                        avatar = await fetch_avatar(entry["player"], self.cache_path, self.config.proxy)
                        image = draw_start_gaming(
                            avatar,
                            entry["player"]["personaname"],
                            entry["player"]["gameextrainfo"],
                            nickname,
                        )
                        images.append(image)
                
                if images:
                    if len(images) > 1:
                        image = vertically_concatenate_images(images)
                    else:
                        image = images[0]
                    chain = [Plain("\n".join(msg)), Image.fromBytes(image_to_bytes(image))]
                else:
                    chain = [Plain("\n".join(msg))]
                
                await self.context.send_message(unified_msg_origin, MessageChain(chain=chain))
                logger.info(f"群组 {parent_id}: 播报完成（部分模式）")
                
            elif self.config.steam_broadcast_type == "none":
                chain = [Plain("\n".join(msg))]
                await self.context.send_message(unified_msg_origin, MessageChain(chain=chain))
                logger.info(f"群组 {parent_id}: 播报完成（仅文字模式）")
                
        except Exception as e:
            logger.error(f"播报Steam状态失败: {e}")
    
    # 命令处理器
    @filter.command("steamhelp")
    async def steam_help(self, event: AstrMessageEvent):
        """查看Steam插件帮助"""
        help_text = """
Steam Info 插件帮助：
steamhelp: 查看帮助
steambind [Steam ID 或 Steam好友代码]: 绑定Steam ID
steamunbind: 解绑Steam ID
steaminfo: 查看自己的Steam主页
steaminfo @某人: 查看被@用户的Steam主页
steaminfo [Steam ID 或好友代码]: 通过ID查看Steam主页
steamcheck: 查看Steam好友状态
steamenable: 启用Steam播报
steamdisable: 禁用Steam播报
steamnickname [昵称]: 设置玩家昵称
        """.strip()
        yield event.plain_result(help_text)
    
    @filter.command("steambind")
    async def steam_bind(self, event: AstrMessageEvent, steam_id_or_code: str):
        """绑定Steam ID"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        user_id = event.get_sender_id()
        
        if not steam_id_or_code.isdigit():
            yield event.plain_result("请输入正确的 Steam ID 或 Steam好友代码，格式: steambind [Steam ID 或 Steam好友代码]")
            return
        
        steam_id = get_steam_id(steam_id_or_code)
        if not steam_id:
            yield event.plain_result("请输入正确的 Steam ID 或 Steam好友代码")
            return
        
        existing_bind = await self.data_store.get_bind(parent_id, user_id)
        if existing_bind:
            existing_bind["steam_id"] = steam_id
            existing_bind["unified_msg_origin"] = event.unified_msg_origin
            await self.data_store.update_bind(parent_id, user_id, existing_bind)
            yield event.plain_result(f"已更新你的 Steam ID 为 {steam_id}")
        else:
            await self.data_store.add_bind(parent_id, {
                "user_id": user_id,
                "steam_id": steam_id,
                "nickname": None,
                "unified_msg_origin": event.unified_msg_origin,
            })
            yield event.plain_result(f"已绑定你的 Steam ID 为 {steam_id}")
    
    @filter.command("steamunbind")
    async def steam_unbind(self, event: AstrMessageEvent):
        """解绑Steam ID"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        user_id = event.get_sender_id()
        
        existing_bind = await self.data_store.get_bind(parent_id, user_id)
        if existing_bind:
            await self.data_store.remove_bind(parent_id, user_id)
            yield event.plain_result("已解绑 Steam ID")
        else:
            yield event.plain_result("未绑定 Steam ID")
    
    @filter.command("steaminfo")
    async def steam_info(self, event: AstrMessageEvent, target: Optional[str] = None):
        """查看Steam信息

        用法：
        - steaminfo: 查看自己的 Steam 信息
        - steaminfo @someone: 查看被 @ 用户的 Steam 信息
        - steaminfo [Steam ID 或好友代码]: 通过 ID 查看 Steam 信息
        """
        parent_id = event.get_group_id() or event.unified_msg_origin

        # 获取 bot 自己的 ID，用于过滤 @bot 的情况
        self_id = event.get_self_id()

        # 从消息链中获取 @某人（排除 @bot 自己）
        message_chain = event.get_messages()
        at_targets = [
            seg for seg in message_chain
            if hasattr(seg, 'qq') and str(seg.qq) != self_id
        ]

        if at_targets:
            # @了其他用户，查询该用户
            target_user_id = str(at_targets[0].qq)
            bind_info = await self.data_store.get_bind(parent_id, target_user_id)
            if not bind_info:
                yield event.plain_result("该用户未绑定 Steam ID")
                return
            steam_id = bind_info["steam_id"]
            steam_friend_code = str(int(steam_id) - STEAM_ID_OFFSET)
        elif target and target.isdigit():
            # 输入了Steam ID或好友代码
            steam_id_input = int(target)
            if steam_id_input < STEAM_ID_OFFSET:
                steam_friend_code = steam_id_input
                steam_id = str(steam_id_input + STEAM_ID_OFFSET)
            else:
                steam_friend_code = steam_id_input - STEAM_ID_OFFSET
                steam_id = str(steam_id_input)
        else:
            # 查看自己的
            bind_info = await self.data_store.get_bind(parent_id, event.get_sender_id())
            if not bind_info:
                yield event.plain_result("未绑定 Steam ID, 请使用 \"steambind [Steam ID 或 Steam好友代码]\" 绑定 Steam ID")
                return
            steam_id = bind_info["steam_id"]
            steam_friend_code = str(int(steam_id) - STEAM_ID_OFFSET)
        
        try:
            player_data = await get_user_data(int(steam_id), self.cache_path, self.config.proxy)
            
            draw_data = [
                {
                    "game_header": game["game_image"],
                    "game_name": game["game_name"],
                    "game_time": f"{game['play_time']} 小时",
                    "last_play_time": game["last_played"],
                    "achievements": game["achievements"],
                    "completed_achievement_number": game.get("completed_achievement_number"),
                    "total_achievement_number": game.get("total_achievement_number"),
                }
                for game in player_data["game_data"]
            ]
            
            image = draw_player_status(
                player_data["background"],
                player_data["avatar"],
                player_data["player_name"],
                str(steam_friend_code),
                player_data["description"],
                player_data["recent_2_week_play_time"],
                draw_data,
            )
            
            yield event.chain_result([Image.fromBytes(image_to_bytes(image))])
            
        except Exception as e:
            logger.error(f"获取Steam信息失败: {e}")
            yield event.plain_result(f"获取Steam信息失败: {e}")
    
    @filter.command("steamcheck")
    async def steam_check(self, event: AstrMessageEvent):
        """查看Steam好友状态"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        
        try:
            steam_ids = await self.data_store.get_all_binds(parent_id)
            if not steam_ids:
                yield event.plain_result("当前群组没有绑定的Steam用户")
                return
            
            steam_info = await get_steam_users_info(
                steam_ids, self.config.steam_api_key, self.config.proxy
            )
            
            if not steam_info.get("response", {}).get("players"):
                yield event.plain_result("连接 Steam API 失败，请重试")
                return
            
            steam_status_data = [
                await convert_player_name_to_nickname(
                    await simplize_steam_player_data(player, self.config.proxy, self.cache_path),
                    parent_id,
                    self.data_store,
                )
                for player in steam_info["response"]["players"]
            ]
            
            parent_avatar, parent_name = await self.data_store.get_parent(parent_id)
            image = draw_friends_status(parent_avatar, parent_name, steam_status_data)
            
            yield event.chain_result([Image.fromBytes(image_to_bytes(image))])
            
        except Exception as e:
            logger.error(f"查看Steam好友状态失败: {e}")
            yield event.plain_result(f"查看Steam好友状态失败: {e}")
    
    @filter.command("steamenable")
    async def steam_enable(self, event: AstrMessageEvent):
        """启用Steam播报"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        await self.data_store.enable_parent(parent_id)
        yield event.plain_result("已启用 Steam 播报")
    
    @filter.command("steamdisable")
    async def steam_disable(self, event: AstrMessageEvent):
        """禁用Steam播报"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        await self.data_store.disable_parent(parent_id)
        yield event.plain_result("已禁用 Steam 播报")
    
    @filter.command("steamnickname")
    async def steam_nickname(self, event: AstrMessageEvent, nickname: str):
        """设置玩家昵称"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        user_id = event.get_sender_id()
        
        if not nickname:
            yield event.plain_result("请输入昵称，格式: steamnickname [昵称]")
            return
        
        bind_info = await self.data_store.get_bind(parent_id, user_id)
        if not bind_info:
            yield event.plain_result("未绑定 Steam ID，请先使用 steambind 绑定 Steam ID 后再设置昵称")
            return
        
        bind_info["nickname"] = nickname
        await self.data_store.update_bind(parent_id, user_id, bind_info)
        
        yield event.plain_result(f"已设置你的昵称为 {nickname}，将在 Steam 播报中显示")
    
    @filter.command("steamdebug")
    async def steam_debug(self, event: AstrMessageEvent):
        """调试命令：显示当前绑定数据和状态"""
        parent_id = event.get_group_id() or event.unified_msg_origin
        
        try:
            # 获取绑定数据
            bind_data = await self.data_store.get_bind_data()
            parent_binds = bind_data.get(parent_id, [])
            
            # 获取 unified_msg_origin
            umo_dict = await self.data_store.get_unified_msg_origins()
            
            # 获取禁用状态
            is_disabled = await self.data_store.is_parent_disabled(parent_id)
            
            # 获取 Steam 信息数据
            steam_info_data = await self.data_store.get_steam_info_data()
            
            debug_info = f"""调试信息：
群组 ID: {parent_id}
unified_msg_origin: {umo_dict.get(parent_id, '未设置')}
播报禁用: {is_disabled}
绑定用户数: {len(parent_binds)}
Steam 信息数据数: {len(steam_info_data)}

绑定用户列表:"""
            
            for bind in parent_binds:
                debug_info += f"""
- 用户 {bind.get('user_id')}: Steam ID {bind.get('steam_id')}, 昵称 {bind.get('nickname')}, UMO {bind.get('unified_msg_origin', '未设置')}"""
            
            yield event.plain_result(debug_info)
            
        except Exception as e:
            logger.error(f"获取调试信息失败: {e}")
            yield event.plain_result(f"获取调试信息失败: {e}")
