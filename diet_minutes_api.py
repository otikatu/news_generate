import requests
from typing import List, Dict, Optional
import datetime

class DietMinutesAPI:
    """
    国会会議録検索システム API へのリクエストを管理するクラス
    """
    BASE_URL = "https://kokkai.ndl.go.jp/api/speech"

    def fetch_speeches(self, 
                       any_keyword: Optional[str] = None, 
                       from_date: Optional[str] = None, 
                       until_date: Optional[str] = None, 
                       speaker: Optional[str] = None,
                       maximum_records: int = 100) -> List[Dict]:
        """
        指定した条件で発言録を取得する
        """
        params = {
            "maximumRecords": maximum_records,
            "recordPacking": "json"
        }
        if any_keyword:
            params["any"] = any_keyword
        if from_date:
            params["from"] = from_date
        if until_date:
            params["until"] = until_date
        if speaker:
            params["speaker"] = speaker

        try:
            print(f"Fetching from Diet API: {params}")
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            # APIのレスポンス構造に合わせて抽出
            speeches = data.get("speechRecord", [])
            print(f"Successfully fetched {len(speeches)} speeches.")
            return speeches
        except Exception as e:
            print(f"Error fetching from Diet API: {e}")
            return []

if __name__ == "__main__":
    # 簡易テスト
    api = DietMinutesAPI()
    # 直近3ヶ月程度のニュースを想定したテスト
    today = datetime.date.today()
    last_month = today - datetime.timedelta(days=30)
    
    results = api.fetch_speeches(
        any_keyword="少子化対策", 
        from_date=last_month.strftime("%Y-%m-%d")
    )
    
    for r in results[:3]:
        print(f"---")
        print(f"日付: {r.get('date')}")
        print(f"会議名: {r.get('nameOfMeeting')}")
        print(f"発言者: {r.get('speaker')}")
        print(f"内容: {r.get('speech')[:100]}...")
