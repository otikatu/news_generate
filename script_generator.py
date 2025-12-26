from openai import OpenAI
import google.generativeai as genai
from typing import List, Dict, Optional
import os
from datetime import datetime
import json
import re

class ScriptGenerator:
    """
    収集した情報を元に要約台本を生成するクラス（OpenAI / Gemini ハイブリッド対応）
    """
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model

        if self.provider == "openai":
            if not self.api_key:
                self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI APIキーが提供されていません。")
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == "gemini":
            if not self.api_key:
                self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("Gemini APIキーが提供されていません。")
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
        else:
            raise ValueError(f"未知のプロバイダーです: {provider}")

    def generate(self, topic: str, news_list: List[Dict], diet_speeches: List[Dict]) -> str:
        """
        情報を統合して台本を生成
        """
        news_context = "\n".join([
            f"ソース: {n['source']}\nタイトル: {n['title']}\n要約: {n['summary']}\n---" 
            for n in news_list
        ])
        
        diet_context = "\n".join([
            f"日付: {s.get('date')}\n発言者: {s.get('speaker')}\n会議録: {s.get('speech')[:500]}...\n---" 
            for s in diet_speeches
        ])

        today_str = datetime.now().strftime("%Y年%m月%d日")
        
        # 検索結果が空の場合のメッセージ
        if not news_list and not diet_speeches:
            data_status = f"【警告】指定されたキーワード「{topic}」に関する直近のニュースおよび国会議事録は見つかりませんでした。現在（{today_str}時点）の最新状況として特筆すべき動きがない可能性があります。"
        else:
            data_status = f"以下に、最新（{today_str}時点）の情報を集約しました。"

        prompt = f"""
あなたは精鋭の政治解説系YouTuber兼ニュース編集者です。
今日は {today_str} です。

{data_status}

【トピック】: {topic}

【最新ニュース】
{news_context}

【国会議事録】
{diet_context}

【台本構成案】
1. タイトルキャプション（目を引く一文）
2. ニュースの要点（3行で分かりやすく）
3. 国会での主な議論（野党の追及や政府の答弁を、出典を明記しながら解説）
4. この議題のこれからの注目点

【制約事項】
- 必ず情報の出典（◯◯新聞、国会議事録など）を文中に明記すること。
- 検索結果が空の場合は、無理にニュースを捏造せず、「現在、このトピックに関する新しい動きは見られませんが、これまでの経緯をまとめると...」というトーンで解説してください。
- 過去の議事録データ（例：2023年の第211回国会など）が含まれている場合は、それが「過去の議論」であることを明示してください。
- 専門用語は分かりやすく噛み砕いて説明すること。
- 客観的でありつつ、視聴者が「なるほど」と思うような深みのある解説にすること。
- 【重要】最後に、以下のJSON形式で「プレゼン資料用の構成データ」を出力してください。
```json
[
  {{
    "title": "スライド1のタイトル（例：今回のニュースの要点）",
    "content": "・箇条書き1\\n・箇条書き2\\n・箇条書き3",
    "caption": "スライドのノート部分に記載する補足説明や要約"
  }},
  {{
    "title": "スライド2のタイトル...",
    "content": "...",
    "caption": "..."
  }}
]
```
このJSONブロックは、台本の最後に ````json ... ```` の形式で必ず含めてください。
"""

        if self.provider == "openai":
            return self._generate_openai(prompt)
        elif self.provider == "gemini":
            return self._generate_gemini(prompt)

    def _generate_openai(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは正確さと分かりやすさを両立した政治ジャーナリストです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAIによる台本生成中にエラーが発生しました: {e}"

    def _generate_gemini(self, prompt: str) -> str:
        try:
            # Geminiは system_instruction を使うか、プロンプトに含める
            response = self.client.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Geminiによる台本生成中にエラーが発生しました: {e}"

    def extract_json_from_response(self, text: str) -> List[Dict]:
        """
        レスポンスからJSONブロックを抽出する
        """
        try:
            # ```json ... ``` を探す
            match = re.search(r"```json(.*?)```", text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                return json.loads(json_str)
            
            # そのままリスト形式っぽい場合
            match = re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
                
            return []
        except Exception as e:
            print(f"Error extracting JSON: {e}")
            return []

    def extract_keyword_tags(self, headlines: List[str]) -> List[str]:
        """
        大量の見出しから、今注目すべき政治キーワードを5〜6個抽出する
        """
        if not headlines:
            return []

        headlines_str = "\n".join(headlines)
        prompt = f"""
以下の最新ニュースの見出しリストから、現在注目されている具体的な政治キーワード（議題）を5〜6個抽出してください。
ニュース解説動画のネタとして適切な、具体的で検索されやすいワードを選んでください。

【制約事項】:
- キーワードは短く（2〜10文字程度）。
- 重複を避け、バリエーション豊かなキーワードにすること。
- 出力はカンマ区切りでキーワードのみを返してください。

【見出しリスト】:
{headlines_str}
"""
        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                tags = response.choices[0].message.content.strip().split(",")
            else: # Assuming self.provider == "gemini"
                response = self.client.generate_content(prompt)
                tags = response.text.strip().split(",")
            
            # クリーニング (余計な空白を消すなど)
            return [t.strip().replace("「", "").replace("」", "") for t in tags if t.strip()][:6]
        except Exception as e:
            print(f"Error extracting tags: {e}")
            return []

if __name__ == "__main__":
    # テスト
    print("OpenAI/Gemini Hybrid Test")
