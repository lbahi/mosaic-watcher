import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "45"))

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
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[Telegram error] {e}")

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
            slots = parse_slots(r.text)
            all_slots.extend(slots)
        except Exception as e:
            print(f"[Fetch error] {url} → {e}")
    return all_slots

async def main():
    print(f"🚀 Watcher started — checking every {CHECK_INTERVAL}s")
    async with httpx.AsyncClient() as client:
        await send_telegram(
            client,
            "🟢 <b>Mosaic Watcher is running</b>\n"
            f"Checking every {CHECK_INTERVAL} seconds for Turkey visa slots (Algiers)."
        )
        last_seen: set = set()
        errors = 0

        while True:
            try:
                slots = await check_all_months(client)
                now   = datetime.now().strftime("%H:%M:%S")

                if slots:
                    slot_keys = {s["date"] for s in slots}
                    new_slots = [s for s in slots if s["date"] not in last_seen]

                    if new_slots:
                        lines = "\n".join(f"📅 {s['date']} — {s['info']}" for s in new_slots)
                        msg = (
                            f"🚨 <b>SLOTS AVAILABLE NOW!</b>\n\n"
                            f"{lines}\n\n"
                            f"⏰ {now}\n"
                            f"👉 <a href='https://appointment.mosaicvisa.com/calendar/9'>Book immediately</a>"
                        )
                        await send_telegram(client, msg)
                        print(f"[{now}] ✅ ALERT SENT — {len(new_slots)} new slot(s)")
                    else:
                        print(f"[{now}] ✅ Slots still visible (already notified)")

                    last_seen = slot_keys
                else:
                    if last_seen:
                        await send_telegram(client, "ℹ️ Previously available slots are now gone.")
                    print(f"[{now}] ❌ No slots")
                    last_seen = set()

                errors = 0

            except Exception as e:
                errors += 1
                print(f"[ERROR #{errors}] {e}")
                if errors == 10:
                    await send_telegram(client, f"⚠️ <b>Watcher error</b>\n10 failures in a row.\n{str(e)[:200]}")

            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
