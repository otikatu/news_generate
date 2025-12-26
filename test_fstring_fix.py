
from datetime import datetime

today_str = datetime.now().strftime("%Y年%m月%d日")
data_status = "Status"
topic = "Topic"
news_context = "News"
diet_context = "Diet"

try:
    prompt = f"""
    今日は {today_str} です。
    {data_status}
    {topic}
    {news_context}
    {diet_context}
    以下JSON:
    [
      {{
        "title": "スライド1",
        "content": "...",
        "caption": "..."
      }}
    ]
    """
    print("SUCCESS: Prompt created successfully without format error.")
except Exception as e:
    print(f"FAILED: {e}")
