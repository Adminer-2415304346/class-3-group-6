# 第9—10周功能优化任务：石兆翔（SZX）— blog

收件人：石兆翔；学号：2415304346；个人分支：`szx_branch`；复核搭档：GCY。
范围：`src/DjangoBlog/blog/`及下列指定关联文件。基线：`main@52b783b4d8e6670b8d22638cf2fdfc39592bf4ad`。
状态更新（2026-11-02）：B91/B92已实现，代码baf8998，433项相关回归及本地HTTP/浏览器验证通过；B93选做未实施，GCY独立复核待确认。[实现与证据](../成员成果/SZX/实现说明.md)。第9周完成主要实现，第10周完成全App功能测试、联调、报告和MP4素材；具体日历截止按组长通知。

## 1. 本轮目标与基线事实

先按第7节同步并保存本人统计起点；先采集基线，再开始业务实现。

文章浏览量原子更新；图片上传权限与文件校验；选做分类环检测。

实现前基线：Article.viewed()读取实例views后加一并save；fileupload仍使用固定sign、csrf_exempt及客户端字段名推断图片。上轮的草稿详情、清缓存权限和HTML转义已修复，保持其回归。

## 2. 文件与职责边界

路径除特别说明外均相对`src/DjangoBlog/`。

| 文件/范围 | 本轮工作 |
| --- | --- |
| `blog/models.py` | Article.viewed；选做Category.clean/分类树 |
| `blog/views.py` | fileupload；详情消费新浏览量 |
| `blog/forms.py、blog/admin.py` | 选做分类表单校验，按实际调用补齐 |
| `templates/blog/` | 上传演示入口可新增独立页，保持其他成员模板边界 |
| `blog/test_week910_functional.py`（新增） | 本轮功能和回归测试，使用Django Client验证HTTP/表单/数据库结果 |

SZX同时负责公共settings、总路由、媒体路由、共享信号与配置入口的集成。其余App由对应成员实施；本轮先完成B91/B92，文章撤稿/搜索索引全生命周期仍作为另列待办，不能连带写成已经解决。本任务单供组长自用，SZX负责实现与集成。

## 3. 两个必做功能与一个选做项

以下数量是本组工作安排；课件硬要求是优化系统并覆盖每个App功能测试，不是老师规定“每人恰好两个”。先完成可运行、可验证的必做项，再做选做。

### B91（必做）浏览量原子更新

保持Article.viewed()调用接口，使用数据库F表达式/条件更新完成增量；同步当前实例的最终整数值，避免把F表达式留在实例导致后续保存再次递增。处理记录不存在的边界；核对详情缓存与实际增量展示。用两个同时读到旧值的实例复现丢更新，再验证两次调用累计+2。

### B92（必做）可用的受控图片上传

按共享约定改造blog:upload：有效staff、POST、CSRF、file字段、5MiB和2000万像素阈值，允许JPEG/PNG/WEBP；用Pillow验证实际内容并生成服务端文件名，保存到媒体存储，返回统一JSON。非法/超限/伪装图片不给部分成功结果，不遗留写入文件；保留正常图片可在浏览器打开的证据。

### B93（选做）分类防环与可观察错误

Category增加自指/多层环校验，后台表单回显错误；分类树遍历对历史环有界退出。覆盖根、普通多层、自己为父、祖先回挂；已有分类/文章URL保持。

## 4. 统一接口与配置（实施前遵守）

[共享配置与接口约定v1.1](../共享配置与接口约定.md)已由SZX统一制定；本任务单可单独转发，完整契约从同步后的仓库取得。公共settings、总路由和共享信号仅SZX集成。

```python
from djangoblog.maintenance_config import get_maintenance_option

options = get_maintenance_option("UPLOAD_MAX_BYTES")
```

入口及B92配置接入已实现；下列任务要求保留为验收依据。修改默认阈值/参数/返回值前交SZX更新统一约定；成员自己的演示配置/测试可用MAINTENANCE_OPTIONS部分覆盖。缓存键使用week910:<app>:<purpose>:<摘要>，敏感标识不明文写入键/日志。

## 5. 必测功能清单

每项保留前置数据、操作/请求、预期、实际结果与证据。对能稳定复现的旧缺陷先保留修复前失败，再验证修复；新增功能保留基线行为与验收证据。不得把预期直接填成“已通过”。

| 编号 | 场景 | 验收结果 |
| --- | --- | --- |
| B-T01 | 首页/分类/标签/归档与已发布详情 | 正常展示；草稿访问规则保持上轮约定 |
| B-T02 | 两个旧值实例依次调用viewed | 数据库累计+2，实例属性是整数 |
| B-T03 | 详情请求后再保存标题 | 浏览数不因遗留F表达式额外递增 |
| B-T04 | 匿名/普通用户/未激活staff上传 | 403；无文件落盘 |
| B-T05 | 缺CSRF或非POST | 403/405；无文件落盘 |
| B-T06 | 合法PNG/JPEG/WEBP上传 | 200 JSON；媒体URL可读取且路径受控 |
| B-T07 | 改名脚本/损坏图片/超大小/超像素 | 400；无残留文件 |
| B-T08 | 带路径文件名与重复文件名 | 服务端命名，不越界覆盖 |
| B-T09 | 后台文章保存、评论区、清缓存接口 | 已有权限、缓存和HTML回归继续通过 |

