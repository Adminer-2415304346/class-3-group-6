# 第七、八周个人任务单｜王子扬 WZY｜comments（修订版）

> 修订说明（2026-10-30，基于对本机真实仓库的核查）：
> 1. 仓库根路径由 `E:\软件工程方法学\class-3-group-6` 改为真实存在的 `E:\git\Git小组作业\class-3-group-6`（原路径在本机不存在）。
> 2. §5 隔离命令的 `.\src\DjangoBlog\.venv\Scripts\python.exe` 在本机不存在；实际可用且与已产证据（python 3.11.9）一致的解释器是 `py -3.11`（`C:\Users\wang0\AppData\Local\Programs\Python\Python311\python.exe`）。注意：该解释器已装 ruff 0.17.1 / bandit 1.9.4，但**未装 django / haystack**，所以 `run_isolated_tests.py` 需先搭建一个含项目依赖的隔离 venv 才能跑。
> 3. §7 引用的模板目录 `E:\软件工程方法学` 在本机不存在，需向组长确认两份 docx 模板的实际位置。
> 4. 补充：`comments/comments_tags.py`（包根）是一个**空文件**，与 `comments/templatetags/comments_tags.py` 不是同一文件，会被 scan_app 计入 11 个扫描文件，疑似 git 残留/误提交，建议核对后删除或在材料中说明。

## 1. 身份、范围与交付目标

- 姓名：王子扬；学号：2415304348；个人分支：`wzy_branch`。
- 仓库：`E:\git\Git小组作业\class-3-group-6`；代码根：`src/DjangoBlog`。
- 本人独立主评 Django App：`comments`，已列入 `djangoblog/settings.py` 的 `INSTALLED_APPS`。
- 目标：完整阅读评论 App、补充本人学习标注，完成质量分析、真实工具扫描及至少一项经验证的合适改进。
- 按“第七周基线和分析 → 第八周改进、验证、复扫”执行；具体截止日期按组长通知。
- 主评范围只有 `comments`；文章详情、登录保护、邮件信号、前端表情组件作为调用依赖追踪。
- 跨 App 修改由对应 owner 协作：`blog` 为 SZX，`accounts` 为 YFY，`djangoblog` 为 GCY。
- 同伴复核搭档：SY 宋洋；双方互审，WZY 也要复核其 `servermanager` 材料。

## 2. 文件清单与阅读范围

以下路径均相对于 `src/DjangoBlog`；评论提交、表情 API、模板标签和通知工具都要覆盖。

| 分组 | 文件 | 阅读、分析重点 |
|---|---|---|
| 核心入口 | `comments/urls.py` | 评论 POST 与 reaction GET/POST 路由 |
| 核心控制 | `comments/views.py` | 登录要求、正文校验、开关、父评论和反应切换 |
| 核心模型 | `comments/models.py` | 评论关联、公开标记、反应枚举、唯一约束及统计 |
| 核心校验 | `comments/forms.py` | `body` 与隐藏 `parent_comment_id` 的校验边界 |
| 后台支持 | `comments/admin.py` | 评论启停动作与普通保存/批量更新差异 |
| 通知支持 | `comments/utils.py` | 发表评论与回复邮件、异常处理及外部依赖 |
| 模板标签 | `comments/templatetags/comments_tags.py` | 评论树递归、输入集合、标签输出与模板参数 |
| 注册配置 | `comments/apps.py` | AppConfig；短配置不强行堆叠块注释 |
| 已有测试 | `comments/tests.py`、`comments/test_views.py`、`comments/test_comment_business_logic.py` | 提交/审核/回复、视图与模型业务已有覆盖及盲点 |
| 初始化 | `comments/__init__.py`、`comments/templatetags/__init__.py`、`comments/migrations/__init__.py` | 阅读用途；空文件不虚构业务说明 |
| 数据演进 | `comments/migrations/0001_initial.py`、`0002_alter_comment_is_enable.py` | 初始关联与公开标记演进 |
| 数据演进 | `comments/migrations/0003_alter_comment_options_remove_comment_created_time_and_more.py`、`0004_comment_idx_art_parent_enable_comment_idx_enable_id.py`、`0005_commentreaction.py` | 字段变化、索引及表情唯一约束；不为计数重写历史迁移 |

