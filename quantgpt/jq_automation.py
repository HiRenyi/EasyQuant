"""JoinQuant browser automation via Playwright.

Browser stays alive in background after startup().
Call run_backtest() to execute a strategy on the already-logged-in session.

Usage:
    service = JQAutomationService()
    await service.startup()       # launch browser + login once
    result = await service.run_backtest(code, config, on_status=callback)
    # ... run more backtests ...
    await service.shutdown()      # cleanup
"""

import asyncio
import csv
import io
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

# ---- Configuration ----

JQ_LOGIN_URL = "https://www.joinquant.com/user/login/index"
JQ_ALGORITHM_URL = "https://www.joinquant.com/algorithm/index/edit"
JQ_BACKTEST_TIMEOUT = int(os.environ.get("JQ_BACKTEST_TIMEOUT", "900"))  # seconds
STEP_TIMEOUT = 30_000  # ms, per-step timeout for element detection
POLL_INTERVAL = 3  # seconds, polling interval for backtest completion


# ---- Selector configuration (centralized for easy maintenance) ----

SELECTORS = {
    # Login page
    "login_tab_password": [
        'text=密码登录',
    ],
    "login_phone_input": [
        'input[name="phone"]',
        'input[name="mobile"]',
        'input[placeholder*="手机"]',
        'input[type="tel"]',
    ],
    "login_password_input": [
        'input[name="password"]',
        'input[type="password"]',
    ],
    "login_agreement_checkbox": [
        'input[type="checkbox"]',
        '.agreement input',
        '.protocol input',
    ],
    "login_button": [
        'button:has-text("登 录")',
        'button:has-text("登录")',
        'button[type="submit"]',
        '.login-btn',
        'input[type="submit"]',
    ],
    "login_success_indicator": [
        '.user-name',
        '.user-avatar',
        '.user-info',
        'a[href*="logout"]',
        'a[href*="/user/"]',
    ],
    "captcha_indicator": [
        '.captcha',
        '#captcha',
        'img[src*="captcha"]',
        '.geetest',
        '.slider-captcha',
    ],
    # Strategy editor (JoinQuant uses Ace Editor)
    "code_editor": [
        '#ide-container',
        '.ace_editor',
        '.CodeMirror',
        '.monaco-editor',
    ],
    # Backtest controls (exact JoinQuant IDs)
    "start_date_input": [
        '#startTime',
        'input[name="backtest[startTime]"]',
    ],
    "end_date_input": [
        '#endTime',
        'input[name="backtest[endTime]"]',
    ],
    "capital_input": [
        '#daily_backtest_capital_base_box',
        'input[name="backtest[baseCapital]"]',
    ],
    "frequency_input": [
        '#frequency',
    ],
    "run_backtest_button": [
        '#daily-new-backtest-button',
        '#full-backtest-button',
        'button:has-text("运行回测")',
        'a:has-text("运行回测")',
    ],
    "compile_run_button": [
        '#validate-button',
        'text="编译运行"',
        'li:has-text("编译运行")',
        'a:has-text("编译运行")',
    ],
    # Results page (backtest/detail)
    "backtest_complete_indicator": [
        'text=回测完成',
        '.top-level-stat',
    ],
    "backtest_running_indicator": [
        'text=回测中',
        'text=排队中',
        '.backtest-loading',
    ],
    "backtest_error_indicator": [
        'text=回测失败',
        'text=编译错误',
        '.backtest-error',
    ],
}


# ---- Data classes ----

@dataclass
class JQBacktestConfig:
    start_date: str = "2023-01-01"
    end_date: str = "2025-12-31"
    initial_capital: float = 1_000_000.0
    benchmark: str = "000300.XSHG"
    frequency: str = "day"  # "day" | "minute"


@dataclass
class JQBacktestResult:
    success: bool = False
    error: str | None = None
    metrics: dict = field(default_factory=dict)
    equity_curve: list[dict] = field(default_factory=list)   # [{date, strategy_return, benchmark_return}]
    trades: list[dict] = field(default_factory=list)          # [{date, security, direction, amount, price, ...}]
    daily_positions: list[dict] = field(default_factory=list)  # [{date, security, amount, avg_cost, ...}]
    csv_path: str | None = None
    screenshot_path: str | None = None


# ---- Helper ----

