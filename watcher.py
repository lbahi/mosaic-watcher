import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import os

# ─── CORE CONFIG ────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
CHAT_ID          = os.environ["CHAT_ID"]
CHECK_INTERVAL   = int(os.environ.get("CHECK_INTERVAL", "10"))
TWILIO_SID       = os.environ["TWILIO_SID"]
TWILIO_TOKEN     = os.environ["TWILIO_TOKEN"]
TWILIO_FROM      = os.environ["TWILIO_FROM"]
TWILIO_TO        = os.environ["TWILIO_TO"]

# ─── YOUR PERSONAL DETAILS ──────────────────────────────────
P_NAME           = os.environ["P_NAME"]
P_SURNAME        = os.environ["P_SURNAME"]
P_DOB            = os.environ["P_DOB"]
P_PLACE_BIRTH    = os.environ["P_PLACE_BIRTH"]
P_FATHER         = os.environ["P_FATHER"]
P_MOTHER         = os.environ["P_MOTHER"]
P_OCCUPATION     = os.environ["P_OCCUPATION"]
P_PASSPORT_PLACE = os.environ["P_PASSPORT_PLACE"]
P_PASSPORT_ISSUE = os.environ["P_PASSPORT_ISSUE"]
P_PASSPORT_EXP   = os.environ["P_PASSPORT_EXP"]
P_ADDRESS        = os.environ["P_ADDRESS"]
P_CITY           = os.environ["P_CITY"]
P_ZIPCODE        = os.environ["P_ZIPCODE"]
P_EMAIL          = os.environ["P_EMAIL"]
P_PHONE          = os.environ["P_PHONE"]
P_DEPARTURE      = os.environ["P_DEPARTURE"]
P_RETURN         = os.environ["P_RETURN"]
# ────────────────────────────────────────────────────────────

MONTHS_TO_CHECK = [
    "https://appointment.mosaicvisa.com/calendar/9?month=2026-03",
    "https://appointment.mosaicvisa.com/calendar/9?month=2026-04",
    "https://appointment.mosaicvisa.com/calendar/9?month=2026-05",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


async def send_telegram(client: httpx.AsyncClient, message: str):
    try:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[Telegram error] {e}")


async def make_phone_call(client: httpx.AsyncClient):
    try:
        twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="en-US" voice="alice">
    Urgent! A Turkey visa appointment slot is available!
    Open Telegram immediately. All your details are ready.
    Go book your appointment now!
  </Say>
  <Pause length="1"/>
  <Say language="en-US" voice="alice">
    Repeating. Open Telegram now and book your appointment!
  </Say>
</Response>'''
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"To": TWILIO_TO, "From": TWILIO_FROM, "Twiml": twiml},
            timeout=15,
        )
        print("📞 Phone call triggered!")
    except Exception as e:
        print(f"[Twilio error] {e}")


async def send_cheatsheet(client: httpx.AsyncClient, slots: list):
    """Send fully formatted cheat sheet with all booking details."""
    now   = datetime.now().strftime("%H:%M:%S")
    lines = "\n".join(f"📅 {s['date']} — {s['info']}" for s in slots)

    msg = (
        f"🚨 <b>SLOT AVAILABLE — BOOK NOW!</b>\n"
        f"{lines}\n"
        f"⏰ Detected at {now}\n\n"

        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📋 STEP 1 — First page:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Applicants: <b>1</b>\n"
        f"• Email: <code>{P_EMAIL}</code>\n"
        f"• Phone: <code>{P_PHONE}</code>\n\n"

        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📋 STEP 2 — After SMS code, fill form:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Name: <code>{P_NAME}</code>\n"
        f"• Surname: <code>{P_SURNAME}</code>\n"
        f"• Date of birth: <code>{P_DOB}</code>\n"
        f"• Place of birth: <code>{P_PLACE_BIRTH}</code>\n"
        f"• Father: <code>{P_FATHER}</code>\n"
        f"• Mother: <code>{P_MOTHER}</code>\n"
        f"• Occupation: <code>{P_OCCUPATION}</code>\n"
        f"• Passport place: <code>{P_PASSPORT_PLACE}</code>\n"
        f"• Passport issued: <code>{P_PASSPORT_ISSUE}</code>\n"
        f"• Passport expiry: <code>{P_PASSPORT_EXP}</code>\n"
        f"• Address: <code>{P_ADDRESS}</code>\n"
        f"• City: <code>{P_CITY}</code>\n"
        f"• Zip: <code>{P_ZIPCODE}</code>\n"
        f"• Departure: <code>{P_DEPARTURE}</code>\n"
        f"• Return: <code>{P_RETURN}</code>\n\n"

        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 <a href='https://appointment.mosaicvisa.com/calendar/9'>"
        f"OPEN BOOKING PAGE NOW</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await send_telegram(client, msg)


def parse_slots(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    found = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            date_text  = cells[0].get_text(strip=True)
            avail_text = cells[1].get_text(strip=True)
            if "Available" in avail_text and date_text:
                found.append({"date": date_text, "info": avail_text})
    return found


async def check_all_months(client: httpx.AsyncClient) -> list:
    all_slots = []
    for url in MONTHS_TO_CHECK:
        try:
            r = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            r.raise_for_status()
            all_slots.extend(parse_slots(r.text))
        except Exception as e:
            print(f"[Fetch error] {url} → {e}")
    return all_slots


async def main():
    print(f"🚀 Watcher started — checking every {CHECK_INTERVAL}s")
    async with httpx.AsyncClient() as client:
        await send_telegram(
            client,
            "🟢 <b>Mosaic Watcher is running</b>\n"
            f"Checking every {CHECK_INTERVAL} seconds for Turkey visa slots (Algiers).\n"
            "📞 Phone call enabled!\n"
            "📋 Instant cheat sheet on slot detection!"
        )

        last_seen: set  = set()
        errors          = 0
        call_cooldown   = 0

        while True:
            try:
                slots = await check_all_months(client)
                now   = datetime.now().strftime("%H:%M:%S")

                if slots:
                    slot_keys = {s["date"] for s in slots}
                    new_slots = [s for s in slots if s["date"] not in last_seen]

                    if new_slots:
                        # Send full cheat sheet immediately
                        await send_cheatsheet(client, new_slots)

                        # Trigger phone call (max once every 5 minutes)
                        if call_cooldown <= 0:
                            await make_phone_call(client)
                            call_cooldown = 30  # 30 × 10s = 5 min

                        print(f"[{now}] ✅ ALERT + CHEATSHEET SENT — {len(new_slots)} slot(s)")
                    else:
                        print(f"[{now}] ✅ Slots still open (already notified)")

                    last_seen = slot_keys
                    if call_cooldown > 0:
                        call_cooldown -= 1

                else:
                    if last_seen:
                        await send_telegram(client, "ℹ️ Slots are now gone.")
                    print(f"[{now}] ❌ No slots")
                    last_seen     = set()
                    call_cooldown = 0

                errors = 0

            except Exception as e:
                errors += 1
                print(f"[ERROR #{errors}] {e}")
                if errors == 10:
                    await send_telegram(
                        client,
                        f"⚠️ <b>10 errors in a row</b>\n{str(e)[:200]}"
                    )

            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
