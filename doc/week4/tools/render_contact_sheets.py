"""Create temporary contact sheets from Word-exported PDFs for visual QA."""

import os
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


folder = Path(os.environ['TEMP']) / 'class3group6-week4-preview'
font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 24)
for pdf_path in folder.glob('*.pdf'):
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(.72, .72), alpha=False)
        image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        pages.append(image)
    columns = 2
    width = max(image.width for image in pages)
    height = max(image.height for image in pages)
    rows = (len(pages) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * (width + 30) + 30, rows * (height + 60) + 20), '#E7EBF2')
    draw = ImageDraw.Draw(sheet)
    for index, image in enumerate(pages):
        x = 30 + (index % columns) * (width + 30)
        y = 40 + (index // columns) * (height + 60)
        sheet.paste(image, (x, y))
        draw.text((x, y - 32), f'{pdf_path.stem} · 第 {index + 1} 页', font=font, fill='#17315B')
    output = folder / (pdf_path.stem + '-contact.png')
    sheet.save(output)
    print(output)
