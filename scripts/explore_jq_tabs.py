"""
Research script: Explore JoinQuant backtest result page tabs.

This script:
1. Starts the JQ automation service (login is cached)
2. Runs a fresh backtest with a 5/20 MA crossover strategy on 000001.XSHE
3. Clicks each sidebar tab and captures screenshots + DOM content
4. Investigates the "导出" button behavior
5. Prints all findings to stdout

Usage:
    cd /Users/macbook/Projects/my_python_project/quantgpt
    python scripts/explore_jq_tabs.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from quantgpt.jq_automation import JQAutomationService, JQBacktestConfig, _take_screenshot

# ---- Strategy that actually trades ----
STRATEGY_CODE = '''
def initialize(context):
    context.s1 = '000001.XSHE'
    context.short_period = 5
    context.long_period = 20
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # Enable logging to see trades
    log.set_level('order', 'debug')

def handle_data(context, data):
    s1 = context.s1
    prices = attribute_history(s1, context.long_period + 1, '1d', ['close'])
    short_ma = prices['close'][-context.short_period:].mean()
    long_ma = prices['close'].mean()

    current_position = context.portfolio.positions.get(s1)

    if short_ma > long_ma:
        if not current_position:
            order_value(s1, context.portfolio.available_cash * 0.95)
            log.info("BUY %s: short_ma=%.2f > long_ma=%.2f" % (s1, short_ma, long_ma))
    elif short_ma < long_ma:
        if current_position:
            order_target(s1, 0)
            log.info("SELL %s: short_ma=%.2f < long_ma=%.2f" % (s1, short_ma, long_ma))
'''

SCREENSHOT_DIR = Path("data/jq_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Sidebar tabs to explore (in order)
SIDEBAR_TABS = [
    "收益概述",
    "交易详情",
    "每日持仓&收益",
    "日志输出",
    "性能分析",
    "策略代码",
]


async def take_tab_screenshot(page, name: str) -> str:
    """Take a screenshot with a descriptive name."""
    path = SCREENSHOT_DIR / f"tab_{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"  Screenshot saved: {path}")
    return str(path)


async def explore_tab_content(page, tab_name: str) -> dict:
    """Extract DOM structure and content from the currently active tab."""
    info = {"tab": tab_name, "content_type": "unknown", "details": {}}

    await page.wait_for_timeout(2000)  # let content load

    # Get the main content area structure
    content_info = await page.evaluate("""(tabName) => {
        const result = {
            url: location.href,
            title: document.title,
            mainContentHTML: '',
            tables: [],
            charts: [],
            textBlocks: [],
            codeBlocks: [],
            allText: '',
        };

        // Find the main content area (right side of sidebar)
        // JQ uses a layout where sidebar is on the left, content on the right
        const contentArea = document.querySelector('.backtest-detail-content, .main-content, .right-content, [class*="content"]');

        // Look for tables
        const tables = document.querySelectorAll('table');
        tables.forEach((table, idx) => {
            const headers = [];
            const headerCells = table.querySelectorAll('thead th, thead td, tr:first-child th, tr:first-child td');
            headerCells.forEach(h => headers.push(h.innerText.trim()));

            const rows = [];
            const bodyRows = table.querySelectorAll('tbody tr');
            const rowCount = bodyRows.length;
            // Get first 5 rows as sample
            bodyRows.forEach((row, ridx) => {
                if (ridx < 5) {
                    const cells = [];
                    row.querySelectorAll('td').forEach(c => cells.push(c.innerText.trim()));
                    rows.push(cells);
                }
            });

            result.tables.push({
                index: idx,
                headers: headers,
                rowCount: rowCount,
                sampleRows: rows,
                tableClass: table.className,
                tableId: table.id,
                parentClass: table.parentElement?.className || '',
            });
        });

        // Look for chart containers (ECharts / canvas)
        const canvases = document.querySelectorAll('canvas');
        canvases.forEach((canvas, idx) => {
            const parent = canvas.parentElement;
            const grandparent = parent?.parentElement;
            result.charts.push({
                index: idx,
                width: canvas.width,
                height: canvas.height,
                parentId: parent?.id || '',
                parentClass: parent?.className || '',
                grandparentId: grandparent?.id || '',
                grandparentClass: grandparent?.className || '',
            });
        });

        // Look for ECharts instances
        try {
            if (typeof echarts !== 'undefined') {
                const echartsInstances = document.querySelectorAll('[_echarts_instance_]');
                echartsInstances.forEach((el, idx) => {
                    try {
                        const instance = echarts.getInstanceByDom(el);
                        if (instance) {
                            const option = instance.getOption();
                            result.charts.push({
                                index: 100 + idx,
                                type: 'echarts',
                                seriesCount: option?.series?.length || 0,
                                seriesTypes: (option?.series || []).map(s => s.type),
                                hasXAxis: !!option?.xAxis,
                                hasYAxis: !!option?.yAxis,
                                elementId: el.id,
                                elementClass: el.className,
                            });
                        }
                    } catch(e) {}
                });
            }
        } catch(e) {}

        // Look for code blocks
        const codeEls = document.querySelectorAll('pre, code, .ace_editor, .CodeMirror');
        codeEls.forEach((el, idx) => {
            result.codeBlocks.push({
                index: idx,
                tag: el.tagName,
                className: el.className,
                textLength: el.innerText?.length || 0,
                textPreview: (el.innerText || '').substring(0, 200),
            });
        });

        // Get text content of main area (not sidebar)
        // The sidebar has class containing "sidebar" or "left"
        const mainArea = document.querySelector('.backtest-section-right')
            || document.querySelector('.detail-right')
            || document.querySelector('[class*="right-panel"]')
            || document.querySelector('[class*="main-content"]');

        if (mainArea) {
            result.allText = mainArea.innerText.substring(0, 3000);
        } else {
            // Fallback: get body text minus sidebar
            result.allText = document.body.innerText.substring(0, 3000);
        }

        // Get the entire DOM structure of the content area for analysis
        const sidebar = document.querySelector('.backtest-section-left, .detail-left, [class*="sidebar"], [class*="left-panel"]');
        if (sidebar) {
            result.sidebarHTML = sidebar.innerHTML.substring(0, 2000);
            result.sidebarText = sidebar.innerText;
        }

        // Get the page's main sections
        const sections = document.querySelectorAll('section, .section, [class*="section"]');
        result.sectionCount = sections.length;

        // Check for pagination
        const pagination = document.querySelector('.pagination, .ant-pagination, [class*="pager"]');
        if (pagination) {
            result.hasPagination = true;
            result.paginationText = pagination.innerText.trim();
        }

        // Check for download/export buttons
        const exportBtns = document.querySelectorAll('[class*="export"], [class*="download"]');
        result.exportButtonCount = exportBtns.length;

        return result;
    }""", tab_name)

    info["details"] = content_info

    # Determine content type
    if content_info.get("tables") and len(content_info["tables"]) > 0:
        info["content_type"] = "table"
    if content_info.get("charts") and len(content_info["charts"]) > 0:
        info["content_type"] = "chart" if info["content_type"] == "unknown" else "table+chart"
    if content_info.get("codeBlocks") and len(content_info["codeBlocks"]) > 0:
        info["content_type"] = "code"
    if info["content_type"] == "unknown":
        info["content_type"] = "text"

    return info


async def click_sidebar_tab(page, tab_name: str) -> bool:
    """Click a sidebar tab by its text content."""
    # Try multiple strategies

    # Strategy 1: Find anchor or element with exact text
    clicked = await page.evaluate("""(tabName) => {
        // Look through all elements in the sidebar
        const candidates = document.querySelectorAll('a, li, div, span, .sidebar-item');
        for (const el of candidates) {
            const text = el.innerText?.trim();
            // Match exact text or text that starts with tabName
            if (text === tabName || text.startsWith(tabName)) {
                // Make sure it's in the sidebar (left side)
                const rect = el.getBoundingClientRect();
                if (rect.left < 300 && rect.width > 0 && rect.height > 0) {
                    el.click();
                    return true;
                }
            }
        }
        return false;
    }""", tab_name)

    if clicked:
        print(f"  Clicked sidebar tab: {tab_name}")
        return True

    # Strategy 2: Playwright text selector
    try:
        el = await page.wait_for_selector(f'text="{tab_name}"', timeout=3000)
        if el:
            await el.click()
            print(f"  Clicked sidebar tab (text selector): {tab_name}")
            return True
    except Exception:
        pass

    print(f"  WARNING: Could not click sidebar tab: {tab_name}")
    return False


async def explore_export_button(page) -> dict:
    """Investigate the 导出 button behavior."""
    result = {
        "found": False,
        "type": "unknown",
        "menu_items": [],
        "download_triggered": False,
    }

    # First, find the export button
    export_info = await page.evaluate("""() => {
        const result = {
            buttons: [],
            dropdowns: [],
        };

        // Find all elements containing "导出"
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
            if (el.children.length === 0 || el.tagName === 'BUTTON' || el.tagName === 'A') {
                const text = el.innerText?.trim();
                if (text && text.includes('导出') && text.length < 20) {
                    result.buttons.push({
                        tag: el.tagName,
                        text: text,
                        className: el.className,
                        id: el.id,
                        href: el.href || '',
                        rect: el.getBoundingClientRect(),
                        parentTag: el.parentElement?.tagName || '',
                        parentClass: el.parentElement?.className || '',
                        parentId: el.parentElement?.id || '',
                        outerHTML: el.outerHTML.substring(0, 500),
                    });
                }
            }
        }

        // Also look for dropdown menus that might already be visible
        const dropdowns = document.querySelectorAll('.dropdown-menu, .ant-dropdown, [class*="dropdown"], [class*="popover"]');
        dropdowns.forEach(dd => {
            result.dropdowns.push({
                className: dd.className,
                text: dd.innerText?.substring(0, 200),
                visible: dd.offsetParent !== null,
            });
        });

        return result;
    }""")

    print(f"\n=== Export Button Analysis ===")
    print(f"Found {len(export_info['buttons'])} elements containing '导出':")
    for btn in export_info['buttons']:
        print(f"  Tag: {btn['tag']}, Text: '{btn['text']}', Class: '{btn['className']}'")
        print(f"  ID: '{btn['id']}', Parent: {btn['parentTag']}.{btn['parentClass']}")
        print(f"  OuterHTML: {btn['outerHTML'][:200]}")

    if not export_info['buttons']:
        return result

    result["found"] = True

    # Take screenshot before clicking
    await take_tab_screenshot(page, "export_before_click")

    # Try clicking the export button
    clicked = await page.evaluate("""() => {
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
            const text = el.innerText?.trim();
            if (text === '导出' || text === '导 出') {
                el.click();
                return true;
            }
        }
        return false;
    }""")

    if clicked:
        print("  Clicked 导出 button")
        await page.wait_for_timeout(1500)

        # Take screenshot after clicking
        await take_tab_screenshot(page, "export_after_click")

        # Check what appeared
        after_click = await page.evaluate("""() => {
            const result = {
                newDropdowns: [],
                newMenuItems: [],
                downloadLinks: [],
                visiblePopups: [],
            };

            // Check for newly visible dropdowns/menus
            const dropdowns = document.querySelectorAll(
                '.dropdown-menu, .ant-dropdown, [class*="dropdown"], [class*="popover"], [class*="menu"], ul[role="menu"]'
            );
            dropdowns.forEach(dd => {
                if (dd.offsetParent !== null || getComputedStyle(dd).display !== 'none') {
                    result.newDropdowns.push({
                        className: dd.className,
                        id: dd.id,
                        text: dd.innerText?.substring(0, 500),
                        html: dd.innerHTML?.substring(0, 1000),
                    });

                    // Get menu items
                    const items = dd.querySelectorAll('a, li, .menu-item, [class*="item"]');
                    items.forEach(item => {
                        const t = item.innerText?.trim();
                        if (t && t.length < 50) {
                            result.newMenuItems.push({
                                text: t,
                                tag: item.tagName,
                                href: item.href || '',
                                className: item.className,
                            });
                        }
                    });
                }
            });

            // Check for download links
            const links = document.querySelectorAll('a[download], a[href*="download"], a[href*="export"]');
            links.forEach(a => {
                result.downloadLinks.push({
                    text: a.innerText?.trim(),
                    href: a.href,
                    download: a.download,
                });
            });

            // Check for any newly visible popup/modal
            const modals = document.querySelectorAll('.modal, .dialog, [class*="modal"], [class*="dialog"]');
            modals.forEach(m => {
                if (m.offsetParent !== null) {
                    result.visiblePopups.push({
                        className: m.className,
                        text: m.innerText?.substring(0, 300),
                    });
                }
            });

            return result;
        }""")

        print(f"  After click - Dropdowns found: {len(after_click['newDropdowns'])}")
        for dd in after_click['newDropdowns']:
            print(f"    Dropdown class: {dd['className']}")
            print(f"    Dropdown text: {dd['text'][:200]}")

        print(f"  Menu items found: {len(after_click['newMenuItems'])}")
        for item in after_click['newMenuItems']:
            print(f"    Item: '{item['text']}' (tag={item['tag']}, href={item.get('href', '')})")

        result["menu_items"] = after_click['newMenuItems']
        result["dropdowns"] = after_click['newDropdowns']

        print(f"  Download links found: {len(after_click['downloadLinks'])}")
        for dl in after_click['downloadLinks']:
            print(f"    Download: '{dl['text']}' -> {dl['href']}")

    return result


async def setup_download_listener(page):
    """Set up a download event listener."""
    # Playwright download handling
    downloads = []

    def on_download(download):
        downloads.append({
            "url": download.url,
            "suggested_filename": download.suggested_filename,
        })
        print(f"  DOWNLOAD triggered: {download.suggested_filename} from {download.url[:100]}")

    page.on("download", on_download)
    return downloads


async def main():
    print("=" * 70)
    print("JoinQuant Backtest Result Page - Tab Exploration Research")
    print("=" * 70)

    service = JQAutomationService()

    try:
        # Step 1: Start service
        print("\n[1/5] Starting JQ automation service...")
        ok = await service.startup()
        if not ok:
            print("ERROR: Failed to start/login. Check credentials and browser state.")
            return
        print("  Login successful!")

        page = service._page
        assert page is not None

        # Set up download listener
        downloads = await setup_download_listener(page)

        # Step 2: Navigate to latest backtest result (skip re-running)
        print("\n[2/5] Navigating to latest backtest result...")

        # First try: go to backtest list and find latest
        LATEST_BACKTEST_URL = "https://www.joinquant.com/algorithm/backtest/detail?backtestId=a70f426cc3f134f71e8cf568dceef7ff"
        try:
            await page.goto(LATEST_BACKTEST_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Direct navigation failed: {e}")
            # Fallback: try via algorithm page -> backtest list
            await page.goto("https://www.joinquant.com/algorithm/index/edit", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

        current_url = page.url
        print(f"  Current URL: {current_url}")

        if "backtest/detail" not in current_url:
            print("  Not on a backtest detail page. Trying to run a fresh backtest...")
            config = JQBacktestConfig(
                start_date="2023-01-01",
                end_date="2024-06-30",
                initial_capital=100000,
                frequency="day",
            )
            result = await service.run_backtest(STRATEGY_CODE, config, on_status=lambda s: print(f"  Status: {s}"))
            if not result.success:
                print(f"  ERROR: {result.error}")
                return
            current_url = page.url
            print(f"  After backtest URL: {current_url}")

        # Wait for page to fully load
        await page.wait_for_timeout(2000)
        print("  On backtest results page!")

        # Step 3: Explore each sidebar tab
        print("\n[3/5] Exploring sidebar tabs...")

        all_tab_info = {}

        for i, tab_name in enumerate(SIDEBAR_TABS):
            print(f"\n--- Tab {i+1}/{len(SIDEBAR_TABS)}: {tab_name} ---")

            # Click the tab
            clicked = await click_sidebar_tab(page, tab_name)

            if not clicked:
                print(f"  Skipping (could not click)")
                continue

            # Wait for content to load
            await page.wait_for_timeout(3000)

            # Take screenshot
            safe_name = tab_name.replace("&", "_and_").replace(" ", "_")
            await take_tab_screenshot(page, f"{i+1}_{safe_name}")

            # Extract DOM content
            tab_info = await explore_tab_content(page, tab_name)
            all_tab_info[tab_name] = tab_info

            # Print summary
            print(f"  Content type: {tab_info['content_type']}")
            details = tab_info['details']

            if details.get('tables'):
                for t in details['tables']:
                    print(f"  Table: headers={t['headers']}, rows={t['rowCount']}, class='{t['tableClass']}'")
                    if t['sampleRows']:
                        for row in t['sampleRows'][:2]:
                            print(f"    Sample row: {row}")

            if details.get('charts'):
                for c in details['charts']:
                    ctype = c.get('type', 'canvas')
                    print(f"  Chart: type={ctype}, parentClass='{c.get('parentClass', '')}', id='{c.get('parentId', '') or c.get('elementId', '')}'")
                    if 'seriesTypes' in c:
                        print(f"    Series: {c['seriesTypes']}")

            if details.get('codeBlocks'):
                for cb in details['codeBlocks']:
                    print(f"  Code block: tag={cb['tag']}, class='{cb['className']}', length={cb['textLength']}")
                    if cb['textPreview']:
                        print(f"    Preview: {cb['textPreview'][:100]}...")

            # Print some of the text content
            text = details.get('allText', '')
            if text:
                # Show first 500 chars
                preview = text[:500].replace('\n', '\n    ')
                print(f"  Text preview:\n    {preview}")

        # Step 4: Back to 收益概述 to explore sub-items
        print("\n[4/5] Exploring 收益概述 sub-items (chart selectors)...")
        await click_sidebar_tab(page, "收益概述")
        await page.wait_for_timeout(2000)

        # Get all sidebar items (including sub-items)
        sidebar_items = await page.evaluate("""() => {
            const items = [];
            // Get all clickable items in the sidebar
            const sidebar = document.querySelector('.backtest-section-left, .detail-left, [class*="sidebar"]');
            if (!sidebar) {
                // Fallback: find by position
                const allEls = document.querySelectorAll('a, li, div, span');
                for (const el of allEls) {
                    const rect = el.getBoundingClientRect();
                    if (rect.left < 250 && rect.width > 20 && rect.height > 10 && rect.top > 150) {
                        const text = el.innerText?.trim();
                        if (text && text.length < 30 && text.length > 0) {
                            items.push({
                                text: text,
                                tag: el.tagName,
                                className: el.className,
                                x: rect.left,
                                y: rect.top,
                                isActive: el.classList?.contains('active') || false,
                            });
                        }
                    }
                }
            } else {
                const children = sidebar.querySelectorAll('a, li, div, span');
                children.forEach(el => {
                    const text = el.innerText?.trim();
                    if (text && text.length < 30 && el.offsetHeight > 0) {
                        items.push({
                            text: text,
                            tag: el.tagName,
                            className: el.className,
                            isActive: el.classList?.contains('active') || false,
                        });
                    }
                });
            }
            return items;
        }""")

        print(f"  Sidebar items found: {len(sidebar_items)}")
        seen = set()
        for item in sidebar_items:
            text = item['text']
            if text not in seen and len(text) < 20:
                seen.add(text)
                print(f"    [{item['tag']}] {text} (class={item['className'][:50]})")

        # Step 5: Explore export button
        print("\n[5/5] Investigating export button...")

        # First, go back to 收益概述
        await click_sidebar_tab(page, "收益概述")
        await page.wait_for_timeout(1500)

        export_result = await explore_export_button(page)

        # If export has a dropdown, try to click each option and monitor downloads
        if export_result.get("menu_items"):
            for item in export_result["menu_items"]:
                item_text = item['text']
                if not item_text or item_text in ('导出', '导 出'):
                    continue
                print(f"\n  Trying to click export option: '{item_text}'...")

                # Re-click the export button to open dropdown
                await page.evaluate("""() => {
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        const text = el.innerText?.trim();
                        if (text === '导出' || text === '导 出') {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                await page.wait_for_timeout(500)

                # Click the specific menu item
                clicked = await page.evaluate(f"""(itemText) => {{
                    const allEls = document.querySelectorAll('a, li, div, span, button');
                    for (const el of allEls) {{
                        if (el.innerText?.trim() === itemText && el.offsetParent !== null) {{
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""", item_text)

                if clicked:
                    print(f"    Clicked '{item_text}'")
                    await page.wait_for_timeout(3000)
                    await take_tab_screenshot(page, f"export_{item_text.replace(' ', '_')}")

                    # Check for downloads
                    if downloads:
                        print(f"    Downloads triggered: {json.dumps(downloads, ensure_ascii=False)}")

        # Check if any downloads happened
        print(f"\n  Total downloads captured: {len(downloads)}")
        for dl in downloads:
            print(f"    {dl}")

        # Final: get the full sidebar DOM structure for reference
        print("\n\n" + "=" * 70)
        print("FULL SIDEBAR DOM STRUCTURE")
        print("=" * 70)

        sidebar_html = await page.evaluate("""() => {
            // Try to get the sidebar element
            const sidebar = document.querySelector('.backtest-section-left')
                || document.querySelector('[class*="left-panel"]')
                || document.querySelector('[class*="sidebar"]');
            if (sidebar) {
                return {
                    html: sidebar.outerHTML.substring(0, 5000),
                    text: sidebar.innerText,
                    className: sidebar.className,
                    id: sidebar.id,
                };
            }
            // Fallback: get all elements in the left 220px
            const leftEls = [];
            document.querySelectorAll('*').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.left < 220 && rect.width > 20 && rect.height > 0 && rect.top > 100) {
                    if (el.children.length === 0) {
                        leftEls.push({tag: el.tagName, text: el.innerText?.trim(), class: el.className});
                    }
                }
            });
            return {html: '', text: JSON.stringify(leftEls, null, 2), className: 'fallback', id: ''};
        }""")

        print(f"Sidebar class: {sidebar_html.get('className', '')}")
        print(f"Sidebar text:\n{sidebar_html.get('text', '')}")
        print(f"\nSidebar HTML (first 3000 chars):\n{sidebar_html.get('html', '')[:3000]}")

        # Get the top action buttons structure
        print("\n\n" + "=" * 70)
        print("TOP ACTION BUTTONS STRUCTURE")
        print("=" * 70)

        top_buttons = await page.evaluate("""() => {
            const result = [];
            // Find buttons in the header area
            const allBtns = document.querySelectorAll('button, a, [class*="btn"]');
            allBtns.forEach(btn => {
                const rect = btn.getBoundingClientRect();
                if (rect.top < 160 && rect.right > 800) {  // top-right area
                    result.push({
                        text: btn.innerText?.trim(),
                        tag: btn.tagName,
                        className: btn.className,
                        id: btn.id,
                        href: btn.href || '',
                        outerHTML: btn.outerHTML.substring(0, 300),
                    });
                }
            });
            return result;
        }""")

        for btn in top_buttons:
            if btn['text']:
                print(f"  [{btn['tag']}] '{btn['text']}' class='{btn['className'][:60]}' id='{btn['id']}'")
                print(f"    HTML: {btn['outerHTML'][:200]}")

        # Summary
        print("\n\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        for tab_name, info in all_tab_info.items():
            print(f"\n{tab_name}:")
            print(f"  Content type: {info['content_type']}")
            details = info['details']
            if details.get('tables'):
                for t in details['tables']:
                    print(f"  Table: {t['rowCount']} rows, headers: {t['headers']}")
            if details.get('charts'):
                for c in details['charts']:
                    print(f"  Chart: type={c.get('type', 'canvas')}")
            if details.get('codeBlocks'):
                for cb in details['codeBlocks']:
                    print(f"  Code: {cb['tag']} ({cb['textLength']} chars)")

        print(f"\nDownloads captured: {len(downloads)}")
        for dl in downloads:
            print(f"  {dl}")

        print(f"\nScreenshots saved to: {SCREENSHOT_DIR.resolve()}")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n\nShutting down browser...")
        await service.shutdown()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
