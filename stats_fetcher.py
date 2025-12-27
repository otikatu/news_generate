import requests
from typing import List, Dict, Optional
import os

class StatsFetcher:
    """
    政府統計の総合窓口 (e-Stat) APIからデータを取得するクラス
    """
    BASE_URL = "https://www.e-stat.go.jp/api/ex-api/3.0/json"

    def __init__(self, app_id: Optional[str] = None):
        self.app_id = app_id or os.getenv("ESTAT_APP_ID")

    def search_stats(self, keyword: str) -> List[Dict]:
        """
        統計表を検索して一覧を取得する
        """
        if not self.app_id:
            print("e-Stat App ID is not set.")
            return []

        endpoint = f"{self.BASE_URL}/getStatsList"
        params = {
            "appId": self.app_id,
            "searchWord": keyword,
            "limit": 10
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            # レスポンス構造: GET_STATS_LIST -> DATALIST_INF -> TABLE_INF
            stats_list = []
            table_inf = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {}).get("TABLE_INF", [])
            
            # 1件のみの場合リストではないことがある
            if isinstance(table_inf, dict):
                table_inf = [table_inf]
                
            for table in table_inf:
                stats_list.append({
                    "id": table.get("@id"),
                    "title": table.get("TITLE", {}).get("$", "無題"),
                    "org": table.get("STAT_NAME", {}).get("$", "不明"),
                    "cycle": table.get("CYCLE", {}).get("$", "-")
                })
            return stats_list
        except Exception as e:
            print(f"Error searching stats: {e}")
            return []

    def get_stats_data(self, stats_id: str) -> Optional[Dict]:
        """
        統計データIDを指定して実際の数値を抜粋取得する
        """
        if not self.app_id:
            return None

        endpoint = f"{self.BASE_URL}/getStatsData"
        params = {
            "appId": self.app_id,
            "statsDataId": stats_id,
            "limit": 5 # 取得件数を制限 (台本要約用)
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting stats data: {e}")
            return None

if __name__ == "__main__":
    # テスト (要AppID)
    fetcher = StatsFetcher()
    results = fetcher.search_stats("家計収支")
    for r in results[:3]:
        print(f"Title: {r['title']}, Org: {r['org']}")
