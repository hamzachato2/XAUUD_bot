import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

URL = "https://www.myfxbook.com/community/outlook/XAUUSD"

if not TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")

TG = f"https://api.telegram.org/bot{TOKEN}"

def send_message(text):
    requests.post(
        f"{TG}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=30
    ).raise_for_status()

def get_number(value):
    return float(value.replace(",", ""))

def get_action_data(text, action):
    pattern = (
        rf"{action}\s+([\d.]+)\s*%\s+"
        rf"([\d,]+(?:\.\d+)?)\s+lots?\s+([\d,]+)"
    )
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        raise ValueError(f"{action} data not found")

    return {
        "percent": float(match.group(1)),
        "lots": get_number(match.group(2)),
        "positions": int(match.group(3).replace(",", ""))
    }

def get_xauusd_sentiment():
    response = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    header = re.search(
        r"Symbol\s+Action\s+Percentage\s+Volume\s+Positions",
        page_text,
        re.IGNORECASE
    )

    if not header:
        raise ValueError("Myfxbook table was not found")

    table_text = page_text[header.end():]
    table_text = table_text.split("Market Depth")[0]

    sell = get_action_data(table_text, "Short")
    buy = get_action_data(table_text, "Long")

    return buy, sell

def make_report():
    buy, sell = get_xauusd_sentiment()

    if buy["lots"] > sell["lots"]:
        bigger = "BUY"
    elif sell["lots"] > buy["lots"]:
        bigger = "SELL"
    else:
        bigger = "EQUAL"

    now = datetime.now(
        timezone(timedelta(hours=3))
    ).strftime("%Y-%m-%d %H:%M:%S")

    total_positions = buy["positions"] + sell["positions"]

    return (
        "🦅 XAUUSD MARKET SENTIMENT\n\n"
        f"🕒 Time: {now} (Iraq)\n\n"
        "🟢 BUY / LONG\n"
        f"Percentage: {buy['percent']}%\n"
        f"Positions: {buy['positions']:,}\n"
        f"Volume: {buy['lots']:,.2f} lots\n\n"
        "🔴 SELL / SHORT\n"
        f"Percentage: {sell['percent']}%\n"
        f"Positions: {sell['positions']:,}\n"
        f"Volume: {sell['lots']:,.2f} lots\n\n"
        "📊 TOTAL POSITIONS\n"
        f"{total_positions:,}\n\n"
        f"🏆 More volume: {bigger}\n\n"
        "⚠️ Sentiment data is not a guaranteed trade signal."
    )

def handle_message(message):
    chat_id = str(message["chat"]["id"])

    if chat_id != str(CHAT_ID):
        return

    command = message.get("text", "").strip().split()[0].split("@")[0].lower()

    if command == "/start":
        send_message(
            "🦅 XAUUSD Sentiment Bot\n\n"
            "بۆ وەرگرتنی دۆخی بازاڕ ئەم فەرمانە بنێرە:\n"
            "/analysis"
        )

    elif command == "/analysis":
        send_message("⏳ چاوەڕێ بکە، داتای XAUUSD دەهێنم...")
        try:
            report = make_report()
            send_message(report)
        except Exception as error:
            print("Analysis error:", error)
            send_message(
                "❌ نەمتوانی داتای Myfxbook بهێنم.\n"
                "تکایە دواتر هەوڵ بدەرەوە."
            )

def main():
    print("XAUUSD Sentiment Bot started.")
    offset = None

    while True:
        try:
            response = requests.get(
                f"{TG}/getUpdates",
                params={
                    "timeout": 30,
                    "offset": offset
                },
                timeout=40
            )
            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data["result"]:
                offset = update["update_id"] + 1

                message = update.get("message")
                if message:
                    handle_message(message)

        except Exception as error:
            print("Bot error:", error)
            time.sleep(5)

if __name__ == "__main__":
    main()
