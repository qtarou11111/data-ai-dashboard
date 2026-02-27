"""Data.ai API でアプリのダウンロード数・アクティブユーザー数を取得するスクリプト

事前準備:
  pip3 install requests python-dotenv

使い方:
  # .env ファイルに API キーを設定
  echo "DATAAI_API_KEY=your_api_key_here" > .env

  # ダウンロード数を取得（iOS）
  python3 dataai_app_stats.py --app-id 123456789 --market ios --metric downloads

  # アクティブユーザー数を取得（MAU）
  python3 dataai_app_stats.py --app-id 123456789 --market ios --metric mau

  # DAU を取得
  python3 dataai_app_stats.py --app-id 123456789 --market ios --metric dau

  # Google Play アプリ
  python3 dataai_app_stats.py --app-id com.example.app --market google-play --metric downloads

  # 期間・国を指定
  python3 dataai_app_stats.py --app-id 123456789 --market ios --metric downloads \\
      --start 2025-01-01 --end 2025-01-31 --country JP
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.appannie.com/v1.3"


def get_headers():
    api_key = os.getenv("DATAAI_API_KEY")
    if not api_key:
        print("エラー: DATAAI_API_KEY が設定されていません。")
        print(".env ファイルに DATAAI_API_KEY=your_key を記載してください。")
        sys.exit(1)
    return {"Authorization": f"bearer {api_key}"}


def get_downloads(app_id, market, country, start_date, end_date, granularity):
    """ダウンロード数の推定値を取得する。"""
    url = f"{BASE_URL}/intelligence/apps/{market}/app/{app_id}/history"
    params = {
        "countries": country,
        "feeds": "downloads",
        "granularity": granularity,
        "start_date": start_date,
        "end_date": end_date,
    }
    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


def get_active_users(app_id, market, country, start_date, end_date, granularity):
    """アクティブユーザー数（DAU/MAU）を取得する。"""
    url = f"{BASE_URL}/intelligence/apps/{market}/app/{app_id}/usage-history"
    params = {
        "countries": country,
        "granularity": granularity,
        "start_date": start_date,
        "end_date": end_date,
    }
    resp = requests.get(url, headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


def format_number(n):
    """数値を読みやすい形式にフォーマットする。"""
    if n is None:
        return "N/A"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def print_downloads(data):
    """ダウンロード数の結果を表示する。"""
    product_name = data.get("product_name", "Unknown")
    market = data.get("market", "")
    print(f"\nアプリ: {product_name} ({market})")
    print("=" * 50)
    print(f"{'日付':<14} {'国':<6} {'ダウンロード数':>14}")
    print("-" * 50)

    items = data.get("list", [])
    if not items:
        print("データが見つかりませんでした。")
        return

    total = 0
    for item in items:
        date = item.get("date", "")
        country = item.get("country", "")
        estimate = item.get("estimate", 0)
        total += estimate or 0
        print(f"{date:<14} {country:<6} {format_number(estimate):>14}")

    print("-" * 50)
    print(f"{'合計':<21} {format_number(total):>14}")


def print_active_users(data, metric_label):
    """アクティブユーザー数の結果を表示する。"""
    product_name = data.get("product_name", data.get("product_id", "Unknown"))
    market = data.get("market", "")
    print(f"\nアプリ: {product_name} ({market})")
    print(f"指標: {metric_label}")
    print("=" * 50)
    print(f"{'日付':<14} {'国':<6} {'アクティブユーザー':>18}")
    print("-" * 50)

    items = data.get("list", [])
    if not items:
        print("データが見つかりませんでした。")
        return

    for item in items:
        date = item.get("date", "")
        country = item.get("country", "")
        users = item.get("active_users", 0)
        print(f"{date:<14} {country:<6} {format_number(users):>18}")


def main():
    parser = argparse.ArgumentParser(description="Data.ai API でアプリ統計を取得")
    parser.add_argument("--app-id", required=True, help="アプリID (iOS: 数値, Google Play: パッケージ名)")
    parser.add_argument("--market", required=True, choices=["ios", "google-play"], help="マーケット")
    parser.add_argument("--metric", required=True, choices=["downloads", "dau", "mau"], help="取得する指標")
    parser.add_argument("--country", default="JP", help="国コード (デフォルト: JP)")
    parser.add_argument("--start", default=None, help="開始日 (YYYY-MM-DD, デフォルト: 30日前)")
    parser.add_argument("--end", default=None, help="終了日 (YYYY-MM-DD, デフォルト: 昨日)")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力")

    args = parser.parse_args()

    today = datetime.now().date()
    end_date = args.end or (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = args.start or (today - timedelta(days=30)).strftime("%Y-%m-%d")

    print(f"期間: {start_date} 〜 {end_date}")
    print(f"国: {args.country}")

    try:
        if args.metric == "downloads":
            data = get_downloads(args.app_id, args.market, args.country, start_date, end_date, "daily")
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print_downloads(data)

        elif args.metric == "dau":
            data = get_active_users(args.app_id, args.market, args.country, start_date, end_date, "daily")
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print_active_users(data, "DAU (日次アクティブユーザー)")

        elif args.metric == "mau":
            data = get_active_users(args.app_id, args.market, args.country, start_date, end_date, "monthly")
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print_active_users(data, "MAU (月次アクティブユーザー)")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 401:
            print("エラー: 認証に失敗しました。APIキーを確認してください。")
        elif status == 403:
            print("エラー: アクセス権限がありません。サブスクリプションプランを確認してください。")
        elif status == 404:
            print(f"エラー: アプリID '{args.app_id}' が見つかりません。")
        else:
            print(f"エラー: HTTP {status}")
        print(f"詳細: {e.response.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
