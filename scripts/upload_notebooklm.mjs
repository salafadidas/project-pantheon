#!/usr/bin/env node
/**
 * upload_notebooklm.mjs
 *
 * 自動將最新 PROJECT_PLAN_vX.Y.md 上傳到 NotebookLM
 * 帳號：salafadidas@gmail.com
 * Notebook：Project Pantheon（萬神殿計畫）
 *
 * 用法：
 *   node scripts/upload_notebooklm.mjs
 *
 * 首次執行：會開啟有頭瀏覽器，請手動登入 Google，之後 session 永久保存。
 * 後續執行：自動完成，無需干預。
 *
 * 前置條件（Mac）：
 *   brew install node
 *   npm install -g playwright
 *   npx playwright install chromium
 */

import { chromium } from 'playwright';
import { execSync } from 'child_process';
import { existsSync, readdirSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import { homedir, tmpdir } from 'os';

// ── 設定 ────────────────────────────────────────────────────────────────────
const PROFILE_DIR   = join(homedir(), '.pantheon-playwright-profile');
const NOTEBOOK_NAME = 'Project Pantheon（萬神殿計畫）';
const DOCS_DIR      = join(new URL('.', import.meta.url).pathname, '..', 'docs');
const NOTEBOOKLM    = 'https://notebooklm.google.com';

// ── 工具函式 ─────────────────────────────────────────────────────────────────
function findLatestPlan() {
  const files = readdirSync(DOCS_DIR)
    .filter(f => /^PROJECT_PLAN_v[\d.]+\.md$/.test(f))
    .sort((a, b) => {
      const ver = f => f.match(/v([\d.]+)/)[1].split('.').map(Number);
      const [va, vb] = [ver(a), ver(b)];
      for (let i = 0; i < Math.max(va.length, vb.length); i++) {
        const diff = (vb[i] || 0) - (va[i] || 0);
        if (diff !== 0) return diff;
      }
      return 0;
    });

  if (files.length === 0) throw new Error('找不到 PROJECT_PLAN_vX.Y.md');
  const latest = files[0];
  console.log(`📄 最新 plan 檔案：${latest}`);
  return join(DOCS_DIR, latest);
}

async function waitAndClick(page, selector, description, timeout = 10000) {
  console.log(`  → ${description}`);
  await page.waitForSelector(selector, { timeout });
  await page.click(selector);
}

// ── 主流程 ───────────────────────────────────────────────────────────────────
async function main() {
  const planPath = findLatestPlan();
  const planName = planPath.split('/').pop();

  const profileExists = existsSync(PROFILE_DIR);
  if (!profileExists) {
    mkdirSync(PROFILE_DIR, { recursive: true });
  }

  // --headless flag：用於自動排程（launchd）；首次執行必須有頭瀏覽器
  const wantHeadless = process.argv.includes('--headless') || process.env.PANTHEON_HEADLESS === '1';
  const headless = wantHeadless && profileExists;
  if (wantHeadless && !profileExists) {
    console.log('⚠️  尚無已儲存的 Google session，改用有頭瀏覽器進行首次登入。');
  }
  if (!headless) {
    console.log('\n🔑 請在開啟的瀏覽器中登入 salafadidas@gmail.com（已登入則會自動跳過）');
  }

  const context = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless,
    slowMo: headless ? 0 : 300,
    viewport: { width: 1280, height: 800 },
    args: ['--no-sandbox'],
  });

  const page = await context.newPage();

  try {
    // ── 1. 前往 NotebookLM ──────────────────────────────────────────────────
    console.log('\n🌐 前往 NotebookLM...');
    await page.goto(NOTEBOOKLM, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    // 用 URL 判斷是否需要登入（比文字偵測更可靠）
    const checkLoginNeeded = () => {
      const u = page.url();
      return !u.includes('notebooklm.google.com') || u.includes('accounts.google') || u.includes('signin');
    };
    if (checkLoginNeeded()) {
      console.log('⏳ 請在開啟的瀏覽器視窗中登入 salafadidas@gmail.com（等待最多 3 分鐘）...');
      await page.waitForURL(
        url => url.toString().includes('notebooklm.google.com') && !url.toString().includes('accounts.google'),
        { timeout: 180000 }
      );
      await page.waitForLoadState('networkidle');
      console.log('  ✅ 登入完成');
    }

    // ── 2. 找到目標 Notebook ────────────────────────────────────────────────
    console.log(`\n🔍 尋找 notebook：${NOTEBOOK_NAME}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 先嘗試精確比對，若失敗改用部分比對
    let notebookCard = page.getByText(NOTEBOOK_NAME, { exact: true }).first();
    const exactVisible = await notebookCard.isVisible().catch(() => false);
    if (!exactVisible) {
      console.log('  → 精確比對未找到，改用部分比對...');
      notebookCard = page.getByText('Project Pantheon', { exact: false }).first();
    }
    await notebookCard.waitFor({ timeout: 20000 });
    await notebookCard.click();
    await page.waitForLoadState('networkidle');
    console.log('  ✅ 已開啟 notebook');

    // ── 3. 刪除舊版 PROJECT_PLAN source ────────────────────────────────────
    console.log('\n🗑️  尋找並刪除舊版 PROJECT_PLAN source...');
    await page.waitForTimeout(2000);

    // 找所有包含 PROJECT_PLAN 的 source item
    const sourceItems = page.locator('[data-source-title*="PROJECT_PLAN"], [title*="PROJECT_PLAN"]');
    const count = await sourceItems.count();

    if (count > 0) {
      for (let i = count - 1; i >= 0; i--) {
        const item = sourceItems.nth(i);
        const title = await item.getAttribute('data-source-title') || await item.getAttribute('title') || '';
        console.log(`  → 刪除：${title}`);

        // hover 顯示刪除按鈕
        await item.hover();
        await page.waitForTimeout(500);

        // 點選更多選項（⋮）或刪除按鈕
        const moreBtn = item.locator('button[aria-label*="more"], button[aria-label*="More"], button[aria-label*="刪除"]').first();
        if (await moreBtn.isVisible()) {
          await moreBtn.click();
          await page.waitForTimeout(300);
          // 點選 Delete / Remove
          await page.locator('text=/^(Delete|Remove|刪除)/i').first().click();
          await page.waitForTimeout(1000);
        }
      }
      console.log('  ✅ 舊版已刪除');
    } else {
      // 嘗試用 Sources 面板通用方式搜尋
      const allSources = page.locator('.source-item, [class*="SourceChip"], [class*="source-chip"]');
      const total = await allSources.count();
      let deleted = 0;
      for (let i = total - 1; i >= 0; i--) {
        const src = allSources.nth(i);
        const text = await src.innerText().catch(() => '');
        if (text.includes('PROJECT_PLAN')) {
          await src.hover();
          await page.waitForTimeout(400);
          const del = src.locator('button').last();
          if (await del.isVisible()) {
            await del.click();
            await page.waitForTimeout(800);
            deleted++;
          }
        }
      }
      if (deleted === 0) {
        console.log('  ℹ️  未找到舊版 PROJECT_PLAN source（首次上傳）');
      } else {
        console.log(`  ✅ 已刪除 ${deleted} 個舊版`);
      }
    }

    // ── 4. 上傳新版 plan 檔案 ───────────────────────────────────────────────
    console.log(`\n📤 上傳：${planName}`);

    // 點擊 Add source / + 按鈕
    const addBtn = page.locator('button[aria-label*="Add source"], button[aria-label*="add source"], button:has-text("Add source"), button[mattooltip*="source"]').first();
    await addBtn.waitFor({ timeout: 10000 });
    await addBtn.click();
    await page.waitForTimeout(800);

    // 選擇「Upload file」
    const uploadOption = page.locator('text=/Upload file|上傳檔案/i').first();
    await uploadOption.waitFor({ timeout: 5000 });
    await uploadOption.click();
    await page.waitForTimeout(500);

    // 處理 file input
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.locator('input[type="file"]').first().click().catch(() => {}),
    ]);
    await fileChooser.setFiles(planPath);
    console.log('  → 檔案已選擇，等待上傳完成...');

    // 等待上傳完成（source 出現在列表）
    await page.waitForSelector(`text="${planName.replace('.md', '')}"`, { timeout: 60000 })
      .catch(() => console.log('  ⚠️  無法確認上傳狀態，請手動確認'));

    console.log(`\n✅ 上傳完成：${planName}`);
    console.log(`   Notebook：${NOTEBOOK_NAME}`);
    console.log(`   帳號：salafadidas@gmail.com\n`);

    await page.waitForTimeout(2000);

  } finally {
    await context.close();
  }
}

main().catch(err => {
  console.error('\n❌ 錯誤：', err.message);
  process.exit(1);
});
