# 第七、八周个人任务单｜喻飞扬 YFY｜accounts

## 1. 身份、范围与交付目标

- 姓名：喻飞扬；学号：2415304347；个人分支：`yfy_branch`。
- 仓库：`E:\软件工程方法学\class-3-group-6`；代码根：`src/DjangoBlog`。
- 本人独立主评 Django App：`accounts`，已列入 `djangoblog/settings.py` 的 `INSTALLED_APPS`。
- 目标：完成账号模块阅读与本人署名注释，形成可核查的人工质量分析、工具扫描及至少一项合适改进。
- 本单按“第七周建立基线和分析 → 第八周改进、验证和复扫”执行；具体截止时间按组长通知。
- 只主评 `accounts`；OAuth、公共认证基类、邮件信号和页面组件可追踪调用，不计作本人另选 App。
- 跨 App 修改先与对应 owner 协作：`oauth` 为 GZX，`djangoblog` 为 GCY，`blog` 为 SZX。
- 同伴复核搭档：GZX 顾梓鑫；双方互审，YFY 也要复核其 `oauth` 材料。

## 2. 文件清单与阅读范围

以下路径均相对于 `src/DjangoBlog`；核心文件逐个阅读，不只挑已有注释最多的文件。

| 分组 | 文件 | 阅读、分析重点 |
|---|---|---|
| 核心入口 | `accounts/urls.py` | 路由名、视图绑定和项目实际命名空间 |
| 核心控制 | `accounts/views.py` | 注册/激活、登录/退出、验证码与密码重设 |
| 核心校验 | `accounts/forms.py` | 密码、重复邮箱、邮箱存在性及验证码校验 |
| 核心模型 | `accounts/models.py` | `BlogUser` 对 `AbstractUser` 的扩展、默认值及链接 |
| 核心认证 | `accounts/user_login_backend.py` | 用户名/邮箱查询、密码验证与用户恢复 |
| 核心工具 | `accounts/utils.py` | 验证码缓存键、300 秒 TTL、验证及发信入口 |
| 后台支持 | `accounts/admin.py` | 用户新增/修改表单、自定义字段与后台约束 |
| 注册配置 | `accounts/apps.py` | AppConfig；简单配置不强行堆叠块注释 |
| 已有测试 | `accounts/tests.py`、`accounts/test_user_business_logic.py` | 账号业务、密码和验证码已有覆盖及盲点 |
| 已有测试 | `accounts/test_login_page.py`、`accounts/test_account_pages.py`、`accounts/test_admin.py` | 登录/账户页面、后台新增用户回归 |
| 初始化 | `accounts/__init__.py`、`accounts/templatetags/__init__.py` | 阅读用途；空文件不强行制造业务说明 |
| 数据演进 | `accounts/migrations/0001_initial.py`、`0002_alter_bloguser_options_remove_bloguser_created_time_and_more.py`、`__init__.py` | 对照当前模型；不为统计重写历史迁移 |

跨边界只读线索：`djangoblog/urls.py`、`base_views.py`、`settings.py`、`utils.py`、`blog_signals.py`；`templates/account/`；`oauth/views.py`。
模板和公共辅助代码用于验证输入输出，不纳入本人 `accounts` 注释量和扫描结果的分母。

## 3. 三条源码调用阅读路线

1. 注册激活：`accounts/urls.py` → `RegisterView` → `RegisterForm` / `BlogUser` → `send_email` / 邮件信号 → `account_result`。
   对照项目 namespace、未激活状态、签名、重复邮箱与失败跳转，画出真实成功/失败分支。
2. 登录会话：`LoginView.get_form_kwargs` → `LoginForm(AuthenticationForm)` → `EmailOrUsernameModelBackend.authenticate` → `auth.login` → Session/Cookie → `LogoutView`。
   区分表单的激活检查、认证后端的职责，以及 `logged_user` 标记与真实会话凭证。
