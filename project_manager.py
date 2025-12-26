import json
import os
import datetime
from typing import List, Dict

PROJECTS_DIR = "projects"

def ensure_projects_dir():
    """プロジェクト保存用ディレクトリを作成する"""
    if not os.path.exists(PROJECTS_DIR):
        os.makedirs(PROJECTS_DIR)

def save_project(topic: str, script: str, news_list: List[Dict], diet_speeches: List[Dict], provider: str, model: str):
    """プロジェクトをJSONファイルとして保存する"""
    ensure_projects_dir()
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"project_{timestamp}.json"
    filepath = os.path.join(PROJECTS_DIR, filename)
    
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "topic": topic,
        "script": script,
        "news_list": news_list,
        "diet_speeches": diet_speeches,
        "provider": provider,
        "model": model
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filepath

def list_projects() -> List[Dict]:
    """保存されたプロジェクトの一覧を取得する（最新順）"""
    ensure_projects_dir()
    projects = []
    
    for filename in os.listdir(PROJECTS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(PROJECTS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["filename"] = filename
                    projects.append(data)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    # タイムスタンプでソート（新しい順）
    return sorted(projects, key=lambda x: x.get("timestamp", ""), reverse=True)

def delete_project(filename: str):
    """プロジェクトを削除する"""
    filepath = os.path.join(PROJECTS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
