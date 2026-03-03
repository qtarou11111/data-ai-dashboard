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
COLORS = ["#6366f1", "#f43f5e", "#f59e42", "#10b981", "#8b5cf6", "#06b6d4"]


# ─── セッション初期化（一度だけ） ───
def init_state():
    defaults = {
        "selected_apps": [],
        "dl_df": None,
        "dau_df": None,
        "last_updated": None,
        "last_country": "JP",
        "last_start": "",
        "last_end": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─── アプリDB ───
@st.cache_data(ttl=600)
def load_apps_db():
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


def save_groups(groups):
    data = load_apps_db()
    data["groups"] = groups
    save_apps_db(data)


# ─── ユーティリティ: アプリ一意キー ───
def app_key(app):
    return f"{app['app_id']}|{app['market']}"


def apps_to_labels(apps, app_options_map):
    """selected_apps → multiselect のラベルリスト"""
    labels = []
    for a in apps:
        k = app_key(a)
        if k in app_options_map:
            labels.append(app_options_map[k]["label_key"])
    return labels


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
        "countries": country, "feeds": "downloads",
        "granularity": "daily", "start_date": start_date, "end_date": end_date,
    }
    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_active_users(app_id, market, country, start_date, end_date, _v=2):
    # Usage API は "google-play" ではなく "all-android" を要求する
    usage_market = "all-android" if market == "google-play" else market
    url = f"{BASE_URL}/intelligence/apps/{usage_market}/app/{app_id}/usage-history"
    params = {
        "countries": country, "granularity": "daily",
        "start_date": start_date, "end_date": end_date,
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
    rows = []
    for item in data.get("list", []):
        date = item.get("date", "")
        users = _safe_int(item.get("active_users"))
        device = item.get("device", "unknown")
        rows.append({"date": date, "dau": users, "app": label, "device": device})
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
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="'Inter', sans-serif", size=12, color="#374151"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11, color="#6b7280"), bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=16, r=16, t=32, b=16),
        xaxis=dict(showgrid=False, linecolor="#e5e7eb", tickfont=dict(size=10, color="#9ca3af")),
        yaxis=dict(gridcolor="#f3f4f6", linecolor="#e5e7eb", tickfont=dict(size=10, color="#9ca3af"), separatethousands=True),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", bordercolor="#e5e7eb", font_size=12, font_color="#1f2937"),
    )
    return fig