3. 密码恢复：`ForgetPasswordEmailCode` → `ForgetPasswordCodeForm` → `generate_code` / `set_code` → `ForgetPasswordForm` → `utils.verify` → `make_password` / 用户保存。
   逐项核实有效期、错误输入、重试、成功后验证码生命周期与邮件失败反馈。

## 4. 第七周：建立基线、阅读标注与人工分析

1. 在本人分支同步最新 `develop`，先检查本地未提交文件，记录开始时的提交 SHA 和环境；冲突联系组长处理。
2. 先保留未改动基线，再进行注释和代码改进，避免只有“改完后的扫描”。
3. 按文件清单逐个阅读，在有意义的位置新增本人注释，统一使用 `# YFY：`。
4. 模块层：文件职责、输入输出、外部依赖、与其他 App 的边界；可以用连续多行本人注释。
5. 函数/类层：关键入口的目的、前置条件、返回值和失败路径；不只翻译函数名。
6. 核心块层：说明认证、重定向检查、密码哈希、验证码 TTL 等分支“为何这样处理”和实际边界。
7. 如某函数很短且含义明确，不逐行解释赋值；注释必须与当前源码一致。
8. 保留原有 YFY、其他成员和项目原作者的注释；不得改署名、复制旧内容冒充本轮新增。
9. 对发现不准确的旧注释，以修订说明记录原位置与依据；不得把历史贡献全部计入本轮工作量。
10. 建立 `注释统计.md`：逐文件记录基线已有本人注释行、本轮新增本人注释行、修订/删除数及覆盖层次。
11. 统计以基线 SHA 到当前补丁的实际新增物理注释行为准；只改缩进、搬移或重复粘贴不算新增学习标注。
12. 对测试、配置和迁移按实际改动分组统计；没有改动的文件明确记 0，不制造统一数字。

人工质量分析至少记录 6 条有源码依据的观察，覆盖以下四个方面，并同时包含正例和问题。

| 方面 | 本模块可观察内容 | 每条必须提供 |
|---|---|---|
| 编码风格 | 命名、导入、异常处理、重复校验、注释准确性 | 文件/符号、片段或行号、对可读性的影响 |
| 设计 | 视图/表单/认证后端分工、公共基类、会话与邮件边界 | 调用关系、设计取舍及维护影响 |
| 技能正例 | 密码哈希、表单复用、同站重定向检查等候选 | 核实后的实现证据与适用条件 |
| 缺陷/风险 | 输入异常、状态策略、验证码生命周期等候选 | 触发输入、实际/预期、严重程度与验证方法 |

第六周 UC04—UC06 仅作待核实线索：注册结果反向路由、验证码消费/限流、认证后端空用户名处理、激活状态策略。
必须重新核对当前分支，并用最小复现确认；不得直接写成“本周已经评估”或“已经修复”。

## 5. 真实扫描：基线 → 核实 → 改进 → 验证 → 复扫

- 统一工具：Ruff `0.17.1` 与 Bandit `1.9.4`；工具配置及驱动都位于 `doc/week7-8/tools/`。
- Ruff 使用 E/F/I/B/C90、100 字符行长、圈复杂度阈值 10；Bandit 全规则且 `--ignore-nosec`，不能用新增忽略标记掩盖问题。
- 驱动只静态读取所选 App，不导入或启动 Django；业务 Python（含 commands、模板标签、初始化入口）纳入扫描。
- 统一排除 `migrations/`、`test*.py` 和 `tests/`，测试与迁移仍须人工阅读并在规模统计中单列。
- 课件中的 SonarQube IDE、Gitee 等可补充，但不能替代真实基线与复扫，也不代表本机已经安装。
- 在组长确认的独立工具环境中，从仓库根 `E:\软件工程方法学\class-3-group-6` 执行：

```powershell
python -m pip install -r doc/week7-8/tools/requirements-quality.txt
python doc/week7-8/tools/scan_app.py accounts baseline
# 完成至少一项合适改进及必要验证后，以同一环境和配置执行：
python doc/week7-8/tools/scan_app.py accounts after
```

