import streamlit as st
import datetime
import asyncio
import os
import subprocess
from diet_minutes_api import DietMinutesAPI
from news_fetcher import NewsFetcher
from script_generator import ScriptGenerator
from komei_scraper import KomeiScraper
from slide_generator import SlideGenerator
from law_fetcher import LawFetcher
from stats_fetcher import StatsFetcher
from settings_manager import load_settings, save_settings
from project_manager import save_project, list_projects, delete_project
import re
import json

# ページ設定
st.set_page_config(page_title="国会NEWS台本", layout="wide")

# カスタムCSSの注入 (シンプル＆クリーン)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Noto+Sans+JP:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans JP', sans-serif;
    }

    /* タイトルデザイン (シンプル版) */
    .title-area {
        margin-bottom: 2rem;
    }
    .title-text {
        font-size: 2.5rem;
        font-weight: 800;
        color: #2196f3;
        line-height: 1.2;
    }
    .subtitle-text {
        font-size: 1rem;
        color: #888;
        margin-top: 5px;
    }

    /* ボタンの角丸 */
    div.stButton > button {
        border-radius: 10px;
        transition: all 0.2s ease;
    }
    
    /* カードの角丸 (テーマの色を活かすため背景指定なし) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        padding: 1.2rem !important;
    }

    /* モバイル用調整 */
    @media (max-width: 640px) {
        .title-text { font-size: 1.8rem; }
    }
</style>
""", unsafe_allow_html=True)

# ユーティリティ
def clean_script_text(text: str) -> str:
    """台本からJSONブロックを除去する"""
    if not text:
        return ""
    # ```json ... ``` を除去
    text = re.sub(r"```json.*?```", "", text, flags=re.DOTALL)
    # 裸の JSON 配列っぽい部分も除去 (念のため)
    text = re.sub(r"\[\s*\{.*\}\s*\]", "", text, flags=re.DOTALL)
    return text.strip()

# Playwrightのブラウザをクラウド環境でインストール
@st.cache_resource
def ensure_playwright_browsers():
    # Streamlit Cloudの検知 (環境変数またはパス)
    is_cloud = os.environ.get("STREAMLIT_SERVER_GATHER_USAGE_STATS") is not None or os.path.exists("/home/appuser")
    if is_cloud:
        try:
            # ブラウザが既にあるかチェック (高速化のため)
            if not os.path.exists("/home/appuser/.cache/ms-playwright"):
                subprocess.run(["playwright", "install", "chromium"], check=True)
            return True
        except Exception as e:
            st.error(f"Playwrightのインストールに失敗しました: {e}")
            return False
    return True

ensure_playwright_browsers()

# 設定の読み込み
saved_settings = load_settings()

st.markdown("""
<div class="title-area">
    <div class="title-text">🏛️ 国会NEWS台本</div>
    <div class="subtitle-text">最新ニュースと国会議事録から、高品質な解説台本を。</div>
