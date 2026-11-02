# 第9—10周功能优化任务：喻飞扬（YFY）— accounts

收件人：喻飞扬；学号：2415304347；个人分支：`yfy_branch`；复核搭档：GZX。
范围：`src/DjangoBlog/accounts/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态：任务已分配，业务优化待本人实施/验证；日期与结果按实际填写。第9周完成主要实现，第10周完成全App功能测试、联调、报告和MP4素材；具体日历截止按组长通知。

## 1. 本轮目标与当前事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

找回密码验证码服务端冷却与前端同步；错误次数和锁定；选做激活链接时效/重发。

验证码有效期已有5分钟、成功重置后消费；发送接口仍返回文本ok，前端launcherAccount.js已有本地倒计时，但服务端没有发送限频。verify只比对缓存，没有重试次数；不要把上轮的一次消费重复计为本轮新功能。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `accounts/utils.py` | 验证码、命名空间、冷却与失败状态 |
| `accounts/views.py、accounts/forms.py` | 发送接口、请求上下文、错误回显和成功消费 |
| `templates/account/forget_password.html` | 服务器剩余时间与提示 |
| `frontend/src/components/launcherAccount.js` | 解析新JSON；兼容该组件的注册/登录用途 |
| `accounts/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

YFY负责账号模板及launcherAccount.js，其他人不同时修改该文件。公共发信函数/信号不变；配置直接调用get_maintenance_option。若verify需接收上下文，保留既有两位置参数调用并新增关键字参数，HTTP路径显式传入上下文。GZX负责OAuth，YFY配合核对激活/登录及同邮箱账号边界。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### A91（必做）服务端验证码发送冷却

使用RESET_SEND_COOLDOWN_SECONDS=60；按规范化邮箱控制重复发送，不能只禁用浏览器按钮。保留URL和email字段，成功/限频/格式错误/投递故障遵循共享JSON与HTTP约定。冷却拒绝时不发信也不覆盖旧码；发送失败可重试且不留下可用新码。前端解析服务端retry_after，不依赖客户端自填60；同页多次点击和第二个浏览器窗口均验证。

### A92（必做）验证码失败次数和挑战锁定

同邮箱与当前重置挑战连续5次错误后锁定900秒；正常有效期300秒、成功重置后立即消费。挑战与浏览器上下文关联，避免任意访客只凭邮箱锁死别人账号；记录缓存后端/并发边界。缺邮箱/空码/其他字段不合法不错误计为一次真实码尝试；校验只读与最终消费职责分开。向表单返回明确可见错误，锁定期正确码也不可重置，过期/解锁/新挑战有明确状态流转。

### A93（选做）激活链接期限与重新发送

仅本地accounts激活链路，独立salt=week910.accounts.activate；增加到期验证和受控重发，已激活访问保持幂等。与GZX邮箱绑定签名隔离，不替他改oauth。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.0](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("RESET_SEND_COOLDOWN_SECONDS")
```

入口已经提供，业务限制仍需本人接入。修改默认阈值/参数/返回值前交SZX更新统一约定；成员自己的演示配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| A-T01 | 注册、激活、用户名/邮箱登录、登出 | 有效路径可用，未激活用户仍拒绝登录 |
| A-T02 | 首次申请有效邮箱验证码 | 200 sent；只发一次，缓存TTL正确 |
| A-T03 | 60秒内同邮箱重复/第二窗口申请 | 429 rate_limited和Retry-After；邮件与原码不变 |
| A-T04 | 冷却结束/另一个邮箱申请 | 按规定可发送，状态互不串用 |
| A-T05 | 非法邮箱/邮件后端异常 | 400/503；可恢复，未泄露账号存在性或密钥 |
| A-T06 | 错误码达到5次与锁定中正确码 | 锁定阻止重置，实际剩余时间可核对 |
| A-T07 | 缺字段、空码、其他表单字段错误 | 表单正常回显，失败次数和消费无误 |
| A-T08 | 正常重置/复用旧码/过期码 | 一次成功、第二次失败、过期失败 |
| A-T09 | 前端倒计时、429、发送失败和重复点击 | 界面与服务端状态一致，注册/登录组件无回归 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/YFY/证据/baseline-tests.json accounts.test_auth_hardening accounts.tests accounts.test_user_business_logic accounts.test_admin accounts.test_login_page accounts.test_account_pages djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/YFY/证据/after-tests.json accounts.test_auth_hardening accounts.tests accounts.test_user_business_logic accounts.test_admin accounts.test_login_page accounts.test_account_pages djangoblog.test_week910_configuration accounts.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py accounts baseline --output-dir doc/week9-10/成员成果/YFY/证据/baseline-scan
python doc/week7-8/tools/scan_app.py accounts after --output-dir doc/week9-10/成员成果/YFY/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 本地演示顺序

1. 打开找回密码页，第一次发送后展示倒计时；用第二窗口说明服务端也拒绝重复发送。
2. 在演示配置或可控测试中展示第5次错误后的锁定，明确说明演示时长覆盖值。
3. 使用新的有效挑战完成密码重置，登录成功，再展示旧码无法重复使用；本地邮件替身标注清楚。

GCY提供settings_demo后，在该配置下本地运行并验证本模块；隔离单测和本地整站功能测试分别记录。个人提交操作脚本、可复现样本和预期画面；集成测试通过后，由组长石兆翔在同一个本地版本上统一讲解并录制MP4，开头列第6组及六人姓名。组员不必单独录制视频。替身与真实外部服务验证分开标注。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch yfy_branch
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/YFY/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/YFY/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin yfy_branch
```

交付到`doc/week9-10/成员成果/YFY/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `演示脚本.md`：本地前置、逐步操作、解说、可演示结果、使用的替身或时长覆盖。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。Word正式报告由组长汇总，使用宋体/Times New Roman和黑色文字；视频MP4，不打包。

复核搭档GZX按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [Django缓存及计数边界](https://docs.djangoproject.com/en/5.2/topics/cache/)
- [Django签名](https://docs.djangoproject.com/en/5.2/topics/signing/)
