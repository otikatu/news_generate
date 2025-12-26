# 政治ニュース & 国会議事録 要約台本システム

このシステムは、ウェブ上の政治ニュース（RSS）と国会議事録を横断的に検索し、AIが信頼性の高い解説台本を自動生成するツールです。

## 特徴
- **マルチソース検索**: 主要6紙の政治ニュースRSSを同時に取得。
- **一次情報へのアクセス**: 国立国会図書館の国会議事録APIを使用し、実際の議論を確認。
- **公明新聞連携**: アカウント情報を設定することで、電子版からの記事自動取得をサポート（ベータ版）。
- **出典明記**: 生成される台本には、必ず情報のソース名が記載されます。

## セットアップ

1. **環境構築**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **アプリの起動**
   ```bash
   streamlit run app.py
   ```

3. **使い方**
   - サイドバーに `OpenAI API Key` を入力します。
   - 必要に応じて公明新聞の `ID/PASS` を入力します。
   - 議題（例：政治家）や期間を入力し、「台本を生成する」をクリックしてください。

## ファイル構成
- `app.py`: StreamlitのUI本体
- `diet_minutes_api.py`: 国会議事録API連携
- `news_fetcher.py`: ニュースRSS取得
- `komei_scraper.py`: 公明新聞自動ログイン・取得
- `script_generator.py`: LLM (GPT-4o) による台本生成
