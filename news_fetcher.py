import feedparser
import datetime
import urllib.parse
from typing import List, Dict

class NewsFetcher:
    """
    主要メディアのRSSフィードから政治ニュースを収集するクラス
    """
    SOURCES = {
        "NHK政治マガジン": "https://www.nhk.or.jp/rss/news/cat5.xml",
        "日経新聞(政治)": "https://www.nikkei.com/rss/politics/index.xml",
        "読売新聞(政治)": "https://www.yomiuri.co.jp/rss/politics/index.xml",
        "産経新聞(政治)": "https://www.sankei.com/rss/news/politics.xml",
        "毎日新聞(政治)": "https://mainichi.jp/rss/etc/politics.xml",
        "朝日新聞(政治)": "https://www.asahi.com/rss/politics/index.xml"
    }

    def get_trending_headlines(self) -> List[str]:
        """
        全ソースから最新の見出しを取得する (Google News Top Storiesを含む)
        """
        headlines = []
        
        # 1. Google News Top Stories (Japan)
        try:
            feed = feedparser.parse("https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja")
            for entry in feed.entries[:10]:
                headlines.append(entry.get("title", ""))
        except Exception as e:
            print(f"Error fetching Google News trends: {e}")

        # 2. 既存の特定メディアRSS
        for source_name, url in self.SOURCES.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    headlines.append(entry.get("title", ""))
            except Exception as e:
                print(f"Error fetching headlines from {source_name}: {e}")
        return headlines

    def fetch_all_news(self, keyword: str = "", days: int = 7) -> List[Dict]:
        """
        全ソース(Google News検索含む)から指定したキーワードを含む直近ニュースを取得
        """
        all_news = []
        now = datetime.datetime.now(datetime.timezone.utc)
        # 指定された日数分をカバーするために余裕を持たせる (days+1)
        search_limit_dt = now - datetime.timedelta(days=days + 1)
        
        # 1. Google News Search (広範なニュース収集用)
        if keyword:
            try:
                # 複数キーワード(カンマ)をスペースに変換
                google_query = keyword.replace(",", " ")
                encoded_query = urllib.parse.quote(google_query)
                google_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
                print(f"Searching Google News for: {google_query} (encoded: {encoded_query})")
                feed = feedparser.parse(google_url)
                
                for entry in feed.entries:
                    published = entry.get("published_parsed")
                    published_dt = None
                    if published:
                        published_dt = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
                        # 日付フィルタリング
                        if published_dt < search_limit_dt:
                            continue
                    
                    # 配信元情報の取得
                    source_info = entry.get("source")
                    source_name = "Googleニュース"
                    if isinstance(source_info, dict):
                        source_name = f"Googleニュース ({source_info.get('title', '不明')})"
                    elif isinstance(source_info, str):
                        source_name = f"Googleニュース ({source_info})"

                    all_news.append({
                        "source": source_name,
                        "title": entry.get("title"),
                        "link": entry.get("link"),
                        "summary": entry.get("summary", ""),
                        "published": published_dt.strftime("%Y-%m-%d %H:%M") if published_dt else "不明"
                    })
            except Exception as e:
                print(f"Error searching Google News: {e}")

        # 2. 特定メディアのRSSフィード (既存)
        for news_source_name, url in self.SOURCES.items():
            try:
                print(f"Fetching news from {news_source_name}...")
                feed = feedparser.parse(url)
                
                for entry in feed.entries:
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    published_dt = None
                    if published:
                        published_dt = datetime.datetime(*published[:6], tzinfo=datetime.timezone.utc)
                        if published_dt < search_limit_dt:
                            continue
                    
                    # キーワードチェック (RSSは全数取得のためフィルタリングが必要)
                    content = (entry.get("title", "") + entry.get("summary", "")).lower()
                    if keyword.lower() in content:
                        all_news.append({
                            "source": news_source_name,
                            "title": entry.get("title"),
                            "link": entry.get("link"),
                            "summary": entry.get("summary", ""),
                            "published": published_dt.strftime("%Y-%m-%d %H:%M") if published_dt else "不明"
                        })
            except Exception as e:
                print(f"Error fetching {news_source_name}: {e}")
                
        # 重複排除 (リンクで判定)
        unique_news = {n["link"]: n for n in all_news}.values()
        return sorted(unique_news, key=lambda x: x["published"], reverse=True)

if __name__ == "__main__":
    fetcher = NewsFetcher()
    results = fetcher.fetch_all_news(keyword="内閣", days=3)
    for news in results:
        print(f"[{news['source']}] {news['published']} - {news['title']}")
        print(f"URL: {news['link']}\n")
