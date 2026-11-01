"""Build course-template DOCX reports from confirmed facts and repository evidence.

Requires python-docx. Reads source as text/AST only; never starts Django or exports PDF.
"""

import ast
import hashlib
import io
import json
import subprocess
import tokenize
import warnings
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[3]
WEEK = ROOT / 'doc/week7-8'
FACTS_PATH = WEEK / 'content/week78_confirmed_facts.json'
FACTS = json.loads(FACTS_PATH.read_text(encoding='utf-8'))
MEMBERS = FACTS['members']
SOURCE_REF = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
SOURCE_BRANCH = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
SOURCE_LABEL = f'{SOURCE_BRANCH}@{SOURCE_REF[:7]}'
SOURCE_URL = 'https://github.com/Adminer-2415304346/class-3-group-6'
OUTPUTS = {
    'coding': WEEK / 'AI Agent工程实践-Python语言编码规范.docx',
    'quality': WEEK / 'AI Agent工程实践-开源软件质量分析报告.docx',
}
RECORD = WEEK / '文档编制记录'
BLACK = '000000'

REVIEW_CHECKS = [
    ('RC01', '版本与归属', '确认分支、App、基线/改进提交；保留原作者和补修者；先同步develop。'),
    ('RC02', '阅读与注释', '模块、关键函数及核心块有职责/理由/边界说明；逐文件统计明确新增、修订与既有。'),
    ('RC03', '人工分析', '风格、设计、技能正例、缺陷四类观察均有路径/符号/可复现依据，候选风险单列。'),
    ('RC04', '扫描可比性', '前后工具版本、规则、目标版本、cwd、文件和排除范围一致；保存源码/配置哈希。'),
    ('RC05', '改进与回归', '至少一项适当改进有验证；必要时保留修复前失败证据；不以语法通过代替行为测试。'),
    ('RC06', '数据与状态', '0与未测分开；告警、误报、解析错误分别记录；测试分母/隔离边界和遗留项明确。'),
    ('RC07', '跨App契约', '核对参数/返回类型、权限、缓存键及事务时机；覆盖普通写入、批量与完整级联路径。'),
    ('RC08', '安全与副作用', '检查HTTP方法/身份/CSRF、输入归属、HTML上下文、密钥与随机值、外呼超时。'),
    ('RC09', '提交与材料', '只提交本轮范围及必要证据；无虚拟环境/密钥；Word、MD、代码版本及数字可追溯。'),
    ('RC10', '本人确认', '复核人填写日期、问题、处理及结论；未确认留待补；集成工具核查不代替本人签署。'),
]

PLAN_ROWS = [
    ('第7周任务阶段', '精读/三层注释、人工四类分析、基线与规范草稿', '各App主责；SZX统筹', '源码说明、四份素材、可复核baseline', '按第7周任务安排'),
    ('第8周任务阶段', '适当改进、回归验证、同配置复扫及互查', '各App主责与互查搭档', '修复及测试证据、after、互查结论', '按第8周任务安排'),
    ('11月2日接手', '按组长指示由SZX完成SY模块、素材和专项核查', 'SZX代SY', '原快照保留；390项联合回归、统一复扫和四份材料', '2026-11-02完成'),
    ('汇总与交付', '更新六App总表、规范/质量Word和下一步计划', 'SZX汇总；组长负责最终提交', '结构/分页检查；个人分支提交develop，main由组长决定', '本轮汇总；合并见PR38'),
]

OPTIMIZATIONS = [
    ('P1', '部署与复核', '生产凭据/真实回调联调，补强接手版本的独立复核', '组长/部署维护人', '不用兼容默认凭据；实际复核与代办自检分别留痕'),
    ('P1', '文章与搜索失效', '统一文章批量发布/撤稿、普通删除与搜索索引的生命周期', 'SZX/GCY，协调WZY', '撤稿不再公开展示/搜索命中；相关缓存与索引验证'),
    ('P1', 'OAuth账号边界', 'state、隐藏ID归属、签名时效/一次性及邮箱归属策略', 'GZX/YFY，协调GCY', '模拟伪造/过期/重复使用及未激活账号，不越权关联'),
    ('P1', '上传与外部依赖', '上传授权/大小/格式/路径；显式搜索初始化与TLS异常策略', 'SZX/GCY', '越权/伪装/超限拒绝；无搜索服务时普通读取可用'),
    ('P1', '找回密码限频', '在secrets与成功消费基础上增加限流、失败次数及配额', 'YFY/GCY', '有效期、次数、重复/过期与正常用户流程均有断言'),
    ('P2', '查询和数据一致性', '浏览量原子更新、分类环校验、评论树与计数查询优化', 'SZX/WZY', '并发计数不丢失；环拒绝；同数据对比查询数及结果'),
    ('P2', '构建与运维', '生产Vite产物、结构化命令白名单、并发确认/会话TTL及输出限制', '组长安排维护人', '产物可用；并发至多一次执行，过期状态失效，输出和子任务受控'),
]

REFERENCES = [
    ('S1', 'PEP 8：项目一致性、缩进、命名和导入等基础建议', 'https://peps.python.org/pep-0008/'),
    ('S2', 'Django 5.2：事务与提交后回调', 'https://docs.djangoproject.com/en/5.2/topics/db/transactions/'),
    ('S3', 'Python 3.12：secrets安全随机值', 'https://docs.python.org/3.12/library/secrets.html'),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence_match(path, expected):
    """Accept only byte identity or UTF-8 LF/CRLF equivalence in historical text hashes."""
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() == expected:
        return 'exact'
    data.decode('utf-8')
    lf = data.replace(b'\r\n', b'\n')
    candidates = [lf, lf.replace(b'\n', b'\r\n')]
    assert any(hashlib.sha256(item).hexdigest() == expected for item in candidates), path
    return 'LF/CRLF only'


def git_files(app):
    data = subprocess.check_output([
        'git', 'ls-tree', '-r', '-z', '--name-only', SOURCE_REF, '--', f'src/DjangoBlog/{app}',
    ], cwd=ROOT)
    return [name for name in data.decode('utf-8').split('\0') if name.endswith('.py')]


def collect_inventory():
    result = {}
    parse_warnings = []
    for member in MEMBERS:
        files = git_files(member['app'])
        items = []
        for name in files:
            source = (ROOT / name).read_text(encoding='utf-8-sig')
            category = 'production'
            if 'migrations' in Path(name).parts:
                category = 'migration'
            elif Path(name).name.startswith('test') or 'tests' in Path(name).parts:
                category = 'test'
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter('always', SyntaxWarning)
                tree = ast.parse(source)
            parse_warnings += [f'{name}: {warning.message}' for warning in captured]
            comments = [token for token in tokenize.generate_tokens(io.StringIO(source).readline)
                        if token.type == tokenize.COMMENT]
            items.append({
                'path': name, 'relative': Path(name).relative_to('src/DjangoBlog').as_posix(),
                'category': category, 'physical_lines': len(source.splitlines()),
                'nonempty_lines': sum(bool(line.strip()) for line in source.splitlines()),
                'classes': sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
                'functions': sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 for node in ast.walk(tree)),
                'comment_lines': len(comments),
                'signed': {person['tag']: sum(person['tag'] in token.string for token in comments)
                           for person in MEMBERS},
                'sha256': digest(ROOT / name),
            })
        result[member['app']] = items
    return result, parse_warnings