跨边界只读线索：`blog/models.py`、`blog/views.py`、`djangoblog/base_views.py`、`djangoblog/blog_signals.py`、`djangoblog/admin_site.py`。
交互对照：`templates/comments/tags/`、`templates/blog/article_detail.html`、`frontend/src/components/commentSystem.js`、`reactionPicker.js`。
这些共享/前端文件不计入本人 App 注释新增量和扫描分母；需要修订时先协调负责成员。

## 3. 三条源码调用阅读路线

1. 评论回复：`comments/urls.py` → `CommentPostView` → `AuthenticatedFormView` / `CommentForm` → `Article` / `BlogSettings` → `Comment.save`。
   对照正常表单和 HTMX 回复，追踪父 ID、作者来源、文章开关、免审核与需审核分支。
2. 表情互动：`reactionPicker` 的 SSR 数据/GET 降级 → `CommentReactionView.get/post` → `get_or_create` / 删除 → `get_reactions_summary`。
   区分公开读取与登录写入、八种枚举、按三元组唯一，以及统计总数与最多十个用户名列表。
3. 展示通知：文章详情公开评论查询 → 模板/`comments_tags` 递归 → 评论保存信号 → `send_comment_email` → 邮件发送入口。
   再对照 `CommentAdmin` 批量启停，判断它是否触发普通保存同样的信号和缓存行为。

## 4. 第七周：建立基线、本人标注与人工分析

1. 在本人分支同步最新 `develop`，先确认工作区和历史改动，记录开始提交 SHA；遇到冲突联系组长。
2. 先保存未改动扫描基线，再进行注释与改进，确保 before/after 可比。
3. 核心文件逐一阅读，用 `# WZY：` 写本人新增注释，描述真实实现而非理想功能。
4. 模块层：说明评论/表情/通知/模板标签文件的责任、主要输入输出和依赖边界。
5. 函数/类层：解释关键入口的前置条件、校验职责、返回形式和可能失败路径。
6. 核心块层：说明公开标志、审核开关、父评论关联、枚举检查、get_or_create 切换与分组统计等关键判断。
7. 不把每次赋值和 import 都翻译一遍；短配置或空文件按实际内容处理，不强凑三层注释。
8. 保留原有 WZY、其他成员和项目原作者标注，不替换署名、不将旧标注全部当成本轮贡献。
9. 若旧注释错误，记录修订位置和依据；特别避免将 `is_enable=True` 直接写成“已人工审核”。
10. 新建 `注释统计.md`，每文件记录基线已有 WZY 注释行、本轮新增 WZY 注释行、修改/删除数、旧标注修订数及覆盖层次，并附基线 SHA。
11. 本轮新增量按基线 SHA 到当前补丁的实际新增物理注释行计算；搬移、换署名、重复粘贴不算新增。
12. 测试、迁移和核心业务分组统计；未改动文件记 0，统计附差异范围与基线依据。

人工分析至少给出 6 条有证据的观察，四个方面都要有，正例与问题均应覆盖。

| 方面 | 本 App 的观察方向 | 每条必须提供 |
|---|---|---|
| 编码风格 | 重复查询、导入组织、异常反馈、注释准确性 | 文件/符号、片段或行号、维护影响 |
| 设计 | 视图/表单/模型职责、SSR/API 分工、信号与后台动作 | 调用关系、取舍及边界 |
| 技能正例 | 登录和 CSRF 保护、唯一约束、查询预加载等候选 | 核实后的实现依据及适用条件 |
| 缺陷/风险 | 跨文章回复、开关一致性、异常与查询成本等候选 | 最小触发、实际/预期、影响及验证办法 |

