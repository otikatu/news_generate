import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def test():
    async with aiohttp.ClientSession() as session:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with session.get("https://digital.komei-shimbun.jp/", headers=headers) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            # aタグのテキストを表示してみる
            links = soup.find_all("a")
            print(f"Found {len(links)} links")
            for link in links[:20]:
                text = link.get_text(strip=True)
                if len(text) > 5:
                    print(f"Link: {text}")

if __name__ == "__main__":
    asyncio.run(test())