INVENTORY, PARSE_WARNINGS = collect_inventory()
TEST_EVIDENCE = WEEK / FACTS['verification']['manifest']
TEST_RECORD = json.loads(TEST_EVIDENCE.read_text(encoding='utf-8'))
assert TEST_RECORD['test_count'] == FACTS['verification']['test_count'] and TEST_RECORD['failure_count'] == 0
TEST_COUNT = TEST_RECORD['test_count']
TEST_PER_APP = FACTS['verification']['per_app']
TAKEOVER_PATH = WEEK / FACTS['takeover']['record']
TAKEOVER = json.loads(TAKEOVER_PATH.read_text('utf-8'))
TEST_SOURCE_MATCHES = {name: evidence_match(ROOT / name, expected)
                       for name, expected in TEST_RECORD['source_sha256'].items()}
ACCOUNT_SCAN_SUMMARY = WEEK / FACTS['accounts_comparison']['summary']
ACCOUNT_SCAN = json.loads(ACCOUNT_SCAN_SUMMARY.read_text(encoding='utf-8'))
assert ACCOUNT_SCAN['same_file_paths'] and ACCOUNT_SCAN['tools'] == {'ruff': '0.17.1', 'bandit': '1.9.4'}
for config_name, expected in ACCOUNT_SCAN['config_sha256'].items():
    assert digest(WEEK / 'tools' / config_name) == expected, config_name
ACCOUNT_AFTER = json.loads((ACCOUNT_SCAN_SUMMARY.parent / 'after/manifest.json').read_text('utf-8'))
ACCOUNT_SOURCE_MATCHES = {item['path']: evidence_match(ROOT / 'src/DjangoBlog' / item['path'], item['sha256'])
                          for item in ACCOUNT_AFTER['files']}
ACCOUNT_COUNTS = ACCOUNT_SCAN['results']


def text_properties(properties):
    """Apply the group's Chinese/Latin fonts and explicit black, without theme overrides."""
    fonts = properties.get_or_add_rFonts()
    fonts.attrib.clear()
    for name, value in [('ascii', 'Times New Roman'), ('hAnsi', 'Times New Roman'),
                        ('cs', 'Times New Roman'), ('eastAsia', '宋体')]:
        fonts.set(qn('w:' + name), value)
    color = properties.get_or_add_color()
    color.attrib.clear()
    color.set(qn('w:val'), BLACK)


def run_font(run, size=10.5, bold=False):
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(BLACK)
    text_properties(run._element.get_or_add_rPr())


def para(document, text, *, small=False, bold=False):
    paragraph = document.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.line_spacing = 1.15
    fmt.space_after = Pt(3 if '编码规范' in document.core_properties.title else 5)
    fmt.widow_control = True
    fmt.keep_with_next = False
    run_font(paragraph.add_run(str(text)), 9 if small else 10.5, bold)
    return paragraph


def heading(document, text, level=1, page=False):
    paragraph = document.add_heading(text, level)
    fmt = paragraph.paragraph_format
    fmt.keep_with_next = True
    fmt.page_break_before = page
    fmt.space_before = Pt(12 if level == 1 else 8)
    fmt.space_after = Pt(6)
    for run in paragraph.runs:
        run_font(run, 14 if level == 1 else 11.5, True)
    return paragraph


def callout(document, text):
    paragraph = para(document, text)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), 'F2F2F2')
    paragraph._p.get_or_add_pPr().append(shd)
    return paragraph


def table(document, headers, rows, weights=None, size=9):
    rows = list(rows)
    width = (document.sections[-1].page_width - document.sections[-1].left_margin
             - document.sections[-1].right_margin) / 360000
    weights = weights or [1] * len(headers)
    widths = [width * weight / sum(weights) for weight in weights]
    grid = document.add_table(rows=1, cols=len(headers))
    grid.alignment = WD_TABLE_ALIGNMENT.CENTER
    grid.autofit = False
    for column, cm in zip(grid.columns, widths):
        column.width = Cm(cm)
    for index, values in enumerate([headers, *rows]):
        row = grid.rows[0] if index == 0 else grid.add_row()
        prop = row._tr.get_or_add_trPr()
        prop.append(OxmlElement('w:cantSplit'))
        if index == 0:
            prop.append(OxmlElement('w:tblHeader'))
        for cell, value, cm in zip(row.cells, values, widths):
            cell.width = Cm(cm)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr = cell._tc.get_or_add_tcPr()
            margin = OxmlElement('w:tcMar')
            for side in ['top', 'left', 'bottom', 'right']:
                node = OxmlElement('w:' + side)
                node.set(qn('w:w'), '70')
                node.set(qn('w:type'), 'dxa')
                margin.append(node)
            tcpr.append(margin)
            borders = OxmlElement('w:tcBorders')
            for side in ['top', 'left', 'bottom', 'right']:
                node = OxmlElement('w:' + side)
                node.set(qn('w:val'), 'single')
                node.set(qn('w:sz'), '4')
                node.set(qn('w:color'), BLACK)
                borders.append(node)
            tcpr.append(borders)
            if index == 0 or '待补' in str(value) or '待确认' in str(value):
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:fill'), 'F2F2F2')
                tcpr.append(shd)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.line_spacing = 1.05
            paragraph.paragraph_format.space_after = Pt(2)
            # Keep short tables whole; avoid lone headers and lone final rows in longer tables.
            paragraph.paragraph_format.keep_with_next = (
                index < len(rows) if len(rows) <= 5
                else index < 2 or index == len(rows) - 1
            )
            run_font(paragraph.add_run(str(value)), size, index == 0)
    gap = document.add_paragraph()
    gap.paragraph_format.space_after = Pt(0)
    gap.paragraph_format.line_spacing = Pt(2)
    run_font(gap.add_run(''), 2)
    return grid


def code(document, text):
    lines = text.strip('\n').splitlines()
    for index, line in enumerate(lines):
        paragraph = document.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.left_indent = Cm(0.25)
        fmt.right_indent = Cm(0.15)
        fmt.line_spacing = Pt(12)
        fmt.space_after = Pt(0)
        fmt.keep_with_next = index < len(lines) - 1
        fmt.keep_together = True
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:fill'), 'F5F5F5')
        paragraph._p.get_or_add_pPr().append(shd)
        run_font(paragraph.add_run(line or ' '), 8.5)
    para(document, '', small=True).paragraph_format.space_after = Pt(0)


def field(paragraph, instruction, text='1'):
    node = OxmlElement('w:fldSimple')
    node.set(qn('w:instr'), instruction)
    run = OxmlElement('w:r')
    value = OxmlElement('w:t')
    value.text = text
    run.append(value)
    node.append(run)
    paragraph._p.append(node)


