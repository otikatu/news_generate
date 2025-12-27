import requests
from typing import List, Dict, Optional
import json

class SubsidyFetcher:
    """
    jGrants (Jグランツ) APIを使用して補助金情報を取得するクラス
    Base URL: https://api.jgrants-portal.go.jp/exp/v1/public
    """
    BASE_URL = "https://api.jgrants-portal.go.jp/exp/v1/public"

    def search_subsidies(self, keyword: str) -> List[Dict]:
        """
        キーワードで補助金を検索する
        acceptance=1 は「募集中(公募中)」を意味すると推測される
        """
        endpoint = f"{self.BASE_URL}/subsidies"
        params = {
            "keyword": keyword,
            "acceptance": "1", # 1:募集中
            "sort": "created_date",
            "order": "DESC"
        }
        # print(f"Debug: Requesting {endpoint} with {params}")
        headers = {
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            # print(f"Debug: Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")
                return []
                
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # API response structure validation
            if isinstance(data, dict):
                items = data.get("result", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []

            # print(f"Debug: Items found for '{keyword}': {len(items)}")

            for item in items:
                # 必要な情報を抽出
                # API response keys: id, name, title, target_area_search, subsidy_max_limit, acceptance_start/end_datetime, target_number_of_employees
                deadline = item.get("acceptance_end_datetime", "不明")
                if deadline and "T" in deadline:
                    deadline = deadline.split("T")[0] # ISO format to YYYY-MM-DD
                    
                limit = item.get("subsidy_max_limit")
                limit_str = f"{limit:,}円" if limit else "不明"
                
                results.append({
                    "id": item.get("id"),
                    "name": item.get("name"), # ID-like name e.g. S-00007562
                    "title": item.get("title"), # Actual title
                    "target": item.get("target_number_of_employees"), 
                    "area": item.get("target_area_search"), 
                    "deadline": deadline,
                    "limit": limit_str,
                    "url": item.get("front_page_url", f"https://www.jgrants-portal.go.jp/subsidy/{item.get('id')}") # Fallback URL construction
                })
                
            return results
        except Exception as e:
            print(f"Error searching subsidies: {e}")
            return []

if __name__ == "__main__":
    # Test
    fetcher = SubsidyFetcher()
    print("--- Subsidy Search Test ---")
    
    test_keywords = ["IT", "事業", "経営", "補助金"]
    
    for kw in test_keywords:
        print(f"\nSearching for: {kw}")
        subs = fetcher.search_subsidies(kw)
        if not subs:
            print("  No subsidies found.")
        else:
            print(f"  Found {len(subs)} subsidies.")
            for s in subs[:2]:
                print(f"  - [{s['deadline']}] {s['title']} (Max: {s['limit']})")
