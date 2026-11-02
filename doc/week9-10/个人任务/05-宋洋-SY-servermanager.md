# 第9—10周功能优化任务：宋洋（SY）— servermanager

收件人：宋洋；学号：2415304330；个人分支：`sy`；复核搭档：WZY。
范围：`src/DjangoBlog/servermanager/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态：任务已分配，业务优化待本人实施/验证；日期与结果按实际填写。第9周完成主要实现，第10周完成全App功能测试、联调、报告和MP4素材；具体日历截止按组长通知。

## 1. 本轮目标与当前事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

固定动作允许列表替代shell文本；管理员/确认票据过期和单次消费；选做本地机器人演示命令。

上轮SZX代办已经修复语法/层级、SDK、纯JSON状态、顺序重复Y、公开文章过滤和非破坏存储回退；33项本App测试通过。CommandHandler仍shell=True，管理员状态无有效期，顺序清空会话不代表并发一次消费。本轮仍由宋洋主责，保留旧SZX/GZX署名。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `servermanager/api/commonapi.py` | CommandHandler固定动作、timeout和输出结果 |
| `servermanager/robot.py` | 状态期限、待确认票据与退出/重新认证 |
| `servermanager/models.py、admin.py及新迁移` | 命令动作ID提示、持久化确认票据 |
| `servermanager/management/commands/（选做新增）` | 本地消息链路演示，不依赖真实微信/模型 |
| `servermanager/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

个人分支实际名是sy，不是sy_branch。只改servermanager和自己的新增迁移；共享邮件日志投递和djangoblog设置交SZX集成。仅本轮本人实际完成的内容署名SY；如需组长代办，应先交接并记录真实执行者，不直接把上轮代码改署名。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### S91（必做）固定动作允许列表

按共享约定保留run(title)，数据库command字段存动作ID。首先只注册python_version，内部固定[sys.executable,"--version"]；受ROBOT_ALLOWED_ACTIONS控制、shell=False，不能让聊天消息或数据库文字变成任意参数/批处理。旧shell配置明确拒绝并提示迁移。帮助只列可执行项；覆盖成功、拒绝、超时、非零退出和消息输出上限。返回截断与实际进程内存/进程树终止分别说明。

### S92（必做）管理员期限及命令确认票据

认证有效900秒，命令确认60秒；票据绑定用户、动作、期限及消费状态，退出/重新认证使旧票据不可复活。并发确认用数据库条件更新/唯一约束等持久化机制，只有一个请求取得执行资格；失败/过期/重放路径执行器次数为0。新状态仍为有界纯JSON，旧会话不能因缺期限字段无限保留管理员权限。

### S93（选做）本地机器人消息链路演示工具

新增明确的management命令或仅DEMO_MODE可用的演示入口，驱动真实MessageHandler；聊天/微信以标注替身替换，允许动作仍走固定注册表。把正常、过期、重复确认过程录入脚本，生产默认不暴露模拟身份入口。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.0](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("ROBOT_CONFIRM_TTL_SECONDS")
```

入口已经提供，业务限制仍需本人接入。修改默认阈值/参数/返回值前交SZX更新统一约定；成员自己的演示配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| S-T01 | recent/category/search公开文章链路 | 有/无结果及草稿/页面/陈旧索引边界保持 |
| S-T02 | 普通消息、帮助、管理员口令与3次失败 | 既有流程保持，不意外执行命令 |
| S-T03 | 允许的python_version | 固定argv、shell=False、配置timeout，无用户拼接 |
| S-T04 | 未允许动作、旧shell串、未知标题 | 拒绝；subprocess调用次数0 |
| S-T05 | 超时/非零退出/超长返回 | 明确结果；返回消息长度符合阈值 |
| S-T06 | 会话/确认分别到期、exit和重新认证 | 旧票据不可执行；执行器次数0 |
| S-T07 | 同用户重复Y、不同用户拿同票据 | 只能一次且归属校验生效 |
| S-T08 | 并发条件消费同一票据 | 仅一个请求获执行资格；记录实际DB/并发验证边界 |
| S-T09 | 畸形JSON、旧状态、缓存/文件存储回退 | 拒绝不可信状态，不删除已有会话数据 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/SY/证据/baseline-tests.json servermanager.tests servermanager.test_week78_takeover djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/SY/证据/after-tests.json servermanager.tests servermanager.test_week78_takeover djangoblog.test_week910_configuration servermanager.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py servermanager baseline --output-dir doc/week9-10/成员成果/SY/证据/baseline-scan
python doc/week7-8/tools/scan_app.py servermanager after --output-dir doc/week9-10/成员成果/SY/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 本地演示顺序

1. 在本地系统/演示命令中展示普通查询、管理员认证和帮助。
2. 执行固定python_version并展示结果，接着确认旧shell文本被拒绝。
3. 展示确认超时、退出、重复Y不再次执行；视频明确哪些是本地替身，测试不调用真实微信或收费模型。

GCY提供settings_demo后，在该配置下本地运行并验证本模块；隔离单测和本地整站功能测试分别记录。个人提交操作脚本、可复现样本和预期画面；集成测试通过后，由组长石兆翔在同一个本地版本上统一讲解并录制MP4，开头列第6组及六人姓名。组员不必单独录制视频。替身与真实外部服务验证分开标注。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch sy
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/SY/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/SY/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin sy
```

交付到`doc/week9-10/成员成果/SY/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `演示脚本.md`：本地前置、逐步操作、解说、可演示结果、使用的替身或时长覆盖。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。Word正式报告由组长汇总，使用宋体/Times New Roman和黑色文字；视频MP4，不打包。

复核搭档WZY按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [Python subprocess及shell边界](https://docs.python.org/3.12/library/subprocess.html)
- [Django事务](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
