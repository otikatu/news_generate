import asyncio
from playwright.async_api import async_playwright
import datetime

async def get_trending_headlines():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 高速化: 画像やCSSの一部をブロック
        await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,otf,ttf}", lambda route: route.abort())
        
        try:
            print("Navigating to home page...")
            await page.goto("https://digital.komei-shimbun.jp/", timeout=30000)
            print("Wait for domcontentloaded...")
            await page.wait_for_load_state("domcontentloaded")
            
            headlines = await page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="/article/"], a[href*="/search/"]'));
                return links.map(a => a.innerText.trim()).filter(t => t.length > 5).slice(0, 10);
            }""")
            print(f"Headlines found: {len(headlines)}")
            for h in headlines:
                print(f"- {h}")
            return headlines
        except Exception as e:
            print(f"Error: {e}")
            return []
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_trending_headlines())