</div>
""", unsafe_allow_html=True)

# サイドバー: 設定
# サイドバー: 設定
with st.sidebar:
    st.header("⚙️ モデル設定")
    
    # settings.json (ローカル) の読み込み
    saved_settings = load_settings()

    # st.secrets (クラウド) または settings.json (ローカル) からデフォルト値を取得
    def get_secret_or_setting(key, setting_key):
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            # secrets.toml が存在しない、またはキーがない場合は無視してローカル設定へ
            pass
        return saved_settings.get(setting_key, "")

    default_openai_key = get_secret_or_setting("OPENAI_API_KEY", "openai_key")
    default_gemini_key = get_secret_or_setting("GEMINI_API_KEY", "gemini_key")
    default_komei_user = get_secret_or_setting("KOMEI_USER", "komei_user")
    default_komei_pass = get_secret_or_setting("KOMEI_PASS", "komei_pass")
    default_estat_id = get_secret_or_setting("ESTAT_APP_ID", "estat_id")
    
    # プロバイダー選択
    provider = st.selectbox("AIプロバイダー", ["OpenAI", "Gemini"], index=0 if saved_settings.get("provider") == "OpenAI" else 1)
    
    if provider == "OpenAI":
        api_key = st.text_input("OpenAI API Key", type="password", key="openai_key_input", value=default_openai_key)
        model = st.selectbox("モデル", ["gpt-4o", "gpt-4o-mini"], index=0 if saved_settings.get("openai_model") == "gpt-4o" else 1)
    else:
        api_key = st.text_input("Gemini API Key", type="password", key="gemini_key_input", value=default_gemini_key)
        model = st.selectbox("モデル", [
            "gemini-3-pro-preview", 
            "gemini-3-pro-image-preview", 
            "gemini-2.5-pro"
        ], index=["gemini-3-pro-preview", "gemini-3-pro-image-preview", "gemini-2.5-pro"].index(saved_settings.get("gemini_model", "gemini-3-pro-preview")))
    
    st.divider()
    st.subheader("💡 外部連携 (オプション)")
    
    komei_user = st.text_input("KOMEI ID", placeholder="example@komei.jp", value=default_komei_user)
    komei_pass = st.text_input("Password", type="password", value=default_komei_pass)
    komei_article_url = st.text_input("公明記事URL", placeholder="https://viewer.komei-shimbun.jp/...", value=saved_settings.get("komei_article_url", ""))
    estat_id = st.text_input("e-Stat App ID", placeholder="取得したIDを入力してください", value=default_estat_id, type="password")

    if st.button("💾 設定を保存"):
        # 入力された値（またはsecretsから読み込まれた値）を保存
        # セキュリティ上の理由でsecretsの値をローカル設定ファイルに書くことになりますが、
        # ユーザーが明示的に保存ボタンを押した場合なので許容します。
        current_settings = {
            "provider": provider,
            "openai_key": api_key, # 入力フィールドの値を採用
            "openai_model": model if provider == "OpenAI" else saved_settings.get("openai_model", "gpt-4o"),
            "gemini_key": api_key, # 入力フィールドの値を採用
            "gemini_model": model if provider == "Gemini" else saved_settings.get("gemini_model", "gemini-3-pro-preview"),
            "komei_user": komei_user,
            "komei_pass": komei_pass,
            "komei_article_url": komei_article_url,
            "estat_id": estat_id
        }
        save_settings(current_settings)
        st.success("設定を保存しました。")

# メイン画面のタブ
tab_main, tab_history = st.tabs(["🚀 台本作成", "📜 履歴一覧"])

with tab_main:
    # 1. 入力フォームを最上部に配置 (レスポンシビリティ向上)
    col1, col2 = st.columns([2, 1])

    if "main_topic_input" not in st.session_state:
        st.session_state["main_topic_input"] = ""

    with col1:
        topic = st.text_input(
            "議題・キーワード（文章での入力もOK！）", 
            placeholder="例：国保逃れについて直近の話題をまとめて",
            key="main_topic_input"
        )
        
    with col2:
        date_range = st.date_input(
            "期間指定",
            value=(datetime.date.today() - datetime.timedelta(days=7), datetime.date.today()),
            help="情報を取得する対象期間を選択してください"
        )

    # ソース選択
    st.markdown("🔍 **収集ソースの選択**")
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        use_komei = st.checkbox("公明新聞", value=True)
    with col_s2:
        use_diet = st.checkbox("国会議事録", value=True)
    with col_s3:
        use_news = st.checkbox("一般ニュース", value=True)
    with col_s4:
        use_law = st.checkbox("e-Gov法令", value=True)
    with col_s5:
        use_stats = st.checkbox("e-Stat統計", value=True)

    # セッション状態の初期化
    if "current_script" not in st.session_state:
        st.session_state["current_script"] = None
    if "current_news" not in st.session_state:
        st.session_state["current_news"] = []
    if "current_speeches" not in st.session_state:
        st.session_state["current_speeches"] = []
    if "show_trends" not in st.session_state:
        st.session_state["show_trends"] = False
    if "current_model" not in st.session_state:
        st.session_state["current_model"] = "N/A"
    if "current_raw_script" not in st.session_state:
        st.session_state["current_raw_script"] = ""

    # 2. 台本生成ボタン
    if st.button("🚀 台本を生成する", type="primary"):
        if not topic:
            st.error("キーワードを入力してください。")
        elif not api_key:
            st.error(f"{provider}のAPIキーをサイドバーに入力してください。")
        else:
            # 前回の情報をクリア
            st.session_state["current_raw_script"] = ""
            st.session_state["current_script"] = ""
            st.session_state["current_slides_data"] = []
            st.session_state["current_news"] = []
            st.session_state["current_speeches"] = []
            
            try:
                generator = ScriptGenerator(provider, api_key, model)
                
                with st.status(f"リクエストを解析中...", expanded=True) as status:
                    # 自然言語解析の実行
                    query_info = generator.analyze_query(topic)
                    search_keywords = ", ".join(query_info["keywords"])
                    st.write(f"🔍 検索キーワードを抽出しました: `{search_keywords}`")
                    
                    # 期間の確定
                    default_start = datetime.date.today() - datetime.timedelta(days=7)
                    user_start = date_range[0]
                    user_end = date_range[1] if len(date_range) == 2 else datetime.date.today()
                    
                    if user_start != default_start:
                        start_date = user_start
                        end_date = user_end
                        st.write(f"📅 ユーザー指定の期間を適用します: {start_date} 〜 {end_date}")
                    elif query_info.get("days"):
                        end_date = datetime.date.today()
                        start_date = end_date - datetime.timedelta(days=query_info["days"])
                        st.write(f"📅 文章から期間を推測しました: {start_date} 〜 {end_date} ({query_info['days']}日間)")
                    else:
                        start_date = user_start
                        end_date = user_end

                    news_list = []
                    speeches = []

                    # --- 1. 国会議事録の取得 ---
                    if use_diet:
                        diet_start = end_date - datetime.timedelta(days=365)
                        st.write(f"🏛️ 国会議事録を検索中 (背景調査のため 1年前まで遡ります: {diet_start} 〜 {end_date})...")
                        diet_api = DietMinutesAPI()
                        speeches = diet_api.fetch_speeches(
                            any_keyword=search_keywords,
                            from_date=diet_start.strftime("%Y-%m-%d"),
                            until_date=end_date.strftime("%Y-%m-%d")
                        )
                        st.write(f"✅ 議事録: {len(speeches)}件取得")
                    else:
                        st.write("⏩ 国会議事録をスキップ")

                    # --- 2. ニュースRSSの取得 ---
                    if use_news:
                        st.write(f"主要メディアのRSSを検索中...")
                        news_fetcher = NewsFetcher()
                        main_kw = query_info["keywords"][0] if query_info["keywords"] else topic
                        news_list = news_fetcher.fetch_all_news(
                            keyword=main_kw,
                            days=(end_date - start_date).days
                        )
                        st.write(f"✅ ニュース: {len(news_list)}件取得 (キーワード: {main_kw})")
                    else:
                        st.write("⏩ その他ニュースをスキップ")

                    # --- 3. 公明新聞スクレイピング ---
                    if use_komei and komei_user and komei_pass:
                        scraper = KomeiScraper()
                        target_urls = []
                        if komei_article_url:
                            target_urls = [komei_article_url]
                        else:
                            st.write("---")
                            k_keywords = query_info.get("keywords", [topic])
                            st.write(f"🔍 公明新聞を検索中 (キーワード候補: {', '.join(k_keywords)})...")
                            for kw in k_keywords:
                                f_urls = asyncio.run(scraper.search_articles(kw))
                                if f_urls:
                                    target_urls.extend(f_urls)
                                    st.write(f"✅ 公明新聞: 「{kw}」で記事が見つかりました")
                                    break
                        if target_urls:
                            target_urls = list(dict.fromkeys(target_urls))[:3]
                            for idx, url in enumerate(target_urls):
                                st.write(f"📄 公明新聞記事の内容を抽出中 ({idx+1}/{len(target_urls)})...")
                                komei_text = asyncio.run(scraper.fetch_article_text(komei_user, komei_pass, url))
                                if komei_text:
                                    news_list.append({
                                        "source": "公明新聞",
                                        "title": f"公明新聞 関連記事 {idx+1}",
                                        "summary": komei_text[:1000] + "...",
                                        "link": url,
                                        "published": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                    })
                                    st.success(f"✅ 公明新聞: 成功")
                                else:
                                    st.error(f"❌ 公明新聞: 失敗")
                        elif not komei_article_url:
                            st.info("ℹ️ 公明新聞: 関連記事なし")
                    else:
                        st.write("⏩ 公明新聞をスキップ")

                    # --- 4. 法令情報の取得 ---
                    law_titles = []
                    if use_law:
                        st.write("e-Gov法令APIを検索中...")
                        law_fetcher = LawFetcher()
                        l_keywords = query_info.get("law_keywords", query_info["keywords"])
                        unique_laws = []
                        seen_ids = set()
                        for kw in l_keywords:
                            st.write(f"🔍 法令: 「{kw}」で検索試行中...")
                            results = law_fetcher.search_laws(kw)
                            if results:
                                for r in results:
                                    if r['id'] not in seen_ids:
                                        unique_laws.append(r)
                                        seen_ids.add(r['id'])
                            if len(unique_laws) >= 5: break
                        law_titles = [f"{r['title']} ({r['number']})" for r in unique_laws[:5]]
                        st.write(f"✅ 法令: {len(law_titles)}件特定")

                    # --- 5. 統計情報の取得 ---
                    stats_summaries = []
                    if use_stats:
                        st.write("e-Stat統計APIを検索中...")
                        stats_fetcher = StatsFetcher(app_id=estat_id)
                        s_keywords = query_info.get("stats_keywords", query_info["keywords"])
                        unique_stats = []
                        seen_ids = set()
                        for kw in s_keywords:
                            st.write(f"📊 統計: 「{kw}」で検索試行中...")
                            results = stats_fetcher.search_stats(kw)
                            if results:
                                for r in results:
                                    if r['id'] not in seen_ids:
                                        unique_stats.append(r)
                                        seen_ids.add(r['id'])
                            if len(unique_stats) >= 5: break
                        stats_summaries = [f"{r['title']} ({r['org']})" for r in unique_stats[:5]]
                        st.write(f"✅ 統計: {len(stats_summaries)}件特定")

                    # --- 6. 台本生成 ---
                    st.write(f"AI ({model}) が台本を執筆中...")
                    generator = ScriptGenerator(provider=provider, api_key=api_key, model=model)
                    generated_text = generator.generate(topic, news_list, speeches, law_titles, stats_summaries)
                    slides_data = generator.extract_json_from_response(generated_text)
                    
                    st.session_state["current_raw_script"] = generated_text
                    st.session_state["current_script"] = clean_script_text(generated_text)
                    st.session_state["current_slides_data"] = slides_data
                    st.session_state["current_news"] = news_list
                    st.session_state["current_speeches"] = speeches
                    st.session_state["current_topic"] = topic
                    st.session_state["current_provider"] = provider
                    st.session_state["current_model"] = model
                    
                    status.update(label="完了！", state="complete", expanded=False)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    # 生成結果の表示
    if st.session_state["current_script"]:
        st.divider()
        st.subheader(f"📝 生成された要約台本 ({st.session_state['current_model']})")
        
        # 台本の編集・閲覧
        new_script = st.text_area(
            "台本内容 (直接編集も可能です)", 
            value=st.session_state["current_script"], 
            height=400,
            key="display_script_area"
        )
        st.session_state["current_script"] = new_script

        # --- 台本の再構成（Refinement） ---
        st.markdown("🪄 **AIに再構成を依頼する**")
        refine_instruction = st.text_input(
            "追加の指示（例：もっと具体例を増やして、トーンを明るくして、議論を深掘りして）",
            placeholder="ここに指示を入力してください...",
            key="refine_input"
        )
        
        if st.button("✨ 再構成を実行"):
            if not refine_instruction:
                st.warning("指示を入力してください。")
            else:
                try:
                    with st.status("台本を再構成中...", expanded=True) as status:
                        generator = ScriptGenerator(
                            provider=st.session_state["current_provider"], 
                            api_key=api_key, 
                            model=st.session_state["current_model"]
                        )
                        # 最新の(編集された)台本と、生データを組み合わせて再送
                        new_raw_text = generator.refine(
                            st.session_state["current_raw_script"], 
                            refine_instruction
                        )
                        
                        # 更新
                        st.session_state["current_raw_script"] = new_raw_text
                        st.session_state["current_script"] = clean_script_text(new_raw_text)
                        st.session_state["current_slides_data"] = generator.extract_json_from_response(new_raw_text)
                        
                        status.update(label="再構成完了！", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"再構成中にエラーが発生しました: {e}")

        col_save, _ = st.columns([1, 4])
        with col_save:
            if st.button("💾 プロジェクトを保存する"):
                path = save_project(
                    st.session_state["current_topic"], 
                    st.session_state["current_raw_script"], # 保存はフルデータ
                    st.session_state["current_news"], 
                    st.session_state["current_speeches"], 
                    st.session_state["current_provider"], 
                    st.session_state["current_model"]
                )
                st.success(f"保存完了: {path}")

        # プレゼン資料ダウンロード機能
        if st.session_state.get("current_slides_data"):
            st.divider()
            st.subheader("📊 プレゼン資料の生成")
            st.info("台本から構造化データを抽出し、自動生成されたスライド資料です。")
            
            presentation_title = f"{st.session_state['current_topic']}に関する解説"
            slide_gen = SlideGenerator()
            pptx_path = slide_gen.create_slides(presentation_title, st.session_state["current_slides_data"])
            
            with open(pptx_path, "rb") as f:
                st.download_button(
                    label="📥 プレゼン資料(.pptx)をダウンロード",
                    data=f,
                    file_name=f"presentation_{datetime.date.today()}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
            
            with st.expander("📊 スライド構成データ (JSON) を確認"):
                st.json(st.session_state["current_slides_data"])

        with st.expander("取得データ（ソース）の確認"):
            tab_n, tab_s = st.tabs(["🗞️ ニュース・記事", "🏛️ 国会議事録"])
            with tab_n:
                if not st.session_state["current_news"]:
                    st.info("取得されたニュースはありません。")
                for n in st.session_state["current_news"]:
                    with st.container(border=True):
                        st.write(f"**[{n['source']}] {n['title']}**")
                        st.caption(f"リンク: {n.get('link', 'N/A')}")
            with tab_s:
                if not st.session_state["current_speeches"]:
                    st.info("取得された議事録はありません。")
                for s in st.session_state["current_speeches"]:
                    with st.container(border=True):
                        st.write(f"**{s.get('speaker')}** ({s.get('date')} - {s.get('nameOfMeeting')})")
                        st.write(s.get('speech'))

    st.divider()

    # タグクリック時の追加ロジック (callbackで使用)
    def on_tag_click(new_tag):
        current = st.session_state.get("main_topic_input", "")
        if current:
            # すでに含まれているかチェック
            tags = [t.strip() for t in current.split(",")]
            if new_tag not in tags:
                st.session_state["main_topic_input"] = f"{current}, {new_tag}"
        else:
            st.session_state["main_topic_input"] = new_tag

    @st.cache_data(ttl=3600)  # 1時間キャッシュに戻す
    def fetch_trending_info(_provider, _api_key, _model):
        async def _fetch():
            fetcher = NewsFetcher()
            scraper = KomeiScraper()
            generator = ScriptGenerator(provider=_provider, api_key=_api_key, model=_model)
            
            # 1. 見出し取得 (個別エラーハンドリング)
            res_general = []
            res_komei = []
            err_general = None
            err_komei = None
            
            try:
                res_general = await asyncio.to_thread(fetcher.get_trending_headlines)
            except Exception as e:
                err_general = str(e)
            
            try:
                res_komei = await scraper.get_trending_headlines()
            except Exception as e:
                err_komei = str(e)
            
            # 2. キーワード抽出 (個別エラーハンドリング)
            gen_tags = []
            kom_tags = []
            
            if res_general:
                try:
                    gen_tags = await asyncio.to_thread(generator.extract_keyword_tags, res_general)
                except Exception as e:
                    err_general = f"Tags Error: {e}" if not err_general else f"{err_general} | Tags Error: {e}"
            
            if res_komei:
                try:
                    kom_tags = await asyncio.to_thread(generator.extract_keyword_tags, res_komei)
                except Exception as e:
                    err_komei = f"Tags Error: {e}" if not err_komei else f"{err_komei} | Tags Error: {e}"

            return {
                "general": {"tags": gen_tags, "headlines": res_general, "error": err_general},
                "komei": {"tags": kom_tags, "headlines": res_komei, "error": err_komei}
            }
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_fetch())
        except Exception as e:
            # st.error はキャッシュ内では使えないため warning で返すか空にする
            # 実際には呼び出し元で表示できるようにエラー情報を追加可能
            return {
                "general": {"tags": [], "headlines": []}, 
                "komei": {"tags": [], "headlines": []},
                "error": str(e)
            }

    st.divider()

    # 3. 注目キーワード・トレンドセクション (手動またはエキスパンダー形式)
    st.markdown("### 🔥 トレンド・注目キーワード")
    
    if not st.session_state.get("show_trends", False):
        if st.button("🔍 今注目のキーワードを読み込む", use_container_width=True):
            st.session_state["show_trends"] = True
            st.rerun()
    else:
        # APIキーがある場合のみタグを表示
        if not api_key:
            st.warning(f"{provider} の API キーが設定されていません。トレンドの抽出には AI 連携が必要です。")
            st.info("サイドバーでキーを入力するか、Streamlit Cloud の Secrets で設定してください。")
            st.session_state["show_trends"] = False
        else:
            with st.spinner("トレンド情報を取得中..."):
                trend_data = fetch_trending_info(provider, api_key, model)
                
                # エラーがあれば表示
                if "error" in trend_data:
                    st.error(f"トレンド取得中にエラーが発生しました: {trend_data['error']}")
                    st.info("Playwright の起動に失敗している可能性があります（クラウド環境の制限など）。")
            
            # 1. 一般ニュースセクション
            with st.container(border=True):
                st.markdown("🗞️ **一般ニュースの注目ワード**")
                tags = trend_data["general"]["tags"]
                if tags:
                    tag_cols = st.columns(len(tags))
                    for i, tag in enumerate(tags):
                        tag_cols[i].button(
                            f"#{tag}", 
                            key=f"tag_gen_{tag}", 
                            use_container_width=True,
                            on_click=on_tag_click,
                            args=(tag,)
                        )
                
                headlines = trend_data["general"]["headlines"]
                if headlines:
                    for h in headlines[:3]:
                        st.markdown(f"- <small>{h}</small>", unsafe_allow_html=True)
                    if len(headlines) > 3:
                        with st.expander("もっと見る"):
                            for h in headlines[3:]:
                                st.markdown(f"- <small>{h}</small>", unsafe_allow_html=True)

            # 2. 公明新聞セクション
            with st.container(border=True):
                st.markdown("🏢 **公明新聞の注目ワード**")
                
                # 個別エラーの表示
                if trend_data["komei"].get("error"):
                    st.warning(f"取得エラー: {trend_data['komei']['error']}")
                
                tags = trend_data["komei"]["tags"]
                if tags:
                    tag_cols = st.columns(len(tags))
                    for i, tag in enumerate(tags):
                        tag_cols[i].button(
                            f"#{tag}", 
                            key=f"tag_kom_{tag}", 
                            use_container_width=True,
                            on_click=on_tag_click,
                            args=(tag,)
                        )
                
                headlines = trend_data["komei"]["headlines"]
                if headlines:
                    for h in headlines[:3]:
                        st.markdown(f"- <small>{h}</small>", unsafe_allow_html=True)
                    if len(headlines) > 3:
                        with st.expander("もっと見る"):
                            for h in headlines[3:]:
                                st.markdown(f"- <small>{h}</small>", unsafe_allow_html=True)
            
            if st.button("トレンドを閉じる"):
                st.session_state["show_trends"] = False
                st.rerun()

with tab_history:
    st.header("📜 保存済みプロジェクト")
    history = list_projects()
    
    if not history:
        st.info("保存されたプロジェクトはありません。")
    else:
        for proj in history:
            with st.container(border=True):
                col_h1, col_h2, col_h3 = st.columns([3, 2, 1])
                with col_h1:
                    st.write(f"**トピック: {proj['topic']}**")
                    st.caption(f"日時: {proj['timestamp']} | モデル: {proj['model']}")
                with col_h2:
                    if st.button("台本を表示", key=f"view_{proj['filename']}"):
                        st.session_state["view_proj"] = proj
                        # メイン画面にも反映させる (ロード機能)
                        st.session_state["current_topic"] = proj.get("topic", "")
                        st.session_state["current_script"] = proj.get("script", "")
                        st.session_state["current_raw_script"] = proj.get("raw_script", proj.get("script", ""))
                        st.session_state["current_news"] = proj.get("news_list", [])
                        st.session_state["current_speeches"] = proj.get("diet_speeches", [])
                        st.session_state["current_slides_data"] = proj.get("slides_data", [])
                        st.session_state["current_model"] = proj.get("model", "N/A")
                        st.session_state["current_provider"] = proj.get("provider", "N/A")
                        st.success(f"「{proj['topic']}」をロードしました。「台本作成」タブで編集できます。")
                with col_h3:
                    if st.button("削除", key=f"del_{proj['filename']}", type="secondary"):
                        delete_project(proj['filename'])
                        st.rerun()

    if "view_proj" in st.session_state:
        proj = st.session_state["view_proj"]
        st.divider()
        st.subheader(f"🔍 プレビュー: {proj['topic']}")
        st.text_area("保存された台本", value=proj['script'], height=400)
        
        with st.expander("保存時のソースを確認"):
            st.write(f"AIプロバイダー: {proj['provider']} ({proj['model']})")
            st.write(f"ニュース数: {len(proj.get('news_list', []))}件")
            st.write(f"議事録数: {len(proj.get('diet_speeches', []))}件")
            if st.button("プレビューを閉じる"):
                del st.session_state["view_proj"]
                st.rerun()

# フッター
st.divider()
st.caption("Powered by 国会議事録検索システムAPI & OpenAI/Google Gemini")