第六周 UC07—UC08 只作候选线索：父评论归属、全站关闭后的直接提交、无效父 ID、表情切换语义、批量启停后的缓存。
重新检查当前分支并复现；不要因旧文档提过，就写成已经确认或已经修复的本周成果。

## 5. 真实扫描：基线 → 核实 → 改进 → 验证 → 复扫

- 统一工具：Ruff `0.17.1` 与 Bandit `1.9.4`；工具配置及驱动都位于 `doc/week7-8/tools/`。
- Ruff 使用 E/F/I/B/C90、100 字符行长、圈复杂度阈值 10；Bandit 全规则且 `--ignore-nosec`，不能用新增忽略标记掩盖问题。
- 驱动只静态读取所选 App，不导入或启动 Django；业务 Python（含 commands、模板标签、初始化入口）纳入扫描。
- 统一排除 `migrations/`、`test*.py` 和 `tests/`，测试与迁移仍须人工阅读并在规模统计中单列。
- 课件中的 SonarQube IDE、Gitee 等可补充，但不能替代真实基线与复扫，也不代表本机已经安装。
- 在组长确认的独立工具环境中执行（本机核实：用 `py -3.11`，即 `C:\Users\wang0\AppData\Local\Programs\Python\Python311\python.exe`，与已产证据 python 3.11.9 一致；scan_app.py 会自定位仓库根并在 `src/DjangoBlog` 内以相对路径运行，无需先 cd）：

```powershell
py -3.11 -m pip install -r doc/week7-8/tools/requirements-quality.txt
py -3.11 doc/week7-8/tools/scan_app.py comments baseline
# 完成至少一项合适改进及必要验证后，以同一环境和配置执行：
py -3.11 doc/week7-8/tools/scan_app.py comments after
```

- 驱动自动保存到 `doc/week7-8/成员成果/WZY/原始工具结果/baseline/` 与 `after/`，每轮有 `ruff.json`、`bandit.json`、`manifest.json`。
- `manifest.json` 包含 SHA、版本、配置哈希、逐文件规模、排除清单、实际命令和退出码；保留原始文件，人工结论另写。
- 已有证据目录会拒绝覆盖；不要为重跑删除旧基线，先向组长说明并约定新一轮证据保存方式。
- 工具与验证记录.md 补充环境、扫描开始时工作区状态及实际输出；不把“驱动执行完成”写成“零告警”。

1. 先运行 baseline，再逐条核实，分类为确认问题、误报及依据、需环境确认、暂缓及原因。
2. 从确认工具发现或人工问题中至少选一项合适改进；动手前写明范围、风险、预期行为和验收条件。
3. 可优先考察父评论归属校验、错误反馈或清晰的局部查询改进；是否成立以本人复现和当前源码为准。
4. 修改只主评本人 App；跨边界调整先与对应 owner 协作，记录接口约定和各自改动范围。
5. 保留实际补丁及改进前后证据；注释新增本身不代替一项确认问题的改进。
6. 复用已有测试，对所改行为补必要回归，检查能否暴露改进前的问题。
7. Django 检查与测试必须使用组长确认的隔离配置/runner；本项目启动、插件和保存信号可能外呼，不能直接用正式配置运行。
8. 记录隔离方式、具体测试标签、完整命令、退出码及结果；模拟邮件/禁用插件应写明未覆盖的集成边界。
9. 数据库或依赖不可用时保存真实错误及未验证范围，条件解决后再补跑；查询优化须用相同数据给出查询次数证据。
10. 同范围同配置运行 after，按规则/位置对比新增、消失和保留的问题，解释剩余项和新引入项。
11. 工具发现导致的非零退出、工具启动错误与测试失败分别记录，未实际运行的项目不能写“通过”。

**隔离验证命令（仓库根执行）**

先阅读所选测试的请求、邮件和插件调用，按必要性 mock 外部行为；再指定实际存在的测试标签执行，不能将 runner 默认的 blog 测试当成本人验证。

