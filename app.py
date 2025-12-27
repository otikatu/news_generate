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
from settings_manager import load_settings, save_settings
from project_manager import save_project, list_projects, delete_project

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
            "komei_article_url": komei_article_url
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
            "議題・キーワード (複数入力はカンマ区切り)", 
            placeholder="例：防衛増税, 少子化対策",
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
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        use_komei = st.checkbox("公明新聞(全文取得)", value=True)
    with col_s2:
        use_diet = st.checkbox("国会議事録", value=True)
    with col_s3:
        use_news = st.checkbox("一般ニュース (Google & RSS)", value=True)

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

    # 2. 台本生成ボタン (トレンド待ちを回避するために上に移動)
    if st.button("🚀 台本を生成する", type="primary"):
        if not topic:
            st.error("キーワードを入力してください。")
        elif not api_key:
            st.error(f"{provider}のAPIキーをサイドバーに入力してください。")
        else:
            # 期間の確定（1つしか選ばれていない場合は終了日を今日にする）
            start_date = date_range[0]
            end_date = date_range[1] if len(date_range) == 2 else datetime.date.today()

            news_list = []
            speeches = []

            try:
                with st.status(f"情報を収集中 ({provider})...", expanded=True) as status:
                    # 1. 国会議事録の取得
                    if use_diet:
                        st.write("国会議事録を検索中...")
                        diet_api = DietMinutesAPI()
                        speeches = diet_api.fetch_speeches(
                            any_keyword=topic,
                            from_date=start_date.strftime("%Y-%m-%d"),
                            until_date=end_date.strftime("%Y-%m-%d")
                        )
                        st.write(f"✅ 議事録: {len(speeches)}件取得")
                    else:
                        st.write("⏩ 国会議事録をスキップ")

                    # 2. ニュースRSSの取得
                    if use_news:
                        st.write("主要メディアのRSSを検索中...")
                        news_fetcher = NewsFetcher()
                        news_list = news_fetcher.fetch_all_news(
                            keyword=topic,
                            days=(end_date - start_date).days
                        )
                        st.write(f"✅ ニュース: {len(news_list)}件取得")
                    else:
                        st.write("⏩ その他ニュースをスキップ")

                    # 3. 公明新聞スクレイピング
                    if use_komei and komei_user and komei_pass:
                        scraper = KomeiScraper()
                        target_urls = []
                        
                        if komei_article_url:
                            target_urls = [komei_article_url]
                        else:
                            st.write("---")
                            st.write(f"🔍 公明新聞から「{topic}」に関連する記事を自動検索中...")
                            target_urls = asyncio.run(scraper.search_articles(topic))
                        
                        if target_urls:
                            for idx, url in enumerate(target_urls):
                                st.write(f"📄 記事を取得中 ({idx+1}/{len(target_urls)}): {url}")
                                komei_text = asyncio.run(scraper.fetch_article_text(komei_user, komei_pass, url))
                                if komei_text:
                                    news_list.append({
                                        "source": "公明新聞",
                                        "title": f"検索記事 {idx+1}",
                                        "summary": komei_text[:1000] + "...",
                                        "link": url,
                                        "published": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                    })
                                    st.success(f"✅ 公明新聞: 記事{idx+1}の取得に成功しました。")
                                else:
                                    st.error(f"❌ 公明新聞: 記事{idx+1}の取得に失敗しました。")
                        elif not komei_article_url:
                            st.info("ℹ️ 公明新聞: 関連する最新記事は見つかりませんでした。")
                    else:
                        st.write("⏩ 公明新聞をスキップ")

                    # 4. 台本生成
                    st.write(f"AI ({model}) が台本を執筆中...")
                    if not news_list and not speeches:
                        st.warning(f"「{topic}」に関する最新情報が見つかりませんでした。AIは過去の知識に基づいて台本を作成します。")
                    
                    generator = ScriptGenerator(provider=provider, api_key=api_key, model=model)
                    generated_text = generator.generate(topic, news_list, speeches)
                    
                    # プレゼン資料用データを抽出
                    slides_data = generator.extract_json_from_response(generated_text)
                    
                    # 全て成功した場合のみセッション状態を更新 (Atomic update)
                    st.session_state["current_script"] = generated_text
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
        st.session_state["current_script"] = st.text_area(
            "台本内容 (コピーして利用してください)", 
            value=st.session_state["current_script"], 
            height=400
        )
        
        if st.button("💾 プロジェクトを保存する"):
            path = save_project(
                st.session_state["current_topic"], 
                st.session_state["current_script"], 
                st.session_state["current_news"], 
                st.session_state["current_speeches"], 
                st.session_state["current_provider"], 
                st.session_state["current_model"]
            )
            st.success(f"プロジェクトを保存しました: {path}")

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
