// Capture real pages from the locally seeded demo database.
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const baseUrl = process.env.BLOG_BASE_URL || 'http://127.0.0.1:8765';
const outDir = path.resolve(__dirname, '..', 'assets');
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_EXECUTABLE || undefined,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const capture = async (name, url) => {
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
      if (!response || response.status() >= 400) throw new Error(`${name}: HTTP ${response?.status()}`);
      await page.screenshot({ path: path.join(outDir, name), animations: 'disabled' });
      console.log(`${name}: ${response.status()} ${page.url()} | ${await page.title()}`);
    };

    await capture('01-home-desktop.png', `${baseUrl}/`);
    const articleHref = await page.locator('a[href*="/article/"]')
      .filter({ hasText: '提示注入与越权调用' }).first().getAttribute('href');
    const categoryHref = await page.locator('a[href*="/category/"]').first().getAttribute('href');
    if (!articleHref || !categoryHref) throw new Error('Article or category link missing on homepage');
    await capture('02-article-detail.png', new URL(articleHref, baseUrl).href);
    await page.getByText('发表评论', { exact: true }).first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(outDir, '02b-article-comments.png'), animations: 'disabled' });
    await capture('03-category.png', new URL(categoryHref, baseUrl).href);
    await capture('04-login.png', `${baseUrl}/login/`);
    await capture('04b-search.png', `${baseUrl}/search/?q=Agent`);

    await page.setViewportSize({ width: 390, height: 844 });
    await capture('05-home-mobile.png', `${baseUrl}/`);
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
