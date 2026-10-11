# 第五周交付物

本周主题为“AI Agent 工程实践”，系统定位仍为技术博客，不把文章中介绍的 Agent 能力当作博客已实现的功能。

| 文件 | 用途 |
| --- | --- |
| `AI Agent工程实践-软件数据模型设计说明书.docx` | 按课程模板编制的数据模型说明书，含 ER 图片、11 个业务模型的字段字典、关联及约束分析 |
| `第五周计划与组会记录.md` | 10 月 9 日线下组会信息、工作安排及截至 10 月 11 日的会后进度 |
| `第五周集成验收记录.md` | 六名成员的提交覆盖、审校内容、实际验收结果与发布边界 |
| `assets/` | 嵌入说明书的 ER 图原图 |
| `tools/inspect_models.py` | 只读核对 Django 模型及迁移字段，不修改业务数据 |
| `tools/build_data_document.py` | 根据课程模板与模型元数据生成说明书和图示 |
| `tools/run_acceptance.py` | 使用内存测试库及本地替代服务运行本周相关的隔离回归，不连接业务 MySQL |

## 生成与复核

模板默认位于仓库上一级目录：`文档模板-软件数据模型设计说明书模板.docx`。在仓库根目录执行（PowerShell）：

```powershell
# 数据库连接信息沿用本机环境设置，不要把密码写入脚本或提交。
$env:PYTHONUTF8 = '1'
.\src\DjangoBlog\.venv\Scripts\python.exe .\doc\week5\tools\inspect_models.py |
    python .\doc\week5\tools\build_data_document.py --metadata-stdin
```

生成器所用 Python 需安装 `python-docx` 和 Pillow；上述第二个 `python` 可替换成自己的文档工具解释器路径。编制者使用文档工具提供的 Python，业务模型检查使用仓库 `.venv`。模型检查会初始化 Django，需满足项目设置中的本机依赖；它不执行迁移或读写业务记录。生成器发现模型与迁移字段类型不一致时会停止，提醒先核查代码，而不是静默生成不一致的说明书。

正式 DOCX 已做页面渲染和逐页检查，临时 PDF 与页面截图不属于仓库交付物。第四周目录中的数据模型初稿仅作历史留存，第五周以本目录说明书为准。

隔离回归检查在仓库根目录执行：

```powershell
.\src\DjangoBlog\.venv\Scripts\python.exe -B .\doc\week5\tools\run_acceptance.py
```

该命令使用 SQLite 内存库、进程内缓存、内存邮件后端和简化搜索后端；禁用 Cloudflare 插件及外部 HTTP 请求，不更改项目正式配置。它不等同于生产 MySQL、真实搜索服务或邮件服务的端到端验收。前端测试和构建命令见验收记录。

## 提交流程

六名成员的个人提交现已齐备，本轮修正及技术验收记录由组长在 `szx_branch` 汇总，按已授权流程先合入 `develop`，再统一合入 `main`，保留各成员原始提交。课程中的 `master` 对应本仓库的 `main`。文件放入本地目录不等于已经完成远程提交，最终需在远程 `main/doc/week5` 核对成果及 GitHub 合并记录。
