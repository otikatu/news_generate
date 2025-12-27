import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import urllib.parse

class LawFetcher:
    """
    e-Gov法令API v2を使用して法令情報を取得するクラス
    """
    BASE_URL = "https://laws.e-gov.go.jp/api/2"

    def search_laws(self, keyword: str) -> List[Dict]:
        """
        キーワードで法令を検索し、メタ情報を取得する
        """
        endpoint = f"{self.BASE_URL}/lawnames"
        params = {
            "keyword": keyword
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            # API v2 は XML を返す (JSON 試行版もあるが XML が安定)
            root = ET.fromstring(response.content)
            laws = []
            
            # XML構造: <DataRoot><ApplData><LawNameListInfo>...
            for info in root.findall(".//LawNameListInfo"):
                law_title = info.find("LawName")
                law_id = info.find("LawId")
                law_num = info.find("LawNo")
                promulgation_date = info.find("PromulgationDate") # 公布日
                
                if law_title is not None and law_id is not None:
                    laws.append({
                        "id": law_id.text,
                        "title": law_title.text,
                        "number": law_num.text if law_num is not None else "",
                        "promulgation_date": promulgation_date.text if promulgation_date is not None else "不明"
                    })
            return laws
        except Exception as e:
            print(f"Error searching laws: {e}")
            return []

    def fetch_law_text(self, law_id: str) -> Optional[str]:
        """
        法令IDを指定して本文（抜粋）を取得する
        """
        endpoint = f"{self.BASE_URL}/lawdata/{law_id}"
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            # 法令本文は非常に長いため、冒頭部分や重要な章を抽出するのが現実的
            # ここでは簡易的に冒頭のテキストを抽出
            texts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())
            
            full_text = "\n".join(texts)
            # 長すぎる場合は制限 (LLMのコンテキスト制限考慮)
            return full_text[:3000] + "..." if len(full_text) > 3000 else full_text
            
        except Exception as e:
            print(f"Error fetching law text: {e}")
            return None

if __name__ == "__main__":
    # テスト
    fetcher = LawFetcher()
    results = fetcher.search_laws("防衛")
    for r in results[:3]:
        print(f"Title: {r['title']}, ID: {r['id']}")
