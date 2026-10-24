#!/usr/bin/env python3
"""Find the best study-meetup times for a group, and write a calendar invite for the one picked.

    python3 scripts/find_time.py slots --input group.json
    python3 scripts/find_time.py slots --sample
    python3 scripts/find_time.py ics --title "CSE 355 Exam Rescue" --where "Hayden Library" \
        --start 2026-10-27T16:00 --end 2026-10-27T17:30 --out ~/meow-meow/invite.ics

All times are the student's local wall-clock time ("2026-10-27T16:00"), no time zones.

group.json:
{
  "from": "2026-10-26", "to": "2026-10-28",       # days to search, inclusive
  "day_start": "09:00", "day_end": "22:00",        # waking/campus hours to consider
  "minutes": 90,                                   # session length
  "before": "2026-10-28T09:00",                    # optional: must end by this (the exam)
  "people": [
    {"name": "You",  "busy": [["2026-10-26T10:30", "2026-10-26T11:45"]]},
    {"name": "Ava",  "free": [["2026-10-27T15:00", "2026-10-27T19:00"]]},
    {"name": "Leo",  "busy": []}
  ]
}
Each person gives "busy" blocks (everything else counts as free) or "free" blocks (everything else
counts as busy). A person with neither is treated as free.

Prints up to 3 options as plain text (or JSON with --json): first the slots everyone can make; if
there are none, the slots most people can make and who would miss them.
Exit codes: 0 ok, 2 bad input, 3 no slot works for anyone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample_group.json"
STEP = timedelta(minutes=30)


def fail(msg: str, code: int):
    print(msg, file=sys.stderr)
    sys.exit(code)


def dt(s: str, what: str) -> datetime:
    try:
        return datetime.fromisoformat(str(s))
    except ValueError:
        fail(f"Bad date/time for {what}: {s!r} (use 2026-10-27T16:00)", 2)


def tm(s: str, what: str) -> time:
    try:
        return time.fromisoformat(str(s))
    except ValueError:
        fail(f"Bad time for {what}: {s!r} (use 09:00)", 2)


def blocks(raw, who: str) -> list[tuple[datetime, datetime]]:
    out = []
    for b in raw or []:
        if not isinstance(b, (list, tuple)) or len(b) != 2:
            fail(f"Each block for {who} must be [start, end]", 2)
        a, z = dt(b[0], who), dt(b[1], who)
        if z <= a:
            fail(f"Block for {who} ends before it starts: {b}", 2)
        out.append((a, z))
    return out


def overlaps(a0, a1, blocks_) -> bool:
    return any(a0 < z and a < a1 for a, z in blocks_)


def inside(a0, a1, blocks_) -> bool:
    return any(a <= a0 and a1 <= z for a, z in blocks_)


def can_make(person: dict, a0: datetime, a1: datetime) -> bool:
    if person["free"] is not None:
        return inside(a0, a1, person["free"])
    return not overlaps(a0, a1, person["busy"])


def nice(a0: datetime, a1: datetime) -> str:
    def t(d):
        s = d.strftime("%I:%M %p").lstrip("0")
        return s.replace(":00 ", " ")
    return f"{a0.strftime('%a, %b')} {a0.day} · {t(a0)}–{t(a1)}"


def comfort(a0: datetime) -> int:
    """Lower is better: afternoons and early evenings beat early mornings and late nights."""
    h = a0.hour + a0.minute / 60
    if 13 <= h <= 19:
        return 0
    if 10 <= h < 13 or 19 < h <= 20.5:
        return 1
    return 2


def find_slots(g: dict) -> dict:
    try:
        d0, d1 = date.fromisoformat(g["from"]), date.fromisoformat(g["to"])
    except (KeyError, ValueError):
        fail("Give 'from' and 'to' as dates like 2026-10-26.", 2)
    ds, de = tm(g.get("day_start", "09:00"), "day_start"), tm(g.get("day_end", "22:00"), "day_end")
    length = timedelta(minutes=int(g.get("minutes") or 60))
    before = dt(g["before"], "before") if g.get("before") else None
    people = []
    for p in g.get("people") or []:
        name = str(p.get("name") or "").strip() or f"Person {len(people) + 1}"
        people.append({"name": name, "busy": blocks(p.get("busy"), name),
                       "free": blocks(p["free"], name) if "free" in p else None})
    if not people:
        fail("Add at least one person.", 2)

    cands = []
    day = d0
    while day <= d1:
        start, end = datetime.combine(day, ds), datetime.combine(day, de)
        a0 = start
        while a0 + length <= end:
            a1 = a0 + length
            if before is None or a1 <= before:
                ok = [p["name"] for p in people if can_make(p, a0, a1)]
                if ok:
                    cands.append((a0, a1, ok))
            a0 += STEP
        day += timedelta(days=1)
    if not cands:
        fail("No time works for anyone in that window.", 3)

    best_n = max(len(c[2]) for c in cands)
    top = [c for c in cands if len(c[2]) == best_n]
    top.sort(key=lambda c: (comfort(c[0]), c[0]))
    picked = []
    for c in top:  # spread options out: at least 2 hours apart
        if all(abs((c[0] - q[0]).total_seconds()) >= 7200 for q in picked):
            picked.append(c)
        if len(picked) == 3:
            break
    names = [p["name"] for p in people]
    return {
        "everyone": best_n == len(people),
        "group_size": len(people),
        "options": [{"start": a.isoformat(timespec="minutes"), "end": z.isoformat(timespec="minutes"),
                     "label": nice(a, z), "can_make": ok,
                     "would_miss": [n for n in names if n not in ok]} for a, z, ok in picked],
    }


def describe(r: dict) -> str:
    lines = ["Everyone's free:" if r["everyone"] else "No time fits everyone. Closest options:"]
    for i, o in enumerate(r["options"], 1):
        miss = "" if not o["would_miss"] else f" (misses: {', '.join(o['would_miss'])})"
        lines.append(f"{i}. {o['label']}{miss}")
    return "\n".join(lines)



def ics(
    title: str,
    where: str,
    start: str,
    end: str,
    out: Path,
    tz_name: str = "America/Phoenix",
    reminder_minutes: int | None = None,
):
    a, z = dt(start, "start"), dt(end, "end")

    if a.tzinfo is not None or z.tzinfo is not None:
        fail("Use local dates and times without UTC offsets.", 2)

    if z <= a:
        fail("End must be after start.", 2)

    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        fail(f"Unknown timezone: {tz_name}", 2)

    def to_utc(local_dt):
        aware = local_dt.replace(tzinfo=tz)

        # Reject nonexistent local times during DST transitions.
        if aware.astimezone(timezone.utc).astimezone(tz).replace(
            tzinfo=None
        ) != local_dt:
            fail(f"Invalid local time in {tz_name}: {local_dt}", 2)

        return aware.astimezone(timezone.utc)

    start_utc = to_utc(a)
    end_utc = to_utc(z)

    if end_utc <= start_utc:
        fail("End must be after start in UTC.", 2)

    if reminder_minutes is not None and reminder_minutes <= 0:
        fail("Reminder must be a positive number of minutes.", 2)

    def esc(s: str) -> str:
        return (
            s.replace("\\", "\\\\")
             .replace(";", "\\;")
             .replace(",", "\\,")
             .replace("\n", "\\n")
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fmt = "%Y%m%dT%H%M%SZ"

    event_id = f"{title}|{start_utc.isoformat()}|{end_utc.isoformat()}"
    uid = hashlib.sha256(event_id.encode()).hexdigest()[:24] + "@meow-meow"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Team 11:11//Meow-Meow//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start_utc.strftime(fmt)}",
        f"DTEND:{end_utc.strftime(fmt)}",
        f"SUMMARY:{esc(title)}",
        f"LOCATION:{esc(where)}",
        f"DESCRIPTION:{esc('Planned by Meow-Meow. Timezone: ' + tz_name)}",
    ]

    if reminder_minutes is not None:
        lines.extend([
            "BEGIN:VALARM",
            f"TRIGGER:-PT{reminder_minutes}M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Your study session is coming up!",
            "END:VALARM",
        ])

    lines.extend([
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])

    out = out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes("\r\n".join(lines).encode("utf-8"))

    print(str(out))



def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("slots")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", type=Path)
    g.add_argument("--sample", action="store_true")
    s.add_argument("--json", action="store_true")
    i = sub.add_parser("ics")
    i.add_argument("--title", required=True)
    i.add_argument("--where", default="")
    i.add_argument("--start", required=True)
    i.add_argument("--end", required=True)
    i.add_argument("--out", type=Path, default=Path.home() / "meow-meow" / "invite.ics")
    i.add_argument("--timezone", default="America/Phoenix")
    i.add_argument("--reminder-minutes", type=int, default=None)
    a = ap.parse_args()

    if a.cmd == "ics":
        ics(
    a.title,
    a.where,
    a.start,
    a.end,
    a.out,
    tz_name=a.timezone,
    reminder_minutes=a.reminder_minutes,
)
        return
    path = SAMPLE if a.sample else a.input
    try:
        group = json.loads(path.read_text())
    except OSError:
        fail(f"Can't read {path}", 2)
    except ValueError as exc:
        fail(f"{path} is not valid JSON: {exc}", 2)
    r = find_slots(group)
    print(json.dumps(r, indent=2) if a.json else describe(r))


if __name__ == "__main__":
    main()
