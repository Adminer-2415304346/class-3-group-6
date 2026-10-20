# 第7—8周个人任务：宋洋（SY）— servermanager

收件人：宋洋，学号2415304330；个人分支：`sy`。
项目根目录：`E:\软件工程方法学\class-3-group-6`；主责app：`src/DjangoBlog/servermanager/`。
截止时间按组长最新通知执行；本任务单不代填开始、完成时间或评估结果。
本文件是任务安排，下面的源码问题都是待核实候选，不表示已经修复。

## 1. 本轮目标和交接边界

- 你独立负责已在`settings.py`的`INSTALLED_APPS`注册的`servermanager`，完成精读注释、人工质量分析、工具评估与至少一项适当改进。
- 六人主责互不重复：SZX—blog、YFY—accounts、WZY—comments、GZX—oauth、GCY—djangoblog、SY—servermanager。
- 你此前的`templates/`和`frontend/`不是`INSTALLED_APPS`中的独立app，本轮不能继续以它们代替个人app任务。
- `servermanager`由顾梓鑫交接；请接收`/robot`入口、消息分发、BlogApi、命令确认与会话存储的旧阅读说明和问题清单。
- GZX仅作交接协助，不保留对servermanager的重复主责；保留其既有署名，不能直接换成SY计入新增。
- `blog`、`djangoblog`及相关模板仅作调用证据；跨app缺陷记录并交对应成员，避免同时覆盖对方文件。
- 不需要打包；源码和个人Markdown交组长汇总，截止以最新通知为准。

## 2. 文件清单与阅读优先级

以下路径均相对`src/DjangoBlog/`，请在个人记录中写清实际阅读和修改范围。

| 分组 | 文件 | 必须理解的内容 |
| --- | --- | --- |
| 核心 | `servermanager/urls.py` | `/robot`由WeRoBot的make_view接管，未走本app普通View |
| 核心 | `servermanager/robot.py` | WeRoBot初始化、过滤器、消息兜底、会话状态和命令确认 |
| 核心 | `servermanager/api/blogapi.py` | Haystack搜索、分类/最新文章查询、返回数量与公开条件 |
| 核心 | `servermanager/api/commonapi.py` | ChatGPT适配、命令列表、命令查找与系统命令调用 |
| 核心 | `servermanager/MemcacheStorage.py` | WeRoBot会话接口、key前缀、JSON与Django缓存 |
| 核心 | `servermanager/models.py` | commands命令配置、EmailSendLog字段和时间戳 |
| 核心 | `servermanager/admin.py` | 命令管理、邮件日志只读及禁止新增的边界 |
| 测试 | `servermanager/tests.py` | 当前测试是否真实调用ChatGPT或系统命令，以及断言有效性 |
| 配置入口 | `servermanager/apps.py`、`servermanager/__init__.py`、`servermanager/api/__init__.py` | app及包入口，不强行为空文件加业务 |
| 占位文件 | `servermanager/views.py` | 当前占位；说明路由实际去robot，不虚构已实现普通视图 |
| 迁移核对 | `servermanager/migrations/0001_initial.py`、`0002_alter_emailsendlog_options_and_more.py`、`__init__.py` | 命令与邮件日志模型演变；只读，勿为扫描改历史迁移 |

关联证据：`blog/models.py`、`djangoblog/urls.py`、`djangoblog/utils.py`、`djangoblog/blog_signals.py`、`djangoblog/settings.py`。
如借助页面或模板理解日志显示，只把它们列为证据，不恢复模板/前端作为第二主责范围。

## 3. 按真实调用完成三条阅读路线

1. 文章查询：项目URLConf → `servermanager.urls` → `make_view(robot)` → `@robot.filter`的`search/category/recents` → BlogApi → 搜索索引/ORM → 文本或ArticlesReply。
   记录关键词转换、最多8条、文章公开条件；`weather/idcard`当前返回建设中，不能写成已实现服务。
2. 消息与命令：`@robot.handler echo` → `MessageHandler` → `WxUserInfo`状态 → 管理员口令核验 → 命令名与Y确认 → `CommandHandler.run` → 系统调用替身。
   说明未认证、失败次数、退出、确认执行和普通聊天分支；阅读时不得实际执行数据库内命令。
3. 存储与日志：robot初始化 → `MemcacheStorage.is_available`及缓存会话；另沿`utils.send_email` → `blog_signals.send_email_signal_handler` → SMTP → `EmailSendLog` → `EmailSendLogAdmin`追溯。
   两条存储链相互独立；servermanager提供邮件日志模型，实际SMTP发送在djangoblog，不要误写职责。

## 4. 三层署名注释要求