async def _find_element(page: Page, selector_list: list[str], timeout: int = STEP_TIMEOUT):
    """Try multiple selectors, return the first element found."""
    per_selector_timeout = max(timeout // len(selector_list), 3000)
    for selector in selector_list:
        try:
            element = await page.wait_for_selector(selector, timeout=per_selector_timeout)
            if element:
                return element
        except Exception:
            continue
    raise TimeoutError(f"未找到元素, 尝试的选择器: {selector_list}")


async def _take_screenshot(page: Page, name: str) -> str | None:
    """Take a debug screenshot, return the path."""
    try:
        screenshots_dir = Path("data/jq_screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = screenshots_dir / f"{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        logger.info(f"Screenshot saved: {path}")
        return str(path)
    except Exception as e:
        logger.warning(f"Failed to take screenshot: {e}")
        return None


def _sanitize_error(raw: str) -> str:
    """Strip internal Playwright/browser details from error messages shown to users."""
    if "Timeout" in raw and "exceeded" in raw:
        return "回测执行超时，请稍后重试"
    if "Target page, context or browser has been closed" in raw:
        return "回测引擎异常断开，请稍后重试"
    if "net::ERR_" in raw or "Navigation failed" in raw:
        return "回测平台网络连接失败，请稍后重试"
    if "intercepts pointer events" in raw or "introjs" in raw:
        return "回测平台页面加载异常，请稍后重试"
    # Fallback: hide raw Playwright details
    if "ElementHandle" in raw or "Locator" in raw or "playwright" in raw.lower():
        return "回测执行过程中发生异常，请稍后重试"
    # Keep short, generic errors as-is
    if len(raw) > 200:
        return "回测执行过程中发生异常，请稍后重试"
    return f"回测异常: {raw}"


# ---- Main Service (persistent browser) ----

class JQAutomationService:
    """Manages a persistent Playwright browser session for JoinQuant automation.

    Call startup() once at application boot to launch browser and login.
    Then call run_backtest() for each backtest — it reuses the existing session.
    Call shutdown() at application exit.
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        headless: bool = True,
    ):
        self.username = username or os.environ.get("JQ_USERNAME", "")
        self.password = password or os.environ.get("JQ_PASSWORD", "")
        self.headless = headless if os.environ.get("JQ_HEADLESS", "true").lower() != "false" else False
        self._state_path = Path("data/jq_browser_state/state.json")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

        # Persistent browser state
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._logged_in = False

    @property
    def is_ready(self) -> bool:
        """True if browser is running and logged in."""
        return self._logged_in and self._page is not None and not self._page.is_closed()

    # ---- Lifecycle ----

    async def startup(self) -> bool:
        """Launch browser, login to JoinQuant, and keep session alive.

        Returns True if login succeeded.
        """
        async with self._lock:
            if self.is_ready:
                logger.info("JQ browser already running and logged in")
                return True

            await self._cleanup()

            logger.info(f"Launching JQ browser (headless={self.headless})...")
            self._playwright = await async_playwright().start()

            browser_args = [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=browser_args,
            )

            context_kwargs = {
                "viewport": {"width": 1440, "height": 900},
                "user_agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            if self._state_path.exists():
                try:
                    context_kwargs["storage_state"] = str(self._state_path)
                except Exception:
                    pass

            self._context = await self._browser.new_context(**context_kwargs)
            self._page = await self._context.new_page()

            # Attempt login
            self._logged_in = await self._ensure_logged_in(self._page)
            if self._logged_in:
                # Save session for future reuse
                try:
                    await self._context.storage_state(path=str(self._state_path))
                except Exception as e:
                    logger.warning(f"Failed to save browser state: {e}")
                logger.info("JQ browser started and logged in — ready for backtests")
            else:
                logger.error("JQ login failed")
                await _take_screenshot(self._page, "startup_login_failed")

            return self._logged_in

    async def shutdown(self):
        """Close browser and cleanup."""
        async with self._lock:
            await self._cleanup()
            logger.info("JQ browser shut down")

    async def _cleanup(self):
        """Internal cleanup of browser resources."""
        self._logged_in = False
        if self._page and not self._page.is_closed():
            try:
                await self._page.close()
            except Exception:
                pass
        self._page = None
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        self._context = None
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._playwright = None

    # ---- Backtest (reuses persistent browser) ----

    async def run_backtest(
        self,
        strategy_code: str,
        config: JQBacktestConfig,
        on_status: Callable[[str], None] | None = None,
    ) -> JQBacktestResult:
        """Run a backtest on the already-logged-in JQ session.

        If browser is not ready, tries startup() automatically.
        """
        async with self._lock:
            return await self._run_backtest_impl(strategy_code, config, on_status)

    async def _run_backtest_impl(
        self,
        strategy_code: str,
        config: JQBacktestConfig,
        on_status: Callable[[str], None] | None,
    ) -> JQBacktestResult:
        result = JQBacktestResult()

        def _status(s: str):
            if on_status:
                on_status(s)

        # Ensure browser is ready
        if not self.is_ready:
            _status("launching_browser")
            _status("logging_in")
            ok = await self._startup_unlocked()
            if not ok:
                result.error = "回测引擎启动失败，请稍后重试"
                if self._page:
                    result.screenshot_path = await _take_screenshot(self._page, "login_failed")
                return result

        page = self._page
        assert page is not None

        try:
            # ---- Navigate to strategy editor ----
            _status("setting_code")
            # Only goto editor if not already there
            if "algorithm" not in page.url or "backtest/detail" in page.url:
                logger.info(f"Navigating to editor (current: {page.url[:60]})")
                await page.goto(JQ_ALGORITHM_URL, wait_until="domcontentloaded", timeout=30000)
            else:
                logger.info("Already on editor page, skipping navigation")

            # Quick session check: if we got redirected to login, re-login
            if "login" in page.url.lower():
                _status("logging_in")
                self._logged_in = False
                ok = await self._startup_unlocked()
                if not ok:
                    result.error = "回测引擎连接失败，请稍后重试"
                    result.screenshot_path = await _take_screenshot(self._page, "relogin_failed")
                    return result
                page = self._page
                assert page is not None
                await page.goto(JQ_ALGORITHM_URL, wait_until="domcontentloaded", timeout=30000)

            await page.wait_for_timeout(500)  # brief pause for editor ready

            # ---- Dismiss introjs overlay / tutorial popups ----
            await self._dismiss_overlays(page)

            # ---- Set strategy code ----
            code_set = await self._set_strategy_code(page, strategy_code)
            if not code_set:
                result.error = "无法设置策略代码到编辑器"
                result.screenshot_path = await _take_screenshot(page, "set_code_failed")
                return result

            # ---- Save code so JQ recognizes the new code ----
            await self._save_code(page)

            # ---- Verify code was actually written ----
            try:
                editor_code = await page.evaluate("""() => {
                    // Read from Ace editor
                    const container = document.getElementById('ide-container');
                    if (container && container.env && container.env.editor) {
                        return container.env.editor.getValue().substring(0, 200);
                    }
                    const aceEl = document.querySelector('.ace_editor');
                    if (aceEl && aceEl.env && aceEl.env.editor) {
                        return aceEl.env.editor.getValue().substring(0, 200);
                    }
                    // Fallback: read textarea
                    const ta = document.getElementById('code');
                    if (ta) return ta.value.substring(0, 200);
                    return "COULD_NOT_READ";
                }""")
                code_preview = strategy_code[:100].replace('\n', '\\n')
                editor_preview = (editor_code or "").replace('\n', '\\n')[:100]
                logger.info(f"Code verification — expected: {code_preview}...")
                logger.info(f"Code verification — editor:   {editor_preview}...")
                if editor_code and strategy_code[:50] not in editor_code:
                    logger.warning("Code mismatch! Editor content doesn't match injected code")
            except Exception as e:
                logger.warning(f"Could not verify code: {e}")

            # ---- Configure backtest params ----
            _status("configuring_backtest")
            await self._dismiss_overlays(page)
            await self._configure_backtest_params(page, config)

            # ---- Run backtest ----
            _status("running_backtest")
            await self._dismiss_overlays(page)
            run_clicked = await self._click_run_backtest(page)
            if not run_clicked:
                result.error = "无法点击运行回测按钮"
                result.screenshot_path = await _take_screenshot(page, "run_failed")
                return result

            # ---- Wait for completion ----
            _status("waiting_completion")
            completed = await self._wait_for_completion(page)
            if not completed:
                result.error = f"回测超时（{JQ_BACKTEST_TIMEOUT}秒）"
                result.screenshot_path = await _take_screenshot(page, "timeout")
                return result

            # Check for backtest errors
            error_text = await self._check_backtest_error(page)
            if error_text:
                result.error = f"回测执行错误: {error_text}"
                result.screenshot_path = await _take_screenshot(page, "backtest_error")
                return result

            # ---- Scrape results ----
            _status("scraping_results")
            await self._scrape_results(page, result)

            result.screenshot_path = await _take_screenshot(page, "success")
            result.success = True

            # Pre-navigate back to editor so next backtest starts faster
            try:
                await page.goto(JQ_ALGORITHM_URL, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass  # non-critical

        except Exception as e:
            logger.error(f"JQ automation error: {e}", exc_info=True)
            result.error = _sanitize_error(str(e))
            if page and not page.is_closed():
                result.screenshot_path = await _take_screenshot(page, "exception")

        return result

    # ---- Internal startup (no lock) ----

    async def _startup_unlocked(self) -> bool:
        """Launch browser + login without acquiring the lock (caller holds it)."""
        await self._cleanup()

        self._playwright = await async_playwright().start()

        browser_args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=browser_args,
        )

        context_kwargs = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if self._state_path.exists():
            try:
                context_kwargs["storage_state"] = str(self._state_path)
            except Exception:
                pass

        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()

        self._logged_in = await self._ensure_logged_in(self._page)
        if self._logged_in:
            try:
                await self._context.storage_state(path=str(self._state_path))
            except Exception:
                pass
        return self._logged_in

    async def _check_session_valid(self) -> bool:
        """Quick check: navigate to algorithm page, see if we get redirected to login."""
        if not self._page or self._page.is_closed():
            return False
        try:
            await self._page.goto(JQ_ALGORITHM_URL, wait_until="domcontentloaded", timeout=15000)
            await self._page.wait_for_timeout(1500)
            return "login" not in self._page.url.lower()
        except Exception:
            return False

    # ---- Login ----

    async def _ensure_logged_in(self, page: Page) -> bool:
        """Navigate to JQ and login if needed. Returns True on success."""
        # First check if session cookie is still valid
        try:
            await page.goto(JQ_ALGORITHM_URL, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            if "login" not in page.url.lower():
                for selector in SELECTORS["login_success_indicator"]:
                    try:
                        el = await page.wait_for_selector(selector, timeout=3000)
                        if el:
                            logger.info("Already logged in (session reuse)")
                            return True
                    except Exception:
                        continue
                if "algorithm" in page.url.lower():
                    logger.info("Already logged in (URL check)")
                    return True
        except Exception:
            pass

        # Need fresh login
        logger.info("Navigating to login page...")
        await page.goto(JQ_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)

        # Switch to password login tab if needed
        try:
            for selector in SELECTORS["login_tab_password"]:
                try:
                    tab = await page.wait_for_selector(selector, timeout=3000)
                    if tab and await tab.is_visible():
                        await tab.click()
                        await page.wait_for_timeout(500)
                        logger.info("Clicked '密码登录' tab")
                        break
                except Exception:
                    continue
        except Exception:
            pass  # might already be on password tab

        # Check for CAPTCHA
        for selector in SELECTORS["captcha_indicator"]:
            try:
                captcha = await page.wait_for_selector(selector, timeout=2000)
                if captcha and await captcha.is_visible():
                    logger.warning("CAPTCHA detected — cannot auto-login")
                    return False
            except Exception:
                continue

        # Fill phone number
        try:
            phone_input = await _find_element(page, SELECTORS["login_phone_input"])
            await phone_input.click()
            await phone_input.fill("")
            await phone_input.fill(self.username)
        except TimeoutError:
            logger.error("Cannot find phone input field")
            return False

        # Fill password
        try:
            pwd_input = await _find_element(page, SELECTORS["login_password_input"])
            await pwd_input.click()
            await pwd_input.fill("")
            await pwd_input.fill(self.password)
        except TimeoutError:
            logger.error("Cannot find password input field")
            return False

        # Tick the agreement checkbox
        try:
            for selector in SELECTORS["login_agreement_checkbox"]:
                try:
                    checkbox = await page.wait_for_selector(selector, timeout=3000)
                    if checkbox:
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            await checkbox.check()
                            logger.info("Checked user agreement checkbox")
                        else:
                            logger.info("Agreement checkbox already checked")
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Could not find agreement checkbox: {e}")

        # Click login button
        try:
            login_btn = await _find_element(page, SELECTORS["login_button"])
            await login_btn.click()
            logger.info("Clicked login button")
        except TimeoutError:
            logger.error("Cannot find login button")
            return False

        # Wait for navigation after login
        await page.wait_for_timeout(4000)

        # Check if login succeeded
        if "login" in page.url.lower():
            # Still on login page
            for selector in SELECTORS["captcha_indicator"]:
                try:
                    captcha = await page.wait_for_selector(selector, timeout=2000)
                    if captcha and await captcha.is_visible():
                        logger.warning("CAPTCHA appeared after login attempt")
                        return False
                except Exception:
                    continue
            # Take screenshot for debugging
            await _take_screenshot(page, "login_failed")
            logger.error("Login failed — still on login page")
            return False

        logger.info("Login successful")
        return True

    # ---- Editor operations ----

    async def _set_strategy_code(self, page: Page, code: str) -> bool:
        """Set the strategy code in the JQ editor.

        JQ uses Ace Editor as the visual layer, but the actual code is
        stored in a hidden textarea#code. We must set BOTH to ensure
        the platform picks up the new code when running backtest.
        """
        escaped_code = json.dumps(code)

        try:
            result = await page.evaluate(f"""() => {{
                const code = {escaped_code};
                let aceSet = false;
                let textareaSet = false;

                // 1. Set Ace Editor (visual layer)
                const container = document.getElementById('ide-container');
                let editor = null;
                if (container && container.env && container.env.editor) {{
                    editor = container.env.editor;
                }} else {{
                    const aceEl = document.querySelector('.ace_editor');
                    if (aceEl && aceEl.env && aceEl.env.editor) {{
                        editor = aceEl.env.editor;
                    }}
                }}
                if (editor) {{
                    editor.setValue(code, -1);
                    aceSet = true;
                }}

                // 2. Set hidden textarea#code (data layer — JQ reads this)
                const ta = document.getElementById('code');
                if (ta) {{
                    ta.value = code;
                    ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                    ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                    textareaSet = true;
                }}

                return {{ace: aceSet, textarea: textareaSet}};
            }}""")
            logger.info(f"Strategy code set: ace={result.get('ace')}, textarea={result.get('textarea')}")
            if result.get("ace") or result.get("textarea"):
                return True
        except Exception as e:
            logger.warning(f"Code injection failed: {e}")

        logger.error("Failed to set strategy code — no editor found")
        return False

    async def _save_code(self, page: Page):
        """Save code in JQ editor so the server has the latest version.

        JQ's "运行回测" runs whatever is saved on the server, NOT what's
        in the editor. We must explicitly save first.
        """
        saved = False

        # Method 1: Click the "保 存" tab/button at the top of the editor
        # In JQ, it appears as a tab-like element with text "保 存" (note the space)
        try:
            # Try multiple ways to find the save button
            for selector in [
                'text="保 存"',             # Playwright text selector (exact match with space)
                'text="保存"',              # Without space
                '#save-button',
                'li:has-text("保 存")',     # It might be an <li> tab
                'a:has-text("保 存")',
                'div:has-text("保 存") >> nth=0',
            ]:
                try:
                    btn = await page.wait_for_selector(selector, timeout=2000)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(2000)  # Wait for server round-trip
                        logger.info(f"Code saved via: {selector}")
                        saved = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

        if not saved:
            # Method 2: Keyboard shortcut
            try:
                await page.keyboard.press("Meta+s")
                await page.wait_for_timeout(500)
                await page.keyboard.press("Control+s")
                await page.wait_for_timeout(2000)
                logger.info("Code saved via keyboard shortcut")
                saved = True
            except Exception as e:
                logger.warning(f"Could not save code: {e}")

        if not saved:
            logger.warning("Failed to save code — backtest may use old version!")

    async def _configure_backtest_params(self, page: Page, config: JQBacktestConfig):
        """Set backtest configuration parameters via JoinQuant's form.

        JQ uses jQuery datepicker for date fields. Simply setting .value
        is not enough — we must trigger the proper jQuery/DOM events so
        the framework picks up the change.
        """
        # Helper JS: set value + dispatch change/input + jQuery trigger
        # Playwright evaluate only accepts ONE arg, so we pass {id, val} as object
        SET_INPUT_JS = """({id, val}) => {
            const el = document.getElementById(id);
            if (!el) return false;
            // Use native input value setter to bypass React/jQuery getter caching
            const nativeSet = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeSet.call(el, val);
            // Dispatch DOM events
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('blur', {bubbles: true}));
            // Also trigger jQuery events if $ is available
            if (window.$ || window.jQuery) {
                const $el = (window.$ || window.jQuery)(el);
                $el.val(val).trigger('change').trigger('input');
            }
            return true;
        }"""

        # Start date
        try:
            ok = await page.evaluate(SET_INPUT_JS, {"id": "startTime", "val": config.start_date})
            logger.info(f"Set start date: {config.start_date} (ok={ok})")
        except Exception as e:
            logger.warning(f"Could not set start date: {e}")

        # End date
        try:
            ok = await page.evaluate(SET_INPUT_JS, {"id": "endTime", "val": config.end_date})
            logger.info(f"Set end date: {config.end_date} (ok={ok})")
        except Exception as e:
            logger.warning(f"Could not set end date: {e}")

        # Initial capital
        try:
            ok = await page.evaluate(SET_INPUT_JS, {"id": "daily_backtest_capital_base_box", "val": str(int(config.initial_capital))})
            logger.info(f"Set capital: {int(config.initial_capital)} (ok={ok})")
        except Exception as e:
            logger.warning(f"Could not set initial capital: {e}")

        # Frequency (hidden input)
        try:
            await page.evaluate(SET_INPUT_JS, {"id": "frequency", "val": config.frequency})
        except Exception as e:
            logger.warning(f"Could not set frequency: {e}")

        # Verify values were applied
        try:
            actual = await page.evaluate("""() => ({
                start: document.getElementById('startTime')?.value,
                end: document.getElementById('endTime')?.value,
                capital: document.getElementById('daily_backtest_capital_base_box')?.value,
            })""")
            logger.info(f"Verified form values: {actual}")
        except Exception:
            pass

    async def _dismiss_overlays(self, page: Page):
        """Dismiss introjs tutorial overlays and any modal popups that block interaction."""
        try:
            removed = await page.evaluate("""() => {
                let count = 0;
                // Remove introjs overlay & tooltip
                document.querySelectorAll('.introjs-overlay, .introjs-helperLayer, .introjs-tooltipReferenceLayer, .introjs-tooltip, .introjs-fixedTooltip').forEach(el => {
                    el.remove();
                    count++;
                });
                // Click any "skip" / "不再提示" / "跳过" / "知道了" / "关闭" buttons
                const skipTexts = ['不再提示', '跳过', '知道了', '关闭', 'Skip', 'Got it', 'Done'];
                document.querySelectorAll('a, button, span').forEach(el => {
                    const text = (el.textContent || '').trim();
                    if (skipTexts.some(t => text.includes(t)) && el.offsetParent !== null) {
                        el.click();
                        count++;
                    }
                });
                // Handle Element UI modal dialogs (JQ积分提示等)
                document.querySelectorAll('.el-message-box__wrapper, .el-dialog__wrapper, .v-modal').forEach(el => {
                    el.remove();
                    count++;
                });
                // Remove any remaining overlay divs covering the page
                document.querySelectorAll('[class*="overlay"]').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.position === 'fixed' || style.position === 'absolute') {
                        if (parseFloat(style.zIndex) > 999) {
                            el.remove();
                            count++;
                        }
                    }
                });
                return count;
            }""")
            if removed:
                logger.info(f"Dismissed {removed} overlay element(s)")
                await page.wait_for_timeout(300)
        except Exception as e:
            logger.warning(f"Failed to dismiss overlays: {e}")

    async def _click_run_backtest(self, page: Page) -> bool:
        """Click the '运行回测' button. Returns True on success."""
        # Record pre-click URL to detect navigation to result page
        self._pre_run_url = page.url

        try:
            await self._dismiss_overlays(page)
            btn = await _find_element(page, SELECTORS["run_backtest_button"], timeout=10000)
            await btn.click()
            await page.wait_for_timeout(2000)
            logger.info("Clicked '运行回测' button")
            return True
        except TimeoutError:
            logger.error("Cannot find '运行回测' button")
            return False

    async def _wait_for_completion(self, page: Page) -> bool:
        """Wait for backtest to complete.

        Flow:
        1. After clicking run, JQ redirects to /algorithm/backtest/detail?backtestId=NEW_ID
        2. First wait for URL to change to a NEW backtest detail page
        3. Then poll for '回测完成' text on that page
        """
        pre_url = getattr(self, "_pre_run_url", "")
        elapsed = 0

        # Phase 1: Wait for redirect to a new backtest result page
        logger.info("Waiting for redirect to new backtest result page...")
        while elapsed < 60:  # max 60s to get redirected
            current_url = page.url
            if "backtest/detail" in current_url and current_url != pre_url:
                logger.info(f"Redirected to new backtest: {current_url[:100]}")
                break
            await page.wait_for_timeout(POLL_INTERVAL * 1000)
            elapsed += POLL_INTERVAL
        else:
            logger.warning("Never redirected to backtest detail page")
            # Still try to detect completion on current page
            pass

        # Phase 2: On the result page, poll for completion
        # First wait a moment for the page to settle — it should show "回测中" initially
        await page.wait_for_timeout(2000)

        while elapsed < JQ_BACKTEST_TIMEOUT:
            state = await page.evaluate("""() => {
                const text = document.body.innerText || "";
                return {
                    completed: text.includes("回测完成"),
                    running: text.includes("回测中") || text.includes("排队中"),
                    failed: text.includes("回测失败") || text.includes("编译错误"),
                    url: location.href,
                };
            }""")

            if state.get("completed"):
                logger.info(f"Backtest completed (url={state['url'][:80]})")
                return True

            if state.get("failed"):
                logger.warning("Backtest failed indicator detected")
                return True  # caller will check error via _check_backtest_error

            if state.get("running"):
                logger.debug(f"Backtest still running... ({elapsed}s)")

            await page.wait_for_timeout(POLL_INTERVAL * 1000)
            elapsed += POLL_INTERVAL

        logger.warning(f"Backtest timed out after {JQ_BACKTEST_TIMEOUT}s")
        return False

    async def _check_backtest_error(self, page: Page) -> str | None:
        """Check if the backtest has an error on the results page.

        Tries to extract the actual error from the log output tab.
        """
        try:
            error = await page.evaluate("""() => {
                const text = document.body.innerText || "";
                if (!text.includes("回测失败") && !text.includes("编译错误")) return null;

                // Try to find error details in log output
                const logEl = document.querySelector('.log-content, .log-output, #log-content, .backtest-log');
                if (logEl) {
                    const logText = logEl.innerText.trim();
                    if (logText) return logText.substring(0, 800);
                }
                // Try error message elements
                const errEl = document.querySelector('.error-message, .compile-error, .backtest-error');
                if (errEl) return errEl.innerText.trim().substring(0, 800);
                // Fallback
                return text.includes("编译错误") ? "编译错误" : "回测失败";
            }""")
            if not error:
                return None

            # Try clicking "日志输出" tab to get more details
            if error in ("回测失败", "编译错误"):
                try:
                    log_tab = await page.query_selector('text=日志输出')
                    if log_tab:
                        await log_tab.click()
                        await page.wait_for_timeout(1500)
                        log_detail = await page.evaluate("""() => {
                            const el = document.querySelector('.log-content, .log-output, #log-content, .backtest-log, pre');
                            if (el) return el.innerText.trim().substring(0, 800);
                            // Fallback: look for any red/error text in the page
                            const reds = document.querySelectorAll('[style*="color: red"], [style*="color:red"], .text-danger, .error');
                            let msg = '';
                            reds.forEach(r => { msg += r.innerText.trim() + '\\n'; });
                            return msg.substring(0, 800) || null;
                        }""")
                        if log_detail:
                            error = log_detail
                except Exception as e:
                    logger.warning(f"Could not read log tab: {e}")

            logger.info(f"Backtest error detail: {error[:200]}")
            return error
        except Exception:
            return None

    async def _scrape_results(self, page: Page, result: JQBacktestResult):
        """Extract backtest results from the JQ backtest detail page.

        Steps:
        1. Scrape summary metrics from .top-level-stat elements
        2. Download free CSV export (收益概述) → parse into equity_curve
        3. Navigate to #tab-transactioninfo → scrape trade table
        4. Navigate to #tab-positioninfo → scrape daily position table
        """
        result_url = page.url
        await page.wait_for_timeout(2000)

        # ---- Step 1: Scrape metrics from .top-level-stat ----
        try:
            metrics_raw = await page.evaluate("""() => {
                const stats = document.querySelectorAll(".top-level-stat");
                const result = {};
                stats.forEach(stat => {
                    const lines = stat.innerText.trim().split("\\n");
                    if (lines.length >= 2) {
                        const label = lines[0].trim();
                        const value = lines[1].trim();
                        if (label && value) result[label] = value;
                    }
                });
                return result;
            }""")
            if metrics_raw:
                result.metrics = _parse_metrics(metrics_raw)
                logger.info(f"Scraped {len(metrics_raw)} metrics: {list(metrics_raw.keys())}")
        except Exception as e:
            logger.warning(f"Metrics scraping failed: {e}")

        # ---- Step 2: Download CSV export (收益概述, free) ----
        try:
            await self._download_csv_export(page, result)
        except Exception as e:
            logger.warning(f"CSV export failed: {e}")

        # ---- Step 3: Scrape trade details via hash navigation ----
        try:
            await self._scrape_trades_via_hash(page, result_url, result)
        except Exception as e:
            logger.warning(f"Trade scraping failed: {e}")

        # ---- Step 4: Scrape daily positions via hash navigation ----
        try:
            await self._scrape_positions_via_hash(page, result_url, result)
        except Exception as e:
            logger.warning(f"Position scraping failed: {e}")

    async def _download_csv_export(self, page: Page, result: JQBacktestResult):
        """Download the free '收益概述' CSV export and parse it into equity_curve."""
        # Click the export dropdown toggle
        try:
            export_btn = await page.wait_for_selector("#backtest-menu-toggle", timeout=5000)
        except Exception:
            logger.info("No export button found, skipping CSV download")
            return

        await export_btn.click()
        await page.wait_for_timeout(1000)

        # Click the CSV export button and intercept the download
        try:
            async with page.expect_download(timeout=15000) as download_info:
                # Click the export CSV link
                csv_btn = await page.wait_for_selector("#export-csv-button", timeout=5000)
                if not csv_btn:
                    # Fallback: look for export link by text
                    csv_btn = await page.wait_for_selector('a[download="data.xls"]', timeout=3000)
                await csv_btn.click()

            download = await download_info.value

            # Save to local path
            download_dir = Path("data/jq_downloads")
            download_dir.mkdir(parents=True, exist_ok=True)
            csv_path = download_dir / f"{download.suggested_filename or 'data.xls'}"
            await download.save_as(str(csv_path))
            result.csv_path = str(csv_path)
            logger.info(f"CSV downloaded: {csv_path}")

            # Parse the CSV/XLS file (JQ exports in GBK encoding)
            raw_bytes = csv_path.read_bytes()
            # Try GBK first (JQ default), then UTF-8 fallback
            for encoding in ("gbk", "gb2312", "utf-8-sig", "utf-8"):
                try:
                    content = raw_bytes.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                content = raw_bytes.decode("gbk", errors="replace")

            result.equity_curve = _parse_csv_returns(content)
            logger.info(f"Parsed {len(result.equity_curve)} data points from CSV")

        except Exception as e:
            logger.warning(f"CSV download/parse failed: {e}")
            # Close dropdown if still open
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

    async def _scrape_trades_via_hash(self, page: Page, result_url: str, result: JQBacktestResult):
        """Navigate to #tab-transactioninfo and scrape the trade details table."""
        base_url = result_url.split("#")[0]
        await page.goto(f"{base_url}#tab-transactioninfo", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        trades = await self._scrape_table_all_pages(page)
        if trades:
            result.trades = trades
            logger.info(f"Scraped {len(trades)} trades from 交易详情")

    async def _scrape_positions_via_hash(self, page: Page, result_url: str, result: JQBacktestResult):
        """Navigate to #tab-positioninfo and scrape the daily positions table."""
        base_url = result_url.split("#")[0]
        await page.goto(f"{base_url}#tab-positioninfo", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        positions = await self._scrape_table_all_pages(page)
        if positions:
            result.daily_positions = positions
            logger.info(f"Scraped {len(positions)} daily position rows from 每日持仓&收益")

    async def _scrape_table_all_pages(self, page: Page) -> list[dict]:
        """Scrape all rows from the currently visible table, handling pagination."""
        all_rows: list[dict] = []
        max_pages = 50  # safety limit

        for _ in range(max_pages):
            # Scrape current page's table
            page_data = await page.evaluate("""() => {
                const table = document.querySelector("table");
                if (!table) return { headers: [], rows: [] };

                const headers = Array.from(table.querySelectorAll("thead th"))
                    .map(h => h.innerText.trim());
                const rows = [];
                table.querySelectorAll("tbody tr").forEach(tr => {
                    const cells = Array.from(tr.querySelectorAll("td"))
                        .map(td => td.innerText.trim());
                    if (cells.length > 0 && cells.some(c => c !== '')) {
                        rows.push(cells);
                    }
                });
                return { headers, rows };
            }""")

            headers = page_data.get("headers", [])
            rows = page_data.get("rows", [])

            for row_cells in rows:
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(row_cells):
                        row_dict[header] = row_cells[i]
                if row_dict:
                    all_rows.append(row_dict)

            # Check for next page button
            has_next = await page.evaluate("""() => {
                const nextBtn = document.querySelector('.pagination .next:not(.disabled) a, .pagination li:last-child:not(.disabled) a');
                if (nextBtn) {
                    nextBtn.click();
                    return true;
                }
                return false;
            }""")

            if not has_next:
                break

            await page.wait_for_timeout(1500)  # wait for next page to load

        return all_rows


# ---- CSV Parsing ----

def _parse_csv_returns(content: str) -> list[dict]:
    """Parse the JQ '收益概述' CSV into a list of daily return data points.

    CSV columns: 时间, 基准收益, 策略收益, 当日盈利, 当日亏损, 当日买入, 当日卖出, 超额收益(%)
    Values are percentages WITHOUT % sign (e.g., -1.3 means -1.3%).
    """
    result = []
    try:
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            date = row.get("时间", "").strip()[:10]  # 只保留 YYYY-MM-DD，去掉时分秒
            if not date:
                continue

            # Values are percentages (e.g., -1.3 = -1.3%), divide by 100 for decimal
            strategy_return = _parse_csv_number(row.get("策略收益", "")) / 100.0
            benchmark_return = _parse_csv_number(row.get("基准收益", "")) / 100.0
            excess_return = _parse_csv_number(row.get("超额收益(%)", row.get("超额收益", ""))) / 100.0

            result.append({
                "date": date,
                "strategy_return": round(strategy_return, 6),
                "benchmark_return": round(benchmark_return, 6),
                "excess_return": round(excess_return, 6),
                "daily_profit": _parse_csv_number(row.get("当日盈利", "")),
                "daily_loss": _parse_csv_number(row.get("当日亏损", "")),
                "daily_buy": _parse_csv_number(row.get("当日买入", "")),
                "daily_sell": _parse_csv_number(row.get("当日卖出", "")),
            })
    except Exception as e:
        logger.warning(f"CSV parse error: {e}")

    return result


def _parse_csv_number(s: str) -> float:
    """Parse a number string from CSV."""
    if not s:
        return 0.0
    s = s.strip().replace(",", "").replace("，", "")
    try:
        return round(float(s), 2)
    except (ValueError, TypeError):
        return 0.0


# ---- Metric Parsing ----

def _parse_metrics(raw: dict[str, str]) -> dict:
    """Parse scraped metric strings into typed values."""
    name_map = {
        "策略收益": "total_return",
        "总收益": "total_return",
        "累计收益": "total_return",
        "策略年化收益": "annual_return",
        "年化收益": "annual_return",
        "年化收益率": "annual_return",
        "超额收益": "excess_return",
        "基准收益": "benchmark_return",
        "阿尔法": "alpha",
        "Alpha": "alpha",
        "alpha": "alpha",
        "贝塔": "beta",
        "Beta": "beta",
        "beta": "beta",
        "夏普比率": "sharpe_ratio",
        "Sharpe": "sharpe_ratio",
        "索提诺比率": "sortino_ratio",
        "信息比率": "information_ratio",
        "最大回撤": "max_drawdown",
        "超额收益最大回撤": "excess_max_drawdown",
        "胜率": "win_rate",
        "日胜率": "daily_win_rate",
        "盈亏比": "profit_loss_ratio",
        "波动率": "volatility",
        "策略波动率": "volatility",
        "基准波动率": "benchmark_volatility",
        "基准年化": "benchmark_annual",
        "盈利次数": "win_count",
        "亏损次数": "loss_count",
        "日均超额收益": "daily_excess_return",
        "超额收益夏普比率": "excess_sharpe",
    }
    result = {}
    for label, value_str in raw.items():
        key = name_map.get(label.strip())
        if key:
            result[key] = _parse_number(value_str)
    return result


def _parse_number(s: str) -> float:
    """Parse a numeric string, handling %, commas, etc."""
    s = s.strip().replace(",", "").replace("，", "")
    is_pct = s.endswith("%")
    s = s.rstrip("%")
    try:
        val = float(s)
        if is_pct:
            val /= 100.0
        return round(val, 6)
    except (ValueError, TypeError):
        return 0.0


# ---- Module-level singleton ----

_jq_service: JQAutomationService | None = None


def get_jq_service() -> JQAutomationService:
    """Get or create the singleton JQAutomationService."""
    global _jq_service
    if _jq_service is None:
        _jq_service = JQAutomationService()
    return _jq_service