def hyperlink(paragraph, label, url):
    from docx.opc.constants import RELATIONSHIP_TYPE
    link = OxmlElement('w:hyperlink')
    link.set(qn('r:id'), paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK,
                                               is_external=True))
    run = OxmlElement('w:r')
    properties = OxmlElement('w:rPr')
    text_properties(properties)
    run.append(properties)
    text = OxmlElement('w:t')
    text.text = label
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def new_document(kind, title):
    template = WEEK / '模板' / ('编码规范.docx' if kind == 'coding' else '质量分析报告.docx')
    document = Document(template)
    body = document._element.body
    for element in list(body):
        if element.tag != qn('w:sectPr'):
            body.remove(element)
    for level in range(1, 4):
        name = f'Heading {level}'
        if name not in document.styles:
            style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = document.styles['Normal']
            outline = OxmlElement('w:outlineLvl')
            outline.set(qn('w:val'), str(level - 1))
            style._element.get_or_add_pPr().append(outline)
    for section in document.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.3)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.6)
        section.right_margin = Cm(2.4)
        section.header_distance = Cm(0.9)
        section.footer_distance = Cm(0.9)
        paragraph = section.header.paragraphs[0]
        paragraph.text = ''
        run_font(paragraph.add_run(f'{FACTS["group"]} · DjangoBlog · 第7—8周'), 8.5)
        paragraph = section.footer.paragraphs[0]
        paragraph.text = ''
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_font(paragraph.add_run('课程汇总稿  |  第 '), 8.5)
        field(paragraph, 'PAGE')
        run_font(paragraph.add_run(' 页 / 共 '), 8.5)
        field(paragraph, 'NUMPAGES')
        run_font(paragraph.add_run(' 页'), 8.5)
    document.styles['Normal'].font.size = Pt(10.5)
    document.styles['Normal'].font.name = 'Times New Roman'
    document.styles['Normal']._element.get_or_add_rPr().get_or_add_rFonts().set(
        qn('w:eastAsia'), '宋体')
    props = document.core_properties
    props.title = title
    props.subject = '第七、八周软件工程方法学课程任务'
    props.author = FACTS['group']
    props.last_modified_by = '石兆翔（组长整理）'
    props.version = FACTS['document_version']
    props.content_status = '本轮汇总稿；实际执行归属、核查方式及未验证边界见文内'
    props.created = datetime(2026, 10, 31, tzinfo=timezone.utc)
    props.modified = datetime.now(timezone.utc)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(8)
    run_font(paragraph.add_run(title), 22, True)
    para(document, f'第7—8周 · v{FACTS["document_version"]} {FACTS["document_label"]}', bold=True)
    para(document, f'组号：{FACTS["group"]}    更新日期：{FACTS["compiled_date"]}')
    para(document, '小组成员：' + '、'.join(member['name'] for member in MEMBERS))
    para(document, f'源码参照：{SOURCE_LABEL}    汇总人：石兆翔；编制输入另存指纹', small=True)
    return document


def normalize_properties(document):
    orders = {
        'pPr': ('pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr '
                'suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap '
                'overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd '
                'snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc '
                'textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle '
                'rPr sectPr pPrChange').split(),
        'tcPr': ('cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar '
                 'textDirection tcFitText vAlign hideMark headers cellIns cellDel '
                 'cellMerge tcPrChange').split(),
    }
    for name, order in orders.items():
        ranks = {qn('w:' + value): index for index, value in enumerate(order)}
        for properties in document._element.body.iter(qn('w:' + name)):
            for child in sorted(list(properties), key=lambda item: ranks.get(item.tag, len(order))):
                properties.append(child)


def save(document, path):
    # Cover template styles, table styles, fields, hyperlinks and headers/footers as well.
    for style in document.styles:
        text_properties(style._element.get_or_add_rPr())
    for part in document.part.package.parts:
        root = getattr(part, '_element', None)
        if root is None:
            continue
        for run in root.iter(qn('w:r')):
            text_properties(run.get_or_add_rPr())
        for properties in root.iter(qn('w:rPr')):
            text_properties(properties)
    normalize_properties(document)
    temporary = path.with_name(path.stem + '.building.docx')
    document.save(temporary)
    temporary.replace(path)


