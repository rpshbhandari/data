"""Build the subscribable calendar feeds from v1/calendar/bs.json.

    python3 scripts/ics.py           write calendar/nepali.ics and calendar/english.ics

scripts/check.py --write runs this too, and check.py fails if the feeds are out of
step with bs.json. The feeds depend on nothing but bs.json (no "today"), so they
only change when bs.json does.

Each day is one all-day event, so the date never shifts for people outside Nepal.
Its UID comes from the AD date: when a projected year is corrected, each day's
event is updated in place instead of being duplicated.
"""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BS = ROOT / "v1" / "calendar" / "bs.json"
OUT = ROOT / "calendar"
DOMAIN = "data.rupeshbhandari.com.np"
YEARS_BACK = 1  # the feed starts this many years before the last official year


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """ICS lines are at most 75 bytes; longer ones go on in lines that start with a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > 75:
            out.append(cur.decode("utf-8"))
            cur = b" "
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def days(cal, first_year):
    """(AD date, year entry, month entry, day) for every day from Baisakh 1 of first_year."""
    for y in cal["years"]:
        if y["year"] < first_year:
            continue
        d = date.fromisoformat(y["starts"])
        for m, length in enumerate(y["months"]):
            for day in range(1, length + 1):
                yield d, y, cal["months"][m], day
                d += timedelta(days=1)


def nepali(cal):
    digits = lambda n: "".join(cal["digits"][int(c)] for c in str(n))

    def event(d, y, month, day):
        weekday = cal["weekdays"][(d.weekday() + 1) % 7]["ne"]
        title = f'{month["ne"]} {digits(day)}' + (f', {digits(y["year"])}' if day == 1 else "")
        note = f'{weekday}, {digits(day)} {month["ne"]} {digits(y["year"])}'
        if y["status"] == "projected":
            note += "\nअनुमानित मिति: पात्रो स्वीकृत भएपछि फेरिन सक्छ।"
        return title, note

    return {"slug": "ne", "name": "नेपाली मिति", "desc": "हरेक दिनको विक्रम संवत् मिति", "event": event}


def english(cal):
    def event(d, y, month, day):
        weekday = cal["weekdays"][(d.weekday() + 1) % 7]["en"]
        title = f'{month["en"]} {day}' + (f', {y["year"]}' if day == 1 else "")
        note = f'{weekday}, {month["en"]} {day}, {y["year"]} BS'
        if y["status"] == "projected":
            note += "\nProjected: may change when the year's calendar is approved."
        return title, note

    return {"slug": "en", "name": "Nepali Date (BS)", "desc": "The Bikram Sambat date on every day", "event": event}


FEEDS = {"nepali.ics": nepali, "english.ics": english}


def build(cal):
    """{file name: feed text} for every feed."""
    official = [y["year"] for y in cal["years"] if y["status"] == "official"]
    first_year = (official[-1] if official else cal["years"][0]["year"]) - YEARS_BACK
    stamp = cal["updated"].replace("-", "") + "T000000Z"   # changes only when bs.json does
    feeds = {}
    for name, make in FEEDS.items():
        feed = make(cal)
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//{DOMAIN}//Bikram Sambat {feed['slug']}//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{esc(feed['name'])}",
            f"X-WR-CALDESC:{esc(feed['desc'])}",
            "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
            "X-PUBLISHED-TTL:PT12H",
        ]
        for d, y, month, day in days(cal, first_year):
            title, note = feed["event"](d, y, month, day)
            lines += [
                "BEGIN:VEVENT",
                f"UID:{d:%Y%m%d}-{feed['slug']}@{DOMAIN}",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                f"SUMMARY:{esc(title)}",
                f"DESCRIPTION:{esc(note)}",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        feeds[name] = "".join(fold(l) + "\r\n" for l in lines)
    return feeds


def write(feeds):
    OUT.mkdir(exist_ok=True)
    for name, text in feeds.items():
        (OUT / name).write_bytes(text.encode("utf-8"))


def stale(feeds):
    """Names of the feeds whose file is missing or differs from what bs.json gives."""
    return [n for n, t in feeds.items() if not (OUT / n).exists() or (OUT / n).read_bytes() != t.encode("utf-8")]


if __name__ == "__main__":
    feeds = build(json.loads(BS.read_text(encoding="utf-8")))
    write(feeds)
    print("wrote", ", ".join(f"calendar/{n}" for n in feeds))
