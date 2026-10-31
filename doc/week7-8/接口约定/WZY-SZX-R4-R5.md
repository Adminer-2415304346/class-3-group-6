# WZY与SZX：R4/R5接口约定 v1

日期：2026-10-31。依据：WZY提交`186cb680de48b6b1ee8955c0a3651e4d8d09a595`的《改进计划》P4。
本轮集成基线：`develop@e4c7d3d1311b3a22c0133c4d18d8e9386c6ba479`。
本文件完成SZX侧的消费接口确认并提供可调用入口；不代填WZY、GCY的确认，也不把待接入项写成已修复。

| 条目 | WZY原问题 | SZX本轮完成 | 仍由对方完成 |
| --- | --- | --- | --- |
| R4 | `Comment.get_reactions_summary`逐表情查用户名、当前用户状态，查询过多 | 确定SSR/API兼容结构、当前用户隔离和验收要求；修复SSR属性转义并补消费方回归 | WZY实现查询优化并提供查询数对比；涉及共享前端改造再与SY/SZX确认 |
| R5 | 后台批量启停走`QuerySet.update`，不触发保存信号与缓存失效 | 提供`blog.comment_cache.invalidate_comment_caches`、真实缓存键及提交时机；补事务/回滚/批量示例验证 | WZY接入后台写入口；GCY协调普通保存、禁用、删除信号及整页缓存策略；双方补集成验证 |

## 1. R4：保持接口，优化内部查询

### 1.1 Python入口及返回结构

入口保持`comment.get_reactions_summary(user=None) -> dict`，不新增必填参数。
传入当前请求的已认证用户，匿名请求传`None`或`AnonymousUser`。SSR调用仍为：

```python
comment_item.get_reactions_summary(request.user if request.user.is_authenticated else None)
```

有记录的emoji才出现在结果中；没有记录返回`{}`。结构示例：

```json
{
  "👍": {"count": 12, "has_reacted": true, "users": ["Alice", "Bob"]}
}
```

| 字段 | 约定 |
| --- | --- |
| 顶层键 | 使用`CommentReaction.REACTION_CHOICES`的emoji原值，保留`❤️`等变体选择符，不改为英文标识 |
| `count` | 当前评论、该emoji的实际记录总数，整数；不是tooltip名单长度 |
| `has_reacted` | 布尔值，仅表示当前查看用户是否参与；匿名一律`false` |
| `users` | 最多10个字符串，使用`nickname or username`；不暴露邮箱、用户对象或用户ID；优化后按reaction主键升序确定前10个 |

即使当前用户不在前10个展示名单中，`has_reacted`也必须正确。
不同emoji独立切换；优化不改为“一个人只能选一种emoji”。返回Python数据，不返回拼好的HTML。

### 1.2 HTTP与SSR消费约定

- GET路由仍为`/comment/<comment_id>/react`，成功返回`{"success": true, "reactions": {...}}`。
- POST字段仍为`reaction_type=<emoji>`，成功返回`success`、`action`（`added`或`removed`）、`reactions`。
- 本轮不更改现有登录、CSRF、评论公开状态检查和错误状态码；可见性判断仍由入口视图承担。
- `frontend/src/components/reactionPicker.js`继续直接读取`data.reactions`；不要求前端另传“用户已点集合”。客户端信息不能作为服务端统计或权限的依据。
- `has_reacted`与请求用户相关，不得把包含它的整份结果仅按comment_id放入共享缓存；若以后加缓存，应拆公共计数与用户状态并约定reaction写入失效。
- SZX保证`comment_item_modern.html`中的JSON按HTML属性上下文强制转义：`|to_json|force_escape`。浏览器读取`dataset.reactions`后仍得到合法JSON，昵称中的引号/尖括号不能产生新属性。

### 1.3 查询预算与验收