def coding_document():
    document = new_document('coding', 'Python语言编码规范')
    callout(document, '本稿依据课程模板、现有工具配置与已确认案例整理。适用于本轮新增和修改代码；'
            '存量偏离逐项记录整改依据。SY部分按组长指示由SZX代办，实际署名与核查方式另行说明。')
    heading(document, '1  规范制定的主要目的')
    para(document, '统一六人协作时的命名、格式、注释、接口及验证方式，使代码能被另一位成员理解、'
         '复现和维护；将质量问题落实到具体路径、触发、修复及证据。')
    para(document, '规范同时约束行为兼容和证据真实性。减少告警不能以引入功能回归为代价；'
         '缓存、权限和输入输出的契约必须由相应回归保护。')
    heading(document, '2  规范的适用范围')
    table(document, ['范围', '适用说明'], [
        ('六个主责App', 'blog、accounts、comments、oauth、servermanager、djangoblog；模板/前端按关联接口核查。'),
        ('代码类别', '业务Python、包入口、管理命令与模板标签；测试和迁移分别统计与审查。'),
        ('实施边界', '新增/修改代码优先满足；公共名称与返回类型改动先协调，存量整改不随意扩大补丁。'),
        ('优先依据', '课程要求、已确认业务契约、本组规则和统一工具配置；基础风格参考S1。'),
    ], [1, 4])
    heading(document, '3  规范')
    rules = [
        ('CS01  编码、缩进与排版',
         '使用UTF-8、4空格缩进，文件末尾保留换行，去除无意义行尾空格；本组行长为100字符，以ruff.toml为准。'
         '这是本组项目约定，不将PEP 8的默认建议误写为100。顶层定义之间留出合理空行，长表达式采用括号换行。'),
        ('CS02  命名与兼容',
         '模块、函数和变量使用有业务含义的snake_case，类使用CapWords，常量使用UPPER_CASE。'
         '不混用id、邮箱、第三方标识等不同概念；修改既有公开名称、路由、模型字段前核对调用与迁移，避免只为改名破坏兼容。'),
        ('CS03  导入与依赖',
         '按标准库、第三方、本地模块分组，生产代码使用显式导入，移除确实未使用的导入与变量。'
         '采用统一扫描cwd；未经核实不对全目录自动修复。避免模块导入时触发业务写库或网络外呼。'),
        ('CS04  函数职责与接口',
         '函数聚焦一个清晰职责，写明关键参数、返回值、状态及副作用。保留已约定返回类型，'
         '例如Article.comment_list仍返回QuerySet；不能为了查询优化擅自改成list，导致filter等调用失效。'),
        ('CS05  阅读注释与署名',
         '按模块层、关键函数/方法层、核心逻辑层说明职责、理由和边界，使用# SZX：等本人缩写；保留原作者，'
         '由他人修订时注明修订者。区分当前注释、既有注释、本周新增和修订，不能把总量当新增或替别人确认阅读。'),
        ('CS06  可选参数与异常',
         '先识别可选上下文，再取值或调用；不以bare except掩盖索引、类型或业务错误。只处理能够合理恢复的异常，'
         '必要时记录日志。可选get_cache_key缺失可回退，但方法内部真异常应向上传播。G2的无参回归作为反例保留证据。'),
        ('CS07  ORM、归属与状态',
         '对公开入口按发布、启用、激活等真实状态筛选；回复父ID、隐藏字段和第三方ID必须校验归属。'
         '校验失败返回约定的表单错误或HTTP状态，不让已知无效输入冒泡为500；模型choices不能冒充数据库强约束。'),
        ('CS08  写入权限与请求边界',
         '有副作用入口明确HTTP方法、身份/权限及CSRF，不能用GET执行清缓存等管理写操作。'
         '直接login与authenticate路径分别核对；不能根据前端隐藏字段或cookie声称服务端已完成权限判断。'),
        ('CS09  模板与HTML上下文',
         '区分普通文本、HTML、属性和脚本上下文，优先自动转义或适当框架接口。mark_safe不执行净化。'
         'JSON嵌入单引号HTML属性时仍须按属性上下文强制转义；昵称中的引号和尖括号必须能安全往返。'),
        ('CS10  缓存、事务与批量操作',
         '记录真实缓存键、空值语义、所有读写入口及失效时机。数据库相关展示缓存成功提交后失效，回滚保留[S2]；'
         '批量更新固定待改主键并按能力锁行，显式调用失效入口。完整级联删除按实际被删对象覆盖各文章，不能只取一层子回复。'
         '保留无关验证码等状态，不以cache.clear替代局部失效。'),
        ('CS11  外部服务与通知',
         'HTTP显式设置超时，记录失败和降级边界；本项目OAuth使用10秒、百度推送5秒的现有约定。'
         'TLS校验与错误处理不可默默降级；真实联调和mock结果分别说明。缓存清理不附带邮件，事务通知时机与投递保证分开约定。'),
        ('CS12  密钥与验证码',
         '密钥来自配置/环境，报告与日志不含真实凭据。找回密码等安全随机值使用secrets[S3]；当前六位ASCII数字协议'
         '保留前导零与重复数字。随机值、有效期、成功消费、限频和失败次数是不同控制点；未实现项列入后续计划。'),
        ('CS13  测试与查询预算',
         '验证正常、无效、匿名/越权、空值及关键事务/并发交错边界，断言明确结果。缺陷回归在可行时留修复前失败证据。'
         'R4测量边界为单次get_reactions_summary，当前1查询并满足最多2查询预算，不将整页成本混入；不得漏计人数或名单外用户状态。'),
        ('CS14  扫描与证据',
         '固定Ruff0.17.1、Bandit1.9.4、规则与目标版本、cwd和生产/测试/迁移范围。保存原始JSON、命令、退出码、源码/配置哈希。'
         '发现、误报、解析错误与未执行分开；Ruff返回1表示发现告警，不等于工具崩溃。旧证据不覆盖，新轮次另存。'),
        ('CS15  协作、复核与提交',
         '开工前fetch并核对个人分支是否已整合最新develop；拉取远端引用不等于当前分支完成合并。'
         '跨App先确认接口和范围，冲突保留双方有效逻辑及作者。个人分支提交到develop，全组完成后由组长负责main最终合并。'
         '本人复核日期、意见和结论由本人确认，自动化核查不代签。'),
    ]
    for title, text in rules:
        heading(document, '3.' + title[2:4].lstrip('0') + '  ' + title[6:], 2)
        para(document, f'[{title[:4]}] ' + text)
        if title.startswith('CS06'):
            code(document, '''key = None
if args:
    get_cache_key = getattr(args[0], 'get_cache_key', None)
    if callable(get_cache_key):
        key = get_cache_key()  # 方法自身错误传播''')
            para(document, '摘录：djangoblog/utils.py:cache_decorator的可选上下文处理；'
                 '完整回退实现及回归见仓库对应方法。', small=True)
        if title.startswith('CS09'):
            code(document, "data-reactions='{{ comment_item|get_reactions_for_user:user|to_json|force_escape }}'")
            para(document, '实例：templates/comments/tags/comment_item_modern.html；实际SSR属性往返测试覆盖恶意昵称。', small=True)
        if title.startswith('CS12'):
            code(document, "return ''.join(secrets.choice(string.digits) for _ in range(6))")
            para(document, '实例：djangoblog/utils.py:generate_code；本轮账户回归保留成功消费验证码的验证。', small=True)
    heading(document, '3.16  本轮互查通过条件', 2)
    table(document, ['编号', '检查项', '通过条件'], REVIEW_CHECKS, [0.7, 1.1, 4], 8.8)
    para(document, 'P1：功能/权限回归、证据失真或范围错误，修复并验证后再验收；P2：影响可靠性或维护的缺项，'
         '明确整改/保留理由；P3：低影响排版与历史风格项，纳入有证据的后续计划。通过可附遗留项，但不能隐去阻断问题。')
    heading(document, '3.17  本组可执行工具约定与参考', 2)
    code(document, '''python doc/week7-8/tools/scan_app.py <app> baseline
python doc/week7-8/tools/scan_app.py <app> after --output-dir <新证据目录>''')
    para(document, '静态工具使用独立环境；cwd由统一驱动固定为src/DjangoBlog；业务扫描排除migrations、test*.py、tests目录。'
         '测试/迁移仍人工阅读并单列统计，不从报告中消失。')
    for label, name, url in REFERENCES:
        paragraph = para(document, f'[{label}] ', small=True)
        hyperlink(paragraph, name, url)
    para(document, '项目依据：tools/ruff.toml、tools/bandit.yaml、个人任务单、已确认源码及成员成果；'
         '外部资料访问日期为2026-10-31。具体代码证据以质量报告附录索引为准。', small=True)
    save(document, OUTPUTS['coding'])


def production_items(app):
    return [item for item in INVENTORY[app] if item['category'] == 'production']


