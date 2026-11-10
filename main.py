
import os
import re
import time
import traceback
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ==============================
# TELEGRAM SETTINGS
# ==============================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

URL = "https://www.myfxbook.com/community/outlook/XAUUSD"

if not TOKEN or not CHAT_ID:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing"
    )

TG = f"https://api.telegram.org/bot{TOKEN}"

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
})


# ==============================
# TELEGRAM SEND MESSAGE
# ==============================

def send_message(text):

    response = requests.post(
        f"{TG}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram error: {result}")

    return result


# ==============================
# NUMBER CONVERSION
# ==============================

def get_number(value):

    return float(value.replace(",", ""))


# ==============================
# GET BUY / SELL DATA
# ==============================

def get_action_data(text, action):

    pattern = (
        rf"\b{action}\s+"
        rf"([\d.]+)\s*%\s+"
        rf"([\d,]+(?:\.\d+)?)\s+"
        rf"(?:lots?\s+)?"
        rf"([\d,]+)\b"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:

        raise ValueError(
            f"{action} data not found on Myfxbook"
        )

    return {

        "percent": float(match.group(1)),

        "lots": get_number(match.group(2)),

        "positions": int(
            match.group(3).replace(",", "")
        )
    }


# ==============================
# GET XAUUSD SENTIMENT
# ==============================

def get_xauusd_sentiment():

    print("Connecting to Myfxbook...")

    response = session.get(
        URL,
        timeout=40
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    page_text = soup.get_text(
        " ",
        strip=True
    )

    if not page_text:

        raise ValueError(
            "Myfxbook returned an empty page"
        )

    print("Myfxbook page received.")

    # Try to locate the sentiment table

    header = re.search(
        r"Symbol\s+Action\s+Percentage\s+Volume\s+Positions",
        page_text,
        re.IGNORECASE
    )

    if header:

        table_text = page_text[header.end():]

        table_text = re.split(
            r"Market Depth",
            table_text,
            flags=re.IGNORECASE
        )[0]

    else:

        # Try searching the full page
        table_text = page_text

    try:

        buy = get_action_data(
            table_text,
            "Long"
        )

        sell = get_action_data(
            table_text,
            "Short"
        )

    except Exception as error:

        print("Myfxbook parsing failed:", error)

        print(
            "PAGE TEXT:",
            page_text[:3000]
        )

        raise ValueError(
            "Myfxbook page format changed, "
            "or the website blocked the request. "
            + str(error)
        )

    print("BUY and SELL data received.")

    return buy, sell


# ==============================
# MAKE REPORT
# ==============================

def make_report():

    buy, sell = get_xauusd_sentiment()

    if buy["lots"] > sell["lots"]:

        bigger = "BUY 🟢"

    elif sell["lots"] > buy["lots"]:

        bigger = "SELL 🔴"

    else:

        bigger = "EQUAL ⚖️"

    now = datetime.now(
        timezone(timedelta(hours=3))
    ).strftime("%Y-%m-%d %H:%M:%S")

    total_positions = (
        buy["positions"] +
        sell["positions"]
    )

    report = (

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

        f"🏆 More Volume: {bigger}\n\n"

        "⚠️ Sentiment is not a guaranteed trade signal."

    )

    return report


# ==============================
# HANDLE TELEGRAM COMMANDS
# ==============================

def handle_message(message):

    chat_id = str(
        message.get("chat", {}).get("id", "")
    )

    if chat_id != str(CHAT_ID):

        return

    text = message.get("text", "").strip()

    if not text:

        return

    command = (
        text.split()[0]
        .split("@")[0]
        .lower()
    )

    if command == "/start":

        send_message(

            "🦅 XAUUSD Sentiment Bot\n\n"

            "Welcome!\n\n"

            "بۆ وەرگرتنی شیکاری بازاڕ ئەم فەرمانە بنێرە:\n\n"

            "/analysis"

        )

    elif command == "/analysis":

        send_message(
            "⏳ چاوەڕێ بکە، داتای XAUUSD دەهێنم..."
        )

        try:

            report = make_report()

            send_message(report)

            print("Analysis sent successfully.")

        except Exception as error:

            print(
                "ANALYSIS ERROR:",
                repr(error)
            )

            traceback.print_exc()

            try:

                send_message(

                    "❌ Myfxbook Error\n\n"

                    f"Error: {type(error).__name__}\n\n"

                    f"Details: {str(error)[:700]}\n\n"

                    "تکایە Logs ـی Railway بپشکنە."

                )

            except Exception as send_error:

                print(
                    "Telegram send error:",
                    repr(send_error)
                )


# ==============================
# MAIN BOT
# ==============================

def main():

    print("🦅 XAUUSD Sentiment Bot Started.")

    # Remove webhook before using polling

    response = requests.post(
        f"{TG}/deleteWebhook",
        data={"drop_pending_updates": "false"},
        timeout=30
    )

    response.raise_for_status()

    if not response.json().get("ok"):

        raise RuntimeError(
            "Could not delete Telegram webhook"
        )

    offset = None

    while True:

        try:

            params = {
                "timeout": 30,
                "allowed_updates": ["message"]
            }

            if offset is not None:

                params["offset"] = offset

            response = requests.get(

                f"{TG}/getUpdates",

                params=params,

                timeout=40

            )

            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):

                print(
                    "Telegram API error:",
                    data
                )

                time.sleep(5)

                continue

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message")

                if message:

                    try:

                        handle_message(message)

                    except Exception as error:

                        print(
                            "MESSAGE ERROR:",
                            repr(error)
                        )

                        traceback.print_exc()

        except Exception as error:

            print(
                "BOT ERROR:",
                repr(error)
            )

            traceback.print_exc()

            time.sleep(5)


# ==============================
# START
# ==============================

if __name__ == "__main__":

    main()
