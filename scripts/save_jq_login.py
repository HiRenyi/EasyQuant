"""打开浏览器让用户手动登录聚宽，自动检测并保存状态。"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

STATE_PATH = Path("data/jq_browser_state/state.json")
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
LOGIN_URL = "https://www.joinquant.com/user/login/index"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        await page.goto(LOGIN_URL)

        print("=== 浏览器已打开，请手动完成登录（含滑块验证）===")
        print("等待登录成功（会自动检测，最多等 180 秒）...")

        for i in range(36):
            await asyncio.sleep(5)
            url = page.url.lower()
            if "login" not in url:
                print(f"检测到已离开登录页 (当前: {url})")
                break
            if i % 6 == 0:
                print(f"  仍在登录页... ({30 - i * 5}s left)")

        if "login" in page.url.lower():
            print("超时，未检测到登录成功。请确认是否已完成登录。")
            await asyncio.sleep(10)

        await ctx.storage_state(path=str(STATE_PATH.resolve()))
        print(f"状态已保存 -> {STATE_PATH.resolve()}")
        print("现在可以把 .env 中 JQ_HEADLESS 改回 true，重启服务即可。")

        await browser.close()


asyncio.run(main())