- 驱动自动保存到 `doc/week7-8/成员成果/YFY/原始工具结果/baseline/` 与 `after/`，每轮有 `ruff.json`、`bandit.json`、`manifest.json`。
- `manifest.json` 包含 SHA、版本、配置哈希、逐文件规模、排除清单、实际命令和退出码；保留原始文件，人工结论另写。
- 已有证据目录会拒绝覆盖；不要为重跑删除旧基线，先向组长说明并约定新一轮证据保存方式。
- `工具与验证记录.md` 补充环境、扫描开始时工作区状态及实际输出；不把“驱动执行完成”写成“零告警”。

1. 先运行 baseline，再逐条核实，分类为确认问题、误报及依据、需环境确认、暂缓及原因。
2. 从确认工具发现或人工问题中至少选一项合适改进；动手前写明范围、风险、预期行为和验收条件。
3. 可优先考察注册反向路由、认证输入或验证码生命周期；是否成立以本人复现和当前源码为准。
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

```powershell
.\src\DjangoBlog\.venv\Scripts\python.exe doc/week7-8/tools/run_isolated_tests.py accounts.test_login_page
```

上述标签对应 `src/DjangoBlog/accounts/test_login_page.py`，后续将本 App 新增的必要回归测试标签一并交给 runner；命令示例不表示测试已通过。
runner 使用 SQLite 内存库、内存缓存与邮箱、Haystack SimpleEngine，移除 Elasticsearch 配置及 cloudflare 缓存插件，阻断 HTTP/套接字外呼，并将评论邮件线程同步执行。
记录实际隔离和 mock、测试数量、stdout/stderr、退出码及 `ISOLATED_TEST_FAILURES`；失败逐项定位，保留原始输出。
该结果用于本地隔离回归，不证明真实 MySQL、Elasticsearch、OAuth 或邮件投递联调完成。

## 6. 第八周交付与同伴复核

本人材料放在 `doc/week7-8/成员成果/YFY/`，直接提交仓库，不打包。

- `质量分析片段.md`：模块概况、业务源码文件/物理行/代码行/类/函数规模（测试迁移单列）、四类观察、证据表、改进前后及剩余问题。
- `工具与验证记录.md`：基线/复扫命令、配置、版本、退出码、工具结果汇总和测试记录。
- `原始工具结果/`：保留 baseline/after 的两种工具 JSON、manifest 和必要日志；敏感值移除需记录脱敏范围。
- `注释统计.md`：逐文件本轮新增行、旧注释保留/修订口径和基线 SHA。
- `改进计划.md`：问题编号、原因、选定方案、实施结果、验证证据与未完成项。
- 同伴复核合入 `工具与验证记录.md`：GZX 的实际复核日期、文件/问题编号、意见、本人处理和复核结论，由复核人确认。

每条证据统一记录：`编号｜文件与符号/当前行号｜基线SHA｜发现方法/规则号｜触发与影响｜处理｜验证命令与结果｜复扫状态`。
请 GZX 重点复核账号激活策略、本站用户与第三方用户关联边界，以及报告是否把候选发现写成既成事实。
交付前核对：核心文件阅读完整、三层注释有实际内容、逐文件新增数可追踪、至少一项改进完成且有必要验证。

## 7. 汇总与 Git 交付

- 将本人的质量分析片段及可复用编码规范建议交组长；个人不单独制造一套与全组冲突的规范。
- 组长依据仓库上一级目录 `E:\软件工程方法学` 中的 `文档模板-开源软件的质量分析报告文档.docx` 和 `文档模板-编码规范.docx` 汇总两份 Word。
- 本人只提交已核对的账号代码、本人证据及材料到 `yfy_branch`，PR 目标为 `develop`，说明改进和真实验证结果。
- 完整流程：`yfy_branch → develop → main`；组长最终集成、复核并合入 `main`，本人不直接提交最终分支。
- 提交前检查差异与暂存清单，不纳入其他成员改动、私钥/密码、本机环境或构建缓存；截止时间以组长通知为准。
