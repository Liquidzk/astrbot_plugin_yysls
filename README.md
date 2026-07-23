# astrbot_plugin_yysls

AstrBot 的燕云十六声排行榜插件。提供最新活动周期的总榜与详细榜图片。

## 指令

- `/燕云`：查看插件帮助
- `/排行榜`：获取两个当前副本的普通、挑战四榜总图
- `/排行榜 五人`：五人普通详细榜
- `/排行榜 五人 挑战`：五人挑战详细榜
- `/排行榜 十人`：十人普通详细榜
- `/排行榜 十人 挑战`：十人挑战详细榜

每个榜单显示前 20 名的名次、队伍和用时；第 21 名以后按连续且相同的用时聚合，例如
`28-32  7:11`。队伍名称最多保留约 12 个汉字的显示空间。

数据来自 [燕云十六声排行榜](https://yysls.rubysiu.cn/yysls/rank)，接口异常时插件会返回简短错误信息。

## 安装

将仓库放入 AstrBot 的 `data/plugins/astrbot_plugin_yysls`，安装依赖并重启 AstrBot：

```bash
pip install -r data/plugins/astrbot_plugin_yysls/requirements.txt
```

要求 AstrBot 4.16.0 或更高版本。