1. 测量边界只包括一次`get_reactions_summary`，不把登录、取Comment或整页渲染查询混进统计。
2. 当前实现有k种已参与emoji时：已登录约`1 + 2k`次，匿名约`1 + k`次；“17次”是8种emoji且登录时的案例，不是每条评论固定开销。
3. WZY优化目标：同一接口最多2次数据库查询，查询次数不随emoji种类增长；不能为减查询而漏计、截断count或丢失当前用户状态。
4. 至少比较0/1/8种emoji、匿名/登录、超过10名参与者、当前用户在名单之外、其他评论数据隔离及POST增删后结果。
5. 若使用单次加载全部reaction记录，需说明高参与量下的内存边界；本轮不默认增加全量预取或整页reaction批量接口。
6. 兼容回归位于`blog.test_comment_interfaces.ReactionSummaryInterfaceTests`。其中查询数只测量、不锁死旧算法；WZY另补优化目标断言（如`assertNumQueries(1/2)`）。

## 2. R5：明确缓存所有权与失效时机

### 2.1 SZX已提供的入口

```python
from blog.comment_cache import invalidate_comment_caches

invalidate_comment_caches(article_ids, using="default")
```

- `article_ids`是正整数文章主键的可迭代对象；空集合无操作，重复ID去重，非法元素抛`ValueError`。
- 函数立即读取并固定ID与键清单，返回`None`，不查文章表、不写数据库、不发邮件。
- `using`传写操作的`queryset.db`。它选择`transaction.on_commit`所属数据库连接，不改变当前项目默认缓存后端或既有键命名。
- 原子事务内在成功提交后删除缓存；回滚不删除；事务外按Django的on_commit规则立即执行。
- 函数不吞缓存后端异常，返回`None`也不是后台成功清理的独立证明；调用方仍需保留错误日志和实际验证。

### 2.2 实际删除的键

| 缓存 | 真实键或构造方式 | 说明 |
| --- | --- | --- |
| 每篇文章评论QuerySet | `CacheKey.ARTICLE_COMMENTS.format(article_id=id)`，即`article_comments_<id>` | 每个受影响文章分别删除 |
| 旧评论模板片段 | `make_template_fragment_key('article_comments', [str(id)])` | 与现有`delete_view_cache`兼容的防御性清理，不表示当前模板启用了这个片段缓存 |
| 五种侧栏 | `sidebari`、`sidebarl`、`sidebarp`、`sidebara`、`sidebars` | 由`LinkShowType.values`生成，匹配`load_sidebar`真实写入；不是`sidebar_<type>` |
| 站点导航/配置上下文 | `seo_processor` | 与现有评论保存路径保持一致 |

禁止通过`cache.clear()`实现本项，避免清掉密码重置验证码等无关状态。
不删除其他文章的评论键。这个入口也不清外部CDN、浏览器响应缓存或任意整页响应缓存。

### 2.3 WZY接入位置及示例

WZY负责`comments/admin.py`的启用、禁用，以及后台单条修改、删除、批量删除等写路径；GCY负责共享信号的收敛。
先捕获受影响文章ID，再执行更新/删除；删除后不能再从原QuerySet取ID。
示例只展示批量启用的最小调用位置，未作为本次补丁改入WZY文件：

```python
from django.db import transaction
from blog.comment_cache import invalidate_comment_caches

using = queryset.db
with transaction.atomic(using=using):
    article_ids = list(queryset.order_by().values_list("article_id", flat=True).distinct())
    queryset.update(is_enable=True)
    invalidate_comment_caches(article_ids, using=using)
```

禁用同理；删除应在删除前取ID，并覆盖级联删除涉及的文章。
如果筛选集合可能并发变化，写入方还需固定待改主键集合/按数据库能力锁行；本例不作为并发一致性证明。
启停动作不能用逐条`save()`补发信号来冒充失效策略，否则可能重复发评论邮件。

### 2.4 GCY/SZX共享边界

- 现有`model_post_save_callback`只在Comment的`is_enable=True`分支清缓存；普通禁用、删除仍需接入。GCY应统一调用同一入口，并覆盖`post_delete`，不靠批量`update`自动发信号。
- 若修改评论归属文章，应覆盖旧、新两个article_id；只拿保存后的ID不够。关联用户/文章的级联删除也要纳入测试。
- 缓存失效不承担通知策略。是否发邮件、在哪个事务阶段发送由通知流程单独约定，不由本入口自动触发。
- `Article.comment_list()`继续返回QuerySet，并保留当前空集合重查行为；完成批量审核/禁用/删除验收前，不重新启用此前撤回的空缓存优化。
- **整页边界仍待落实**：当前详情页没有`cache_page`包装；`archives.html`有一小时整页缓存，HTML中含侧栏。仅删数据键不能清掉已缓存的归档HTML，因此不能据此宣告“全站页面侧栏立即刷新”。SZX/GCY需要另行选择归档只缓存数据或可靠的整页失效方案，并验证域名、协议、端口和响应变体；不通过硬编码`http:80`宣称全部覆盖。

