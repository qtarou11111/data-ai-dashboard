"""data.ai ランキング API からアプリ一覧を取得し apps_db.json を更新するスクリプト

使い方:
  python3 sync_apps.py          # 手動実行

自動実行（1日1回）:
  crontab -e で以下を追加:
  0 6 * * * cd /Users/ryutaronakano/作業/data-ai-lab && python3 sync_apps.py >> sync_apps.log 2>&1
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.appannie.com/v1.2"
APPS_DB_PATH = Path(__file__).parent / "apps_db.json"


def get_headers():
    api_key = os.getenv("DATAAI_API_KEY")
    if not api_key:
        raise RuntimeError("DATAAI_API_KEY が設定されていません。")
    return {"Authorization": f"bearer {api_key}"}


def fetch_ranking(market, device, feed):
    """ランキング API からアプリ一覧を取得する。"""
    url = f"{BASE_URL}/intelligence/apps/{market}/ranking"
    params = {
        "countries": "JP",
        "categories": "Overall",
        "feeds": feed,
        "granularity": "daily",
    }
    if device:
        params["device"] = device
    resp = requests.get(url, headers=get_headers(), params=params)
    if resp.status_code != 200:
        print(f"  SKIP {market}/{feed}/{device}: HTTP {resp.status_code}")
        return []
    return resp.json().get("list", [])


def sync():
    # 既存DBを読み込み
    existing = {}
    if APPS_DB_PATH.exists():
        for app in json.loads(APPS_DB_PATH.read_text(encoding="utf-8")):
            key = (str(app["app_id"]), app["market"])
            existing[key] = app

    # ランキングからアプリを収集
    sources = [
        ("ios", "iphone", "free"),
        ("ios", "iphone", "paid"),
        ("ios", "iphone", "grossing"),
        ("ios", "ipad", "free"),
        ("google-play", None, "free"),
        ("google-play", None, "grossing"),
    ]

    new_count = 0
    for market, device, feed in sources:
        label = f"{market}/{feed}" + (f"/{device}" if device else "")
        print(f"取得中: {label} ...", end=" ", flush=True)
        items = fetch_ranking(market, device, feed)
        print(f"{len(items)} 件")
        for item in items:
            app_id = str(item.get("product_id", ""))
            if not app_id:
                continue
            key = (app_id, market)
            if key not in existing:
                existing[key] = {
                    "app_id": app_id,
                    "market": market,
                    "name": item.get("product_name", ""),
                    "publisher": item.get("publisher_name", ""),
                    "category": item.get("product_category") or item.get("category", ""),
                }
                new_count += 1

    # 保存
    apps_list = sorted(existing.values(), key=lambda a: (a.get("name") or ""))
    APPS_DB_PATH.write_text(
        json.dumps(apps_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n完了: 合計 {len(apps_list)} アプリ（新規 {new_count} 件）")
    print(f"保存先: {APPS_DB_PATH}")


if __name__ == "__main__":
    print(f"=== data.ai アプリDB同期 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    sync()
