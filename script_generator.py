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

    def generate(self, topic: str, news_list: List[Dict], diet_speeches: List[Dict], law_titles: List[str] = [], stats_summaries: List[str] = []) -> str:
        """
        情報を統合して台本を生成 (一次ソース対応版)
        """
        news_context = "\n".join([
            f"ソース: {n['source']}\nタイトル: {n['title']}\n要約: {n['summary']}\n---" 
            for n in news_list
        ])
        
        diet_context = "\n".join([
            f"日付: {s.get('date')}\n発言者: {s.get('speaker')}\n会議録: {s.get('speech')[:500]}...\n---" 
            for s in diet_speeches
        ])

        law_context = "\n".join([f"- {title}" for title in law_titles])
        stats_context = "\n".join([f"- {summary}" for summary in stats_summaries])

        today_str = datetime.now().strftime("%Y年%m月%d日")
        
        # 検索結果が空の場合のメッセージ
        if not news_list and not diet_speeches and not law_titles:
            data_status = f"【警告】指定されたキーワード「{topic}」に関する最新情報（ニュース・国会・法令）は見つかりませんでした。"
        else:
            data_status = f"以下に、最新（{today_str}時点）の多角的な情報を集約しました。"

        prompt = f"""
あなたは精鋭の政治政策アナリスト兼ニュース編集者です。
今日は {today_str} です。

{data_status}

【トピック】: {topic}

【1. 一次ソース（法令・公的データ）】
{law_context if law_context else "（特になし。必要に応じて現行制度に言及してください）"}

【2. 一次ソース（統計・数字）】
{stats_context if stats_context else "（特になし）"}

【3. 一次ソース（国会議事録）】
{diet_context if diet_context else "（直近の審議記録なし）"}

【4. 二次ソース（最新ニュース）】
{news_context}

【台本構成案】
1. タイトルキャプション（目を引く一文）
2. 今回のニュースの本質（何が起きているか）
3. 【信頼性チェック】制度の裏付けと数字の根拠
   - e-Gov法令やe-Stat統計に基づき、「いつから」「誰が」「どれくらい」影響を受けるか数字で解説。
4. 国会での主な議論（野党の追及や政府の答弁を、出典を明記しながら引用）
5. この議題のこれからの注目点（確度ラベル：方針、法案段階、成立済、施行済を明示）

【制約事項】
- 必ず情報の出典（◯◯新聞、国会議事録、e-Gov、e-Statなど）を文中に明記すること。
- 情報の「確度」を意識してください（例：「ニュースでは検討と報じられていますが、法令上は既に...」など）。
- 専門用語は分かりやすく噛み砕いて説明すること。
- 客観的でありつつ、視聴者が「なるほど」と思うような深みのある解説にすること。
- 【重要】最後に、以下のJSON形式で「プレゼン資料用の構成データ」を出力してください。
```json
[
  {{
    "title": "スライドタイトル",
    "content": "・箇条書き1\\n・箇条書き2",
    "caption": "補足説明"
  }}
]
```
このJSONブロックは、台本の最後に ````json ... ```` の形式で必ず含めてください。
"""
        if self.provider == "openai":
            return self._generate_openai(prompt)
        elif self.provider == "gemini":
            return self._generate_gemini(prompt)

    def refine(self, current_script: str, instruction: str) -> str:
        """
        既存の台本に対して、ユーザーの追加指示を反映して再構成する
        """
        prompt = f"""
あなたは精鋭の政治解説系YouTuber兼ニュース編集者です。
現在、以下の台本がありますが、それに対してユーザーから追加の指示がありました。

【現在の台本】:
{current_script}

【ユーザーの追加指示】:
{instruction}

【指示に従って台本をブラッシュアップしてください】
- 既存の良い部分は残しつつ、指示内容を的確に反映してください。
- 専門用語の解説や、出典の明記（◯◯新聞、国会議事録など）というルールは維持してください。
- 【重要】最後に、スライド資料用のJSONデータも新しい内容に合わせて更新し、必ず ````json ... ```` の形式で末尾に含めてください。
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

    def analyze_query(self, user_input: str) -> Dict:
        """
        ユーザーの自然言語入力から、検索エンジン（ニュース・国会・法令・統計）に渡すべき
        最適な「検索キーワード」と「期間（日数）」を抽出する
        """
        prompt = f"""
        ユーザーの入力から、各ソースに合わせた「ヒット率重視」のキーワードを抽出してください。
        重要：政府系API(e-Gov, e-Stat)は非常に堅実で、説明的な言葉ではヒットしません。

        【ユーザーの入力】: {user_input}

        【出力形式 (JSONのみ)】:
        {{
          "keywords": ["政治用語1", "2"], // ニュース・国会用 (例: "国保", "少子化対策")
          "law_keywords": ["法律名の一部1", "2"], // e-Gov用。名詞1つにする。(例: "少子化", "国民健康保険")
          "stats_keywords": ["統計表名の一部1", "2"], // e-Stat用。名詞1つにする。(例: "出生", "家計", "人口")
          "days": 7
        }}

        【抽出のコツ】
        - 法令: 「〜法」の「〜」にあたる部分や、制度の正式名称（例：少子高齢化→少子化、年金、介護）。
        - 統計: 統計調査の名称に含まれる名詞（例：出生数、物価、賃金、世帯）。「対策」「政府」などの余計な言葉は除外してください。
        """
        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                return json.loads(response.choices[0].message.content)
            else: # Gemini
                response = self.client.generate_content(prompt + "\nJSONのみで出力してください。")
                text = response.text
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    res = json.loads(match.group(0))
                else:
                    res = json.loads(text)
                
                # キーワードが不足している場合の補完
                if "law_keywords" not in res: res["law_keywords"] = res.get("keywords", [user_input])
                if "stats_keywords" not in res: res["stats_keywords"] = res.get("keywords", [user_input])
                return res

        except Exception as e:
            print(f"Error analyzing query: {e}")
            return {
                "keywords": [user_input], 
                "law_keywords": [user_input], 
                "stats_keywords": [user_input], 
                "days": None, 
                "intent": "summary"
            }

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