def quality_document():
    document = new_document('quality', '“DjangoBlog”开源软件质量分析报告')
    callout(document, f'最终汇总：覆盖六个App；SY保留原快照和基线，后续由SZX代办。所选联合回归{TEST_COUNT}项通过；'
            '两组本人互查补录、代办专项核查与生产验证边界分别记录，不冒写个人贡献或签署。')
    heading(document, '1  待分析开源软件概述')
    para(document, 'DjangoBlog是以Python/Django实现的技术博客系统，提供文章与分类标签、站点设置、账号认证、第三方授权、'
         '评论/回复与表情反应、检索，以及运维和邮件日志等功能。关联展示采用Django模板和前端资源。')
    para(document, f'本轮主评范围是六个已注册的自有App。统计从Git提交{SOURCE_REF}读取跟踪文件，按AST和token计数；'
         '依赖库、虚拟环境、前端文件与生成文档不混入生产Python分母。类包括嵌套类，函数数含方法；物理行不等于有效代码行。')
    rows = []
    for member in MEMBERS:
        items = production_items(member['app'])
        rows.append((member['app'], len(items), sum(item['physical_lines'] for item in items),
                     sum(item['classes'] for item in items), sum(item['functions'] for item in items)))
    rows.append(('合计', *[sum(row[column] for row in rows) for column in range(1, 5)]))
    table(document, ['App', '生产Python文件', '物理行', 'AST类', '函数/方法'], rows, [1.6, 1.2, 1, 0.8, 1])
    table(document, ['App', '测试/测试基类文件', '迁移Python文件'], [
        (member['app'], sum(item['category'] == 'test' for item in INVENTORY[member['app']]),
         sum(item['category'] == 'migration' for item in INVENTORY[member['app']]))
        for member in MEMBERS
    ], [1.5, 2, 2])
    para(document, '11月2日组长确认SY无法完成，授权SZX接手servermanager。SY原阶段快照b4fe17b及基线原样保留；'
         '其后注释、实现、验证和材料均注明SZX代SY，不写成SY个人独立阅读/编码。')
    heading(document, '2  软件质量分析方法及工具')
    heading(document, '2.1  分析的软件质量要素', 2)
    table(document, ['要素', '本轮关注点'], [
        ('内部质量', '风格与命名、注释真实性、模块职责、接口兼容、异常与缓存设计、查询成本。'),
        ('外部质量', '发布/启用/激活边界、权限与输入归属、异常响应、HTML安全、批量与级联一致性。'),
        ('可追溯性', '固定基线/配置/分母与源码指纹；测试和原始结果可定位，真实联调和隔离测试分开。'),
    ], [1, 4])
    heading(document, '2.2  软件质量分析方法', 2)
    para(document, '按App阅读入口、核心对象与调用链，在模块/方法/关键块署名说明；从风格、设计、技能正例与问题四类人工分析。'
         '静态发现结合源码核实，选取至少一项适当改进，保留必要的失败复现、修复、回归和同配置复扫。')
    para(document, '互查按RC01—RC10执行。候选风险不直接写成既成缺陷；集成验证与成员本人确认分别记录。'
         'SZX/GCY、YFY/GZX已由组长确认完成并补录；未另存的个人意见不补造。'
         'YFY原配置差异与新补扫分别保留。SY原互查安排按接手指示调整为组长专项核查，'
         '没有WZY/SY对最终代办版的独立署名，不把实现者自检写成独立同伴审查。')
    heading(document, '2.3  软件质量分析工具', 2)
    table(document, ['工具', '用途与边界'], [
        ('Ruff 0.17.1', 'E/F/I/B/C90，行长100，复杂度10，统一target=py312；静态告警不证明业务结果。'),
        ('Bandit 1.9.4', '保留全部规则并ignore-nosec；生产显式文件清单排除测试/迁移，误报结合上下文分流。'),
        ('Django 5.2.17测试', '使用SQLite内存、LocMem缓存/邮箱和SimpleEngine；阻断HTTP/socket，覆盖选定标签。'),
        ('Git、AST、tokenize', '核对提交/合并、逐文件规模、结构和注释token；哈希记录源码和配置，计数不是作者确权。'),
    ], [1.4, 4])
    heading(document, '3  人工分析代码的质量情况')
    heading(document, '3.1  代码风格', 2)
    para(document, 'G1将admin_site星号导入改为显式来源；G3清理Whoosh未用导入和变量；WZY最终相关业务11文件Ruff/Bandit均0。'
         '同时，blog和派生检索实现仍有历史排版、导入及复杂度项，不能把部分范围零告警写成整个系统符合规范。')
    para(document, '判定依据采用《Python语言编码规范》CS01—CS05与统一配置。按原作者及SZX补修分别记贡献，'
         '本周新增统计不能由当前缩写行数倒推；逐文件当前快照见附录B。')
    heading(document, '3.2  代码设计', 2)
    table(document, ['观察', '源码与结论'], [
        ('职责与接口', '六App按业务划分；Article.comment_list的QuerySet返回与消费者filter接口保持。'),
        ('缓存调用契约', 'cache_decorator兼容无参函数/参数调用/自定义键；方法真实错误传播，避免G2收窄异常引入IndexError。'),
        ('完整生命周期', '评论pre_save记录旧文章，post_save/post_delete在实际写库连接on_commit失效；批量动作显式失效。'),
        ('数据与整页边界', '归档保留文章数据缓存，HTML按请求渲染，侧栏不被旧整页响应遮挡；外部CDN/浏览器旧响应不在本轮保证内。'),
        ('通知与异常隔离', '缓存入口不发邮件；提交后独立通知，回滚不发送；无__name__插件回调出错仍继续后续链。'),
    ], [1.1, 4])
    heading(document, '3.3  编程技能', 2)
    para(document, '已核对实例包括显式接口与状态筛选、select_related等预加载、回调/Filter扩展、白名单HTML处理、'
         '事务提交后失效、必要字段一次读取聚合与原始证据指纹。每个正例均有适用边界，不能只引用mark_safe、choices或缓存命中即声称安全。')
    code(document, '''# djangoblog/utils.py：可选接口与真实异常分开
key = None
if args:
    get_cache_key = getattr(args[0], 'get_cache_key', None)
    if callable(get_cache_key):
        key = get_cache_key()''')
    para(document, 'R4同一个SELECT计算count、最多10名显示用户和当前查看者参与态。八种已参与表情场景中，'
         '历史登录17/匿名9次，WZY初版2/2，本轮补修1/1；0/1/8种、名单外用户、SSR/API与交错增删均有回归。'
         '仍需遍历该评论全部反应；数据库驱动可能缓冲结果，不宣称无限规模常数内存。')
    heading(document, '3.4  代码质量问题', 2)
    table(document, ['问题', '处理与当前结论', '归属/证据'], [
        ('草稿公开、未授权清缓存、HTML输出', '已按发布/权限/上下文修复并回归；源阶段分析见README。', 'SZX；EV01'),
        ('空用户名/未激活认证与验证码重放', '后端加固、重置成功后消费验证码；84项账户相关测试通过。', 'YFY；EV02'),
        ('OAuth外呼无超时', '四处显式timeout=10；26项业务测试通过。state/IDOR/邮箱归属等仍在后续计划。', 'GZX；EV03'),
        ('跨文章/无效父回复及关闭评论异常', 'R1—R3视图校验修复，状态与表单反馈回归保留。', 'WZY；EV04'),
        ('R4两次读取与R5漏清后代缓存', 'SZX补为单次读取与完整生命周期；318项阶段回归通过，357项集成保持。', 'WZY原改动+SZX补修；EV05'),
        ('G2无参调用IndexError', '原22项全过，GCY初版3项报错；SZX显式识别可选上下文后关闭回归。', 'GCY原改动+SZX补修；EV06'),
        ('验证码用途/插件错误日志', 'SZX改secrets保持六位协议；回调无__name__不阻断后续，新增最小回归通过。', 'SZX；EV06'),
        ('运维代码层级/SDK', '修复SY快照2处语法错误和方法嵌套；更新固定SDK调用及有意义的mock断言。', 'SY原快照；SZX代办；EV12'),
        ('机器人状态与公开数据', '纯JSON状态、三次失败退出、顺序确认消费；拒绝草稿/页面及陈旧私有索引对象。', 'SZX代办；EV12'),
        ('会话回退与命令', '不删除已有会话存储；显式命令超时和退出结果，shell边界告警保留。', 'SZX代办；EV12'),
    ], [1.4, 3.1, 1.4], 8.8)
    heading(document, '4  工具分析代码的质量情况')
    para(document, '下表保留各阶段已确认结果及其分母。不同配置、范围或代码时点的结果不合计为“全系统下降”。'
         f'告警数量不是缺陷数量；没有执行不能填0。当前源码与最新{TEST_COUNT}项记录核对，历史文本哈希仅允许LF/CRLF等价。')
    table(document, ['App/阶段', '生产文件', 'Ruff', 'Bandit', '可比性与来源'], [
        ('blog原阶段', '22', '66→65', '45→39', '同阶段可比；当前新增缓存入口后生产23，历史扫描不能冒充完整最新范围。EV01'),
        ('accounts补扫', '10', f'{ACCOUNT_COUNTS["baseline"]["ruff"]}→{ACCOUNT_COUNTS["after"]["ruff"]}',
         f'{ACCOUNT_COUNTS["baseline"]["bandit"]}→{ACCOUNT_COUNTS["after"]["bandit"]}',
         'SZX于11月2日统一py312配置补扫；保留完整包目录供导入分类，不混用原py313数字。EV02/11'),
        ('oauth', '10', '12→12', '10→6', 'B113×4关闭；B105 URL/空串误报另记。前后配置一致。EV03'),
        ('comments最终', '11', '0', '0', '最终补修快照；旧基线9及中间3/4保留，SZX执行者单列。EV04/05'),
        ('djangoblog统一阶段', '22', '72→34→28', '8→7→5', '原版→GCY→SZX集成，包含上游修复；原自建混入测试数字另存。EV06'),
        ('servermanager代办', '11', '5→0', '3→2', 'SZX同配置补扫；B404/B602属同一管理员shell功能边界，不加nosec。EV12'),
    ], [1.3, 0.7, 0.9, 0.9, 3], 8.5)
    para(document, 'accounts原历史10→8因配置/驱动变更不直接作净下降；本次SZX补扫相同10个业务文件为Ruff9→8、'
         'Bandit0→0，无解析错误。结果包含基线至当前集成版本的变化，不全部归为YFY个人消除；未重新执行Django测试。')
    para(document, 'djangoblog原自建Bandit实际扫27文件，含5个测试文件，after的38条中31条来自测试，'
         '不能按22个生产文件口径合计；已转统一入口并另存after-szx-integration。当前剩余Ruff I001×7、E501×14、'
         'C901×5、B007×1、B904×1；Bandit为日志链接B308/B703各2及Whoosh运行时assert B101×1，处置理由保留。')
    heading(document, '4.1  已确认行为验证与边界', 2)
    table(document, ['范围', '数量', '结果'], [
        (app + '所选标签', str(TEST_PER_APP[app]), '通过')
        for app in ['blog', 'accounts', 'comments', 'oauth', 'djangoblog', 'servermanager']
    ] + [('合计', str(TEST_COUNT), '失败0、错误0、跳过0')], [3, 0.8, 1.2])
    para(document, f'环境：Python{TEST_RECORD["python"]}、Django{TEST_RECORD["django"]}、SQLite内存、LocMem缓存/邮箱、SimpleEngine；'
         'HTTP/socket与未mock系统命令阻断。'
         '不代表全仓库全部测试、真实MySQL/Redis/CDN、OAuth提供商、SMTP投递或前端生产构建均已验证。'
         '原集成357项与本次servermanager33项合并在同一次联合运行中通过。新增31项改进前为22失败6错误；'
         '真实OpenAI模型可用性、微信回调和shell子进程树终止未实测，不把mock通过当作真实联调。')
    heading(document, '5  小组分工')
    table(document, ['成员/标识', '分析模块', '主要工作与注释范围', '互查/交付状态'], [
        (f'{m["name"]}\n{m["id"]}\n# {m["tag"]}：', m['app'],
         f'生产Python {len(production_items(m["app"]))}文件；当前逐文件注释见附录B。' +
         ('SY阶段记录保留；本轮新增说明和实现由SZX代办，详见接手清单。' if m['tag'] == 'SY' else '人工分析、工具和验证按本人材料及SZX补修分别记录。'),
         m['status'] + f'；搭档{m["peer"]}') for m in MEMBERS
    ], [1.3, 0.9, 2.5, 2], 8.8)
    para(document, 'SZX的组长/集成补修不计作其他成员本人返工或人工签署。WZY/GCY原提交在个人分支保留，'
         '后续修复从szx_branch进入develop；不能根据个人分支旧版本再次认定集成版本仍有已修复回归。')
    heading(document, '6  下一步的改进计划')
    table(document, ['级别', '方向', '拟实施内容', '建议负责人', '验收条件'], OPTIMIZATIONS,
          [0.5, 1, 2.3, 1.1, 2.1], 8.5)
    para(document, '以上后续优化计划依据README和已确认剩余项整理；优先级与责任为拟定收尾/改进安排，'
         '按任务阶段安排；日历截止未另存，不写成全部已实施或每位成员已承诺完成。')
    heading(document, '附录A  组会、双周计划与互查标准', page=True)
    meeting = FACTS['meeting']
    table(document, ['项目', '已确认内容'], [
        ('组会时间', f'{meeting["date"]} {meeting["start"]}—{meeting["end"]}'),
        ('形式/地点', f'{meeting["mode"]}，{meeting["place"]}'),
        ('出席/缺席', f'{meeting["attendance"]}；缺席：{meeting["absent"]}'),
        ('主持/记录', f'{meeting["chair"]} / {meeting["recorder"]}'),
        ('记录依据', '组长确认会议事实及结论沿用既定沟通安排；本节为补录，不是逐字记录。'),
    ], [1, 4])
    for index, conclusion in enumerate(meeting['conclusions'], 1):
        para(document, f'结论{index}：{conclusion}')
    para(document, '10月31日的代码集成、测试和补修属于后续进度快照，见正文，不倒填为10月23日当时完成的事项。', small=True)
    heading(document, 'A.1  双周任务阶段与当前收尾安排', 2)
    table(document, ['阶段', '任务', '责任', '交付/验收', '时间'], PLAN_ROWS,
          [1, 2.2, 1.3, 2.1, 1], 8.5)
    plan = FACTS['plan']
    para(document, f'双周起始：{plan["start_date"] or "未单独留存"}；结束：{plan["end_date"] or "未单独留存"}；'
         f'最终截止：{plan["deadline"] or "未单独留存"}。按上表任务周次编排，不以本次日期倒推历史计划。')
    heading(document, 'A.2  互查标准与闭环状态', 2)
    table(document, ['编号', '检查项', '通过条件'], REVIEW_CHECKS, [0.7, 1.1, 4], 8.8)
    table(document, ['配对', '当前状态', '记录与剩余事项'], [
        ('SZX↔GCY', '组长确认双向互查已完成，11月2日补录。', '技术参照沿用原证据；GCY未另存的逐项意见不补造。'),
        ('YFY↔GZX', '组长确认双向互查已完成，原空表已同步。', '沿用原检查和已修正表述；旧日期保留，不新增本人测试声明。'),
        ('WZY/SY原配对', 'SY无法完成，按组长指示改为SZX代办专项核查。', 'SZX核对WZY相关代码，并实现/验证SY模块；没有WZY/SY独立签名，见EV13。'),
    ], [1, 2.2, 2.8], 8.8)
    heading(document, 'A.3  四方向互查补录登记', 2)
    table(document, ['编号/方向', '完成状态', '已有依据'], [
        (f'{item["id"]}\n{item["reviewer"]}→{item["owner"]}', item['status'], item['evidence'])
        for item in FACTS['review_confirmation']['directions']
    ], [1.3, 1.7, 3], 8.8)
    para(document, '补录日期为2026-11-02，确认人为组长石兆翔。实际互查日期未单独留存的保持说明；'
         '个人额外意见、签名及执行命令不补造。完整记录见互查记录/2026-11-02-两组互查补录.md。', small=True)
    heading(document, '附录B  当前集成源码的逐文件注释清单', page=True)
    para(document, '口径：业务Python中的COMMENT token物理行；含缩写按注释字符串包含该缩写计数，可能同一行含多个标识，'
         '不作为独占署名或本周新增量。测试/迁移不混入；本周新增/修订需由个人差分证据确认。此清单填入可核实的当前事实。')
    for member in MEMBERS:
        heading(document, f'B.{MEMBERS.index(member) + 1}  {member["name"]} / {member["app"]}', 2)
        signed_tag = 'SZX' if member['tag'] == 'SY' else member['tag']
        if member['tag'] == 'SY':
            para(document, f'SZX代SY新增署名说明{TAKEOVER["metrics"]["new_signed_lines"]}行、新增/改写物理注释'
                 f'{TAKEOVER["metrics"]["new_comment_lines"]}行；原GZX说明保留。下表含SZX列为实际执行者，不作SY本人贡献。', small=True)
        rows = []
        for item in production_items(member['app']):
            if item['comment_lines'] or item['signed'][signed_tag]:
                others = '、'.join(f'{tag}:{count}' for tag, count in item['signed'].items()
                                  if tag != signed_tag and count and not (member['tag'] == 'SY' and tag == 'SY'))
                rows.append((item['relative'], item['comment_lines'], item['signed'][signed_tag],
                             others or '—'))
        table(document, ['文件（相对src/DjangoBlog）', '注释token行', f'含{signed_tag}', '其他缩写'],
              rows, [3, 1, 0.8, 1.4], 8.5)
        para(document, '未列出的该App业务文件没有COMMENT token；当前总量不等于本周新增，'
             f'本人周际统计与来源见成员成果/{member["tag"]}/注释统计或SZX阶段验证。', small=True)
    heading(document, '附录C  证据索引与交付核对', page=True)
    table(document, ['编号', '仓库路径/来源', '用途'], [
        ('EV01', 'doc/week7-8/README.md；成员成果/SZX/原始工具结果/quality-summary.json', 'blog原阶段分析、规模和工具对比'),
        ('EV02', '成员成果/YFY/工具与验证记录.md；原始工具结果/；验证日志/', 'accounts历史材料、84项；新同配置补扫见EV11'),
        ('EV03', '成员成果/GZX/工具与验证记录.md、互查记录.md及原始工具结果/', 'oauth超时、26项和互查状态'),
        ('EV04', '成员成果/WZY/四份素材及after-r4-r5-szx/', 'comments分阶段问题与最终11文件复扫'),
        ('EV05', '成员成果/SZX/集成修复/2026-10-31/验证结果.md', 'R4/R5边界修复与318项阶段验证'),
        ('EV06', '成员成果/SZX/GCY集成/2026-10-31/验证结果.md；after/manifest.json', 'GCY补修、357项与逐文件指纹'),
        ('EV07', '成员成果/GCY/四份素材及after-szx-integration/', 'djangoblog22文件统一复扫与修订统计'),
        ('EV08', 'content/week78_confirmed_facts.json；第7—8周组会、双周计划与互查标准.md', '组长确认事实、任务阶段及日期未留存说明'),
        ('EV09', 'GitHub PR37；develop@e52f5d0', '5人成果已集成，保留GCY原作者历史'),
        ('EV10', '互查记录/2026-11-02-两组互查补录.md', 'SZX/GCY与YFY/GZX四方向确认及原意见依据'),
        ('EV11', '成员成果/YFY/原始工具结果/2026-11-02-szx-same-config/', 'SZX同配置9→8、0→0补扫；原始JSON/manifest'),
        ('EV12', '成员成果/SY/四份素材、接手完成清单.json及2026-11-02-szx-takeover/', 'SY原快照保留；SZX代办、390项联合与5→0/3→2扫描'),
        ('EV13', '成员成果/SY/接手与专项核查记录.md', '原WZY/SY配对变更及实际执行者，不冒写个人签名'),
    ], [0.6, 3.8, 1.6], 8.3)
    para(document, '除EV01首项README外，上表“成员成果/”路径均相对doc/week7-8。完整源码/模板/输入指纹见文档编制记录。', small=True)
    table(document, ['交付核对项', '本轮状态与边界', '执行/确认方'], [
        ('SY部分接手', '原快照/基线保留；代码、四份素材、注释统计及联合验证均完成。', 'SZX代SY'),
        ('已补齐项目', '两组四方向互查、YFY同配置补扫已入库；不再重复列为待补。', 'SZX/GCY；YFY/GZX'),
        ('专项核查', '按接手安排完成组长核查；没有WZY/SY对新代办版本的独立本人签署。', 'SZX；独立性边界已说明'),
        ('日期口径', '原日历日期未另存；任务周次与收尾触发条件已列，不虚构日期。', '组长'),
        ('Word与提交', '六App数据及实际贡献已汇总，结构/分页校验另存；个人分支至develop，main由组长决定。', 'SZX汇总；组长'),
    ], [1.1, 3.1, 1.3], 9)
    save(document, OUTPUTS['quality'])