- 模块层：在核心文件头说明职责、入口和外部依赖，例如`# SY：本模块接收WeRoBot消息，文章查询、聊天和命令处理走不同分支。`
- 函数/方法层：说明关键输入、返回、失败行为、状态变化与副作用；特殊拼写文件名`MemcacheStorage.py`与类名保持准确。
- 核心代码块/行：解释过滤器、管理员状态、确认步骤、会话序列化、查询条件和日志字段，例如`# SY：管理员状态和口令通过标志分别保存，真正命令执行还需确认。`
- 注释描述当前行为，不能把“支持命令”写成“允许任意用户执行”，也不能把缓存探测写成Redis专用连接检查。
- 原GZX和其他成员标注原样保留；旧标注、移动旧行及修改别人署名都不能计入本轮新增。
- 在`注释统计.md`按文件记录基线提交、模块/函数/核心块新增组数、新增注释行数与行号；多行续行计行数。

## 5. 人工质量分析与候选问题

人工分析至少覆盖四类，每条给出路径/行号、具体行为、影响及核验方法。

| 类别 | 重点观察 | 可引用的正面技能或待核实候选 |
| --- | --- | --- |
| 代码风格 | 类/方法命名、拼写、宽泛异常、重复状态分支 | `commands`类名、提示文字和异常处理可分析，跨层命名改动先核对引用 |
| 设计与技能 | 消息适配、过滤器、API封装、会话接口 | 按正则分发消息、BlogApi封装查询、SessionStorage适配及命令确认可作正面实例 |
| 可靠性与测试 | 初始化副作用、外部接口、超时、断言 | ChatGPT旧式调用与requirements版本兼容性需核实；测试仅非空断言不能证明接口成功 |
| 数据与安全 | 草稿读取、系统命令边界、会话数据、日志 | BlogApi近期/分类查询未显式筛发布态；`os.popen`执行配置命令，需结合鉴权和确认状态分析 |

- `servermanager/tests.py`直接调用`ChatGPT.chat`，并以命令字符串构建CommandHandler测试；运行前必须检查和替换外部/系统副作用。
- `ChatGPT.chat`宽泛捕获后返回固定错误字符串，当前“非空”断言可能把失败当成功；优先考虑明确的隔离成功/失败断言。
- `robot.py`导入阶段实例化BlogApi/CommandHandler、探测缓存并可能选择文件存储，核对导入时查询/文件副作用与测试隔离。
- `MemcacheStorage`实际复用Django配置的缓存，不保证一定是Memcached或Redis；核对默认LocMem下的多进程会话一致性。
- 命令执行、管理员状态与jsonpickle会话反序列化属于需要认真核实的边界；报告不包含实际命令记录、口令或用户消息。
- 优先选择范围小、可证明的改进，例如修复无效测试、收窄异常、清晰的失败分支或减少初始化副作用；不要为清告警重写机器人或擅加危险命令。

## 6. 工具评估与改进闭环

1. 记录基线提交、Python版本、依赖来源与扫描范围；统一使用官方CLI的Ruff 0.17.1与Bandit 1.9.4。
2. SonarQube IDE插件和Gitee整项目扫描是课件示例，可作补充；不表示本机已安装，也不要求同时使用，团队保持可比较口径。
3. 保存改动前`原始工具结果/baseline/`中的`ruff.json`、`bandit.json`、`manifest.json`，不编造分数或完成结论。
4. 人工确认拟处理告警，区分真实缺陷、维护性问题、误报与业务取舍；明确被谁输入、何时触发和有什么影响。
5. 至少完成一项经核实且适合本app范围的质量改进；仅加注释不能代替改进，勿为了数量乱改外部集成。
6. 对实际改进做必要验证，记录触发输入、预期、真实输出和未解决风险；失败或被外部条件阻塞都如实写明。
7. 按相同工具版本、规则、排除项和扫描范围复扫，保留`原始工具结果/after/`中的同名JSON及差异；规则更换不能冒充缺陷减少。
8. 工具结果与人工结论分别呈现；无告警不代表没有缺陷，没有运行过的工具或测试不能写“通过”。

### 统一工具与准确命令

转发任务只需本MD；工具从组长更新后的仓库取得，不要另传或自行修改一套扫描脚本。
使用`doc/week7-8/tools/requirements-quality.txt`、`ruff.toml`、`bandit.yaml`与`scan_app.py`；`python`须指向独立工具环境，勿改项目运行依赖。
从仓库根运行基线：

```powershell
Set-Location 'E:\软件工程方法学\class-3-group-6'
python -m pip install -r doc/week7-8/tools/requirements-quality.txt
python doc/week7-8/tools/scan_app.py servermanager baseline
```

完成改进与必要验证后，同配置复扫：

```powershell
python doc/week7-8/tools/scan_app.py servermanager after
```