# ─── ページ設定 ───
st.set_page_config(page_title="data.ai Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

  /* ── Global Light Theme ── */
  .block-container { padding-top: 1.5rem; max-width: 1400px; }
  html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #1f2937;
  }
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #f8f9fb !important; color: #1f2937;
  }
  header[data-testid="stHeader"] { background: #f8f9fb !important; }

  /* Sidebar */
  [data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e5e7eb; }
  [data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }

  /* Buttons */
  button[kind="primary"], .stButton button[kind="primary"] {
    background: #6366f1 !important; color: white !important;
    border: none !important; font-weight: 600 !important; border-radius: 8px !important;
  }
  button[kind="primary"]:hover { background: #4f46e5 !important; }
  .stButton button:not([kind="primary"]) {
    background: white !important; color: #374151 !important;
    border: 1px solid #d1d5db !important; border-radius: 8px !important;
  }
  .stButton button:not([kind="primary"]):hover { background: #f3f4f6 !important; }

  /* Tabs */
  [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #e5e7eb; }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.82rem; font-weight: 500; padding: 0.5rem 1.2rem; color: #9ca3af;
  }
  [data-testid="stTabs"] [aria-selected="true"] {
    color: #6366f1 !important; border-bottom-color: #6366f1 !important; font-weight: 600;
  }

  /* Progress */
  .stProgress > div > div > div { background: #6366f1 !important; }

  /* ── Header ── */
  .dash-header {
    display: flex; align-items: center; justify-content: space-between;
    margin: 0 0 1.2rem 0; padding-bottom: 1rem; border-bottom: 1px solid #e5e7eb;
  }
  .dash-title {
    font-family: 'Syne', sans-serif; font-size: 1.5rem; font-weight: 800;
    color: #111827 !important; letter-spacing: -0.02em; margin: 0;
  }
  .dash-title span { color: #6366f1; }
  .dash-subtitle { font-size: 0.8rem; color: #6b7280 !important; margin: 0.15rem 0 0 0; }

  /* ── Badges ── */
  .badge-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem; align-items: center; }
  .badge {
    display: inline-flex; align-items: center; gap: 0.3rem;
    padding: 0.25rem 0.7rem; border-radius: 9999px; font-size: 0.72rem; font-weight: 500;
  }
  .badge-outline { border: 1px solid #e5e7eb; color: #6b7280 !important; background: white; }
  .badge-green { background: #ecfdf5; color: #059669 !important; border: 1px solid #a7f3d0; }
  .badge-blue { background: #eef2ff; color: #6366f1 !important; border: 1px solid #c7d2fe; }
  .badge-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .badge-dot-green { background: #10b981; }
  .badge-dot-amber { background: #f59e0b; }

  /* ── App Tags ── */
  .app-tags { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem; }
  .app-tag {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.35rem 0.85rem; border-radius: 8px;
    font-size: 0.78rem; font-weight: 600; border: 1px solid;
  }
  .app-tag-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

  /* ── KPI Cards ── */
  .kpi-card {
    background: white; border: 1px solid #e5e7eb; border-radius: 14px;
    padding: 1.25rem 1.5rem; position: relative; overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .kpi-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 3px; border-radius: 14px 14px 0 0;
  }
  .kpi-accent-cyan::before { background: #6366f1; }
  .kpi-accent-green::before { background: #10b981; }
  .kpi-accent-purple::before { background: #8b5cf6; }
  .kpi-accent-orange::before { background: #f59e42; }
  .kpi-label { font-size: 0.78rem; color: #6b7280 !important; font-weight: 500; margin: 0 0 0.35rem 0; text-transform: uppercase; letter-spacing: 0.04em; }
  .kpi-value { font-family: 'DM Mono', monospace; font-size: 1.85rem; font-weight: 500; color: #111827 !important; margin: 0; }
  .kpi-sub { font-size: 0.75rem; color: #9ca3af !important; margin: 0.25rem 0 0 0; }

  /* ── Section ── */
  .section-header { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: #111827 !important; margin: 0.5rem 0; }
  .section-divider { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0 1rem 0; }

  /* ── Sidebar details ── */
  [data-testid="stSidebar"] .sidebar-logo {
    font-family: 'Syne', sans-serif; font-size: 1.15rem; font-weight: 700;
    color: #6366f1 !important; padding: 0.5rem 0 0.75rem;
    border-bottom: 1px solid #e5e7eb; margin-bottom: 0.75rem;
  }
  .selected-app {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.45rem 0.65rem; margin: 0.2rem 0; border-radius: 8px;
    border: 1px solid #e5e7eb; background: #f9fafb;
  }
  .selected-app-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .selected-app-name { font-size: 0.82rem; font-weight: 500; color: #1f2937 !important; flex: 1; margin: 0; }
  .selected-app-market { font-size: 0.68rem; color: #9ca3af !important; margin: 0; }

  .control-label {
    font-size: 0.72rem; color: #6b7280 !important; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 0.3rem 0;
  }

  /* ── Control Card ── */
  .control-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
</style>
""", unsafe_allow_html=True)


# ─── データ読み込み ───
db_data = load_apps_db()
apps_db = db_data["apps"]
groups = db_data.get("groups", [])

# アプリオプションマップを作成 (一度だけ)
# label_key = 表示用ラベル, app_key = 一意キー
app_options_by_label = {}   # label_key → app dict
app_options_by_key = {}     # "app_id|market" → {"label_key": ..., ...app}
for a in apps_db:
    name = a.get("name") or a["app_id"]
    market_short = "iOS" if a.get("market") == "ios" else "Android"
    label_key = f"{name} ({market_short})"
    app_options_by_label[label_key] = a
    app_options_by_key[app_key(a)] = {**a, "label_key": label_key}


# ─── ヘッダー ───
st.markdown("""
<div class="dash-header">
  <div>
    <p class="dash-title">App <span>Intelligence</span> Dashboard</p>
    <p class="dash-subtitle">data.ai API によるアプリ統計分析</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# メインエリア — コントロールパネル
# ═══════════════════════════════════════════════════════════════

st.markdown('<div class="control-card">', unsafe_allow_html=True)

# multiselect の初期値を selected_apps から計算
initial_labels = apps_to_labels(st.session_state.selected_apps, app_options_by_key)

# multiselect の値が変わったら selected_apps を更新する (callback)
def on_app_select_change():
    labels = st.session_state._ms_apps
    new_apps = []
    for lbl in labels:
        if lbl in app_options_by_label:
            a = app_options_by_label[lbl]
            new_apps.append({
                "app_id": a["app_id"],
                "market": a["market"],
                "label": a.get("name") or a["app_id"],
            })
    st.session_state.selected_apps = new_apps

# 初期値をセット (widget がまだ無い場合のみ)
if "_ms_apps" not in st.session_state:
    st.session_state._ms_apps = initial_labels

# rerun 前に予約された値があれば反映（ウィジェット生成前なので安全）
if "_ms_apps_pending" in st.session_state:
    st.session_state._ms_apps = st.session_state._ms_apps_pending
    del st.session_state._ms_apps_pending

# Row 1: アプリ選択 (2/3) + グループ選択+削除 (1/3)
row1_left, row1_right = st.columns([2, 1])

with row1_left:
    st.markdown('<p class="control-label">Apps — アプリを選択（複数可）</p>', unsafe_allow_html=True)
    st.multiselect(
        "Apps",
        options=sorted(app_options_by_label.keys()),
        key="_ms_apps",
        label_visibility="collapsed",
        on_change=on_app_select_change,
    )

with row1_right:
    st.markdown('<p class="control-label">Group</p>', unsafe_allow_html=True)
    group_names = ["--"] + [g["name"] for g in groups]
    grp_sel_col, grp_del_col = st.columns([3, 1])
    with grp_sel_col:
        sel_group = st.selectbox("Group", group_names, label_visibility="collapsed", key="_sel_group")
    with grp_del_col:
        st.markdown('<p class="control-label">&nbsp;</p>', unsafe_allow_html=True)
        del_grp_clicked = st.button("🗑️", key="_del_grp", use_container_width=True, disabled=(sel_group == "--"))

# Row 2: Country + Start + End + Fetch + グループ保存
today = datetime.now().date()
rc1, rc2, rc3, rc4, rc5 = st.columns([1, 1.5, 1.5, 1, 1.5])

with rc1:
    st.markdown('<p class="control-label">Country</p>', unsafe_allow_html=True)
    country = st.text_input("Country", value="JP", label_visibility="collapsed", key="_country")

with rc2:
    st.markdown('<p class="control-label">Start</p>', unsafe_allow_html=True)
    start_date = st.date_input("Start", value=today - timedelta(days=30), label_visibility="collapsed", key="_start")

with rc3:
    st.markdown('<p class="control-label">End</p>', unsafe_allow_html=True)
    end_date = st.date_input("End", value=today - timedelta(days=1), label_visibility="collapsed", key="_end")

with rc4:
    st.markdown('<p class="control-label">&nbsp;</p>', unsafe_allow_html=True)
    fetch_clicked = st.button("Fetch", type="primary", use_container_width=True, key="_fetch")

with rc5:
    st.markdown('<p class="control-label">Save Group</p>', unsafe_allow_html=True)
    save_cols = st.columns([3, 1])
    with save_cols[0]:
        new_group_name = st.text_input("Name", placeholder="New group name...", label_visibility="collapsed", key="_new_grp_name")
    with save_cols[1]:
        save_grp_clicked = st.button("Save", key="_save_grp", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)


# --- グループ読み込み処理 ---
if sel_group != "--":
    group = next((g for g in groups if g["name"] == sel_group), None)
    if group and st.session_state.get("_last_group") != sel_group:
        st.session_state.selected_apps = [dict(a) for a in group["apps"]]
        st.session_state._last_group = sel_group
        # multiselect の値も更新（ウィジェット生成後なので pending に予約）
        st.session_state._ms_apps_pending = apps_to_labels(st.session_state.selected_apps, app_options_by_key)
        st.rerun()
else:
    st.session_state._last_group = None

# --- グループ保存処理 ---
if save_grp_clicked:
    if not st.session_state.selected_apps:
        st.toast("アプリを選択してから保存してください。", icon="⚠️")
    elif not new_group_name:
        st.toast("グループ名を入力してください。", icon="⚠️")
    elif new_group_name in {g["name"] for g in groups}:
        st.toast("同じ名前のグループが既に存在します。", icon="⚠️")
    else:
        new_group = {
            "id": str(uuid.uuid4()),
            "name": new_group_name,
            "apps": [dict(a) for a in st.session_state.selected_apps],
        }
        groups.append(new_group)
        save_groups(groups)
        st.toast(f"グループ「{new_group_name}」を保存しました!", icon="✅")
        st.rerun()

# --- グループ削除処理 ---
if del_grp_clicked and sel_group != "--":
    groups = [g for g in groups if g["name"] != sel_group]
    save_groups(groups)
    st.session_state._last_group = None
    st.toast(f"削除しました。", icon="🗑️")
    st.rerun()


# ═══════════════════════════════════════════════════════════════
# サイドバー — 検索 + 手動追加 (補助的)
# ═══════════════════════════════════════════════════════════════

st.sidebar.markdown('<p class="sidebar-logo">App Search</p>', unsafe_allow_html=True)

# --- 選択済みアプリ表示 ---
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
            if st.button("✕", key=f"rm_{i}", help="Remove"):
                st.session_state.selected_apps.pop(i)
                st.session_state._ms_apps_pending = apps_to_labels(
                    st.session_state.selected_apps, app_options_by_key
                )
                st.rerun()
    if st.sidebar.button("Clear all", key="clear_all"):
        st.session_state.selected_apps = []
        st.session_state._ms_apps_pending = []
        st.rerun()
    st.sidebar.markdown("---")

# --- アプリ検索 ---
st.sidebar.caption("SEARCH & ADD APPS")
if apps_db:
    search_market = st.sidebar.radio(
        "Market", ["All", "iOS", "Android"], horizontal=True, label_visibility="collapsed",
        key="_search_market",
    )
    search_query = st.sidebar.text_input(
        "検索", placeholder="App name, ID, or publisher...", label_visibility="collapsed",
        key="_search_query",
    )

    if search_query and len(search_query) >= 2:
        from difflib import SequenceMatcher

        q = search_query.lower()
        market_filter = {"iOS": "ios", "Android": "google-play"}.get(search_market)
        pool = apps_db if not market_filter else [a for a in apps_db if a.get("market") == market_filter]

        exact = [
            a for a in pool
            if q in (a.get("name") or "").lower()
            or q in (a.get("app_id") or "").lower()
            or q in (a.get("publisher") or "").lower()
        ]

        if len(exact) < 5:
            scored = []
            for a in pool:
                name = (a.get("name") or "").lower()
                ratio = SequenceMatcher(None, q, name).ratio()
                if any(w.startswith(q) for w in name.split()):
                    ratio += 0.3
                if ratio >= 0.35:
                    scored.append((ratio, a))
            scored.sort(key=lambda x: -x[0])
            fuzzy = [a for _, a in scored]
        else:
            fuzzy = []

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
                market_icon = "🍎" if a.get("market") == "ios" else "🤖"
                btn_key = f"add_{a['app_id']}_{a['market']}"
                if st.sidebar.button(f"＋  {market_icon} {name}", key=btn_key, use_container_width=True):
                    entry = {"app_id": a["app_id"], "market": a["market"], "label": name}
                    if entry not in st.session_state.selected_apps:
                        st.session_state.selected_apps.append(entry)
                        # multiselect も同期
                        st.session_state._ms_apps_pending = apps_to_labels(
                            st.session_state.selected_apps, app_options_by_key
                        )
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
                st.session_state._ms_apps_pending = apps_to_labels(
                    st.session_state.selected_apps, app_options_by_key
                )
            st.rerun()

# --- 同カテゴリ レコメンド ---
if st.session_state.selected_apps and apps_db:
    selected_ids = {a["app_id"] for a in st.session_state.selected_apps}
    selected_categories = set()
    for sel in st.session_state.selected_apps:
        for a in apps_db:
            if a["app_id"] == sel["app_id"] and a.get("category"):
                selected_categories.add(a["category"])
    if selected_categories:
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
                        st.session_state._ms_apps_pending = apps_to_labels(
                            st.session_state.selected_apps, app_options_by_key
                        )
                    st.rerun()


# ═══════════════════════════════════════════════════════════════
# ステータスバッジ + メインコンテンツ
# ═══════════════════════════════════════════════════════════════

def render_badges():
    badges = ""
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
    badges += '<span class="badge badge-blue">data.ai API v1.3</span>'
    c = st.session_state.get("last_country", country)
    badges += f'<span class="badge badge-outline">{c}</span>'
    s = st.session_state.get("last_start", "")
    e = st.session_state.get("last_end", "")
    if s and e:
        badges += f'<span class="badge badge-outline">{s} → {e}</span>'
    badges += f'<span class="badge badge-outline">DB: {len(apps_db):,} apps</span>'
    n_selected = len(st.session_state.selected_apps)
    if n_selected:
        badges += f'<span class="badge badge-outline">{n_selected} apps selected</span>'
    st.markdown(f'<div class="badge-row">{badges}</div>', unsafe_allow_html=True)

render_badges()

# ─── 選択中アプリタグ ───
if st.session_state.selected_apps:
    tags_html = ""
    for i, app in enumerate(st.session_state.selected_apps):
        c = COLORS[i % len(COLORS)]
        tags_html += (
            f'<span class="app-tag" style="background:{c}11;color:{c};border-color:{c}33">'
            f'<span class="app-tag-dot" style="background:{c}"></span>'
            f'{app["label"]}</span>'
        )
    st.markdown(f'<div class="app-tags">{tags_html}</div>', unsafe_allow_html=True)


# ─── データ取得 ───
if not st.session_state.selected_apps:
    st.info("上部のセレクターまたはサイドバーからアプリを選択してください。")
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
        except Exception as e:
            errors.append(f"[{app['label']}] Downloads: {str(e)}")
        try:
            dau_data = fetch_active_users(app["app_id"], app["market"], country, start_str, end_str)
            dau_frames.append(parse_active_users(dau_data, app["label"]))
        except requests.exceptions.HTTPError as e:
            errors.append(f"[{app['label']}] DAU: {friendly_error(e)}")
        except Exception as e:
            errors.append(f"[{app['label']}] DAU: {str(e)}")

    progress.empty()

    st.session_state.dl_df = pd.concat(dl_frames, ignore_index=True) if dl_frames else pd.DataFrame()
    st.session_state.dau_df = pd.concat(dau_frames, ignore_index=True) if dau_frames else pd.DataFrame()
    st.session_state.last_updated = datetime.now().strftime("%H:%M:%S")
    st.session_state.last_country = country
    st.session_state.last_start = start_str
    st.session_state.last_end = end_str
    st.session_state.fetch_errors = errors
    st.rerun()

# ─── Fetch エラー表示 ───
for err in st.session_state.get("fetch_errors", []):
    st.error(err)

# ─── データがまだ無い場合 ───
dl_df = st.session_state.get("dl_df")
dau_df = st.session_state.get("dau_df")

if dl_df is None and dau_df is None:
    st.info("**Fetch** ボタンを押してデータを取得してください。")
    st.stop()

if dl_df is None:
    dl_df = pd.DataFrame()
if dau_df is None:
    dau_df = pd.DataFrame()

# ─── デバイスフィルタ ───
device_filter = st.radio(
    "Device", ["All", "iOS", "Android"], horizontal=True, key="_device_filter",
)
if dau_df.empty:
    dau_filtered = dau_df
elif device_filter == "All":
    dau_filtered = dau_df.groupby(["date", "app"], as_index=False)["dau"].sum()
elif device_filter == "iOS":
    dau_filtered = dau_df[dau_df["device"].str.startswith("i", na=False)].copy()
else:
    # iOS 以外をすべて Android として扱う
    dau_filtered = dau_df[~dau_df["device"].str.startswith("i", na=True)].copy()

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
        avg_dau = int(dau_filtered.groupby("date")["dau"].sum().mean()) if not dau_filtered.empty else 0
        device_label = f" ({device_filter})" if device_filter != "All" else ""
        st.markdown(
            f'<div class="kpi-card kpi-accent-purple">'
            f'<p class="kpi-label">Avg. DAU{device_label}</p>'
            f'<p class="kpi-value">{format_number(avg_dau)}</p>'
            f'<p class="kpi-sub">Per day</p></div>',
            unsafe_allow_html=True,
        )

    with kpi_cols[3]:
        peak_dau = int(dau_filtered.groupby("date")["dau"].sum().max()) if not dau_filtered.empty else 0
        st.markdown(
            f'<div class="kpi-card kpi-accent-orange">'
            f'<p class="kpi-label">Peak DAU{device_label}</p>'
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
                    c = COLORS[i % len(COLORS)]
                    fig.add_trace(go.Scatter(
                        x=app_data["date"], y=app_data["downloads"],
                        name=app_name, mode="lines",
                        line=dict(color=c, width=2.5),
                        fill="tozeroy",
                        fillcolor=f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.08)",
                    ))
                apply_chart_style(fig)
                st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    if not dau_filtered.empty:
        st.markdown('<p class="section-header">Active Users (DAU)</p>', unsafe_allow_html=True)
        tab_d2, tab_w2, tab_m2 = st.tabs(["Daily", "Weekly", "Monthly"])
        for tab, (label, freq) in zip([tab_d2, tab_w2, tab_m2], GRANULARITY_OPTIONS.items()):
            with tab:
                agg_method = "sum" if freq is None else "mean"
                plot_df = dau_filtered if freq is None else resample_df(dau_filtered, "dau", freq, agg=agg_method)
                if freq is not None:
                    plot_df["dau"] = plot_df["dau"].round(0).astype(int)
                fig = go.Figure()
                for i, app_name in enumerate(plot_df["app"].unique()):
                    app_data = plot_df[plot_df["app"] == app_name]
                    c = COLORS[i % len(COLORS)]
                    fig.add_trace(go.Scatter(
                        x=app_data["date"], y=app_data["dau"],
                        name=app_name, mode="lines",
                        line=dict(color=c, width=2.5),
                        fill="tozeroy",
                        fillcolor=f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.08)",
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
            st.download_button("Export CSV", dl_df.to_csv(index=False).encode("utf-8"), "downloads.csv", "text/csv")
        else:
            st.caption("No data")

    with tab_dau:
        if not dau_df.empty:
            if device_filter == "All":
                dau_display = dau_df
            elif device_filter == "iOS":
                dau_display = dau_df[dau_df["device"].str.startswith("i", na=False)]
            else:
                dau_display = dau_df[~dau_df["device"].str.startswith("i", na=True)]
            st.dataframe(dau_display, use_container_width=True, hide_index=True)
            st.download_button("Export CSV", dau_display.to_csv(index=False).encode("utf-8"), "dau.csv", "text/csv")
        else:
            st.caption("No data")