> 注意：本机没有 `src/DjangoBlog/.venv`，`py -3.11`（Python311）未安装 django/haystack。执行前需先搭建一个含项目依赖（django、haystack 等）的隔离 venv，或用组长确认的解释器替换下面的 `<venv-python>`。

```powershell
<venv-python> doc/week7-8/tools/run_isolated_tests.py comments.test_comment_business_logic
```

上述标签对应 `src/DjangoBlog/comments/test_comment_business_logic.py`，后续将本 App 新增的必要回归测试标签一并交给 runner；命令示例不表示测试已通过。
runner 使用 SQLite 内存库、内存缓存与邮箱、Haystack SimpleEngine，移除 Elasticsearch 配置及 cloudflare 缓存插件，阻断 HTTP/套接字外呼，并将评论邮件线程同步执行。
记录实际隔离和 mock、测试数量、stdout/stderr、退出码及 `ISOLATED_TEST_FAILURES`；失败逐项定位，保留原始输出。
该结果用于本地隔离回归，不证明真实 MySQL、Elasticsearch、OAuth 或邮件投递联调完成。

## 6. 第八周交付与同伴复核

**组长已复现的协作问题**：`CommentAdmin.enable_commentstatus` 使用批量 `update`，不会触发 `post_save`。
当 `blog.Article.comment_list()` 把空集合作为有效缓存复用时，审核首条评论后页面可能持续显示“暂无评论”。
SZX已撤回这项空缓存优化，保留原有空集重查，并增加对应回归；请核对批量审核/关闭/删除时评论缓存、侧栏及页面缓存的失效。
如改失效策略，与SZX、GCY约定键和触发时机后再提交；不直接在blog重复实施被撤回的优化。

个人材料放在 `doc/week7-8/成员成果/WZY/`，直接交仓库目录，不打包。

- `质量分析片段.md`：模块概况、业务源码文件/物理行/代码行/类/函数规模（测试迁移单列）、四类观察、证据表、改进前后及剩余风险。
- `工具与验证记录.md`：两轮工具配置/命令/版本/退出码、结果对比与必要测试记录。
- `原始工具结果/`：保留 baseline/after 的两种工具 JSON、manifest 和必要日志；敏感值移除需说明脱敏范围。
- `注释统计.md`：逐文件本轮新增物理注释行、旧标注修订数及基线 SHA。
- `改进计划.md`：问题编号、原因、方案、实施补丁、验收结果和未完成项。
- 同伴复核合入 `工具与验证记录.md`：SY 的实际复核日期、问题/文件编号、意见、本人处理与复核结论，由复核人确认。

每条证据统一记录：`编号｜文件与符号/当前行号｜基线SHA｜发现方法/规则号｜触发与影响｜处理｜验证命令与结果｜复扫状态`。
请 SY 重点检查：评论展示与后端公开状态是否一致、回复和表情接口输入输出是否对应、统计结论是否有真实证据。
交付前检查：核心文件无遗漏、三层本人注释有内容、每文件新增数有差异依据、至少一项改进和必要验证已完成。

## 7. 汇总与 Git 交付

- 本人提交模块分析片段及可复用的编码规范建议，供组长整理全组结论。
- 组长按组长确认的模板目录（原文档所写 `E:\软件工程方法学` 在本机不存在，需向组长索取）中的 `文档模板-开源软件的质量分析报告文档.docx` 与 `文档模板-编码规范.docx` 汇总两份 Word。
- 将经核对的评论代码、本人材料和证据提交到 `wzy_branch`，PR 目标为 `develop`，写明真实改进与验证结果。
- 流程为 `wzy_branch → develop → main`；组长完成集成和最终合并，本人不直接改最终分支。
- 提交前核对差异和暂存清单，不混入其他成员改动、本机环境、缓存及敏感信息；实际截止时间按组长通知。
