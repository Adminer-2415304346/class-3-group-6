# 第9—10周功能优化任务：郭曹钰（GCY）— djangoblog

收件人：郭曹钰；学号：2415304331；个人分支：`gcy_branch`；复核搭档：SZX。
范围：`src/DjangoBlog/djangoblog/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态：任务已分配，业务优化待本人实施/验证；日期与结果按实际填写。第9周完成主要实现，第10周完成本App功能测试、联调、维护报告素材和技术交接；具体日历截止按组长通知。

**交付职责：本人负责功能实现、测试和技术交接；全组统一演示、讲解、录制及剪辑由组长石兆翔负责。无需个人演示、单独录视频或编写解说/拍摄脚本。**

## 1. 本轮目标与当前事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

独立本地运行配置与运行说明；可执行环境诊断；选做幂等样例数据初始化。

默认数据库仍为MySQL，邮件SMTP，ES可由环境启用；上一轮390项为隔离测试，不能代替本轮本地整站运行。GCY先前G1—G5与SZX缓存/随机码补修已集成，不从旧个人分支覆盖这些修复。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `djangoblog/settings_demo.py（新增）` | 显式本地运行配置，不改settings.py |
| `djangoblog/demo_checks.py（新增）` | 可测试的本地依赖诊断 |
| `djangoblog/management/commands/demo_healthcheck.py（新增）` | JSON诊断和退出码 |
| `djangoblog/test_week910_functional.py（新增）及本人运行说明` | 覆盖启动、路由、错误页、数据库/缓存与诊断 |
| `djangoblog/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

GCY本轮只写上述新增专用文件和自己的测试/说明。现有settings.py、urls.py、blog_signals.py、utils.py、插件基础层及前端构建配置由SZX修改。提供共享补丁清单，不能直接贴旧版整文件。maintenance_config.py与test_week910_configuration.py归SZX，GCY调用并保留其测试。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### D91（必做）可重复启动的独立本地运行环境

提供djangoblog.settings_demo与完整Windows运行步骤：SQLite、独立媒体/Whoosh索引/日志目录、LocMem缓存和本地邮件；明确移除继承ES配置，不依赖真实服务凭据。迁移、创建本地管理员、npm ci/build、启动浏览器验证均实际执行。SZX集成根路由和媒体路由；各App阈值从统一配置入口取。源代码不提交本机数据库、虚拟环境、node_modules、凭据和生成日志。

### D92（必做）本地环境诊断命令

提供demo_healthcheck --settings=djangoblog.settings_demo --format=json，输出status/checks及可操作的失败说明，检查数据库、缓存、模板、前端manifest及其引用产物、媒体目录可用性。全通过退出0，有失败退出非0；用测试覆盖缺文件、缓存失败、数据库异常，不能吞异常打印成功。默认不请求SMTP/OAuth/微信/OpenAI/ES，不打印配置密钥。

### D93（选做）幂等样例数据初始化

在DEMO_MODE下提供独立管理命令，创建文章/评论功能所需样本；重复执行不重复写入，不清空用户已有数据。账号密码从交互输入/本机环境取得，不提交真实凭据；使用模型公共接口，并向对应App负责人确认字段与数据依赖。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.1](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("RESET_SEND_COOLDOWN_SECONDS")
```

入口已经提供，业务限制仍需本人接入。修改默认阈值/参数/返回值前交SZX更新统一约定；成员本地运行配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| D-T01 | 显式settings_demo加载与迁移 | 使用独立SQLite和本地目录；默认生产设置未被覆盖 |
| D-T02 | 首页、登录/注册、后台、文章/评论页面 | 本地浏览器可操作，静态样式和JS可用 |
| D-T03 | 缓存写读删除、数据库连通 | 诊断真实检查且输出ok |
| D-T04 | 前端manifest与引用产物存在 | 诊断通过，浏览器无缺失资源 |
| D-T05 | manifest缺失/坏JSON/产物缺失 | 诊断failed并非0退出，提示具体修复命令 |
| D-T06 | 数据库/缓存错误、媒体不可用 | 失败被正确区分，不泄露敏感参数 |
| D-T07 | 自定义403/404与插件回调异常 | 原G5和插件后续回调行为保持 |
| D-T08 | 原无参/方法缓存装饰器、验证码随机码 | 旧补修回归保持 |
| D-T09 | 不同工作目录启动及本地邮件 | 路径不依赖绝对盘符，邮件明确标注为本地测试 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/GCY/证据/baseline-tests.json djangoblog.test_week78_gcy_quality djangoblog.tests djangoblog.test_plugins djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/GCY/证据/after-tests.json djangoblog.test_week78_gcy_quality djangoblog.tests djangoblog.test_plugins djangoblog.test_week910_configuration djangoblog.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py djangoblog baseline --output-dir doc/week9-10/成员成果/GCY/证据/baseline-scan
python doc/week7-8/tools/scan_app.py djangoblog after --output-dir doc/week9-10/成员成果/GCY/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 交给组长的功能复现信息

把以下信息写入`实现说明.md`，供组长在统一录制前启动并检查整站：

- 从环境准备、迁移、本地管理员创建、前端构建到启动系统的完整命令、所用设置模块和入口地址。
- 独立数据库/媒体/索引/日志目录的位置规则、本地邮件的读取方式，以及样例数据的准备方法。
- 健康检查命令、JSON字段/退出码含义和常见失败的修复方法；附实际启动、构建及浏览器操作结果。

本人负责把本地运行环境与诊断功能做成可交接的成果，分别记录隔离测试和整站运行验证；统一演示、讲解和MP4录制由组长完成。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch gcy_branch
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/GCY/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/GCY/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin gcy_branch
```

交付到`doc/week9-10/成员成果/GCY/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号；在同一文件补充第6节的入口、样例、操作步骤、预期结果和替身/配置条件。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。本人交上述三份MD及证据。Word正式报告与统一演示、讲解、录制、剪辑由组长负责；Word使用宋体/Times New Roman和黑色文字，视频为MP4，不打包。

复核搭档SZX按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [Django管理命令](https://docs.djangoproject.com/en/5.2/ref/django-admin/)
- [Django缓存](https://docs.djangoproject.com/en/5.2/topics/cache/)
