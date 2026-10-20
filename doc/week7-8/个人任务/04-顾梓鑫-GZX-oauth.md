# 第7—8周个人任务：顾梓鑫（GZX）— oauth

收件人：顾梓鑫，学号2415304345；个人分支：`gzx_branch`。
项目根目录：`E:\软件工程方法学\class-3-group-6`；主责app：`src/DjangoBlog/oauth/`。
截止时间按组长最新通知执行；本任务单不代填开始、完成时间或评估结果。
本文件是任务安排，下面的源码问题都是待核实候选，不表示已经修复。

## 1. 本轮目标和边界

- 你独立负责已在`settings.py`的`INSTALLED_APPS`注册的`oauth`，完成精读注释、人工质量分析、工具评估与至少一项适当改进。
- 六人主责互不重复：SZX—blog、YFY—accounts、WZY—comments、GZX—oauth、GCY—djangoblog、SY—servermanager。
- 本轮将你此前参与的`servermanager`交接宋洋；提供调用说明和旧问题线索，但不再作为你的重复主责app。
- `accounts`、`djangoblog`、`templates/oauth/`仅作调用证据；跨app问题记录并交给对应成员，避免同时改同一文件。
- 保留旧成员署名与贡献，不将旧注释重新署名计成本轮新增，不顺带重构其他app。
- 不需要打包；源码、个人Markdown和原始证据由组长汇总并最终集成。

## 2. 文件清单与阅读优先级

以下路径均相对`src/DjangoBlog/`，请在个人记录中写清实际阅读和修改范围。

| 分组 | 文件 | 必须理解的内容 |
| --- | --- | --- |
| 核心 | `oauth/urls.py` | 授权入口、回调、补邮箱、确认及结果页的路由参数 |
| 核心 | `oauth/views.py` | code换token、身份查找、事务、登录、重定向和绑定分支 |
| 核心 | `oauth/oauthmanager.py` | 抽象管理器、五渠道适配、HTTP请求、配置与缓存 |
| 核心 | `oauth/models.py` | OAuthUser/OAuthConfig字段、关联、可空性与clean边界 |
| 核心 | `oauth/forms.py` | 邮箱和oauthid的表单校验，隐藏字段不能代替权限验证 |
| 核心 | `oauth/admin.py` | OAuthUser只读/禁增以及OAuthConfig后台展示 |
| 核心 | `oauth/templatetags/oauth_tags.py` | 启用渠道到授权链接的数据转换 |
| 测试 | `oauth/tests.py`、`oauth/test_oauth_business_logic.py` | 现有断言、mock覆盖、可能外呼和未验证规则 |
| 配置入口 | `oauth/apps.py`、`oauth/__init__.py`、`oauth/templatetags/__init__.py` | app和模板标签包入口，不强行为空文件补逻辑 |
| 迁移核对 | `oauth/migrations/0001_initial.py`、`0002_alter_oauthconfig_options_alter_oauthuser_options_and_more.py`、`0003_alter_oauthuser_nickname.py`、`__init__.py` | 历史字段和约束；只读，勿为满足扫描随意改历史迁移 |

关联证据：`accounts/models.py`、`accounts/views.py`、`djangoblog/utils.py`、`djangoblog/blog_signals.py`及`templates/oauth/`。
这些关联文件不计为你本轮另一个主责app，也不要复制别人注释作为你的新增成果。

## 3. 按真实调用完成三条阅读路线

1. 授权入口：`oauth_tags.load_oauth_applications` → `get_oauth_apps` → `oauthlogin` → `get_manager_by_type` → 渠道`get_authorization_url` → 302。
   记录`type/next_url`的来源、同域重定向检查、无渠道配置时的行为；区分浏览器跳转和服务端HTTP请求。
2. 授权回调：`authorize` → 渠道`get_access_token_by_code/get_oauth_userinfo` → `(type, openid)`查找 → `transaction.atomic`关联BlogUser → signal与`login`。
   分别说明已有绑定、新用户、资料无邮箱、token失败的分支；不把程序查询写成数据库联合唯一约束。
3. 邮箱补绑：`RequireEmailView` → `RequireEmailForm` → 保存邮箱并生成确认链接 → `send_email` → `emailconfirm` → 本地用户关联与登录。
   邮件发送实际在`djangoblog.blog_signals`，不是servermanager发送；核对ID、签名与邮箱绑定的实际校验。

## 4. 三层署名注释要求

