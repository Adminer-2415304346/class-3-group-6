# 第9—10周功能优化任务：顾梓鑫（GZX）— oauth

收件人：顾梓鑫；学号：2415304345；个人分支：`gzx_branch`；复核搭档：YFY。
范围：`src/DjangoBlog/oauth/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态：任务已分配，业务优化待本人实施/验证；日期与结果按实际填写。第9周完成主要实现，第10周完成全App功能测试、联调、报告和MP4素材；具体日历截止按组长通知。

## 1. 本轮目标与当前事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

OAuth state校验与消费；受控邮箱绑定；选做密钥显示/敏感日志最小化。

oauthlogin/authorize尚无state往返校验；RequireEmailView依赖隐藏oauthid，emailconfirm使用无时效的id签名；authorize按邮箱直接关联本站账号并login，未统一检查is_active。既有HTTP超时10秒已经实施，保持该回归。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `oauth/views.py` | oauthlogin、authorize、RequireEmailView、emailconfirm |
| `oauth/oauthmanager.py` | 各渠道get_authorization_url扩展state，保留现有调用兼容 |
| `oauth/forms.py、urls.py、models.py及新迁移` | 归属校验、待绑定记录和一次消费 |
| `templates/oauth/` | 过期/冲突/重新发起及明确绑定提示 |
| `oauth/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

本轮只由GZX修改oauth及其模板；YFY复核本地账号激活和绑定规则，SZX处理公共信号/总路由/设置。签名salt固定week910.oauth.bind，与accounts激活分离；可新增本App模型/迁移，不对accounts邮箱直接加唯一约束。不同渠道/会话隔离、失效旧链接属于明确的兼容调整，需在实现说明交代。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### O91（必做）state绑定会话并按期一次消费

完全按共享约定第5节：每渠道最新随机state、300秒、绑定当前浏览器和安全next地址。回调先验证再换token；缺失、错误、过期、跨浏览器、重复和渠道不符均拒绝且无平台外呼。保留渠道配置的callback URL，不通过任意callback参数传next；保持原外呼超时。所有已启用渠道的URL构造都支持state，并有虚构响应测试。

### O92（必做）邮箱归属、绑定期限与一次确认

按共享约定新增服务端待绑定记录，600秒，关联OAuthUser、邮箱、nonce、浏览器上下文和消费状态；隐藏ID篡改不产生他人写入。TimestampSigner只做签名/到期，另用数据库条件消费保证重放拒绝。已有绑定仅有效用户可登录；未绑定不按同邮箱静默取得本地账号，同邮箱已有账号需先登录该账号后显式确认。新邮箱、已有账号、取消/重发、旧链接及登录导致session_key轮换分别测试。

### O93（选做）后台与日志敏感数据最小化

OAuthConfigAdmin列表去除明文appsecret，HTTP日志不写完整token/响应/邮箱；保留状态码、渠道和异常类别。测试构造伪凭据确认日志无泄露，并验证正常授权可用。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.0](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("OAUTH_STATE_TTL_SECONDS")
```

入口已经提供，业务限制仍需本人接入。修改默认阈值/参数/返回值前交SZX更新统一约定；成员自己的演示配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| O-T01 | 每个已启用渠道发起授权 | URL含新state且callback保持配置值 |
| O-T02 | 合法同浏览器回调 | 换token一次、按规则登录或进入待绑定 |
| O-T03 | 缺/错/过期/跨浏览器/错渠道state | 拒绝；平台调用次数0 |
| O-T04 | 重复回调、同渠道第二次发起后旧回调 | 拒绝旧值；最新值可用 |
| O-T05 | 未绑定且已有相同邮箱本站账号 | 不能直接登录该账号，先认证后显式确认 |
| O-T06 | 篡改oauthid/email/nonce及换浏览器 | 403或安全错误页，无关联写入 |
| O-T07 | 新邮箱合法绑定、过期/复用/旧链接 | 一次成功，过期和重放拒绝 |
| O-T08 | 本地登录轮换session_key后确认 | 合法上下文保留，登出/不同上下文拒绝 |
| O-T09 | 绑定未激活用户、非法next、HTTP超时/坏响应 | 不建立无效登录态，不开放重定向，无敏感日志 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/GZX/证据/baseline-tests.json oauth.test_oauth_business_logic djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/GZX/证据/after-tests.json oauth.test_oauth_business_logic djangoblog.test_week910_configuration oauth.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py oauth baseline --output-dir doc/week9-10/成员成果/GZX/证据/baseline-scan
python doc/week7-8/tools/scan_app.py oauth after --output-dir doc/week9-10/成员成果/GZX/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 本地演示顺序

1. 先展示本地系统和渠道入口，再用明确标注的模拟提供商走完整回调。
2. 展示合法state成功、篡改/重复回调被拒绝，以及未绑定邮箱的确认流程。
3. 展示同邮箱账号必须先本地登录并确认；读取本地邮件替身链接，证明过期/重放拒绝。不要在默认生产路由中新增免认证模拟登录通路。

GCY提供settings_demo后，在该配置下本地运行并验证本模块；隔离单测和本地整站功能测试分别记录。个人提交操作脚本、可复现样本和预期画面；集成测试通过后，由组长石兆翔在同一个本地版本上统一讲解并录制MP4，开头列第6组及六人姓名。组员不必单独录制视频。替身与真实外部服务验证分开标注。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch gzx_branch
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/GZX/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/GZX/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin gzx_branch
```

交付到`doc/week9-10/成员成果/GZX/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `演示脚本.md`：本地前置、逐步操作、解说、可演示结果、使用的替身或时长覆盖。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。Word正式报告由组长汇总，使用宋体/Times New Roman和黑色文字；视频MP4，不打包。

复核搭档YFY按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [Django时间签名](https://docs.djangoproject.com/en/5.2/topics/signing/)
- [OAuth安全参考RFC9700](https://www.rfc-editor.org/rfc/rfc9700.html)
