"""data.ai ダッシュボード — 複数アプリの日別メトリクス比較

起動方法:
  pip install -r requirements.txt
  streamlit run dashboard.py
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.appannie.com/v1.3"
APPS_DB_PATH = Path(__file__).parent / "apps_db.json"

# ─── カラーパレット ───
COLORS = ["#00d4ff", "#00e676", "#7c3aed", "#f59e42", "#ef4444", "#f472b6"]
COLORS_LIGHT = ["#0a1a2e", "#0a1e14", "#1a0e2e", "#1e1408", "#1e0a0a", "#1e0a14"]


# ─── アプリDB ───
@st.cache_data(ttl=600)
def load_apps_db():
    """apps_db.json を読み込む。旧形式(配列)の場合は新形式に変換。"""
    if APPS_DB_PATH.exists():
        data = json.loads(APPS_DB_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"apps": data, "groups": []}
        return data
    return {"apps": [], "groups": []}


def save_apps_db(data):
    APPS_DB_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    load_apps_db.clear()


def load_groups():
    return load_apps_db().get("groups", [])


def save_groups(groups):
    data = load_apps_db()
    data["groups"] = groups
    save_apps_db(data)


# ─── API ───
def get_headers():
    api_key = os.getenv("DATAAI_API_KEY") or st.secrets.get("DATAAI_API_KEY")
    if not api_key:
        st.error("DATAAI_API_KEY が設定されていません。.env または Streamlit Secrets を確認してください。")
        st.stop()
    return {"Authorization": f"bearer {api_key}"}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_downloads(app_id, market, country, start_date, end_date, _v=2):
    url = f"{BASE_URL}/intelligence/apps/{market}/app/{app_id}/history"
    params = {
        "countries": country,
        "feeds": "downloads",
        "granularity": "daily",
        "start_date": start_date,
        "end_date": end_date,
    }
    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_active_users(app_id, market, country, start_date, end_date, _v=2):
    url = f"{BASE_URL}/intelligence/apps/{market}/app/{app_id}/usage-history"
    params = {
        "countries": country,
        "granularity": "daily",
        "start_date": start_date,
        "end_date": end_date,
    }
    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


# ─── パーサー ───
def _safe_int(val):
    if isinstance(val, (int, float)):
        return int(val)
    return 0


def parse_downloads(data, label):
    daily = {}
    for item in data.get("list", []):
        date = item.get("start_date") or item.get("date", "")
        estimate = _safe_int(item.get("estimate"))
        daily[date] = daily.get(date, 0) + estimate
    rows = [{"date": d, "downloads": v, "app": label} for d, v in sorted(daily.items())]
    return pd.DataFrame(rows)


def parse_active_users(data, label):
    has_total = any(item.get("device") == "ios" for item in data.get("list", []))
    daily = {}
    for item in data.get("list", []):
        if has_total and item.get("device") != "ios":
            continue
        date = item.get("date", "")
        users = _safe_int(item.get("active_users"))
        daily[date] = daily.get(date, 0) + users
    rows = [{"date": d, "dau": v, "app": label} for d, v in sorted(daily.items())]
    return pd.DataFrame(rows)


def friendly_error(e):
    status = e.response.status_code
    if status == 401:
        return "認証に失敗しました。APIキーを確認してください。"
    if status == 403:
        return "アクセス権限がありません。サブスクリプションプランを確認してください。"
    if status == 404:
        return "アプリが見つかりません。アプリIDとマーケットを確認してください。"
    return f"HTTP {status}: {e.response.text}"


def format_number(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def resample_df(df, value_col, freq, agg="sum"):
    if df.empty:
        return df
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.groupby([pd.Grouper(key="date", freq=freq), "app"])[value_col].agg(agg).reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


# ─── グラフ共通スタイル ───
def apply_chart_style(fig):
    fig.update_layout(
        plot_bgcolor="#111827",
        paper_bgcolor="#111827",
        font=dict(family="'DM Mono', 'Inter', sans-serif", size=12, color="#94a3b8"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11, color="#94a3b8"), bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=16, r=16, t=32, b=16),
        xaxis=dict(showgrid=False, linecolor="#1e293b", tickfont=dict(size=10, color="#64748b")),
        yaxis=dict(gridcolor="#1e293b", linecolor="#1e293b", tickfont=dict(size=10, color="#64748b"), separatethousands=True),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#111827", bordercolor="#1e293b", font_size=12, font_color="#f1f5f9"),
    )
    return fig


# ─── ページ設定 ───
st.set_page_config(page_title="data.ai Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

  /* ── Global Dark Theme ── */
  .block-container { padding-top: 2.5rem; max-width: 1280px; }
  html, body, [class*="st-"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  .stApp, [data-testid="stAppViewContainer"] { background: #0a0e1a !important; color: #f1f5f9; }
  header[data-testid="stHeader"] { background: #0a0e1a !important; }

  /* Sidebar dark */
  [data-testid="stSidebar"] { background: #111827 !important; border-right: 1px solid #1e293b; }
  [data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
  [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p,
  [data-testid="stSidebar"] span, [data-testid="stSidebar"] .stCaption p { color: #94a3b8 !important; }
  [data-testid="stSidebar"] input, [data-testid="stSidebar"] select,
  [data-testid="stSidebar"] [data-baseweb="select"] { background: #0a0e1a !important; color: #f1f5f9 !important; border-color: #1e293b !important; }
  [data-testid="stSidebar"] button[kind="primary"] { background: #00d4ff !important; color: #0a0e1a !important; border: none !important; }
  [data-testid="stSidebar"] button:not([kind="primary"]) { background: #1e293b !important; color: #f1f5f9 !important; border: 1px solid #2d3a4d !important; }

  /* Streamlit widget overrides */
  .stTextInput > div > div { background: #111827 !important; border-color: #1e293b !important; color: #f1f5f9 !important; }
  .stDateInput > div > div { background: #111827 !important; border-color: #1e293b !important; color: #f1f5f9 !important; }
  .stSelectbox > div > div { background: #111827 !important; border-color: #1e293b !important; }
  .stRadio label span { color: #94a3b8 !important; }
  .stCheckbox label span { color: #94a3b8 !important; }
  .stTabs [data-baseweb="tab-panel"] { background: transparent !important; }
  div[data-testid="stDataFrame"] { border: 1px solid #1e293b; border-radius: 8px; }

  /* ── Header ── */
  .dash-header {
    display: flex; align-items: center; justify-content: space-between;
    margin: 0 0 0.5rem 0; flex-wrap: wrap; gap: 0.5rem;
  }
  .dash-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem; font-weight: 800; color: #f1f5f9;
    letter-spacing: -0.02em; margin: 0; line-height: 1.3;
  }
  .dash-title span { color: #00d4ff; }
  .dash-subtitle {
    font-size: 0.8rem; color: #94a3b8; font-weight: 400; margin: 0.15rem 0 0 0;
  }

  /* ── Status Badges ── */
  .badge-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; align-items: center; }
  .badge {
    display: inline-flex; align-items: center; gap: 0.3rem;
    padding: 0.2rem 0.65rem; border-radius: 9999px;
    font-size: 0.72rem; font-weight: 500; line-height: 1.4;
  }
  .badge-outline { border: 1px solid #1e293b; color: #94a3b8; background: #111827; }
  .badge-green  { background: #042f1e; color: #00e676; border: 1px solid #065f3a; }
  .badge-blue   { background: #041e30; color: #00d4ff; border: 1px solid #0a3d5c; }
  .badge-amber  { background: #2e1e04; color: #f59e42; border: 1px solid #5c3d0a; }
  .badge-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .badge-dot-green { background: #00e676; }
  .badge-dot-amber { background: #f59e42; }

  /* ── App Tags ── */
  .app-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 1.25rem; }
  .app-tag {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.3rem 0.8rem; border-radius: 8px;
    font-size: 0.78rem; font-weight: 600;
    border: 1px solid; transition: all 0.15s;
  }
  .app-tag-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

  /* ── KPI Cards ── */
  .kpi-card {
    background: #111827; border: 1px solid #1e293b; border-radius: 12px;
    padding: 1.25rem 1.5rem; position: relative; overflow: hidden;
  }
  .kpi-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 3px; border-radius: 12px 12px 0 0;
  }
  .kpi-accent-cyan::before   { background: #00d4ff; }
  .kpi-accent-green::before  { background: #00e676; }
  .kpi-accent-purple::before { background: #7c3aed; }
  .kpi-accent-orange::before { background: #f59e42; }
  .kpi-label { font-size: 0.78rem; color: #94a3b8; font-weight: 500; margin: 0 0 0.35rem 0; text-transform: uppercase; letter-spacing: 0.04em; }
  .kpi-value { font-family: 'DM Mono', monospace; font-size: 1.75rem; font-weight: 500; color: #f1f5f9; margin: 0; letter-spacing: -0.02em; }
  .kpi-sub   { font-size: 0.75rem; color: #64748b; margin: 0.25rem 0 0 0; }

  /* ── Section headers ── */
  .section-header {
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem; font-weight: 600; color: #f1f5f9;
    margin: 0.5rem 0 0.5rem 0; padding: 0;
  }

  /* ── Divider ── */
  .section-divider { border: none; border-top: 1px solid #1e293b; margin: 1.5rem 0 1rem 0; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
  [data-testid="stSidebar"] .sidebar-logo {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem; font-weight: 700; color: #00d4ff;
    padding: 0.5rem 0 0.75rem; border-bottom: 1px solid #1e293b; margin-bottom: 0.75rem;
  }
  .search-result {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.45rem 0.6rem; margin: 0.2rem 0; border-radius: 8px;
    border: 1px solid #1e293b; background: #111827; transition: background 0.1s;
  }
  .search-result:hover { background: #1e293b; }
  .search-result-info { flex: 1; min-width: 0; }
  .search-result-name { font-size: 0.8rem; font-weight: 600; color: #f1f5f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin: 0; }
  .search-result-meta { font-size: 0.65rem; color: #64748b; margin: 0; }
  .selected-app {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.4rem 0.6rem; margin: 0.2rem 0; border-radius: 8px;
    border: 1px solid #1e293b; background: #0a0e1a;
  }
  .selected-app-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .selected-app-name { font-size: 0.8rem; font-weight: 500; color: #f1f5f9; flex: 1; margin: 0; }
  .selected-app-market { font-size: 0.65rem; color: #64748b; margin: 0; }

  /* ── Misc ── */
  [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid #1e293b; }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.8rem; font-weight: 500; padding: 0.5rem 1rem;
    color: #64748b; border-bottom: 2px solid transparent;
  }
  [data-testid="stTabs"] [aria-selected="true"] {
    color: #00d4ff; border-bottom-color: #00d4ff; font-weight: 600;
  }
</style>
""", unsafe_allow_html=True)