脚本固定Ruff规则E/F/I/B/C90、行长100、复杂度10；Bandit不跳过检查并忽略源码nosec抑制。
显式枚举本app的Python文件，排除migrations、test*.py及tests目录，保留管理命令/模板标签；测试仍需人工阅读和必要验证。
脚本不自动修复、不导入或启动Django；输出自动映射到`成员成果/SY/原始工具结果/baseline/`或`after/`。
同一证据目录已存在会拒绝覆盖，保留旧证据后再按组内方案重跑；勿直接删除基线。
工具返回码0/1可能分别表示无告警/有告警，不能把有告警等同运行失败；以manifest、脚本SCAN_ERROR和Bandit解析错误共同核对。
`manifest.json`保留版本、命令、返回码、文件范围、提交及配置哈希；扫描有告警仍须人工核实，脚本未报错不代表问题已修复。

## 7. 隔离验证和数据边界

- 使用明确的独立测试数据库、内存缓存和虚构消息；不得通过真实微信公众号回调或生产配置验证代码。
- 先在测试导入/调用前替换ChatGPT API、系统命令调用和必要网络入口；模拟返回值/异常，禁止真实执行配置中的命令。
- 文章查询验证使用隔离的草稿/发布文章，不访问业务库；涉及Haystack时使用测试索引或替身，不更改生产搜索索引。
- 邮件相关只检查日志模型和脱敏测试内容；如触发发送链，使用测试邮箱后端并替换百度/Cloudflare等保存通知。
- 针对实际改进覆盖成功、失败和关键状态边界，尤其未鉴权/未确认不能执行、聊天失败不被非空断言误判。
- 注释专属改动用diff/语法及AST核对行为未改；业务改进另用实质性断言，不能以AST一致代替功能验证。
- 检查`git diff --check`和本app范围；运行配置、源代码、报告、截图、工具原始结果不得含真实凭据、`.env`、用户消息或命令清单。
- 工具未安装或隔离未就绪时记录缺口交组长；不以真联网、真邮件、真命令作为省略隔离的替代方案。

### 隔离测试准确命令

从更新仓库取得`run_isolated_tests.py`；先给ChatGPT调用补mock及有效断言，再在仓库根执行已核对存在的方法label。

```powershell
.\src\DjangoBlog\.venv\Scripts\python.exe doc/week7-8/tools/run_isolated_tests.py servermanager.tests.ServerManagerTest.test_chat_gpt
```

runner使用SQLite内存库、内存缓存/邮箱及Haystack SimpleEngine，移除ES配置和Cloudflare插件，阻断HTTP/套接字。
评论邮件线程改同步以便断言；不证明真实数据库、ES、平台或异步邮件联调。runner不阻断系统命令，必须另mock命令调用。
目前不存在`servermanager.test_chatgpt_business_logic`；不要复制虚构label或省略label，也不保证整套本app测试可跑。
现有聊天测试非空断言可能把错误文本当成功；结合实际改进选择真实label，记录返回码与失败，不能以阻断网络代替断言。

## 8. 个人交付清单

所有个人分析证据保存至`doc/week7-8/成员成果/SY/`；源码修改仍放原app路径，不复制额外一套源码。

| 产物 | 必须包含 |
| --- | --- |
| `质量分析片段.md` | app边界和GZX交接范围、三条调用路线、风格/设计/正面技能/缺陷、源码证据与改进结果 |
| `工具与验证记录.md` | 工具版本/参数/规则、前后提交、数据库/网络/命令隔离、命令返回码、验证及复扫比较 |
| `原始工具结果/` | 基线、复扫输出和规则配置、必要截图；先脱敏并保持可追溯 |
| `注释统计.md` | 逐文件的基线、三层新增组数/行数/行号；不计旧GZX或原SY标注 |
| `改进计划.md` | 已完成与待办分开；下一步优化优先级、负责人建议、依赖、验收条件及风险 |

另提炼2—4条可复用Python规范建议，附本app实例和理由，写在`质量分析片段.md`末尾供团队汇总。
组长按上级目录`文档模板-开源软件的质量分析报告文档.docx`及`文档模板-编码规范.docx`汇总两份Word。
个人不额外交ZIP、安装包或冒充团队定稿的Word；下一步系统优化计划由组长并入质量报告。

## 9. 复核与集成

- 复核配对：SY ↔ WZY；重点互查外部副作用隔离、管理员/确认状态、查询公开条件和断言有效性。
- 复核须反馈实际检查文件、问题及处理结果；由本人修正主责app，原作者及复核贡献分别保留。
- 工作流为`sy → develop → main`；个人提交仅包含servermanager及SY成果，由组长负责最终main集成。
- 提交前核对源码、注释统计、工具基线和复扫、必要验证与计划一致，并明确报告未完成事项及阻塞。
