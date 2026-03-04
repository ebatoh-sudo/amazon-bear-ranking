#!/usr/bin/env python3
"""
Amazon.co.jp 熊よけ・忌避用品 ベストセラーランキング Top10 を
PA-API (Product Advertising API) 経由で取得し
Google Chat Webhook に投稿するスクリプト
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests
from amazon_paapi import AmazonAPI

GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", "")
AMAZON_ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY", "")
AMAZON_SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY", "")
AMAZON_PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "")

# 熊よけ・忌避用品 のブラウズノードID
BROWSE_NODE_ID = "2201156051"

JST = timezone(timedelta(hours=9))


def fetch_ranking():
    """PA-API でベストセラーランキング情報を取得"""
    if not all([AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG]):
        print("[ERROR] Amazon API認証情報が未設定です。")
        sys.exit(1)

    amazon = AmazonAPI(
        AMAZON_ACCESS_KEY,
        AMAZON_SECRET_KEY,
        AMAZON_PARTNER_TAG,
        country="JP",
    )

    # BrowseNode のベストセラーを取得
    try:
        result = amazon.search_items(
            browse_node_id=BROWSE_NODE_ID,
            sort_by="BestSellers",
            item_count=10,
            resources=[
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "BrowseNodeInfo.BrowseNodes",
            ],
        )
    except Exception as e:
        print(f"[ERROR] PA-API リクエスト失敗: {e}")
        sys.exit(1)

    if not result or not result.items:
        print("[ERROR] PA-APIからデータを取得できませんでした。")
        return []

    items = []
    for rank, product in enumerate(result.items, start=1):
        item = {"rank": str(rank)}

        # タイトル
        item["title"] = product.item_info.title.display_value if product.item_info and product.item_info.title else "不明"

        # URL
        item["url"] = product.detail_page_url or ""

        # 価格
        price_str = "価格不明"
        if product.offers and product.offers.listings:
            listing = product.offers.listings[0]
            if listing.price:
                price_str = f"¥{listing.price.amount:,.0f}" if listing.price.amount else listing.price.display_amount or "価格不明"
            # 元値（セール前価格）
            if listing.saving_basis and listing.saving_basis.amount:
                item["discount"] = f"元値: ¥{listing.saving_basis.amount:,.0f}"
            else:
                item["discount"] = ""
        else:
            item["discount"] = ""
        item["price"] = price_str

        # PA-APIではレビュー情報は取得不可
        item["rating"] = ""
        item["reviews"] = ""

        items.append(item)

    return items


def format_message(items):
    """ランキング情報をGoogle Chat用のメッセージにフォーマット"""
    today = datetime.now(JST).strftime("%Y/%m/%d")
    lines = [
        f"*Amazon 熊よけ・忌避用品 ベストセラー Top10*",
        f"{today} 更新",
        "━" * 30,
    ]
    for item in items:
        lines.append(f"*{item['rank']}位* {item['title']}")
        details = []
        if item.get("price"):
            details.append(item["price"])
        if item.get("discount"):
            details.append(item["discount"])
        if item.get("rating"):
            details.append(item["rating"])
        if item.get("reviews"):
            details.append(f"{item['reviews']}件")
        if details:
            lines.append("　" + " / ".join(details))
        if item.get("url"):
            lines.append(f"　{item['url']}")
        lines.append("")
    return "\n".join(lines)


def send_to_google_chat(message):
    """Google Chat Webhookにメッセージを送信"""
    if not GOOGLE_CHAT_WEBHOOK_URL:
        print("[ERROR] GOOGLE_CHAT_WEBHOOK_URL が未設定です。")
        sys.exit(1)
    resp = requests.post(
        GOOGLE_CHAT_WEBHOOK_URL,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        data=json.dumps({"text": message}),
        timeout=30,
    )
    resp.raise_for_status()
    print(f"[OK] Google Chat に送信完了 (status: {resp.status_code})")


def main():
    print(f"[{datetime.now(JST)}] ランキング取得開始...")
    try:
        items = fetch_ranking()
    except Exception as e:
        print(f"[ERROR] 取得失敗: {e}")
        sys.exit(1)
    if not items:
        print("[ERROR] ランキングデータを取得できませんでした。")
        sys.exit(1)
    print(f"[OK] {len(items)} 件取得")
    message = format_message(items)
    if "--dry-run" in sys.argv:
        print("\n--- プレビュー ---")
        print(message)
        return
    send_to_google_chat(message)


if __name__ == "__main__":
    main()
