"""源码分析图的轻量绘制器：同步输出 PNG、SVG 与可编辑 diagrams.net 页面。"""
from pathlib import Path
from html import escape
import math
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

FONT = r'C:\Windows\Fonts\msyh.ttc'
BOLD = r'C:\Windows\Fonts\msyhbd.ttc'
INK, BLUE, GRAY = '#1D2E47', '#245E91', '#61738A'

class Canvas:
    def __init__(self, title, width=2000, height=1300, subtitle=''):
        self.width, self.height = width, height
        self.title = title
        self.im = Image.new('RGB', (width, height), 'white')
        self.d = ImageDraw.Draw(self.im)
        self.svg = []
        self.model = ET.Element('mxGraphModel', page='1', pageWidth=str(width), pageHeight=str(height), grid='1', gridSize='10')
        self.root = ET.SubElement(self.model, 'root')
        ET.SubElement(self.root, 'mxCell', id='0')
        ET.SubElement(self.root, 'mxCell', id='1', parent='0')
        self.n = 1
        self.text(60, 28, title, 39, bold=True)
        if subtitle: self.text(62, 86, subtitle, 23, color=GRAY)

    def vertex(self, text, style, box):
        self.n += 1
        c = ET.SubElement(self.root, 'mxCell', id=str(self.n), parent='1', value=text, vertex='1', style=style)
        x,y,w,h=box
        ET.SubElement(c,'mxGeometry', x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
        return str(self.n)

    def text(self,x,y,value,size=28,color=INK,bold=False,center=False,bg=False,export=True):
        lines = str(value).split('\n')
        ft = ImageFont.truetype(BOLD if bold else FONT,size)
        widths=[self.d.textlength(v,font=ft) for v in lines]
        w=max(widths,default=0); h=len(lines)*(size+8)
        left=x-w/2 if center else x
        if bg:
            self.d.rectangle((left-5,y-3,left+w+5,y+h+2),fill='white')
            self.svg.append(f'<rect x="{left-5}" y="{y-3}" width="{w+10}" height="{h+5}" fill="white"/>')
        for i,(v,lw) in enumerate(zip(lines,widths)):
            xx=x-lw/2 if center else x; yy=y+i*(size+8)
            self.d.text((xx,yy),v,font=ft,fill=color)
            self.svg.append(f'<text x="{xx}" y="{yy}" font-size="{size}" fill="{color}" dominant-baseline="text-before-edge" font-weight="{700 if bold else 400}">{escape(v)}</text>')
        if export:
            self.vertex('<br>'.join(escape(v) for v in lines),f'text;html=1;whiteSpace=wrap;align={"center" if center else "left"};verticalAlign=top;fontFamily=Microsoft YaHei;fontSize={size};fontColor={color};fontStyle={1 if bold else 0};fillColor={"#FFFFFF" if bg else "none"};strokeColor=none;',(left-3,y-2,w+6,h+4))

    def shape(self,box,label,kind='rect',fill='#F3F7FC',size=28):
        x,y,w,h=box
        if kind=='ellipse':
            self.d.ellipse((x,y,x+w,y+h),fill=fill,outline=BLUE,width=3)
            self.svg.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{BLUE}" stroke-width="3"/>')
            sty='ellipse;'
        elif kind=='store':
            for yy in (y,y+h): self.line([(x,yy),(x+w,yy)],export=False)
            self.line([(x,y),(x,y+h)],export=False)
            sty='shape=partialRectangle;top=1;bottom=1;left=1;right=0;'
        elif kind=='package':
            self.d.rectangle((x,y+25,x+w,y+h),fill=fill,outline=BLUE,width=3)
            self.d.rectangle((x,y,x+w*.4,y+25),fill=fill,outline=BLUE,width=3)
            self.svg.append(f'<path d="M {x} {y+25} V {y} H {x+w*.4} V {y+25} H {x+w} V {y+h} H {x} Z" fill="{fill}" stroke="{BLUE}" stroke-width="3"/>')
            sty='shape=folder;tabWidth=80;tabHeight=25;'
        else:
            self.d.rectangle((x,y,x+w,y+h),fill=fill,outline=BLUE,width=3)
            self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{BLUE}" stroke-width="3"/>')
            sty='rounded=0;'
        self.vertex('',sty+f'html=1;fillColor={fill};strokeColor={BLUE};strokeWidth=3;',box)
        self.text(x+w/2,y+(h-len(label.split('\n'))*(size+8))/2,label,size,center=True)

    def line(self,pts,label='',dashed=False,arrow=False,color=INK,width=3,export=True,labelpos=None):
        for (x1,y1),(x2,y2) in zip(pts,pts[1:]):
            length=math.hypot(x2-x1,y2-y1)
            if dashed and length:
                for offset in range(0,int(length),18):
                    end=min(offset+10,length)
                    self.d.line((x1+(x2-x1)*offset/length,y1+(y2-y1)*offset/length,x1+(x2-x1)*end/length,y1+(y2-y1)*end/length),fill=color,width=width)
            else: self.d.line((x1,y1,x2,y2),fill=color,width=width)
        pstr=' '.join(f'{x},{y}' for x,y in pts)
        dash=' stroke-dasharray="10 8"' if dashed else ''
        self.svg.append(f'<polyline points="{pstr}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')
        if arrow:
            x,y=pts[-1]; px,py=pts[-2]; a=math.atan2(y-py,x-px)
            wing=[(x-16*math.cos(a-.45),y-16*math.sin(a-.45)),(x,y),(x-16*math.cos(a+.45),y-16*math.sin(a+.45))]
            self.d.line(wing,fill=color,width=width)
            self.svg.append(f'<polyline points="{" ".join(f"{a},{b}" for a,b in wing)}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        if export:
            self.n+=1
            c=ET.SubElement(self.root,'mxCell',id=str(self.n),parent='1',edge='1',style=f'html=1;rounded=0;strokeColor={color};strokeWidth={width};endArrow={"open" if arrow else "none"};endFill=0;dashed={int(dashed)};')
            g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
            ET.SubElement(g,'mxPoint',x=str(pts[0][0]),y=str(pts[0][1]),attrib={'as':'sourcePoint'})
            ET.SubElement(g,'mxPoint',x=str(pts[-1][0]),y=str(pts[-1][1]),attrib={'as':'targetPoint'})
            if len(pts)>2:
                a=ET.SubElement(g,'Array',attrib={'as':'points'})
                for x,y in pts[1:-1]: ET.SubElement(a,'mxPoint',x=str(x),y=str(y))
        if label:
            x,y=labelpos or ((pts[0][0]+pts[-1][0])/2,(pts[0][1]+pts[-1][1])/2-38)
            self.text(x,y,label,24,center=True,bg=True)

    def save(self,folder,stem):
        folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
        self.im.save(folder/f'{stem}.png',dpi=(240,240))
        (folder/f'{stem}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}"><rect width="100%" height="100%" fill="white"/><g font-family="Microsoft YaHei, sans-serif">'+''.join(self.svg)+'</g></svg>',encoding='utf-8')

def drawio(pages,path):
    f=ET.Element('mxfile',host='app.diagrams.net',version='24.7.17')
    for i,c in enumerate(pages):
        d=ET.SubElement(f,'diagram',id=f'week6-{i+1}',name=c.title)
        d.append(c.model)
    ET.ElementTree(f).write(path,encoding='utf-8',xml_declaration=True)

def wrap(text,limit):
    """按中英文近似显示宽度换行，不截断内容。"""
    lines=[]; cur=''; length=0
    for c in str(text):
        z=1 if ord(c)>255 else .53
        if c=='\n' or length+z>limit:
            lines.append(cur);cur='';length=0
        if c!='\n': cur+=c;length+=z
    if cur:lines.append(cur)
    return '\n'.join(lines)

def sequence(case,folder):
    ps=case['participants']; ms=case['messages']; n=len(ps)
    step=128
    # 消息标签最多两行时保持箭头之间的空隙。
    height=450+len(ms)*step+100+(100 if case['id']=='UC04' else 0)
    subtitle='注册保存后的结果跳转存在缺陷；第10步起为用户收到邮件后单独发起的激活请求。' if case['id']=='UC04' else '分析级交互：消息名称表达职责；条件与异常见对应的用例说明。'
    c=Canvas(f"{case['id']} {case['name']}顺序图",2200,height,subtitle)
    positions={p['id']:180+i*(1840/max(n-1,1)) for i,p in enumerate(ps)}
    for p in ps:
        x=positions[p['id']]; role=p.get('kind','control')
        fill={'actor':'#FFFFFF','boundary':'#E9F1FC','control':'#F2F1F9','entity':'#EAF4EE','external':'#FFF4E6'}.get(role,'#F3F7FC')
        label=wrap(p['label'],9)
        c.shape((x-165,145,330,195),f'«{role}»\n{label}',fill=fill,size=32)
        c.line([(x,340),(x,height-80)],dashed=True,color='#A4B2C3',width=2)
    for i,m in enumerate(ms):
        x1,x2=positions[m['from']],positions[m['to']]; y=440+i*step
        if case['id']=='UC04' and i>=9:
            y+=100
            if i==9:
                c.line([(75,y-120),(2120,y-120)],dashed=True,color=GRAY,width=2)
                c.text(1100,y-115,'后续独立请求：用户已收到验证邮件并打开有效链接',28,center=True,bg=True)
        reply=m.get('type')=='return'
        txt=f"{i+1}. {m['text']}"
        if x1==x2:
            right=x1+170 if x1<1800 else x1-170
            c.line([(x1,y),(right,y),(right,y+32),(x1,y+32)],dashed=reply,arrow=True)
            c.text(x1+18 if right>x1 else right,y-80,wrap(txt,15),32,bg=True)
        else:
            c.line([(x1,y),(x2,y)],dashed=reply,arrow=True,color=GRAY if reply else INK)
            available=abs(x2-x1)/32-1
            txt=wrap(txt,max(10,available))
            count=len(txt.split('\n'))
            c.text((x1+x2)/2,y-count*40-5,txt,32,center=True,bg=True)
        if not reply:
            c.shape((x2-6,y,12,33),'',fill='white',size=10)
    c.text(60,height-52,'实线：调用/操作    虚线：返回    细条：执行    时间自上而下；图中条件、外部送达与现存缺陷见对应说明。',23,color=GRAY)
    c.save(folder,case['id']+'-顺序图')
    return c
