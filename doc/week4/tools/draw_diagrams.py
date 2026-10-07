"""Render editable-in-code diagrams used by the week-four documents."""

from pathlib import Path
from math import atan2, cos, sin

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parents[1] / 'assets'
OUT.mkdir(parents=True, exist_ok=True)
FONT = r'C:\Windows\Fonts\msyh.ttc'
FONT_BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
NAVY = '#17315B'
BLUE = '#4269C2'
PALE = '#EEF3FC'
TEAL = '#167C81'
TEAL_PALE = '#E8F7F5'
GRAY = '#586779'
LIGHT = '#D8E1EE'
BG = '#FFFFFF'


def f(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def canvas(width, height, title, subtitle):
    im = Image.new('RGB', (width, height), BG)
    d = ImageDraw.Draw(im)
    d.text((64, 36), title, font=f(40, True), fill=NAVY)
    d.text((66, 96), subtitle, font=f(22), fill=GRAY)
    d.line((64, 143, width - 64, 143), fill=LIGHT, width=3)
    return im, d


def box(d, xy, title, detail='', fill=PALE, outline=LIGHT, title_size=29, detail_size=19):
    d.rounded_rectangle(xy, radius=20, fill=fill, outline=outline, width=3)
    x1, y1, x2, y2 = xy
    d.text((x1 + 25, y1 + 22), title, font=f(title_size, True), fill=NAVY)
    if detail:
        for line_index, line in enumerate(detail.split('\n')):
            d.text((x1 + 25, y1 + 69 + line_index * 30), line, font=f(detail_size), fill=GRAY)


def arrow(d, start, end, label=None, color=BLUE, width=5):
    d.line((*start, *end), fill=color, width=width)
    theta = atan2(end[1] - start[1], end[0] - start[0])
    wing = 17
    points = [end,
              (end[0] - wing * cos(theta - .55), end[1] - wing * sin(theta - .55)),
              (end[0] - wing * cos(theta + .55), end[1] - wing * sin(theta + .55))]
    d.polygon(points, fill=color)
    if label:
        midx = (start[0] + end[0]) / 2
        midy = (start[1] + end[1]) / 2
        bbox = d.textbbox((0, 0), label, font=f(19))
        w = bbox[2] - bbox[0]
        d.rounded_rectangle((midx - w / 2 - 8, midy - 33, midx + w / 2 + 8, midy - 4), 7, fill=BG)
        d.text((midx - w / 2, midy - 32), label, font=f(19), fill=TEAL)


def sitemap():
    im, d = canvas(1600, 850, '界面思维导图', '博客内容组织与主要角色入口（依据现有 URL 与模板）')
    box(d, (570, 185, 1030, 300), 'AI Agent 工程实践博客', '以文章发布与交流为核心', fill='#DDEBFF')
    branches = [
        ((85, 390, 450, 535), '内容发现', '首页 / 分类 / 标签\n归档 / 搜索 / 作者', '#EEF3FC'),
        ((465, 390, 815, 535), '文章阅读', '正文 / 目录 / 面包屑\n上一篇 / 下一篇', '#E8F7F5'),
        ((830, 390, 1180, 535), '互动与账号', '评论 / 回复 / 表情\n登录 / 注册 / 找回密码', '#FFF4E6'),
        ((1195, 390, 1530, 535), '内容管理', 'Django Admin\n文章 / 分类 / 标签 / 配置', '#F3EFFF'),
    ]
    for xy, title, detail, fill in branches:
        box(d, xy, title, detail, fill=fill)
        midx = (xy[0] + xy[2]) // 2
        arrow(d, (800, 300), (midx, xy[1] - 8), color=LIGHT, width=4)
    d.rounded_rectangle((85, 635, 1530, 760), radius=20, fill='#F7F9FC')
    d.text((115, 660), '主题内容', font=f(26, True), fill=NAVY)
    d.text((115, 707), '基础与架构  ·  工具与工作流  ·  知识与记忆  ·  评测与安全  ·  应用案例', font=f(25), fill=BLUE)
    im.save(OUT / '06-ui-mindmap.png')


def flow():
    im, d = canvas(1600, 700, '主要界面流转', '实线为读者常用路径；虚线含义在正文说明')
    coords = [
        (60, 235, 330, 360, '首页', '文章摘要 / 导航'),
        (445, 235, 725, 360, '分类 / 标签', '按主题筛选文章'),
        (840, 235, 1130, 360, '文章详情', '正文 / 评论入口'),
        (1240, 235, 1530, 360, '登录 / 注册', '认证后发表评论'),
    ]
    for x1, y1, x2, y2, title, detail in coords:
        box(d, (x1, y1, x2, y2), title, detail)
    for x1, x2, label in [(330, 445, '选择栏目'), (725, 840, '点击文章'), (1130, 1240, '未登录')]:
        arrow(d, (x1 + 4, 298), (x2 - 7, 298), label)
    box(d, (460, 465, 790, 595), '搜索结果', '关键词检索 / 跳转文章', fill=TEAL_PALE)
    box(d, (1010, 465, 1370, 595), '发表评论 / 回复', '提交、审核与展示', fill='#FFF4E6')
    arrow(d, (195, 360), (460, 517), '搜索')
    arrow(d, (790, 510), (950, 365), '打开结果')
    arrow(d, (985, 365), (1080, 460), '已登录')
    arrow(d, (1385, 360), (1190, 460), '登录后返回')
    d.text((62, 645), '补充入口：首页可直接打开文章；文章页可经面包屑返回分类或首页；后台管理仅供授权人员访问。', font=f(20), fill=GRAY)
    im.save(OUT / '07-ui-flow.png')


def template_packages():
    im, d = canvas(1600, 910, 'UML 包图：模板关系', '«extends» 继承布局；«include» 组合局部模板；«tag» 自定义模板标签渲染组件')
    box(d, (70, 185, 475, 360), '«package» 共享布局', 'share_layout/base.html\nshare_layout/base_account.html', fill='#DDEBFF')
    box(d, (625, 185, 1095, 410), '«package» 页面模板', 'blog/article_index.html\nblog/article_detail.html\nblog/article_archives.html\nsearch/search.html  ·  account/login.html', fill=PALE)
    box(d, (70, 535, 475, 780), '«package» 导航与页脚', 'share_layout/nav.html\nshare_layout/footer.html', fill=TEAL_PALE, title_size=26)
    box(d, (625, 535, 1095, 780), '«package» 内容组件', 'blog/tags/article_info.html\nblog/tags/sidebar.html\ncomments/tags/comment_list_modern.html\ncomments/tags/post_comment_modern.html', fill='#FFF4E6', detail_size=18)
    box(d, (1170, 535, 1530, 780), '«package» 标签库', 'blog/templatetags/blog_tags.py\nblog/templatetags/vite_tags.py\ncomments/templatetags/\ncomments_tags.py', fill='#F3EFFF', detail_size=15, title_size=26)
    arrow(d, (625, 285), (480, 285), '«extends»')
    arrow(d, (270, 360), (270, 530), '«include»', color=TEAL)
    arrow(d, (860, 410), (860, 530), '«include» / «tag»', color=TEAL)
    arrow(d, (1095, 750), (1165, 750), '«load» / 调用')
    d.text((75, 835), '注：article_index/detail/search 继承 base；login 继承 base_account；详情页 include 评论组件。', font=f(20), fill=GRAY)
    im.save(OUT / '08-template-packages.png')


def er():
    im, d = canvas(1600, 1040, '核心数据模型 ER 图', '字段为主要字段；Article.tags 的多对多关系由 Django 自动关联表实现')
    entities = [
        ((70, 205, 425, 390), 'BlogUser', 'id  PK\nusername  varchar(150)\nemail  varchar(254)\npassword  varchar(128)'),
        ((625, 205, 990, 435), 'Article', 'id  PK\ntitle  varchar(200), unique\nbody  text / Markdown\nauthor_id, category_id  FK\nstatus, type, pub_time'),
        ((1190, 205, 1530, 390), 'Category', 'id  PK\nname  varchar(30), unique\nparent_category_id  FK\nslug  varchar(60)'),
        ((70, 575, 425, 805), 'Comment', 'id  PK\nbody  TextField ≤ 300 字\narticle_id, author_id  FK\nparent_comment_id  FK\nis_enable  boolean'),
        ((625, 575, 990, 785), 'Article.tags / M2M', 'article_id  FK\ntag_id  FK\nDjango 自动关联表', ),
        ((1190, 575, 1530, 785), 'Tag', 'id  PK\nname  varchar(30), unique\nslug  varchar(60)'),
    ]
    for xy, title, detail in entities:
        box(d, xy, title, detail, fill=PALE if title != 'Article' else '#DDEBFF', detail_size=19)
    arrow(d, (425, 290), (620, 290), '1 : N')
    arrow(d, (1190, 290), (995, 290), '1 : N')
    arrow(d, (800, 435), (800, 570), '1 : N', color=TEAL)
    arrow(d, (990, 680), (1185, 680), 'N : 1', color=TEAL)
    arrow(d, (250, 390), (250, 570), '1 : N', color=TEAL)
    arrow(d, (625, 365), (425, 635), '1 : N', color=TEAL)
    box(d, (70, 890, 745, 990), 'CommentReaction', 'comment_id / user_id FK；reaction_type；联合唯一约束', fill='#FFF4E6', title_size=23)
    box(d, (855, 890, 1530, 990), 'BlogSettings', '站点名称、描述、主题与评论开关；全站单例配置', fill=TEAL_PALE, title_size=23)
    arrow(d, (250, 805), (250, 885), '1 : N', color=TEAL)
    im.save(OUT / '09-data-model-er.png')


if __name__ == '__main__':
    sitemap()
    flow()
    template_packages()
    er()
    print('Generated four diagrams in', OUT)
