"""SZX代SY：从真实扫描、回归和源码差分生成四份课程素材及接手清单。"""

import ast
import hashlib
import io
import json
import subprocess
import tokenize
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEEK = ROOT / 'doc/week7-8'
MEMBER = WEEK / '成员成果/SY'
EVIDENCE = MEMBER / '原始工具结果/2026-11-02-szx-takeover'
BASE = 'e52f5d0f3ed5a58110c9abf29fd4cb1e0b74c9bb'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def write_md(name, text):
    (MEMBER / name).write_text(text.strip() + '\n', encoding='utf-8', newline='\n')


def equivalent(data, expected):
    lf = data.replace(b'\r\n', b'\n')
    return expected in {digest(data), digest(lf), digest(lf.replace(b'\n', b'\r\n'))}


def main():
    after = json.loads((EVIDENCE / 'after/manifest.json').read_text('utf-8'))
    before = json.loads((EVIDENCE / 'before/manifest.json').read_text('utf-8'))
    assert after['test_result']['failures'] == after['test_result']['errors'] == 0
    assert after['regression_ast_sha256'] == before['regression_ast_sha256']
    for name, expected in after['source_sha256'].items():
        assert equivalent((ROOT / name).read_bytes(), expected), name
    code_ref = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    after.update(verified_code_commit=code_ref, test_count=after['test_result']['tests_run'], failure_count=0)
    after['source_sha256']['doc/week7-8/tools/run_isolated_tests.py'] = digest((WEEK / 'tools/run_isolated_tests.py').read_bytes())
    write_json(EVIDENCE / 'after/manifest.json', after)
    scan = json.loads((EVIDENCE / 'after/scan-manifest.json').read_text('utf-8'))
    baseline = json.loads((EVIDENCE / 'before/scan-manifest.json').read_text('utf-8'))
    assert scan['config_sha256'] == baseline['config_sha256']
    assert [row['path'] for row in scan['files']] == [row['path'] for row in baseline['files']]
    annotations = []
    for item in scan['files']:
        path = 'src/DjangoBlog/' + item['path']
        data = (ROOT / path).read_bytes()
        source = data.decode('utf-8-sig')
        original = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT).decode('utf-8-sig')
        old = [token for token in tokenize.generate_tokens(io.StringIO(original).readline) if token.type == tokenize.COMMENT]
        new = [token for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type == tokenize.COMMENT]
        remaining = Counter(token.string for token in old)
        added = []
        for token in new:
            if remaining[token.string]:
                remaining[token.string] -= 1
            else:
                added.append(token)
        assert not any(count and ('GZX' in text or text.startswith('# 未命中') or text.startswith('# 收到消息'))
                       for text, count in remaining.items()), path
        tree = ast.parse(source)
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        groups = {'module': 0, 'function': 0, 'core': 0}
        for token in added:
            if 'SZX（代SY，第7—8周）' not in token.string:
                continue
            if token.start[0] == 1:
                groups['module'] += 1
            elif any(node.lineno < token.start[0] < node.body[0].lineno for node in functions):
                groups['function'] += 1
            else:
                groups['core'] += 1
        annotations.append({
            'path': path, 'physical_lines': len(source.splitlines()), 'sha256': digest(data),
            'new_comment_lines': [token.start[0] for token in added],
            'new_signed_lines': [token.start[0] for token in added if 'SZX（代SY，第7—8周）' in token.string],
            'existing_gzx_signed_lines': [token.start[0] for token in new if 'GZX' in token.string],
            'annotation_groups': groups,
            'ast_unchanged': ast.dump(ast.parse(source)) == ast.dump(ast.parse(original)),
        })
    total = {key: sum(item[key] for item in scan['files']) for key in ['physical_lines', 'code_token_lines', 'classes', 'functions_and_methods']}
    total.update(files=len(scan['files']), new_comment_lines=sum(len(row['new_comment_lines']) for row in annotations),
                 new_signed_lines=sum(len(row['new_signed_lines']) for row in annotations))
    total['annotation_groups'] = {tier: sum(row['annotation_groups'][tier] for row in annotations)
                                  for tier in ['module', 'function', 'core']}
    record = {'date': '2026-11-02', 'original_owner': 'SY 宋洋', 'executor': 'SZX 石兆翔（组长代办）',
              'authorization': '组长确认SY无法完成，由SZX接手其模块工作',
              'sy_stage_commit': 'b4fe17ba9a146021cb5d6b817fa43c10e0cc65be',
              'baseline_commit': BASE, 'verified_code_commit': code_ref, 'metrics': total,
              'baseline_scan': baseline['summary'], 'after_scan': scan['summary'],
              'test_result': after['test_result'], 'before_regression': before['test_result'],
              'annotations': annotations, 'review_mode': 'SZX代办专项核查；不冒充WZY/SY本人签署',
              'remaining': ['管理员配置shell命令的信任边界', '并发确认的原子消费与会话TTL',
                            '生产凭据/模型可用性和真实微信回调', 'MySQL/Redis/SMTP与子进程树终止另行验证']}
    write_json(MEMBER / '接手完成清单.json', record)
    attribution = '''模块归属：宋洋SY（2415304330）；实际执行：石兆翔SZX（组长代办）。
依据组长2026-11-02接手指示，保留SY原始提交b4fe17b及其baseline；后续阅读说明、修复、注释、验证及本文由SZX完成，不写成SY本人独立完成。'''
    summary = f'统一11个业务文件：Ruff {baseline["summary"]["ruff"]}→{scan["summary"]["ruff"]}；Bandit {baseline["summary"]["bandit"]}→{scan["summary"]["bandit"]}。当前所选联合回归{after["test_count"]}项通过，其中servermanager {after["test_result"]["per_app"]["servermanager"]}项。'
    write_md('质量分析片段.md', f'''# 第7—8周 servermanager 质量分析（SZX代SY）

{attribution}

## 1. 范围、规模与阅读路线

本轮业务Python {total['files']}文件、物理{total['physical_lines']}行、代码token覆盖{total['code_token_lines']}行、类{total['classes']}个、函数/方法{total['functions_and_methods']}个。测试和迁移另列，不混入分母。
三条实际阅读路线：`/robot→make_view→过滤器→BlogApi`；`echo→MessageHandler→会话/口令/确认→CommandHandler`；`MemcacheStorage/FileStorage`与共享SMTP→EmailSendLog两条独立链。weather/idcard仍为占位，不记实现。

## 2. 人工四类分析

| 维度 | 源码观察与处理 |
| --- | --- |
| 风格 | 修复SY快照缩进错误与方法嵌套，统一导入/行长，保留历史commands模型名和GZX注释；新增说明署名SZX代SY。 |
| 设计 | 消息分发、查询、命令与会话适配分层；移除对象反序列化，状态只保存标量JSON；文件存储回退不删除已有数据。 |
| 正面技能 | 正则分发、ORM发布态过滤、会话接口、事务外部依赖mock、显式超时、取消异常向上传播均有明确边界。 |
| 缺陷 | SR01—SR07如下；静态发现不直接等同漏洞，命令shell语义有意保留并单列风险。 |

## 3. 已核实问题及改进

| 编号 | 问题 | 当前处理与证据 |
| --- | --- | --- |
| SR01 | SY快照commonapi/tests两处缩进错误，robot方法嵌套进构造函数 | 修复模块/类层级，AST记录保留在before；原提交未改写。 |
| SR02 | ChatCompletion旧SDK调用、失败仅非空断言 | 按固定openai2.54客户端调用，显式超时/关闭重试，测试成功、缺key、空结果和API失败；未真实调用模型。 |
| SR03 | jsonpickle按会话恢复Python对象 | 改纯JSON和严格字段/类型验证；旧对象格式失效为未认证状态。 |
| SR04 | 测试口令特殊分支与弱断言；重复Y重放待执行项 | 使用配置口令与显式测试覆盖，第三次失败结束验证；先消费待执行项，顺序重复Y不重放。 |
| SR05 | 近期/分类未筛发布态，搜索可返回陈旧私有对象 | ORM限定已发布文章；搜索及渲染再次拒绝草稿、页面与已删除对象。 |
| SR06 | 缓存故障阻断启动，回退前删除会话文件 | 探测失败返回不可用并清理探测键；复用既有文件，不自动删除。 |
| SR07 | 旧测试会直接外呼、执行shell，失败也可能通过 | 旧2项改为实际接口的mock断言；新增31项，联合runner同时阻断网络与未mock系统命令。 |

## 4. 工具及遗留边界

{summary}
Bandit保留B404导入subprocess、B602管理员配置shell执行，两条落在同一功能边界；B605迁移到新执行API不等于额外修复独立漏洞。旧B301对象恢复、B105硬编码测试口令已移除。未用nosec隐藏。
生产必须配置管理员口令/机器人令牌；缓存完整性、并发确认原子性、会话TTL、输出内存上限及子进程树终止留后续计划，不作全部安全问题已消除的声明。
''')
    write_md('工具与验证记录.md', f'''# 第7—8周 servermanager 工具与验证（SZX代SY）

{attribution}

## 1. 版本、范围与原记录

基线`{BASE}`与接手代码`{code_ref}`。SY原baseline的11个文件对应旧194ea29，其工具配置未随快照提交、哈希与组内不同；原3个JSON保留，不把它直接当作同配置对比。
补扫采用Ruff0.17.1、Bandit1.9.4，当前组内ruff.toml/bandit.yaml，target=py312，cwd为完整项目包目录，固定11个业务文件，测试/迁移排除。不启动Django进行静态扫描。

## 2. 真实结果

{summary}
before新增31项：{before['test_result']['failures']}失败、{before['test_result']['errors']}错误、其余通过；after联合{after['test_count']}项失败0、错误0、跳过0。前后新增回归AST相同，修复前日志和测试源码保留。
联合分母：blog158、accounts84、comments50、oauth26、djangoblog39、servermanager33。不是全仓所有测试。

## 3. 环境、命令与隔离

Python{after['python']}、Django{after['django']}、OpenAI SDK{after['openai']}。运行依赖安装在临时目录，SQLite测试不需要mysqlclient；未改生产依赖文件。

```powershell
python doc/week7-8/tools/verify_sy_takeover.py before --output-dir <新的基线证据目录>
python doc/week7-8/tools/verify_sy_takeover.py after --output-dir <新的改进证据目录>
```

Python环境需安装仓库固定依赖及质量工具。脚本拒绝覆盖已有目录，实际完整命令、返回码、配置与源码指纹见manifest。
SQLite内存、LocMem缓存/邮箱、SimpleEngine；HTTP/socket及未mock的os.popen/os.system/subprocess被阻断。聊天和命令均用mock；无真实微信回调、OpenAI请求、系统命令、MySQL/Redis/CDN或SMTP投递验证。

## 4. 原始证据与告警

- [before](原始工具结果/2026-11-02-szx-takeover/before/manifest.json)：统一基线、失败回归、SY快照AST。
- [after](原始工具结果/2026-11-02-szx-takeover/after/manifest.json)：390项结果、源码指纹、统一复扫。
- `after-initial/`保留格式整理前的中间复扫，不替代最终after。
- Bandit B404/B602按管理员配置shell的残留边界保留，未加忽略标记；命令超时不等于任意子进程树完整终止。
- [OpenAI Python官方文档](https://developers.openai.com/api/reference/python)与安装SDK用于核对客户端调用。默认模型ID只作兼容保留，可配置Django的OPENAI_CHAT_MODEL；没有证明该ID在某账号上当前可用。

## 5. 核查安排

按组长接手指示，以[组长代办专项核查](接手与专项核查记录.md)记录实际执行。没有WZY/SY对最终代办版本的本人签名，不冒写其独立复核。
''')
    rows = '\n'.join(f'| {item["path"].removeprefix("src/DjangoBlog/")} | {item["annotation_groups"]["module"]}/{item["annotation_groups"]["function"]}/{item["annotation_groups"]["core"]} | {len(item["new_signed_lines"])} | {len(item["new_comment_lines"])} | {", ".join(map(str,item["new_comment_lines"])) or "—"} | {"相同" if item["ast_unchanged"] else "有功能改动"} |' for item in annotations)
    write_md('注释统计.md', f'''# 第7—8周 servermanager 注释统计（SZX代SY）

{attribution}

基线`{BASE}`；当前代码`{code_ref}`。统计仅11个业务文件的COMMENT token，不包含测试、迁移、docstring或这些材料。
按文件注释文本多重集差分，移动/格式化既有说明不计新增；新增含替换无署名模板占位的有效说明。署名前缀为`SZX（代SY，第7—8周）`，不伪装SY署名。

| 文件 | 模块/函数/核心组数 | 新署名说明行 | 新增/改写物理注释行 | 当前行号 | AST与基线 |
| --- | --- | ---: | ---: | --- | --- |
{rows}

合计：{total['new_signed_lines']}行新署名说明、{total['new_comment_lines']}行新增/改写物理注释；模块/函数/核心组数为{total['annotation_groups']['module']}/{total['annotation_groups']['function']}/{total['annotation_groups']['core']}。组数按带署名的说明段计，续行单列为物理行；既有GZX说明保留，空包入口不强行添加业务说明。
模块层在核心文件头说明职责；函数层在聊天、查询、会话及命令入口说明输入/失败边界；核心块说明状态验证、确认消费、公开过滤及缓存探测。逐文件哈希和行号见[接手完成清单](接手完成清单.json)。
''')
    write_md('改进计划.md', f'''# 第7—8周 servermanager 改进计划（SZX代SY）

{attribution}

## 已实施

SR01缩进与方法层级、SR02当前SDK适配、SR03纯JSON、SR04配置口令/三次失败/顺序确认消费、SR05公开过滤、SR06非破坏存储回退、SR07隔离测试均已实施；具体方案和验证见质量分析及工具记录。{summary}

## 后续优化

| 优先级 | 工作 | 建议责任 | 验收 |
| --- | --- | --- | --- |
| P1 | 部署时显式配置机器人令牌、管理员口令和聊天可用模型；真实回调鉴权联调 | 组长/部署维护人 | 不依赖仓库兼容默认值；错误凭据拒绝；不在日志暴露密钥。 |
| P1 | 管理命令改为结构化允许列表，进一步限制shell能力 | 运维模块维护人 | 非允许参数拒绝，合法命令成功，退出/超时有明确结果。 |
| P2 | 并发确认的原子消费、会话TTL和分布式一致性 | 运维模块维护人 | 同一待执行项并发确认至多执行一次，过期会话失效。 |
| P2 | 限制命令输出内存并明确子进程树终止策略 | 运维模块维护人 | 超大输出受限，超时后无遗留子任务；按部署平台验证。 |
| P2 | 搜索索引撤稿联动与启动外部依赖优化 | SZX/共享模块维护人 | 撤稿不命中；无索引服务时普通启动可用，真实环境单测。 |
| P2 | 损坏/无权限文件会话的运维恢复流程 | 部署维护人 | 保留原数据并给出可观察失败，不自动删除已有会话。 |

这些为后续计划，不作已实施或SY本人承诺。组长代办记录与原作者贡献分别保留。
''')
    write_md('接手与专项核查记录.md', '''# SY模块接手与组长专项核查

- 日期：2026-11-02；执行与汇总：石兆翔SZX。
- 授权：组长确认SY无法完成，由我们接手其部分。SY原快照和基线保留；后续由SZX完成，不记为SY个人阅读或独立编码。
- 原WZY↔SY配对按实际执行调整为组长代办专项核查；这不是WZY或SY本人对最终代办版本的签名。

| 方向/事项 | 实际执行 | 核查依据与结论 |
| --- | --- | --- |
| 代SY核查WZY comments | SZX组长集成核查 | 核对R4单次查询、R5后台/共享信号/完整级联及归档边界；原318项阶段记录保留，当前联合390项中的comments50项通过，相关源码未被SY接手覆盖。 |
| servermanager接手验收 | SZX实现与自检、组长汇总 | 31项新回归在改进前暴露22失败6错误；最终33项本App/390项联合通过，统一11文件Ruff0/Bandit2，无解析错误。 |
| 独立本人确认的边界 | 未取得WZY/SY对最终代办版的单独意见 | 不把组长自检写成独立同伴签署；执行方式及限制写入小组报告，而不继续以“等SY本人补交”搁置交付。 |

当前代码、原始日志、扫描与注释依据见四份材料和接手完成清单。SZX/GCY及YFY/GZX的四方向互查仍沿用组长已确认补录，不改写其原意见。
''')
    print(json.dumps({'code_ref': code_ref, 'metrics': total, 'tests': after['test_result']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
