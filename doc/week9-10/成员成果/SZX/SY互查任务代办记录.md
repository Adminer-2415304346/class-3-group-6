# 第9—10周宋洋互查任务代办记录

- 日期 2026-11-15
- 原分工 宋洋（SY）复核王子扬（WZY）的 `comments` C91、C92。
- 执行方式 石兆翔（SZX）组长代办验收。宋洋本人的独立复核意见待取得。
- 验收版本 `develop@1cafb125605ca4f359a23990b316919971fde32e`，评论模块本轮最近的源码和测试提交为 `6be622e`。

| 验收项 | 核对结果 |
| --- | --- |
| C91 评论输入与目标，C-T01～C-T04 | 合法顶层评论和同文章回复保存成功，跳转到新评论，审核开关生效。正文去首尾空白后按共享配置校验，默认 2000 字符可保存，纯空白和 2001 字符有明确提示。草稿或不存在的文章返回 404。文章级评论关闭、无效父评论或跨文章回复均回显表单错误。已发布的独立页面沿用既有规则。 |
| C92 重复与限频，C-T05～C-T07 | 先判重复，再判过频。重复键按用户、文章、规范化正文和回复目标区分，默认窗口 120 秒。同一用户两次成功发布的默认间隔为 30 秒。两次请求通过预检时，唯一约束只允许先占用状态的请求保存评论。 |
| C92 回滚与回归，C-T08～C-T09 | 状态占用和评论保存处于同一事务，模拟入库失败后确认没有冷却残留、通知或错误缓存失效，随后可正常提交。表情切换保持独立，R4 表情接口、R5 缓存、审核可见性及级联删除回归通过。 |

本次采用仓库隔离测试器，运行环境为 Python 3.12.10、Django 5.2.17、内存 SQLite 与本地缓存和邮件替身。复跑 **90 项全部通过**，其中 `comments` 80 项（本轮 C-T01～C-T09 对应 30 项），共享配置 10 项，失败、错误、跳过均为 0。并发结果基于本次隔离测试中的状态抢占和请求调度。C93 为本组选做，本轮未实施。

复跑命令在仓库根目录执行。标准错误原样保存，包含预期 404 和模拟入库异常的日志，最终退出码 0。

```powershell
$evidence = 'doc/week9-10/成员成果/SZX/证据/复核-WZY-comments'
python doc/week7-8/tools/run_isolated_tests.py comments.test_reaction_snapshot comments.tests comments.test_views comments.test_comment_business_logic comments.test_quality_r45 comments.test_week910_functional djangoblog.test_week910_configuration --result-json "$evidence/tests.json" 1> "$evidence/tests.stdout.log" 2> "$evidence/tests.stderr.log"
```

**代办验收结论**　C91、C92 通过。 [测试数据](证据/复核-WZY-comments/tests.json) · [标准输出](证据/复核-WZY-comments/tests.stdout.log) · [详细测试日志](证据/复核-WZY-comments/tests.stderr.log) · [王子扬的功能测试记录](../WZY/功能测试记录.md)
