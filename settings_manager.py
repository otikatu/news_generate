import json
import os
from typing import Dict

SETTINGS_FILE = "settings.json"

def load_settings() -> Dict:
    """設定ファイルを読み込む"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return {}

def save_settings(settings: Dict):
    """設定ファイルを保存する"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")
