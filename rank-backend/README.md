# 燕云排行榜更新工具

从燕云公开排行榜接口抓取完整榜单，生成 AstrBot 插件使用的稳定 JSON 快照。
快照写入采用临时文件替换，不会让 Bot 读到半份数据。

## 当前第 2 期

| 榜单 | rank_name |
| --- | --- |
| 五人挑战 | `rank_team_dungeon_60` |
| 五人普通 | `rank_team_dungeon_63` |
| 十人挑战 | `rank_team10_dungeon_59` |
| 十人普通 | `rank_team10_dungeon_62` |

编号、期数和副本名统一配置在 [`ranks.json`](ranks.json)：

```json
{
  "periodOrder": 2,
  "five": {
    "dungeonName": "沧流走虺",
    "normalRankId": 63,
    "challengeRankId": 60
  },
  "ten": {
    "dungeonName": "风翎掠寒江",
    "normalRankId": 62,
    "challengeRankId": 59
  }
}
```

第 1 期对应值为：五挑 59、五普 62、十挑 58、十普 61。切换期数时只需修改
`ranks.json`；更新器每轮都会重新读取，无需重启 AstrBot。配置格式或编号无效时本轮
更新失败，并保留上一份完整快照。

## 初始化

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

抓取当前四榜并更新插件快照：

```powershell
.\.venv\Scripts\python.exe .\update_current_snapshot.py
```

默认输出到插件目录的 `data/current-ranks.json`。一次完整抓取约 125 个分页请求；
当前数据量为十人榜各 500 队、五人榜各 750 队。

`start-rank-updater.ps1` 每 5 分钟执行一轮，失败时保留上一份完整快照。当前机器通过
`Yanyun Rank Updater` 开机任务运行该脚本。

## 完整导出

原命令保持兼容，可导出原始分页、队员信息、JSON 和 CSV：

```powershell
.\.venv\Scripts\python.exe .\fetch_complete_yysls_ranks.py `
  --rank rank_team_dungeon_60 `
  --rank rank_team10_dungeon_59
```
