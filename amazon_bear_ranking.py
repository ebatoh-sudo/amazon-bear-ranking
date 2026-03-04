#!/usr/bin/env python3
"""
Amazon.co.jp 熊よけ・忌避用品 ベストセラーランキング Top10 を
Google Chat Webhook に投稿するスクリプト
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
AMAZON_URL = "https://www.amazon.co.jp/gp/bestsellers/sports/2201156051"
GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", "")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
JST = timezone(timedelta(hours=9))
def fetch_ranking():
    """Amazonベストセラーページをスクレイピングしてランキング情報を取得"""
    resp = requests.get(AMAZON_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    print(f"[DEBUG] レスポンスサイズ: {len(resp.text)} bytes")
    print(f"[DEBUG] タイトル: {resp.text[resp.text.find('<title'):resp.text.find('</title>')+8] if '<title' in resp.text else 'no title'}")
    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    product_cards = soup.select("div#gridItemRoot")
    if not product_cards:
        product_cards = soup.select("div[id^='p13n-asin-index-']")
    if not product_cards:
        product_cards = soup.select("div.a-cardui._cDEzb_p13n-grid-content_3RQ2P")
    if not product_cards:
        product_cards = soup.select("[data-asin]")
    print(f"[DEBUG] 商品カード数: {len(product_cards)}")
    for card in product_cards[:10]:
        item = {}
        rank_el = card.select_one("span.zg-bdg-text")
        item["rank"] = rank_el.get_text(strip=True).replace("#", "") if rank_el else str(len(items) + 1)
        title_el = (
            card.select_one("a.a-link-normal span div")
            or card.select_one("a.a-link-normal span")
            or card.select_one("div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
            or card.select_one("div._cDEzb_p13n-sc-css-line-clamp-4_2q2cc")
            or card.select_one("span.a-size-small")
        )
        item["title"] = title_el.get_text(strip=True) if title_el else "不明"
        link_el = card.select_one("a.a-link-normal[href]")
        if link_el:
            href = link_el.get("href", "")
            if href.startswith("/"):
                href = "https://www.amazon.co.jp" + href
            item["url"] = href.split("/ref=")[0]
        else:
            item["url"] = ""
        price_el = (
            card.select_one("span.p13n-sc-price")
            or card.select_one("span._cDEzb_p13n-sc-price_3mJ9Z")
            or card.select_one("span.a-price span.a-offscreen")
        )
        item["price"] = price_el.get_text(strip=True) if price_el else "価格不明"
        rating_el = card.select_one("span.a-icon-alt")
        item["rating"] = rating_el.get_text(strip=True) if rating_el else ""
        review_el = card.select_one("a.a-size-small")
        item["reviews"] = review_el.get_text(strip=True) if review_el else ""
        discount_el = card.select_one("span.a-text-price")
        item["discount"] = f"元値: {discount_el.get_text(strip=True)}" if discount_el else ""
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
        print(f"[ERROR] スクレイピング失敗: {e}")
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
