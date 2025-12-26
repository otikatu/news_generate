import asyncio
from playwright.async_api import async_playwright

async def get_trending_headlines():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print("Navigating to home page (no blocking)...")
            await page.goto("https://digital.komei-shimbun.jp/", timeout=30000)
            print("Wait for networkidle...")
            await page.wait_for_load_state("networkidle")
            
            # ページタイトルだけ先に確認
            title = await page.title()
            print(f"Page Title: {title}")

            headlines = await page.evaluate("""() => {
                // セレクタを少し緩める
                const links = Array.from(document.querySelectorAll('a'));
                return links
                    .map(a => ({ text: a.innerText.trim(), href: a.getAttribute('href') }))
                    .filter(item => item.text.length > 10 && item.href && (item.href.includes('/article/') || item.href.includes('/search/')))
                    .slice(0, 10);
            }""")
            
            print(f"Headlines found: {len(headlines)}")
            for h in headlines:
                print(f"- {h['text']} ({h['href']})")
            return headlines
        except Exception as e:
            print(f"Error: {e}")
            return []
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_trending_headlines())
