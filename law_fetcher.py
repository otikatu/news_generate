import requests
from typing import List, Dict, Optional
import json

class LawFetcher:
    """
    e-Gov法令API v2を使用して法令情報を取得するクラス
    """
    BASE_URL = "https://laws.e-gov.go.jp/api/2"

    def search_laws(self, keyword: str) -> List[Dict]:
        """
        法令名で法令を検索し、メタ情報を取得する (/laws エンドポイント)
        """
        endpoint = f"{self.BASE_URL}/laws"
        params = {
            "law_title": keyword
        }
        headers = {
            "Accept": "application/json"
        }
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            laws = []
            
            # v2 JSON structure for /laws: { "laws": [ { "law_info": {...}, "revision_info": {...} }, ... ] }
            items = data.get("laws", [])
            for item in items:
                info = item.get("law_info", {})
                rev = item.get("revision_info", {})
                
                laws.append({
                    "id": info.get("law_id"),
                    "title": rev.get("law_title"),
                    "number": info.get("law_num"),
                    "promulgation_date": info.get("promulgation_date", "不明")
                })
            return laws
        except Exception as e:
            print(f"Error searching laws: {e}")
            return []

    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """
        条文全文からキーワードを検索し、抜粋を取得する (/keyword エンドポイント)
        """
        endpoint = f"{self.BASE_URL}/keyword"
        params = {
            "keyword": keyword
        }
        headers = {
            "Accept": "application/json"
        }
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            items = data.get("items", [])
            for item in items:
                info = item.get("law_info", {})
                rev = item.get("revision_info", {})
                sentences = item.get("sentences", [])
                
                # 抜粋テキストを結合 (<span>タグは削除)
                snippets = []
                for s in sentences:
                    text = s.get("text", "").replace("<span>", "").replace("</span>", "")
                    if text:
                        snippets.append(text)
                
                results.append({
                    "id": info.get("law_id"),
                    "title": rev.get("law_title"),
                    "number": info.get("law_num"),
                    "snippets": snippets[:3] # 上位3件のスニペットを保持
                })
            return results
        except Exception as e:
            print(f"Error searching by keyword: {e}")
            return []

    def fetch_law_text(self, law_id: str) -> Optional[str]:
        """
        法令IDを指定して本文（抜粋）を取得する (/lawdata/{law_id} エンドポイント)
        """
        # Note: /lawdata/{law_id} は v2 でも XML (Media Type: application/xml) が基本のようです。
        # JSON をサポートしているか不明なため、確実に動く XML 取得 + 簡易パースを継続します。
        endpoint = f"{self.BASE_URL}/lawdata/{law_id}"
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            
            # XMLを文字列として処理し、タグを除去してテキストのみを抽出する簡易実装
            import re
            text = response.text
            # タグを除去
            clean_text = re.sub(r'<[^>]+>', ' ', text)
            # 連続する空白を1つに
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            # 長すぎる場合は制限 (LLMのコンテキスト制限考慮)
            return clean_text[:3000] + "..." if len(clean_text) > 3000 else clean_text
            
        except Exception as e:
            print(f"Error fetching law text: {e}")
            return None

if __name__ == "__main__":
    # テスト
    fetcher = LawFetcher()
    print("--- Title Search (laws) ---")
    results = fetcher.search_laws("防衛")
    for r in results[:2]:
        print(f"Title: {r['title']}, ID: {r['id']}")
    
    print("\n--- Full-text Search (keyword) ---")
    kw_results = fetcher.search_by_keyword("防衛")
    for r in kw_results[:2]:
        print(f"Title: {r['title']}")
        for s in r['snippets']:
            print(f"  - {s}")
