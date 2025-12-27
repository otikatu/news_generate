import requests
import json
import subprocess
import urllib.parse
from typing import List, Dict, Optional
import os

class StatsFetcher:
    """
    e-Stat 及び 統計ダッシュボード APIからデータを取得するクラス
    """
    ESTAT_BASE_URL = "https://www.e-stat.go.jp/api/ex-api/3.0/json"
    DASHBOARD_BASE_URL = "https://dashboard.e-stat.go.jp/api/1.0/Json"

    def __init__(self, app_id: Optional[str] = None):
        self.app_id = app_id or os.getenv("ESTAT_APP_ID")

    def _curl_get(self, url: str, params: Dict) -> Optional[Dict]:
        """
        requestsが失敗する場合があるため、外部コマンドのcurlを使用してデータを取得する
        """
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        query = urllib.parse.urlencode(params)
        full_url = f"{url}?{query}"
        try:
            # curl 8.x以降はhttp2デフォルト、適切に通信可能
            result = subprocess.run(
                ["curl", "-s", "-L", full_url, "-A", "curl/8.7.1", "-H", "Accept: */*"],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            # print(f"Curl error for {url}: {e}")
            # HTML errors (JSONDecodeError) fall here.
            # Only print if strict debugging is needed, otherwise silent fail to allow retry
            return None

    def search_indicators(self, keyword: str) -> List[Dict]:
        """
        統計ダッシュボードから指標（系列）を検索する
        """
        url = f"{self.DASHBOARD_BASE_URL}/getIndicatorInfo"
        params = {
            "Lang": "JP",
            "SearchIndicatorWord": keyword
        }
        data = self._curl_get(url, params)
        if not data:
            return []
            
        results = []
        # GET_META_INDICATOR_INF -> METADATA_INF -> CLASS_INF -> CLASS_OBJ
        try:
            class_obj = data.get("GET_META_INDICATOR_INF", {}).get("METADATA_INF", {}).get("CLASS_INF", {}).get("CLASS_OBJ", [])
            
            if isinstance(class_obj, dict):
                class_obj = [class_obj]
                
            for obj in class_obj:
                results.append({
                    "code": obj.get("@code"),
                    "name": obj.get("@name"),
                    "level": obj.get("@level")
                })
        except Exception as e:
            print(f"Error parsing indicator search: {e}")
            
        return results

    def get_indicator_data(self, indicator_code: str, latest_only: bool = True) -> List[Dict]:
        """
        特定の指標コードの時系列データを取得する (Smart Retry Implemented)
        """
        url = f"{self.DASHBOARD_BASE_URL}/getData"
        base_params = { "Lang": "JP", "IndicatorCode": indicator_code }
        
        # 1. First Attempt: Normal
        params = base_params.copy()
        data = self._curl_get(url, params)
        
        if self._is_valid_data(data):
            return self._parse_data(data, latest_only)
            
        # Analyze Failure
        res = data.get("GET_STATS", {}).get("RESULT", {}) if data else {}
        status = str(res.get("status", ""))
        err_msg = res.get("errorMsg", "")
        
        # 2. Retry with RegionalRank=1 
        # Trigger if: Data is None (HTML/Timeout), or Status!=0 (API Error) with size/filter msg
        should_retry_2 = False
        if not data: 
            should_retry_2 = True
        elif status != "0" and ("100000" in err_msg or "絞込" in err_msg): 
            should_retry_2 = True
            
        if should_retry_2:
            print(f"Debug: Retry(RegionalRank=1) for {indicator_code}...")
            params["RegionalRank"] = "1"
            data = self._curl_get(url, params)
            if self._is_valid_data(data):
                return self._parse_data(data, latest_only)
        
        # 3. Retry with IsReadLatestOnly=1 (Final Fallback)
        print(f"Debug: Retry(IsReadLatestOnly=1) for {indicator_code}...")
        params = base_params.copy()
        params["IsReadLatestOnly"] = "1"
        data = self._curl_get(url, params)
        if self._is_valid_data(data):
            return self._parse_data(data, latest_only)
            
        return []

    def _is_valid_data(self, data: Optional[Dict]) -> bool:
        if not data: return False
        try:
            res = data.get("GET_STATS", {}).get("RESULT", {})
            if str(res.get("status")) != "0": return False
            obj = data.get("GET_STATS", {}).get("STATISTICAL_DATA", {}).get("DATA_INF", {}).get("DATA_OBJ")
            return bool(obj)
        except:
            return False

    def _parse_data(self, data: Dict, latest_only: bool) -> List[Dict]:
        try:
            stats_data = data.get("GET_STATS", {}).get("STATISTICAL_DATA", {})
            data_objs = stats_data.get("DATA_INF", {}).get("DATA_OBJ", [])
            if isinstance(data_objs, dict): data_objs = [data_objs]
            
            results = []
            for obj in data_objs:
                val = obj.get("VALUE", {})
                if not val: continue
                results.append({
                    "time": val.get("@time"),
                    "value": val.get("$"),
                    "unit": val.get("@unit")
                })
            
            if latest_only and results: return [results[-1]]
            return results
        except Exception as e:
            print(f"Parse error: {e}")
            return []

    def search_stats(self, keyword: str) -> List[Dict]:
        """
        (従来) 統計表を検索して一覧を取得する (こちらはrequestsで動作確認済み)
        """
        if not self.app_id:
            return []

        endpoint = f"{self.ESTAT_BASE_URL}/getStatsList"
        params = {
            "appId": self.app_id,
            "searchWord": keyword,
            "limit": 10
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            stats_list = []
            table_inf = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {}).get("TABLE_INF", [])
            
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

if __name__ == "__main__":
    # テスト
    fetcher = StatsFetcher()
    print("--- Indicator Search ---")
    indicators = fetcher.search_indicators("消費者物価指数")
    for ind in indicators[:3]:
        print(f"Name: {ind['name']}, Code: {ind['code']}")
        if ind['code']:
            data = fetcher.get_indicator_data(ind['code'])
            for d in data:
                print(f"  Latest: {d['time']} -> {d['value']} {d['unit']}")