### 可直接使用的验证命令

在仓库根使用已安装项目依赖的Python3.12环境。先同步组长任务包，以下baseline命令可执行；新测试文件写完后再运行after。旧runner提供SQLite内存、LocMem缓存/邮箱、SimpleEngine，并阻断网络和未mock系统命令；mock真实边界，不把收费模型/真实邮件或系统维护命令当测试。

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/SZX/证据/baseline-tests.json blog.test_comment_lifecycle blog.test_week78_quality blog.test_views blog.test_templatetags blog.test_context_processors blog.test_middleware blog.test_brand_assets blog.test_article_business_logic blog.test_comment_interfaces djangoblog.test_week910_configuration
```

实现本轮功能、创建上述测试模块后：

```powershell
python doc/week7-8/tools/run_isolated_tests.py --result-json doc/week9-10/成员成果/SZX/证据/after-tests.json blog.test_comment_lifecycle blog.test_week78_quality blog.test_views blog.test_templatetags blog.test_context_processors blog.test_middleware blog.test_brand_assets blog.test_article_business_logic blog.test_comment_interfaces djangoblog.test_week910_configuration blog.test_week910_functional
```

需要保留输出时先创建证据目录，使用新文件名保存完整命令、stdout/stderr和返回码。JSON的failures/errors必须核对；测试条数由实际运行填写。覆盖修改前后相同场景，必要时补本App其他标签。

同配置扫描（每次输出目录须是新的，旧证据不覆盖）：

```powershell
python doc/week7-8/tools/scan_app.py blog baseline --output-dir doc/week9-10/成员成果/SZX/证据/baseline-scan
python doc/week7-8/tools/scan_app.py blog after --output-dir doc/week9-10/成员成果/SZX/证据/after-scan
```

工具环境固定doc/week7-8/tools/requirements-quality.txt；扫描发现须读JSON并说明，不能把驱动退出0等同零告警。扫描可追溯是本组执行规范，课程重点仍是功能与基本测试。

## 6. 本地演示顺序

1. 浏览器打开已发布文章，刷新两次并说明计数变化，展示原子更新回归结果。
2. 以staff登录上传正常图片，打开返回的本地媒体URL。
3. 演示未授权、缺CSRF、伪装或超限文件被拒绝；说明测试数据与生产数据分离。

GCY提供settings_demo后，在该配置下本地运行并验证本模块；隔离单测和本地整站功能测试分别记录。个人提交操作脚本、可复现样本和预期画面；集成测试通过后，由组长石兆翔在同一个本地版本上统一讲解并录制MP4，开头列第6组及六人姓名。组员不必单独录制视频。替身与真实外部服务验证分开标注。

## 7. 同步、提交与交付

先用git status确认并妥善保存未提交工作，再在个人分支合入最新develop；避免从上轮旧个人代码直接重做。命令在本人已有仓库根执行：

```powershell
git fetch origin
git switch szx_branch
git merge origin/develop
New-Item -ItemType Directory -Force -Path doc/week9-10/成员成果/SZX/证据 | Out-Null
git rev-parse HEAD | Set-Content -Encoding utf8 -LiteralPath doc/week9-10/成员成果/SZX/证据/start-commit.txt
```

功能/测试/本人素材分批提交，署名使用本人第9—10周标识并保留旧作者；推送实际个人分支后发起到develop的PR：

```powershell
git status --short
git push origin szx_branch
```

交付到`doc/week9-10/成员成果/SZX/`：

- `实现说明.md`：按本任务ID写现象/目标、方案、改动文件和符号、实际完成/未完成、迁移与兼容说明、依赖及提交号。
- `功能测试记录.md`：按上表逐项写实际结果，含本App既有功能、正常/失败/权限边界；隔离与本地环境分别记录。
- `演示脚本.md`：本地前置、逐步操作、解说、可演示结果、使用的替身或时长覆盖。
- `代码变更统计.md`：功能ID对应文件/提交，业务/测试/文档分开；记录Git新增/删除行并说明哪些属于修改，不能把新增行简单等同修改行。
- `证据/`：真实测试结果、扫描JSON、完整命令/日志及必要截图；不提交凭据、环境目录、数据库、依赖缓存。

组长提供的[维护素材模板](../维护素材模板.md)可复制到本人目录；未执行的结果保持“未执行”。Word正式报告由组长汇总，使用宋体/Times New Roman和黑色文字；视频MP4，不打包。

复核搭档GCY按本轮实际版本写复核意见，SZX负责最终集成。课件写master，当前仓库主分支main；最终交付分支由组长统一处理，成员只提交个人分支到develop。

## 8. 官方参考

- [F表达式与更新](https://docs.djangoproject.com/en/5.2/ref/models/expressions/)
- [文件上传](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/)