def supporting_markdown():
    meeting = FACTS['meeting']
    text = f'''# 第7—8周组会、双周计划与互查标准

更新：{FACTS['compiled_date']}；{FACTS['group']}；组长石兆翔整理。源码参照{SOURCE_LABEL}；编制输入另存指纹。
会议事实及既定安排由组长在对话中确认；细化的验收清单与当前收尾安排在本次整理，不代填成员本人复核。

## 1. 已确认组会记录

- 时间：{meeting['date']} {meeting['start']}—{meeting['end']}。
- 形式/地点：{meeting['mode']}，{meeting['place']}。
- 出席：{meeting['attendance']}；缺席：{meeting['absent']}。
- 主持/记录：{meeting['chair']} / {meeting['recorder']}。
- 记录说明：据组长确认补录，不是逐字记录；后续10月31日修复结果另列为进度快照。

### 会议结论（按组长确认的沟通安排整理）

'''
    text += '\n'.join(f'{index}. {value}' for index, value in enumerate(meeting['conclusions'], 1))
    text += '\n\n## 2. 六人职责与互查配对\n\n| 成员 | App | 个人分支 | 互查搭档 |\n| --- | --- | --- | --- |\n'
    text += '\n'.join(f'| {m["name"]} {m["tag"]} | {m["app"]} | {m["branch"]} | {m["peer"]} |' for m in MEMBERS)
    text += '\n\n## 3. 双周阶段与当前收尾计划\n\n| 阶段 | 任务 | 责任 | 交付/验收 | 时间 |\n| --- | --- | --- | --- | --- |\n'
    text += '\n'.join('| ' + ' | '.join(row) + ' |' for row in PLAN_ROWS)
    text += '\n\n日历起止与最终截止未单独留存；按上表任务周次和收尾条件编排，不推算或回填日期。\n'
    text += '\n## 4. 统一互查标准\n\n| 编号 | 检查项 | 通过条件 |\n| --- | --- | --- |\n'
    text += '\n'.join('| ' + ' | '.join(row) + ' |' for row in REVIEW_CHECKS)
    text += '''

每项记录：基线/改进提交、文件与符号、证据、问题级别、本人处理、复测、复核日期与结论。
P1阻断项修复并验证后再验收；P2/P3明确整改或保留理由。工具核查与本人确认分别记录。

## 5. 当前闭环状态

- SZX↔GCY：组长确认双向互查已完成，2026-11-02补录；技术参照与未留存信息分别记录。
- YFY↔GZX：组长确认双向互查已完成，YFY第7节、GZX第4节和总状态已同步。
- WZY/SY原配对：11月2日SY无法完成，按组长要求由SZX接手并专项核查；没有WZY/SY对最终代办版本的独立签名，不冒写。
- [四方向补录登记](互查记录/2026-11-02-两组互查补录.md)：补录日期不等于实际互查日期，未留存的个人逐项意见不补造。
- [接手专项核查](成员成果/SY/接手与专项核查记录.md)：记录SZX代SY核对WZY及servermanager实现/自检的真实执行方式。

## 6. 当前进度与后续交付

原五App成果及SY接手结果均已汇总；实际集成版本与验证源码见接手清单和PR38，不将个人旧分支当作最终集成源码。
SZX于2026-11-02补齐accounts相同配置/10文件扫描：Ruff9→8、Bandit0→0，保留原历史记录，不冒充YFY本人执行。
SY模块由SZX代办，统一11文件Ruff5→0、Bandit3→2，新增31项改进前22失败6错误，接手后33项本App与390项联合全部通过。
两份Word已纳入六App实际数据、四份代办素材、注释统计、两组互查补录和专项核查，形成v1.0汇总稿。原日历日期未另存的继续说明，不倒填。
本轮代办工作已完成；真实环境联调、独立复核补强及生产部署按后续优化计划处理。
个人分支提交到develop；全组完成后由组长负责main最终合并。本文不代签任何成员本人确认。
'''
    path = WEEK / '第7—8周组会、双周计划与互查标准.md'
    path.write_text(text.rstrip() + '\n', encoding='utf-8', newline='\n')


