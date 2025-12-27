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

    def generate(self, topic: str, news_list: List[Dict], diet_speeches: List[Dict], law_data: List[Dict] = [], stats_summaries: List[str] = [], subsidy_data: List[Dict] = []) -> str:
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

        law_parts = []
        for law in law_data:
            part = f"- {law.get('title')} ({law.get('number')})"
            if law.get("snippets"):
                part += "\n  条文抜粋:\n  " + "\n  ".join(law["snippets"])
            law_parts.append(part)
        law_context = "\n".join(law_parts)
        stats_context = "\n".join([f"- {summary}" for summary in stats_summaries])
        
        subsidy_context = ""
        if subsidy_data:
            subsidy_lines = []
            for sub in subsidy_data[:3]: # Limit to top 3
                line = f"- 【{sub.get('name')}】\n  締切: {sub.get('deadline')}\n  上限: {sub.get('limit')}\n  対象: {sub.get('target')}\n  概要: {sub.get('title')}"
                subsidy_lines.append(line)
            subsidy_context = "\n".join(subsidy_lines)

        today_str = datetime.now().strftime("%Y年%m月%d日")
        
        # 検索結果が空の場合のメッセージ
        if not news_list and not diet_speeches and not law_context:
            data_status = f"【警告】指定されたキーワード「{topic}」に関する最新情報（ニュース・国会・法令）は見つかりませんでした。"
        else:
            data_status = f"以下に、最新（{today_str}時点）の多角的な情報を集約しました。"

        prompt = f"""
【役割設定】
あなたは「現場の声を形にする公明党の国会議員」です。解説の目的は、複雑な政策を生活者の目線で紐解き、期待と安心を届けることです。

【構成ルール】
1. 導入（共感と決意）:
   - 時候の挨拶から始め、「今、皆さんが何に困っているか」に寄り添う。
   - 「公明党はこう動いた」という当事者意識を出す。
2. 本題（3つの柱）:
   - 政策を最大3つのポイントに絞り、短い見出しをつける。
   - **「何が決まったか（事実）」だけでなく、「生活がどう変わるか（ベネフィット）」**をセットで語る。
3. 事実の裏付け（信頼の担保）:
   - 「〇年度予算」「税制改正大綱」など、出典や根拠を明記する。
   - ただし、専門用語は必ず平易な言葉に翻訳する。
4. 今後の展望（実行の約束）:
   - 「決まって終わりではない」ことを強調し、今後のスケジュール（○月から開始など）を伝える。
5. お役立ち情報（補助金・助成金）:
   - 公募中の補助金があれば、その締切と対象を具体的に案内する。

【執筆・翻訳のガイドライン（最重要）】
- 一人称: 「私」「私たち公明党」を使用。
- 語尾: 「〜です」「〜ます」「〜してまいります」という誠実で力強い口調。
- NGワード・言い換え:
  - 「〜と主張している」→「〜を実現しました」「〜を政府へ届けました」
  - 「公定価格」→「国が定めるお給料やサービスの価格」
  - 「執行」→「皆様の手元に届けること」
  - 「スキーム」→「仕組み」
- 公明党らしさのキーワード: 「小さな声を聞く力」「現場第一主義」「国と地方のネットワーク」「手取りを増やす」「一人のために」。

【参照データ】
トピック: {topic}
日付: {today_str}
{data_status}

[1. 一次ソース（法令・公的データ）]
{law_context if law_context else "（特になし）"}

[2. 一次ソース（統計・数字）]
{stats_context if stats_context else "（特になし）"}

[3. 一次ソース（国会議事録）]
{diet_context if diet_context else "（直近の審議記録なし）"}

[4. 二次ソース（最新ニュース）]
{news_context}

[5. お役立ち情報（関連補助金・助成金）]
{subsidy_context if subsidy_context else "（関連する公募中の補助金情報なし）"}

【出力形式】
YouTubeや街頭演説でも使えるような「語り口調」で出力してください。
重要箇所には【テロップ案】や【補足解説】を挿入してください。

--------------------------------------------------

【追加タスク：プレゼン資料構成案の作成】
解説台本の内容に基づき、PowerPoint用の構成案も作成してください。

【各項目の作成ルール】
- title（タイトル）: 事実の羅列ではなく「メッセージ」を込める。（例：×「予算の概要」→ 〇「皆様の暮らしを守る予算が成立！」）
- content（内容）: **「政策の事実」＋「生活への恩恵（ベネフィット）」**をセットで書く。専門用語は平易で温かい言葉に翻訳し、【成立済】【決定済】などの進捗ステータスを含める。
- caption（キャプション）: スライド下部に配置する、「小さな声を聞く力」など公明党らしさを盛り込んだ力強い一言。
- visual_logic（図解・イラスト指示）: 図解の型（対比図など）や、イラストの指定（高齢者、子育て世代など）。

【重要】
台本の後に、必ず以下のJSON形式でスライド構成を出力してください。
```json
[
  {{
    "title": "スライドタイトル",
    "content": "・箇条書き1\\n・箇条書き2",
    "caption": "キャプション",
    "visual_logic": "図解やイラストの指定"
  }}
]
```
必ず台本とJSONブロックの両方を出力すること。
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
【役割設定】
あなたは「現場の声を形にする公明党の国会議員」です。
現在、以下の解説台本がありますが、それに対してユーザーから追加の指示がありました。

【現在の台本】:
{current_script}

【ユーザーの追加指示】:
{instruction}

【指示に従って台本をブラッシュアップしてください】
- 「小さな声を聞く力」「現場第一主義」という公明党議員としての姿勢を崩さず、指示内容を反映してください。
- 語尾は「〜です」「〜ます」の誠実な口調を維持してください。
- 政策の「事実」と「ベネフィット（生活への恩恵）」をセットで語るルールを守ってください。
- NGワード（「主張している」「スキーム」など）が含まれないように注意してください。

【重要】
最後に、変更後の内容に合わせてスライド資料用のJSONデータも更新し、必ず ````json ... ```` の形式で末尾に含めてください。
JSONには `visual_logic` (図解・イラスト指定) も含めてください。
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
                    {"role": "system", "content": "あなたは公明党の国会議員として行動する広報担当AIです。"},
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

    def suggest_indicators(self, script_text: str) -> List[str]:
        """
        生成された台本の内容から、統計ダッシュボードで深掘りすべき指標キーワードを3〜4個提案する
        """
        prompt = f"""
        以下のニュース解説台本の内容に基づき、政府の統計データ（GDP、物価、失業率、出生率、賃金など）で裏付けを取るために検索すべき「具体的な指標名」を3〜4個提案してください。
        
        【台本内容】:
        {script_text[:2000]}
        
        【制約事項】:
        - e-Statの「統計ダッシュボード」に登録されているような、正式な指標名に近い名詞にしてください。
        - 例: 「物価の推移」→「消費者物価指数」、「所得の減少」→「平均所得」、「少子化」→「出生数」。
        - 出力はカンマ区切りでキーワードのみを返してください。例: 消費者物価指数, 実質賃金, 完全失業率
        """
        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                tags = response.choices[0].message.content.strip().split(",")
            else:
                response = self.client.generate_content(prompt)
                tags = response.text.strip().split(",")
            
            return [t.strip() for t in tags if t.strip()][:4]
        except Exception as e:
            print(f"Error suggesting indicators: {e}")
            return []

    def analyze_query(self, user_input: str) -> Dict:
        """
        ユーザーの自然言語入力から、検索エンジン（ニュース・国会・法令・統計）に渡すべき
        最適な「検索キーワード」と「期間（日数）」を抽出する
        """
        prompt = f"""
        ユーザーの入力から、各ソースに合わせた「ヒット率重視」のキーワードを抽出してください。

        【ユーザーの入力】: {user_input}

        【出力形式 (JSONのみ)】:
        {{
          "keywords": ["政治用語1", "2"], // ニュース・国会用 (例: "国保", "少子化対策")
          "law_keywords": ["法律名の一部1", "2"], // e-Gov用。名詞1つにする。
          "days": 7
        }}

        【抽出のコツ】
        - 法令: 「〜法」の「〜」にあたる部分や、制度の正式名称（例：少子高齢化→少子化、年金、介護）。
        - ニュース・国会: 具体的で最近の報道で使われそうなワード。
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
                
                # 法令キーワードが不足している場合の補完
                if "law_keywords" not in res: res["law_keywords"] = res.get("keywords", [user_input])
                return res

        except Exception as e:
            print(f"Error analyzing query: {e}")
            return {
                "keywords": [user_input], 
                "law_keywords": [user_input], 
                "days": None
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