### 2.5 R5最终验收条件

- 首条待审评论批量通过后，重新请求文章详情立即可见。
- 已缓存的非空评论集合在批量禁用/删除后不再展示旧评论，相关侧栏也刷新。
- 一次操作覆盖多篇文章、父评论级联删除、普通后台单条修改、数据库回滚均有断言。
- 无关验证码和其他文章缓存保留；清缓存不触发重复邮件。
- 新请求使用同一QuerySet接口；不保证已经取到旧数据的并发请求或旧模型实例自动刷新。
- 归档整页缓存等边界单独验证；未接入或未验证时，R5状态仍为待完成。

## 3. 本次验证及交接状态

验证命令（使用项目依赖环境，在仓库根执行）：

```powershell
.\src\DjangoBlog\.venv\Scripts\python.exe doc/week7-8/tools/run_isolated_tests.py blog.test_comment_interfaces
```

对应测试同时覆盖R4原有返回结构/SSR/API兼容，以及R5新入口的提交后失效、回滚、去重、ID快照、空输入和批量调用示例。
实际结果：新增14条接口回归，相关范围共114条测试通过；当前R4登录17次/匿名9次的查询成本仍未优化。
原始记录及[验证结果](../成员成果/SZX/接口验证/2026-10-31/验证结果.md)位于SZX接口验证目录；隔离边界为SQLite内存、内存缓存/邮箱、禁用外部搜索与HTTP/套接字外呼。
不代表真实MySQL/Redis/CDN联调，不代替WZY最终性能测试或其后台入口接入验收。

| 确认方 | 当前状态 | 待完成 |
| --- | --- | --- |
| SZX侧 | 已确认消费结构并提供失效入口，14条新增回归及114条相关回归通过 | 归档整页缓存策略与共享信号接入仍需联调 |
| WZY侧 | 已确认结构/预算并接入入口，提交 `c47b944` | 归档整页缓存与共享信号接入仍需与 SZX/GCY 联调，R5 最终验收待完成 |
| GCY侧 | 未代为确认 | 确认信号/删除/旧新归属处理和整页缓存方案，实施后追加证据 |

### WZY 侧确认（2026-10-31，提交 `c47b944`）

- R4：保持 `get_reactions_summary(user=None)` 入口与返回结构，改为「1 次聚合计数 + 1 次流式读全部 reaction」，匿名/登录均恒 2 次查询；`R4_QUERY_COUNTS={"anonymous":2,"authenticated":2}`（优化前登录 17 / 匿名 9）。has_reacted 对名单外查看者仍正确；users 按 reaction 主键升序取前 10，暴露昵称/用户名，不含邮箱与用户 ID；内存边界见改进计划 P4（高参与量只留存 O(表情数×10+1)）。
- R5：`comments/admin.py` 的启/禁用动作、单条修改（`save_model` 覆盖旧/新文章 ID）、单条删除（`delete_model` 含直接子回复）、批量删除（`delete_queryset` 先捕获 ID）均已接入 `invalidate_comment_caches`，`transaction.on_commit` 后失效，不逐条 save()。
- 回归：新增 `comments/test_quality_r45.py`（R4 断言 4 + R5 失效 4）；`blog.test_comment_interfaces` 14 条保持通过；完整 comments+SZX 共 61 tests OK、`ISOLATED_TEST_FAILURES=0`。
- 未完成（非 WZY 侧）：GCY 共享信号收敛（普通禁用/删除、post_delete、改归属旧新 ID）与 SZX/GCY 归档整页缓存方案未接入，故 R5 最终验收仍为待完成。

成员按个人分支提交并合入develop。main的最终合并由组长在全组完成后执行。