- 模块层：在核心文件模块头说明职责、上下游、主要数据及外部依赖，例如`# GZX：本模块适配各OAuth平台，网络响应由调用方处理。`
- 函数/方法层：在关键函数前说明输入、返回、异常、状态变化和副作用，避免把函数名翻译一遍。
- 核心代码块/行：解释身份查找、事务、平台字段映射、重定向与签名核验的理由及边界，例如`# GZX：这里按type与openid查找，模型未声明对应联合唯一。`
- 对关键接口要说明真实行为；不写“保证安全”“永不重复”等源码没有实现的承诺。
- 注释修改与业务改进分开记录；保留原GZX及其他成员标注，旧标注不能算本轮新增。
- 在`注释统计.md`按文件记录：基线提交、模块/函数/核心块新增组数、新增注释行数、对应行号；续行计行数，旧行搬动不算新增。

## 5. 人工质量分析与候选问题

人工分析至少覆盖四类，每条给出路径/行号、具体行为、影响和核验方法。

| 类别 | 重点观察 | 可引用的正面技能或待核实候选 |
| --- | --- | --- |
| 代码风格 | 命名、导入、长函数、重复分支、注释准确性 | 管理器抽象和渠道子类复用；视图是否承担过多职责 |
| 设计与技能 | 平台适配、事务、模型/表单/视图分层 | 抽象接口、事务关联、同域重定向检查是可分析的正面实例 |
| 可靠性 | 网络超时、JSON异常、空资料、平台错误 | `do_get/do_post`未显式传timeout且记录完整响应，需核实可靠性与日志泄露影响 |
| 数据与安全 | 唯一性、启用标志、签名、敏感展示 | OAuthUser无`(type,openid)`联合唯一；OAuthConfig.type仅clean检查；核对禁用渠道后的缓存一致性 |

- `get_oauth_apps`筛选启用配置并缓存100分钟，`get_manager_by_type`复用该清单；`get_config`仅按type取配置。核对禁用后的缓存失效时机，不能直接断言禁用渠道仍可选择。
- 激活/绑定签名是否包含时效、邮箱变化后能否复用，以及OAuth回调是否有state关联校验，均先定位再提出结论。
- `OAuthConfigAdmin.list_display`包含appsecret；核实实际可见角色与展示必要性，报告不放真实字段值。
- `test_oauth_config_type_uniqueness`存在成功/异常均可结束的分支，核实断言是否真正验证预期规则。
- 优先选择范围小、能隔离验证的改进，例如敏感日志最小化、明确异常或可靠性边界、补实质性断言；唯一约束迁移和身份绑定策略需列入团队计划后协调。

## 6. 工具评估与改进闭环

1. 记录基线提交、Python版本、依赖来源和扫描范围；统一使用官方CLI的Ruff 0.17.1与Bandit 1.9.4。
2. 课件的SonarQube IDE插件和Gitee整项目扫描只是示例，可作补充；不表示本机已安装，也不强制分别使用这两个工具。
3. 先保存改动前JSON：`原始工具结果/baseline/`中的`ruff.json`、`bandit.json`、`manifest.json`；无工具结果不要编分数。
4. 人工复核每条拟采用告警，区分真实缺陷、维护性问题、误报和已有设计取舍；模型查询/框架约定不能机械替换。
5. 至少完成一项经核实、与本app有关的适当质量改进；仅补注释不能代替这项改进，勿为清零告警扩大重构。
6. 对改进运行必要验证，写明改动前触发条件、改动后预期、真实结果与剩余风险；未通过如实记录。
7. 使用相同工具版本、规则、排除项和范围复扫，保存`原始工具结果/after/`中的同名JSON及差异；配置变化必须单列，不能冒充代码改善。
8. 区分工具指标与人工结论，不将“无告警”表述成“无缺陷”，本轮任务单不预填任何完成状态。

### 统一工具与准确命令

转发任务只需本MD；工具从组长更新后的仓库取得，不要另传或自行修改一套扫描脚本。
使用`doc/week7-8/tools/requirements-quality.txt`、`ruff.toml`、`bandit.yaml`与`scan_app.py`；`python`须指向独立工具环境，勿改项目运行依赖。
从仓库根运行基线：

```powershell
Set-Location 'E:\软件工程方法学\class-3-group-6'
python -m pip install -r doc/week7-8/tools/requirements-quality.txt
python doc/week7-8/tools/scan_app.py oauth baseline
```

完成改进与必要验证后，同配置复扫：

```powershell
python doc/week7-8/tools/scan_app.py oauth after
```

