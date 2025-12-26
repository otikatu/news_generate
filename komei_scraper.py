import asyncio
from playwright.async_api import async_playwright
from typing import Optional, List
from datetime import datetime

class KomeiScraper:
    """
    公明新聞電子版にログインして記事情報を取得するためのクラス
    """
    BASE_URL = "https://viewer.komei-shimbun.jp/"
    DIGITAL_HOME_URL = "https://digital.komei-shimbun.jp/"
    SEARCH_URL = "https://digital.komei-shimbun.jp/search?keyword="

    async def get_trending_headlines(self) -> List[str]:
        """
        公明新聞電子版のトップページから最新の見出しを取得する
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                await page.goto(self.DIGITAL_HOME_URL, timeout=30000)
                # ある程度読み込まれたら抽出
                await page.wait_for_load_state("load")
                await asyncio.sleep(2) # 少し待つ
                # 見出しの抽出 (aタグの中のテキスト、またはh3など)
                # 調査結果に基づき a[href^="/kmd/article/"] や a[href^="/flag/search/"] を狙う
                headlines = await page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a[href*="/article/"], a[href*="/search/"]'));
                    return links.map(a => a.innerText.trim()).filter(t => t.length > 5).slice(0, 10);
                }""")
                return headlines
            except Exception as e:
                print(f"Error fetching Komei headlines: {e}")
                return []
            finally:
                await browser.close()

    async def search_articles(self, keyword: str) -> List[str]:
        """
        キーワードで記事を検索し、上位のURLリストを返す
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 検索トップページへ
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: 検索ページへ移動中... https://digital.komei-shimbun.jp/search")
                await page.goto("https://digital.komei-shimbun.jp/search")
                
                # キーワード入力 (プレースホルダやaria-labelで指定)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: キーワード「{keyword}」を入力中...")
                search_input = page.locator('input[aria-label="キーワードを入力してください"]')
                await search_input.fill(keyword)
                
                # 検索ボタンクリック
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: 検索ボタンをクリック...")
                await page.click('button[aria-label="検索ボタン"]')
                
                # 結果の待機
                await page.wait_for_selector('a[href^="/flag/search/"]', timeout=15000)
                
                # 記事リンクの抽出
                urls = await page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a[href^="/flag/search/"]'));
                    return links.slice(0, 3).map(a => 'https://digital.komei-shimbun.jp' + a.getAttribute('href'));
                }""")
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: {len(urls)}件の記事が見つかりました。")
                return urls
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] エラー: 公明新聞の検索中に問題が発生しました: {e}")
                # ページの状態をデバッグ用にログ出力
                print(f"Current URL: {page.url}")
                return []
            finally:
                await browser.close()

    async def fetch_article_text(self, user_id: str, password: str, target_url: str) -> Optional[str]:
        """
        ログインして指定されたURLの記事テキストを取得する
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: ログインページへ移動中...")
                await page.goto(self.BASE_URL)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: ログインを実行中...")
                await page.fill("#userId", user_id)
                await page.fill("#password", password)
                await page.click("#login_button")
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: リダイレクト待機中...")
                try:
                    await page.wait_for_url("**/NAViH_S/NAViih*", timeout=30000)
                except Exception:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 警告: 期待されるURLへのリダイレクトがタイムアウトしました。現在のURL: {page.url}")

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: ターゲット記事へ移動中... {target_url}")
                await page.goto(target_url)
                await page.wait_for_load_state("networkidle")
                
                # 記事テキストの抽出を試みる
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: テキスト抽出を試行中...")
                # 1. 直接的な本文要素 (セレクタは推定)
                content = await page.evaluate("""() => {
                    const article = document.querySelector('.article-body, #article_content, .main-text');
                    return article ? article.innerText : document.body.innerText;
                }""")
                
                if len(content) < 100:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 警告: 取得できたテキストが極端に短いです ({len(content)}文字)")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 公明新聞: {len(content)}文字のテキストを取得しました。")
                
                return content

            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] エラー: 公明新聞の取得に失敗しました: {e}")
                return None
            finally:
                await browser.close()

if __name__ == "__main__":
    # テスト用のダミー実行
    import sys
    if len(sys.argv) < 3:
        print("Usage: python komei_scraper.py <user_id> <password> <article_url>")
    else:
        scraper = KomeiScraper()
        text = asyncio.run(scraper.fetch_article_text(sys.argv[1], sys.argv[2], sys.argv[3]))
        print(f"--- 取得結果 ---\n{text[:500]}...")