def main():
    RECORD.mkdir(exist_ok=True)
    coding_document()
    supporting_markdown()
    quality_document()
    input_paths = [FACTS_PATH, Path(__file__), WEEK / '模板/编码规范.docx', WEEK / '模板/质量分析报告.docx',
                   TEST_EVIDENCE, WEEK / 'tools/ruff.toml', WEEK / 'tools/bandit.yaml',
                   WEEK / FACTS['review_confirmation']['record'], ACCOUNT_SCAN_SUMMARY,
                   WEEK / 'tools/supplement_accounts_baseline.py',
                   WEEK / '成员成果/YFY/工具与验证记录.md', WEEK / '成员成果/GZX/互查记录.md',
                   WEEK / '成员成果/GCY/工具与验证记录.md']
    input_paths += [TAKEOVER_PATH, WEEK / FACTS['takeover']['review_record'],
                    WEEK / 'tools/verify_sy_takeover.py', WEEK / 'tools/build_sy_takeover_materials.py',
                    WEEK / 'tools/run_isolated_tests.py', WEEK / 'tools/verify_week78_documents.py',
                    WEEK / 'tools/render_week78_word.ps1']
    input_paths += sorted((WEEK / '成员成果').glob('*/*.md'))
    for phase in ['before', 'after']:
        input_paths += sorted((TEST_EVIDENCE.parent.parent / phase).glob('*.json'))
    input_paths += sorted(path for path in ACCOUNT_SCAN_SUMMARY.parent.rglob('*.json')
                          if path != ACCOUNT_SCAN_SUMMARY)
    input_paths = list(dict.fromkeys(input_paths))
    manifest = {
        'compiled_date': FACTS['compiled_date'], 'source_ref': SOURCE_REF,
        'purpose': 'Final course aggregation with actual executor attribution and verification boundaries.',
        'document_style': FACTS['document_style'],
        'meeting_confirmed': FACTS['meeting'], 'plan_dates': FACTS['plan'],
        'test_evidence': {'test_count': TEST_COUNT, 'failure_count': 0, 'per_app': TEST_PER_APP,
                          'verified_code_commit': TEST_RECORD['verified_code_commit'],
                          'source_comparison': TEST_SOURCE_MATCHES,
                          'comparison_rule': 'Exact bytes or UTF-8 LF/CRLF equivalence only; no semantic changes accepted.'},
        'review_confirmation': FACTS['review_confirmation'],
        'accounts_same_config_supplement': ACCOUNT_SCAN,
        'accounts_source_comparison': ACCOUNT_SOURCE_MATCHES,
        'sy_takeover': TAKEOVER,
        'inputs_sha256': {path.relative_to(ROOT).as_posix(): digest(path) for path in input_paths},
        'inventory': INVENTORY, 'source_parse_warnings': PARSE_WARNINGS,
        'outputs': {kind: {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)}
                    for kind, path in OUTPUTS.items()},
        'rendering': 'Pending native Word XPS-to-PNG verification; no PDF deliverable.',
    }
    (RECORD / '编制与来源.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                          encoding='utf-8', newline='\n')
    print(json.dumps({'source_ref': SOURCE_REF,
                      'outputs': {key: str(path) for key, path in OUTPUTS.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