# ─── ヘッダー ───
st.markdown("""
<div class="dash-header">
  <div>
    <p class="dash-title">App <span>Intelligence</span> Dashboard</p>
    <p class="dash-subtitle">data.ai API によるアプリ統計分析</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ─── サイドバー ───
st.sidebar.markdown('<p class="sidebar-logo">App Intelligence</p>', unsafe_allow_html=True)

db_data = load_apps_db()
apps_db = db_data["apps"]
groups = db_data.get("groups", [])

if "selected_apps" not in st.session_state:
    st.session_state.selected_apps = []

# --- グループ ---
if groups:
    st.sidebar.caption("GROUPS")
    group_names = ["-- Select Group --"] + [g["name"] for g in groups]
    selected_group = st.sidebar.selectbox(
        "Group", group_names, label_visibility="collapsed", key="group_select",
    )
    if selected_group != "-- Select Group --":
        group = next((g for g in groups if g["name"] == selected_group), None)
        if group:
            # グループ選択でアプリを即座に反映
            if st.session_state.get("_last_group") != selected_group:
                st.session_state.selected_apps = [dict(a) for a in group["apps"]]
                st.session_state._last_group = selected_group
                st.rerun()

            col_upd, col_del = st.sidebar.columns(2)
            with col_upd:
                if st.button("Update", key="group_update", use_container_width=True):
                    if st.session_state.selected_apps:
                        group["apps"] = [dict(a) for a in st.session_state.selected_apps]
                        save_groups(groups)
                        st.sidebar.success("Updated!")
                        st.rerun()
            with col_del:
                if st.button("Delete", key="group_delete", use_container_width=True):
                    groups = [g for g in groups if g["name"] != selected_group]
                    save_groups(groups)
                    st.session_state._last_group = None
                    st.sidebar.success("Deleted!")
                    st.rerun()
    else:
        st.session_state._last_group = None

# グループ保存
if st.session_state.selected_apps:
    show_save = st.sidebar.checkbox("Save current as group", value=False, key="show_save_group")
    if show_save:
        new_group_name = st.sidebar.text_input("Group name", key="new_group_name")
        if st.sidebar.button("Save Group", key="save_group"):
            if new_group_name:
                existing_names = {g["name"] for g in groups}
                if new_group_name in existing_names:
                    st.sidebar.error("This group name already exists.")
                else:
                    new_group = {
                        "id": str(uuid.uuid4()),
                        "name": new_group_name,
                        "apps": [dict(a) for a in st.session_state.selected_apps],
                    }
                    groups.append(new_group)
                    save_groups(groups)
                    st.sidebar.success(f"Saved: {new_group_name}")
                    st.rerun()
            else:
                st.sidebar.warning("Enter a group name.")

if groups or st.session_state.selected_apps:
    st.sidebar.markdown("---")

# --- 選択済みアプリ ---
if st.session_state.selected_apps:
    st.sidebar.caption("SELECTED APPS")
    for i, app in enumerate(st.session_state.selected_apps):
        color = COLORS[i % len(COLORS)]
        col_app, col_rm = st.sidebar.columns([5, 1])
        with col_app:
            st.markdown(
                f'<div class="selected-app">'
                f'<span class="selected-app-dot" style="background:{color}"></span>'
                f'<span class="selected-app-name">{app["label"]}</span>'
                f'<span class="selected-app-market">{app["market"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_rm:
            if st.button("✕", key=f"rm_{i}", help="Remove this app"):
                st.session_state.selected_apps.pop(i)
                st.rerun()
    # 一括クリアボタン
    if st.sidebar.button("Clear all", key="clear_all"):
        st.session_state.selected_apps = []
        st.rerun()
    st.sidebar.markdown("---")

# --- アプリ検索 ---
st.sidebar.caption("SEARCH APPS")
if apps_db:
    search_market = st.sidebar.radio(
        "Market", ["All", "iOS", "Android"], horizontal=True, label_visibility="collapsed",
    )
    search_query = st.sidebar.text_input(
        "検索", placeholder="App name, ID, or publisher...", label_visibility="collapsed"
    )

    if search_query and len(search_query) >= 2:
        from difflib import SequenceMatcher

        q = search_query.lower()

        # マーケットフィルタ
        market_filter = {"iOS": "ios", "Android": "google-play"}.get(search_market)
        pool = apps_db if not market_filter else [a for a in apps_db if a.get("market") == market_filter]

        # 完全一致 (部分文字列マッチ)
        exact = [
            a for a in pool
            if q in (a.get("name") or "").lower()
            or q in (a.get("app_id") or "").lower()
            or q in (a.get("publisher") or "").lower()
        ]

        # あいまい検索 (完全一致が少ない場合にフォールバック)
        if len(exact) < 5:
            scored = []
            for a in pool:
                name = (a.get("name") or "").lower()
                ratio = SequenceMatcher(None, q, name).ratio()
                # 単語の先頭一致にボーナス
                words = name.split()
                if any(w.startswith(q) for w in words):
                    ratio += 0.3
                if ratio >= 0.35:
                    scored.append((ratio, a))
            scored.sort(key=lambda x: -x[0])
            fuzzy = [a for _, a in scored]
        else:
            fuzzy = []

        # マージ (完全一致優先、重複除去)
        seen = set()
        filtered = []
        for a in exact + fuzzy:
            key = (a["app_id"], a.get("market", ""))
            if key not in seen:
                seen.add(key)
                filtered.append(a)
            if len(filtered) >= 20:
                break

        if filtered:
            for a in filtered:
                name = a.get("name") or a["app_id"]
                pub = a.get("publisher") or ""
                market_icon = "🍎" if a.get("market") == "ios" else "🤖"
                display = f"{market_icon} {name}"
                btn_key = f"add_{a['app_id']}_{a['market']}"
                if st.sidebar.button(f"＋  {display}", key=btn_key, use_container_width=True):
                    entry = {"app_id": a["app_id"], "market": a["market"], "label": name}
                    if entry not in st.session_state.selected_apps:
                        st.session_state.selected_apps.append(entry)
                    st.rerun()
        else:
            st.sidebar.caption("No results found.")
    elif search_query:
        st.sidebar.caption("Type at least 2 characters.")
else:
    st.sidebar.caption("App DB is empty. Run `python3 sync_apps.py`.")

# --- 手動追加 ---
show_manual = st.sidebar.checkbox("Add app by ID", value=False)
if show_manual:
    manual_id = st.sidebar.text_input("App ID", placeholder="123456789", key="manual_id")
    manual_market = st.sidebar.selectbox("Market", ["ios", "google-play"], key="manual_market")
    manual_label = st.sidebar.text_input("Display name", placeholder="e.g. MyApp iOS", key="manual_label")
    if st.sidebar.button("Add", key="manual_add"):
        if manual_id:
            label = manual_label or f"{manual_id} ({manual_market})"
            entry = {"app_id": manual_id, "market": manual_market, "label": label}
            if entry not in st.session_state.selected_apps:
                st.session_state.selected_apps.append(entry)
            st.rerun()

# --- 同カテゴリ レコメンド ---
if st.session_state.selected_apps and apps_db:
    selected_ids = {a["app_id"] for a in st.session_state.selected_apps}
    # 選択中アプリのカテゴリを収集
    selected_categories = set()
    for sel in st.session_state.selected_apps:
        for a in apps_db:
            if a["app_id"] == sel["app_id"] and a.get("category"):
                selected_categories.add(a["category"])
    if selected_categories:
        # 同カテゴリで未選択のアプリを抽出
        recs = [
            a for a in apps_db
            if a.get("category") in selected_categories
            and a["app_id"] not in selected_ids
            and a.get("name")
        ][:10]
        if recs:
            st.sidebar.markdown("---")
            cats_label = ", ".join(sorted(selected_categories))
            st.sidebar.caption(f"RECOMMENDED ({cats_label})")
            for a in recs:
                name = a.get("name") or a["app_id"]
                btn_key = f"rec_{a['app_id']}_{a['market']}"
                if st.sidebar.button(f"＋  {name}", key=btn_key, use_container_width=True):
                    entry = {"app_id": a["app_id"], "market": a["market"], "label": name}
                    if entry not in st.session_state.selected_apps:
                        st.session_state.selected_apps.append(entry)
                    st.rerun()

st.sidebar.markdown("---")

# --- 期間・国 ---
st.sidebar.caption("FILTERS")
today = datetime.now().date()
start_date = st.sidebar.date_input("Start date", value=today - timedelta(days=30))
end_date = st.sidebar.date_input("End date", value=today - timedelta(days=1))
country = st.sidebar.text_input("Country code", value="JP")

st.sidebar.markdown("")
fetch_clicked = st.sidebar.button("Fetch Data", type="primary", use_container_width=True)


# ─── ステータスバッジ ───
def render_badges():
    """ヘッダー下にステータスバッジを描画する。"""
    badges = ""

    # 最終更新
    updated_at = st.session_state.get("last_updated")
    if updated_at:
        badges += (
            f'<span class="badge badge-green">'
            f'<span class="badge-dot badge-dot-green"></span>'
            f'Updated {updated_at}</span>'
        )
    else:
        badges += (
            '<span class="badge badge-outline">'
            '<span class="badge-dot badge-dot-amber"></span>'
            'Not fetched yet</span>'
        )

    # データソース
    badges += '<span class="badge badge-blue">data.ai API v1.3</span>'

    # 国
    c = st.session_state.get("last_country", country)
    badges += f'<span class="badge badge-outline">{c}</span>'

    # 期間
    s = st.session_state.get("last_start", "")
    e = st.session_state.get("last_end", "")
    if s and e:
        badges += f'<span class="badge badge-outline">{s} → {e}</span>'

    # DB件数
    badges += f'<span class="badge badge-outline">DB: {len(apps_db):,} apps</span>'

    st.markdown(f'<div class="badge-row">{badges}</div>', unsafe_allow_html=True)


render_badges()

# ─── 選択中アプリタグ ───
if st.session_state.selected_apps:
    tags_html = ""
    for i, app in enumerate(st.session_state.selected_apps):
        c = COLORS[i % len(COLORS)]
        bg = COLORS_LIGHT[i % len(COLORS_LIGHT)]
        tags_html += (
            f'<span class="app-tag" style="background:{bg};color:{c};border-color:{c}22">'
            f'<span class="app-tag-dot" style="background:{c}"></span>'
            f'{app["label"]}</span>'
        )
    st.markdown(f'<div class="app-tags">{tags_html}</div>', unsafe_allow_html=True)


# ─── メインエリア ───
if not st.session_state.selected_apps:
    st.info("Search and select apps from the sidebar to get started.")
    st.stop()

if not fetch_clicked and "dl_df" not in st.session_state:
    st.info("Press **Fetch Data** in the sidebar to load metrics.")
    st.stop()

if fetch_clicked:
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    dl_frames = []
    dau_frames = []
    errors = []

    progress = st.progress(0)
    total = len(st.session_state.selected_apps)

    for i, app in enumerate(st.session_state.selected_apps):
        progress.progress((i + 1) / total, text=f"Fetching: {app['label']}")
        try:
            dl_data = fetch_downloads(app["app_id"], app["market"], country, start_str, end_str)
            dl_frames.append(parse_downloads(dl_data, app["label"]))
        except requests.exceptions.HTTPError as e:
            errors.append(f"[{app['label']}] Downloads: {friendly_error(e)}")
        try:
            dau_data = fetch_active_users(app["app_id"], app["market"], country, start_str, end_str)
            dau_frames.append(parse_active_users(dau_data, app["label"]))
        except requests.exceptions.HTTPError as e:
            errors.append(f"[{app['label']}] DAU: {friendly_error(e)}")

    progress.empty()

    for err in errors:
        st.error(err)

    st.session_state.dl_df = pd.concat(dl_frames, ignore_index=True) if dl_frames else pd.DataFrame()
    st.session_state.dau_df = pd.concat(dau_frames, ignore_index=True) if dau_frames else pd.DataFrame()
    st.session_state.last_updated = datetime.now().strftime("%H:%M:%S")
    st.session_state.last_country = country
    st.session_state.last_start = start_str
    st.session_state.last_end = end_str
    st.rerun()

dl_df = st.session_state.get("dl_df", pd.DataFrame())
dau_df = st.session_state.get("dau_df", pd.DataFrame())

# ─── KPI カード ───
if not dl_df.empty or not dau_df.empty:
    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        total_dl = int(dl_df["downloads"].sum()) if not dl_df.empty else 0
        st.markdown(
            f'<div class="kpi-card kpi-accent-cyan">'
            f'<p class="kpi-label">Total Downloads</p>'
            f'<p class="kpi-value">{format_number(total_dl)}</p>'
            f'<p class="kpi-sub">Period total</p></div>',
            unsafe_allow_html=True,
        )

    with kpi_cols[1]:
        avg_dl = int(dl_df.groupby("date")["downloads"].sum().mean()) if not dl_df.empty else 0
        st.markdown(
            f'<div class="kpi-card kpi-accent-green">'
            f'<p class="kpi-label">Avg. Daily Downloads</p>'
            f'<p class="kpi-value">{format_number(avg_dl)}</p>'
            f'<p class="kpi-sub">Per day</p></div>',
            unsafe_allow_html=True,
        )

    with kpi_cols[2]:
        avg_dau = int(dau_df.groupby("date")["dau"].sum().mean()) if not dau_df.empty else 0
        st.markdown(
            f'<div class="kpi-card kpi-accent-purple">'
            f'<p class="kpi-label">Avg. DAU</p>'
            f'<p class="kpi-value">{format_number(avg_dau)}</p>'
            f'<p class="kpi-sub">Per day</p></div>',
            unsafe_allow_html=True,
        )

    with kpi_cols[3]:
        peak_dau = int(dau_df.groupby("date")["dau"].sum().max()) if not dau_df.empty else 0
        st.markdown(
            f'<div class="kpi-card kpi-accent-orange">'
            f'<p class="kpi-label">Peak DAU</p>'
            f'<p class="kpi-value">{format_number(peak_dau)}</p>'
            f'<p class="kpi-sub">Period max</p></div>',
            unsafe_allow_html=True,
        )

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ─── グラフ ───
GRANULARITY_OPTIONS = {"Daily": None, "Weekly": "W-MON", "Monthly": "MS"}

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    if not dl_df.empty:
        st.markdown('<p class="section-header">Downloads</p>', unsafe_allow_html=True)
        tab_d, tab_w, tab_m = st.tabs(["Daily", "Weekly", "Monthly"])
        for tab, (label, freq) in zip([tab_d, tab_w, tab_m], GRANULARITY_OPTIONS.items()):
            with tab:
                plot_df = dl_df if freq is None else resample_df(dl_df, "downloads", freq)
                fig = go.Figure()
                for i, app_name in enumerate(plot_df["app"].unique()):
                    app_data = plot_df[plot_df["app"] == app_name]
                    fig.add_trace(go.Scatter(
                        x=app_data["date"], y=app_data["downloads"],
                        name=app_name, mode="lines",
                        line=dict(color=COLORS[i % len(COLORS)], width=2.5),
                        fill="tozeroy",
                        fillcolor=f"rgba({int(COLORS[i % len(COLORS)][1:3],16)},{int(COLORS[i % len(COLORS)][3:5],16)},{int(COLORS[i % len(COLORS)][5:7],16)},0.15)",
                    ))
                apply_chart_style(fig)
                st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    if not dau_df.empty:
        st.markdown('<p class="section-header">Active Users (DAU)</p>', unsafe_allow_html=True)
        tab_d2, tab_w2, tab_m2 = st.tabs(["Daily", "Weekly", "Monthly"])
        for tab, (label, freq) in zip([tab_d2, tab_w2, tab_m2], GRANULARITY_OPTIONS.items()):
            with tab:
                agg_method = "sum" if freq is None else "mean"
                plot_df = dau_df if freq is None else resample_df(dau_df, "dau", freq, agg=agg_method)
                if freq is not None:
                    plot_df["dau"] = plot_df["dau"].round(0).astype(int)
                fig = go.Figure()
                for i, app_name in enumerate(plot_df["app"].unique()):
                    app_data = plot_df[plot_df["app"] == app_name]
                    fig.add_trace(go.Scatter(
                        x=app_data["date"], y=app_data["dau"],
                        name=app_name, mode="lines",
                        line=dict(color=COLORS[i % len(COLORS)], width=2.5),
                        fill="tozeroy",
                        fillcolor=f"rgba({int(COLORS[i % len(COLORS)][1:3],16)},{int(COLORS[i % len(COLORS)][3:5],16)},{int(COLORS[i % len(COLORS)][5:7],16)},0.15)",
                    ))
                apply_chart_style(fig)
                st.plotly_chart(fig, use_container_width=True)

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ─── データテーブル ───
if not dl_df.empty or not dau_df.empty:
    st.markdown('<p class="section-header">Raw Data</p>', unsafe_allow_html=True)
    tab_dl, tab_dau = st.tabs(["Downloads", "DAU"])

    with tab_dl:
        if not dl_df.empty:
            st.dataframe(dl_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Export CSV", dl_df.to_csv(index=False).encode("utf-8"),
                "downloads.csv", "text/csv",
            )
        else:
            st.caption("No data")

    with tab_dau:
        if not dau_df.empty:
            st.dataframe(dau_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Export CSV", dau_df.to_csv(index=False).encode("utf-8"),
                "dau.csv", "text/csv",
            )
        else:
            st.caption("No data")