脚本固定Ruff规则E/F/I/B/C90、行长100、复杂度10；Bandit不跳过检查并忽略源码nosec抑制。
显式枚举本app的Python文件，排除migrations、test*.py及tests目录，保留管理命令/模板标签；测试仍需人工阅读和必要验证。
脚本不自动修复、不导入或启动Django；输出自动映射到`成员成果/GZX/原始工具结果/baseline/`或`after/`。
同一证据目录已存在会拒绝覆盖，保留旧证据后再按组内方案重跑；勿直接删除基线。
工具返回码0/1可能分别表示无告警/有告警，不能把有告警等同运行失败；以manifest、脚本SCAN_ERROR和Bandit解析错误共同核对。
`manifest.json`保留版本、命令、返回码、文件范围、提交及配置哈希；扫描有告警仍须人工核实，脚本未报错不代表问题已修复。

## 7. 隔离验证和数据边界

- 先检查现有测试是否会真实访问平台；不是所有`oauth/tests.py`路径都已mock，禁止直接用生产配置跑整套测试。
- 使用明确的独立测试数据库、内存缓存与测试邮箱后端，模拟`do_get/do_post`、头像下载、邮件和保存信号外发通知；禁止连接业务库。
- 覆盖与实际改进有关的成功、失败、空响应、超时/非法JSON等分支；输入仅用虚构邮箱、用户和token样例。
- 注释专属修改可用diff/语法及AST核验说明未改变行为；业务改进另用有意义的断言验证，不能拿AST一致证明功能改进。
- 检查`git diff --check`与本app差异；运行配置、源代码、报告、截图和原始扫描日志均不得包含真实凭据或`.env`内容。
- 工具未安装、测试隔离未就绪或失败时，记录具体缺口交组长处理，不伪造结果，也不以真实OAuth登录替代隔离验证。

### 隔离测试准确命令

从更新仓库取得`run_isolated_tests.py`，先补齐被测路径的外呼mock，再在仓库根执行下例；该模块名已核对存在。

```powershell
.\src\DjangoBlog\.venv\Scripts\python.exe doc/week7-8/tools/run_isolated_tests.py oauth.test_oauth_business_logic
```

runner使用SQLite内存库、内存缓存/邮箱及Haystack SimpleEngine，移除ES配置和Cloudflare插件，阻断HTTP/套接字。
评论邮件线程改为同步调用以便断言；这不表示真实异步投递已验证，也不证明MySQL、ES或第三方平台联调通过。
按实际改进选择真实module/class/method label；切勿省略label误跑默认blog测试，也不保证oauth整套现有测试都可通过。
记录真实返回码与失败；网络阻断只是防止外发，不能代替成功/失败响应mock和实质性断言。

## 8. 个人交付清单

所有个人分析证据保存至`doc/week7-8/成员成果/GZX/`；源码修改仍放原app路径，不复制一份散落源码。

| 产物 | 必须包含 |
| --- | --- |
| `质量分析片段.md` | app边界、三条调用路线、风格/设计/正面技能/缺陷、源码证据、已做改进与未解决项 |
| `工具与验证记录.md` | 工具版本/参数/规则、前后提交、隔离方法、命令、返回码、必要验证及同配置复扫比较 |
| `原始工具结果/` | 基线与复扫的原始输出、规则配置、必要截图；文件名可追溯，先脱敏 |
| `注释统计.md` | 按文件的基线、三层新增组数/行数/行号；旧标注与本轮新增分开 |
| `改进计划.md` | 已完成/待办分开；下一步优化的优先级、负责人建议、依赖、验收条件及风险 |

另提炼2—4条可复用的Python规范建议，附本app实例及理由，写入`质量分析片段.md`末尾供团队规范汇总。
组长将个人Markdown按上级目录`文档模板-开源软件的质量分析报告文档.docx`与`文档模板-编码规范.docx`汇总成两份Word。
个人不要另交ZIP、安装包或冒充团队定稿的Word；下一步系统优化计划由组长并入质量报告。

## 9. 复核与集成

- 复核配对：GZX ↔ YFY；重点相互检查OAuth与本地账号边界、数据约束、重定向和邮箱流程。
- 复核须反馈实际检查文件、问题及处理结果；由本人修正个人主责app，保留作者与审校来源。
- 工作流为`gzx_branch → develop → main`；个人提交仅包含oauth及GZX成果，由组长负责最终main集成。
- 提交前确认源码、注释统计、扫描基线和复扫、必要验证、改进计划互相一致，并向组长报告未完成与阻塞项。
