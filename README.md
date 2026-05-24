# AstrBot-Plugin-Steam-Info

✨ Steam 好友状态播报 AstrBot 插件 ✨

## 介绍

这是一个基于 AstrBot 的 Steam 好友状态播报插件，拥有绑定 Steam ID，查询群友状态，展示个人 Steam 主页等功能，支持跨平台，画图部分 100% 使用 Pillow 实现，较无头浏览器渲染更加轻量高效。

本插件从 [nonebot-plugin-steam-info](https://github.com/zhaomaoniu/nonebot-plugin-steam-info) 移植而来。

## 功能

- [x] 绑定 Steam ID
- [x] 群友状态变更播报
- [x] 群友游戏时间播报
- [x] 主动查询群友状态
- [x] 展示个人 Steam 主页
- [x] 设置玩家昵称
- [x] 启用/禁用播报

## 预览

仿照了 Steam 好友列表的样式

图 1. 全部播报
![全部播报](https://raw.githubusercontent.com/zhaomaoniu/nonebot-plugin-steam-info/main/preview.png)

图 2. 部分播报
![部分播报](https://raw.githubusercontent.com/zhaomaoniu/nonebot-plugin-steam-info/main/preview_1.png)

图 3. 个人 Steam 主页
![个人主页](https://raw.githubusercontent.com/zhaomaoniu/nonebot-plugin-steam-info/main/preview_2.png)

## 安装方法

### 方式一：通过 AstrBot WebUI 安装

1. 打开 AstrBot WebUI
2. 进入 插件管理 页面
3. 点击 安装插件
4. 输入插件仓库地址：`https://github.com/Xuemantou/astrbot_plugin_steaminfo`
5. 点击安装

### 方式二：手动安装

1. 克隆本仓库到 AstrBot 的插件目录：

```bash
cd AstrBot/data/plugins
git clone https://github.com/Xuemantou/astrbot_plugin_steaminfo.git
```

2. 安装依赖：

```bash
cd astrbot_plugin_steaminfo
pip install -r requirements.txt
```

3. 重启 AstrBot

## 配置

在 AstrBot WebUI 的插件管理页面中，找到 Steam Info 插件，点击设置进行配置。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| Steam API密钥 | 无 | Steam API Key，支持多个（用逗号分隔），在 [此处](https://steamcommunity.com/dev/apikey) 获取 |
| 代理服务器地址 | 无 | 代理地址，格式: `http://127.0.0.1:7890` |
| 请求间隔 | 300 | Steam API 请求间隔和播报间隔，单位为秒 |
| 播报类型 | `part` | `all` 为全部播报，`part` 为部分播报，`none` 为仅文字 |
| 启动时禁用播报 | `false` | Bot 启动时是否禁用播报 |
| 常规字体路径 | `fonts/MiSans-Regular.ttf` | Regular 字体相对目录 |
| 细体字体路径 | `fonts/MiSans-Light.ttf` | Light 字体相对目录 |
| 粗体字体路径 | `fonts/MiSans-Bold.ttf` | Bold 字体相对目录 |

## 使用

| 命令 | 说明 |
| --- | --- |
| `steamhelp` | 查看帮助 |
| `steambind [Steam ID 或 Steam好友代码]` | 绑定 Steam ID |
| `steamunbind` | 解绑 Steam ID |
| `steaminfo (可选)[@某人 或 Steam ID 或 Steam好友代码]` | 查看 Steam 主页 |
| `steamcheck` | 查询群友 Steam 状态 |
| `steamenable` | 启用群友状态播报 |
| `steamdisable` | 禁用群友状态播报 |
| `steamnickname [昵称]` | 设置玩家昵称，用于辨识 Steam 名称与群昵称不一致的群友 |

## 项目结构

```
astrbot_plugin_steaminfo/
├── main.py              # 主插件类
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # 配置模式
├── requirements.txt     # 依赖
├── config.py            # 配置管理
├── data_source.py       # 数据存储
├── steam.py             # Steam API 调用
├── draw.py              # 图片生成
├── utils.py             # 工具函数
├── models.py            # 数据模型
├── fonts/               # 字体文件
│   ├── MiSans-Regular.ttf
│   ├── MiSans-Light.ttf
│   └── MiSans-Bold.ttf
└── res/                 # 图片资源
```

## 字体说明

本插件使用了 [MiSans](https://hyperos.mi.com/font/zh/) 字体。如果你希望使用其他字体，请在配置中修改字体路径。

## 注意事项

1. 需要先在 [Steam Web API](https://steamcommunity.com/dev/apikey) 获取 API Key
2. 如果需要访问 Steam 社区，可能需要配置代理
3. 插件数据存储在 AstrBot 的数据目录中，不会因为插件更新而丢失

## 致谢

- [nonebot-plugin-steam-info](https://github.com/zhaomaoniu/nonebot-plugin-steam-info) - 原版 NoneBot 插件
- [MiSans](https://hyperos.mi.com/font/zh/) - 字体

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](./LICENSE) 文件。
