"""SZX：品牌图标和模板引用的轻量回归检查，不使用业务数据库。"""

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class BrandAssetTests(SimpleTestCase):
    def setUp(self):
        self.asset_dir = Path(settings.BASE_DIR) / 'blog' / 'static' / 'blog'

    def test_favicon_is_self_contained_and_has_a_reusable_mark(self):
        root = ET.parse(self.asset_dir / 'favicon.svg').getroot()
        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        self.assertEqual(root.attrib['viewBox'], '0 0 64 64')
        self.assertIn('接续', root.find('svg:title', namespace).text)
        self.assertIsNotNone(root.find('svg:g[@id="site-brand-mark"]', namespace))
        for tag in ('image', 'use', 'script'):
            self.assertIsNone(root.find(f'.//svg:{tag}', namespace))

    def test_relay_mark_preserves_the_approved_b_geometry(self):
        root = ET.parse(self.asset_dir / 'favicon.svg').getroot()
        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        paths = root.findall('svg:g[@id="site-brand-mark"]/svg:path', namespace)
        self.assertEqual([path.attrib['d'] for path in paths], [
            'M12 25L25 12H36V20H29L20 29V36H12V25Z',
            'M28 44H35L44 35V28H52V39L39 52H28V44Z',
        ])

    def test_png_fallback_and_touch_icon_have_declared_dimensions(self):
        for filename, size in (('favicon-32.png', 32), ('apple-touch-icon.png', 180)):
            with self.subTest(filename=filename):
                with (self.asset_dir / filename).open('rb') as asset:
                    header = asset.read(24)
                self.assertEqual(header[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(struct.unpack('>II', header[16:24]), (size, size))

    def test_both_icon_formats_and_touch_icon_use_versioned_asset_urls(self):
        html = render_to_string('share_layout/site_icons.html')
        for filename in ('favicon.svg', 'favicon-32.png', 'apple-touch-icon.png'):
            self.assertIn(f'blog/{filename}?v=relay-1', html)
        self.assertIn('sizes="32x32"', html)
        self.assertIn('sizes="180x180"', html)

    def test_page_mark_reuses_the_same_svg_and_is_decorative(self):
        html = render_to_string('share_layout/brand_mark.html')
        self.assertIn('favicon.svg?v=relay-1#site-brand-mark', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('focusable="false"', html)
        self.assertNotIn('<path', html)
