# astrbot_plugin_yysls

AstrBot 的燕云十六声排行榜插件。当前只提供最新活动周期的四榜图片。

## 指令

- `/燕云`：查看插件帮助
- `/排行榜`：获取两个当前副本的普通、挑战四个实时排行榜，每榜显示前 10 名

数据来自 [燕云十六声排行榜](https://yysls.rubysiu.cn/yysls/rank)，接口异常时插件会返回简短错误信息。

## 安装

将仓库放入 AstrBot 的 `data/plugins/astrbot_plugin_yysls`，安装依赖并重启 AstrBot：

```bash
pip install -r data/plugins/astrbot_plugin_yysls/requirements.txt
```

要求 AstrBot 4.16.0 或更高版本。

