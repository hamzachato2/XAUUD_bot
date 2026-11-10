
import os
import time
import traceback
import requests

from datetime import datetime, timezone, timedelta

# =================================
# SETTINGS
# =================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MYFX_EMAIL = os.getenv("MYFXBOOK_EMAIL")
MYFX_PASSWORD = os.getenv("MYFXBOOK_PASSWORD")

API = "https://www.myfxbook.com/api"

if not all([TOKEN, CHAT_ID, MYFX_EMAIL, MYFX_PASSWORD]):
    raise RuntimeError("Missing environment variables")

TG = f"https://api.telegram.org/bot{TOKEN}"

session = requests.Session()


# =================================
# TELEGRAM
# =================================

def send_message(text):

    r = requests.post(
        f"{TG}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=30
    )

    r.raise_for_status()

    result = r.json()

    if not result.get("ok"):
        raise RuntimeError(result)

    return result


# =================================
# MYFXBOOK API LOGIN
# =================================

def myfx_login():

    r = session.get(
        f"{API}/login.json",
        params={
            "email": MYFX_EMAIL,
            "password": MYFX_PASSWORD
        },
        timeout=30
    )

    r.raise_for_status()

    data = r.json()

    if data.get("error"):
        raise RuntimeError(
            "Myfxbook login failed: " +
            str(data.get("message"))
        )

    token = data.get("session")

    if not token:
        raise RuntimeError("Myfxbook session missing")

    return token


# =================================
# GET COMMUNITY OUTLOOK
# =================================

def get_xauusd_sentiment():

    api_session = myfx_login()

    try:

        r = session.get(
            f"{API}/get-community-outlook.json",
            params={
                "session": api_session
            },
            timeout=30
        )

        r.raise_for_status()

        data = r.json()

        if data.get("error"):
            raise RuntimeError(
                "Outlook API error: " +
                str(data.get("message"))
            )

        symbols = data.get("symbols", [])

        gold = None

        for symbol in symbols:

            name = str(
                symbol.get("name", "")
            ).upper().replace("/", "").replace(".", "")

            if name == "XAUUSD":
                gold = symbol
                break

        if not gold:

            available = [
                s.get("name")
                for s in symbols
            ]

            raise ValueError(
                "XAUUSD not found. Available symbols: " +
                str(available)
            )

        buy = {
            "percent": float(gold["longPercentage"]),
            "lots": float(gold["longVolume"]),
            "positions": int(gold["longPositions"])
        }

        sell = {
            "percent": float(gold["shortPercentage"]),
            "lots": float(gold["shortVolume"]),
            "positions": int(gold["shortPositions"])
        }

        return buy, sell

    finally:

        try:

            session.get(
                f"{API}/logout.json",
                params={
                    "session": api_session
                },
                timeout=15
            )

        except Exception as error:

            print("Logout warning:", error)


# =================================
# MAKE REPORT
# =================================

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

        f"🏆 More Volume: {bigger}\n\n"

        "⚠️ Sentiment is not a guaranteed trade signal."

    )


# =================================
# HANDLE COMMANDS
# =================================

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
            "بۆ شیکاری بازاڕ ئەم فەرمانە بنێرە:\n\n"
            "/analysis"
        )

    elif command == "/analysis":

        send_message(
            "⏳ چاوەڕێ بکە، داتای XAUUSD دەهێنم..."
        )

        try:

            report = make_report()

            send_message(report)

            print("Analysis sent successfully")

        except Exception as error:

            print("ANALYSIS ERROR:", repr(error))

            traceback.print_exc()

            send_message(
                "❌ Myfxbook API Error\n\n"
                f"{type(error).__name__}: "
                f"{str(error)[:700]}"
            )


# =================================
# MAIN BOT
# =================================

def main():

    print("🦅 XAUUSD Bot Started")

    r = requests.post(
        f"{TG}/deleteWebhook",
        data={"drop_pending_updates": "false"},
        timeout=30
    )

    r.raise_for_status()

    if not r.json().get("ok"):
        raise RuntimeError("Could not delete webhook")

    offset = None

    while True:

        try:

            params = {
                "timeout": 30,
                "allowed_updates": ["message"]
            }

            if offset is not None:
                params["offset"] = offset

            r = requests.get(
                f"{TG}/getUpdates",
                params=params,
                timeout=40
            )

            r.raise_for_status()

            data = r.json()

            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message")

                if message:

                    try:
                        handle_message(message)

                    except Exception as error:

                        print("MESSAGE ERROR:", repr(error))
                        traceback.print_exc()

        except Exception as error:

            print("BOT ERROR:", repr(error))
            traceback.print_exc()

            time.sleep(5)


# =================================
# START
# =================================

if __name__ == "__main__":
    main()
