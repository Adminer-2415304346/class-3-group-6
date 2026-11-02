# 第9—10周功能优化任务：王子扬（WZY）— comments

收件人：王子扬；学号：2415304348；个人分支：`wzy_branch`；复核搭档：SY。
范围：`src/DjangoBlog/comments/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态：任务已分配，业务优化待本人实施/验证；日期与结果按实际填写。第9周完成主要实现，第10周完成本App功能测试、联调、维护报告素材和技术交接；具体日历截止按组长通知。

**交付职责：本人负责功能实现、测试和技术交接；全组统一演示、讲解、录制及剪辑由组长石兆翔负责。无需个人演示、单独录视频或编写解说/拍摄脚本。**

## 1. 本轮目标与当前事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

评论正文与公开文章校验；发布限频/防重复；选做评论树查询优化。

CommentForm仍直接暴露body，没有本组正文长度规则；CommentPostView已处理关闭评论、无效/跨文章父ID，但发布限频/重复保护尚无。R4单次表情统计、R5完整评论缓存生命周期已由上轮集成实现，保留现有功能。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `comments/forms.py` | 正文规范化、长度和表单错误 |
| `comments/views.py` | 文章/父评论验证、发布状态与限频编排 |
| `comments/models.py及新增辅助模块` | 如使用事务性提交状态，可在本App新增模型/迁移 |
| `templates/comments/` | 错误可见性；选做评论树消费方，先协调blog入口 |
| `comments/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

只改本人comments和明确归属的评论模板。blog.comment_cache.invalidate_comment_caches与get_reactions_summary返回结构/单次读取契约不变，djangoblog.blog_signals由SZX统一修改。新增迁移留在comments，事务状态与提交后通知/失效一起验收，不重新覆盖旧共享信号。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### C91（必做）评论输入和目标文章校验

正文去首尾空白后为1—2000字符；空白、超限、草稿文章、关闭评论及无效/跨文章父ID都明确拒绝，正常公开文章/回复成功。不可公开文章按404处理；已发布独立页面沿用原评论规则。使用表单错误回显正文问题，保持原审核开关和HTML净化链路。

### C92（必做）评论限频和重复保护

同用户成功评论间隔30秒；同用户、同文章、同规范化正文和同回复目标在120秒内拒绝重复。优先识别重复，其他过频给出剩余时间；表情切换不走评论发布冷却。内容/父ID/权限校验失败或事务回滚，不计成功评论、不给缓存和邮件增加副作用。建议用本App事务性状态记录实现可靠回滚；若依赖缓存原子操作，必须说明真实后端和边界，不写成通用分布式保证。

### C93（选做）评论树查询优化

先测多层回复查询数，新增有界的树组织辅助层，并与SZX约定模板接入。Article.comment_list仍返回QuerySet，避免破坏filter调用；以多层、无回复、禁用回复与分页验证行为和查询预算。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.1](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("COMMENT_MAX_LENGTH")
```

入口已经提供，业务限制仍需本人接入。修改默认阈值/参数/返回值前交SZX更新统一约定；成员本地运行配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| C-T01 | 正常顶层评论和同文章回复 | 保存成功，跳到正确锚点，审核开关生效 |
| C-T02 | 纯空白、2000字符边界和2001字符 | 前者拒绝、边界接受、超限拒绝且无记录 |
| C-T03 | 草稿/不存在文章、关闭评论 | 404或既定表单错误；无评论与通知 |
| C-T04 | 无效/跨文章父ID | 原错误回显保持，无500 |
| C-T05 | 同用户重复正文、相同回复目标 | 120秒窗口拒绝重复，不增加记录 |
| C-T06 | 不同正文但距上次成功不足30秒 | 限频；到期可提交 |
| C-T07 | 另一个用户、另一个文章/回复目标 | 重复键隔离；全用户间隔按约定独立验证 |
| C-T08 | 保存异常或事务回滚后再次合法提交 | 无成功冷却残留、无通知和错误缓存失效 |
| C-T09 | 表情GET/POST、审核、禁用、级联删除 | R4/R5及可见性、计数、缓存与通知回归通过 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/WZY/证据/baseline-tests.json comments.test_reaction_snapshot comments.tests comments.test_views comments.test_comment_business_logic comments.test_quality_r45 djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/WZY/证据/after-tests.json comments.test_reaction_snapshot comments.tests comments.test_views comments.test_comment_business_logic comments.test_quality_r45 djangoblog.test_week910_configuration comments.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py comments baseline --output-dir doc/week9-10/成员成果/WZY/证据/baseline-scan
python doc/week7-8/tools/scan_app.py comments after --output-dir doc/week9-10/成员成果/WZY/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 交给组长的功能复现信息

把以下信息写入`实现说明.md`，供组长接手本地系统后复现功能：

- 文章/评论页面入口，公开文章、草稿、父评论样本的准备方式，以及用户和后台审核配置要求。
- 正常评论/回复、空白或超长正文、重复评论、不同正文过频的操作步骤、提示和数据库预期变化。
- 恢复提交的等待条件；若测试缩短了时长，列出覆盖参数。附上表情、审核启停与缓存回归的验证位置。

GCY提供settings_demo后，在该配置下本地运行并验证本模块；隔离测试和本地整站功能测试分别记录。上述信息属于功能交接，统一演示、讲解和MP4录制由组长完成。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch wzy_branch
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/WZY/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/WZY/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin wzy_branch
```

交付到`doc/week9-10/成员成果/WZY/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号；在同一文件补充第6节的入口、样例、操作步骤、预期结果和替身/配置条件。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。本人交上述三份MD及证据。Word正式报告与统一演示、讲解、录制、剪辑由组长负责；Word使用宋体/Times New Roman和黑色文字，视频为MP4，不打包。

复核搭档SY按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [Django缓存边界](https://docs.djangoproject.com/en/5.2/topics/cache/)
- [Django事务](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
