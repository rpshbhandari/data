"""Check every data file before it is published.

    python3 scripts/check.py           check; exit 1 and list the problems
    python3 scripts/check.py --write   also reformat the files and rewrite v1/index.json

Every file needs "dataset", "updated" and "sources". Each dataset then has its
own checks below: rates in range, slabs that join up, dates in order. A file
whose dataset has no checker fails, so add one to CHECKS with each new dataset.
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "v1"
INDEX = V1 / "index.json"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BS_DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[0-2])$")  # Nepali months run to 32 days
FISCAL_YEAR = re.compile(r"^(\d{4})/(\d{2})$")
FRACTION = re.compile(r"^(\d+)(?:/(\d+))?$")  # "1", "2/3"


class Problems(list):
    def __call__(self, where, message):
        self.append(f"{where}: {message}")


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def ad_date(v):
    """The date for an ISO yyyy-mm-dd string, or None."""
    if not isinstance(v, str) or not ISO_DATE.match(v):
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def rate(p, where, v, high=100, allow_null=False):
    if v is None and allow_null:
        return
    if not is_num(v) or not 0 <= v <= high:
        p(where, f"rate {v!r} should be a number from 0 to {high}")


def amount(p, where, v):
    if not is_num(v) or v < 0:
        p(where, f"amount {v!r} should be a number of rupees, 0 or more")


def share(p, where, v):
    m = FRACTION.match(v) if isinstance(v, str) else None
    if not m or (m[2] and int(m[2]) == 0) or not 0 < int(m[1]) / int(m[2] or 1) <= 1:
        p(where, f'share {v!r} should be a fraction such as "1/3"')


def text(p, where, v):
    if not isinstance(v, str) or not v.strip():
        p(where, "should be non-empty text")


def unique_ids(p, where, items):
    ids = [i.get("id") for i in items]
    for dup in sorted({i for i in ids if ids.count(i) > 1}, key=str):
        p(where, f'id "{dup}" appears more than once')


def items(p, where, v):
    """v if it is a non-empty list of objects, else [] after recording the problem."""
    if not isinstance(v, list) or not v or not all(isinstance(i, dict) for i in v):
        p(where, "should be a non-empty list of objects")
        return []
    return v


# ── Every file ───────────────────────────────────────────────────

def check_common(p, where, d, path):
    for key in ("dataset", "updated", "sources"):
        if key not in d:
            p(where, f'missing "{key}"')
    if "updated" in d:
        u = ad_date(d["updated"])
        if u is None:
            p(where, f'"updated" {d["updated"]!r} should be a date like 2026-10-16')
        elif u > date.today():
            p(where, f'"updated" {d["updated"]} is in the future')
    for i, s in enumerate(items(p, f"{where} sources", d.get("sources"))):
        text(p, f"{where} sources[{i}].title", s.get("title"))
        if "url" in s and not str(s["url"]).startswith("https://"):
            p(where, f"sources[{i}].url should start with https://")
    if "fiscal_year" in d:
        fy = d["fiscal_year"]
        m = FISCAL_YEAR.match(fy) if isinstance(fy, str) else None
        if not m or (int(m[1]) + 1) % 100 != int(m[2]):
            p(where, f'"fiscal_year" {fy!r} should look like "2083/84"')
            return
        if re.match(r"^\d{4}-\d{2}$", path.stem) and path.stem != fy.replace("/", "-"):
            p(where, f'file name should be {fy.replace("/", "-")}.json for fiscal year {fy}')
        starts = d.get("starts") or {}
        if starts.get("bs") != f"{m[1]}-04-01":
            p(where, f'"starts.bs" should be {m[1]}-04-01 (Shrawan 1)')
        if ad_date(starts.get("ad")) is None:
            p(where, '"starts.ad" should be the AD date of Shrawan 1, like 2026-07-17')


# ── Each dataset ─────────────────────────────────────────────────

def check_slabs(p, where, slabs):
    slabs = items(p, where, slabs)
    for i, s in enumerate(slabs):
        w = f"{where}[{i}]"
        last = i == len(slabs) - 1
        if i == 0 and s.get("from") != 0:
            p(w, "the first slab should start from 0")
        if i > 0 and s.get("from") != slabs[i - 1].get("to"):
            p(w, f'"from" should equal the previous slab\'s "to" ({slabs[i - 1].get("to")})')
        if last and s.get("to") is not None:
            p(w, 'the top slab should have "to": null')
        if not last and not (is_num(s.get("to")) and is_num(s.get("from")) and s["to"] > s["from"]):
            p(w, '"to" should be more than "from"')
        rate(p, w, s.get("rate"))
        if "rate_if_ssf" in s:
            rate(p, f"{w}.rate_if_ssf", s["rate_if_ssf"])
        if i > 0 and is_num(s.get("rate")) and is_num(slabs[i - 1].get("rate")) and s["rate"] < slabs[i - 1]["rate"]:
            p(w, "rates should not go down from one slab to the next")


def check_income_tax(p, w, d):
    slabs = d.get("slabs") or {}
    for key in ("individual", "couple"):
        check_slabs(p, f"{w} slabs.{key}", slabs.get(key))
    ded = d.get("deductions") or {}
    ret = ded.get("retirement_funds") or {}
    amount(p, f"{w} retirement_funds.cap_with_ssf", ret.get("cap_with_ssf"))
    amount(p, f"{w} retirement_funds.cap_without_ssf", ret.get("cap_without_ssf"))
    share(p, f"{w} retirement_funds.max_share_of_income", ret.get("max_share_of_income"))
    for key in ("life_insurance", "health_insurance", "house_insurance"):
        amount(p, f"{w} deductions.{key}.cap", (ded.get(key) or {}).get("cap"))
    if "tuition_fees" in ded:
        share(p, f"{w} tuition_fees.share", ded["tuition_fees"].get("share"))
        amount(p, f"{w} tuition_fees.cap", ded["tuition_fees"].get("cap"))
    rate(p, f"{w} rebates.women", ((d.get("rebates") or {}).get("women") or {}).get("rate"))
    for i, c in enumerate(d.get("changes", [])):
        text(p, f"{w} changes[{i}]", c)


def check_tds(p, w, d):
    rates = items(p, f"{w} rates", d.get("rates"))
    unique_ids(p, f"{w} rates", rates)
    for r in rates:
        rw = f'{w} rates "{r.get("id")}"'
        text(p, rw + ".payment", r.get("payment"))
        rate(p, rw, r.get("rate"))
        if "threshold" in r:
            amount(p, rw + ".threshold", r["threshold"])
        if "vat_applies" in r and not isinstance(r["vat_applies"], bool):
            p(rw, '"vat_applies" should be true or false')


def check_vat(p, w, d):
    rates = items(p, f"{w} rates", d.get("rates"))
    unique_ids(p, f"{w} rates", rates)
    if not any(r.get("id") == "standard" for r in rates):
        p(w, 'needs a rate with "id": "standard"')
    for r in rates:
        rate(p, f'{w} rates "{r.get("id")}"', r.get("rate"))


def check_depreciation(p, w, d):
    pools = items(p, f"{w} pools", d.get("pools"))
    unique_ids(p, f"{w} pools", pools)
    for pool in pools:
        pw = f'{w} pool {pool.get("id")}'
        rate(p, pw, pool.get("rate"), allow_null=True)
        text(p, pw + ".assets", pool.get("assets"))
        if pool.get("rate") is None:
            text(p, pw + ".method", pool.get("method"))
    for i, a in enumerate(items(p, f"{w} additions", d.get("additions"))):
        share(p, f"{w} additions[{i}]", a.get("share_of_cost"))
    amount(p, f"{w} small_balance.below", (d.get("small_balance") or {}).get("below"))


def check_commission(p, w, d):
    schedules = items(p, f"{w} schedules", d.get("schedules"))
    for i, s in enumerate(schedules):
        sw = f"{w} schedules[{i}]"
        start, end = ad_date(s.get("from")), ad_date(s.get("to"))
        last = i == len(schedules) - 1
        if start is None:
            p(sw, '"from" should be a date like 2024-05-14')
        if last and s.get("to") is not None:
            p(sw, 'the current schedule should have "to": null')
        if not last:
            following = ad_date(schedules[i + 1].get("from"))
            if end is None or start is None or end < start:
                p(sw, '"to" should be a date on or after "from"')
            elif following and following != end + timedelta(days=1):
                p(sw, f'the next schedule should start the day after "to" ({end + timedelta(days=1)})')
        amount(p, sw + ".minimum", s.get("minimum"))
        slabs = items(p, sw + ".slabs", s.get("slabs"))
        for j, slab in enumerate(slabs):
            jw = f"{sw}.slabs[{j}]"
            rate(p, jw, slab.get("rate"), high=5)
            up_to = slab.get("up_to")
            if j == len(slabs) - 1:
                if up_to is not None:
                    p(jw, 'the top slab should have "up_to": null')
            elif not is_num(up_to) or (j > 0 and is_num(slabs[j - 1].get("up_to")) and up_to <= slabs[j - 1]["up_to"]):
                p(jw, '"up_to" should be a number larger than the slab before')


def check_fees(p, w, d):
    rate(p, f"{w} sebon_fee", (d.get("sebon_fee") or {}).get("rate"), high=5)
    amount(p, f"{w} dp_charge", (d.get("dp_charge") or {}).get("amount"))


def check_capital_gains(p, w, d):
    days = d.get("short_term_max_days")
    if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
        p(w, '"short_term_max_days" should be a whole number of days')
    previous = None
    for i, s in enumerate(items(p, f"{w} schedules", d.get("schedules"))):
        sw = f"{w} schedules[{i}]"
        start = ad_date(s.get("from"))
        if start is None:
            p(sw, '"from" should be a date like 2026-09-22')
        elif previous and start <= previous:
            p(sw, "schedules should be in date order")
        previous = start or previous
        ind = s.get("individual") or {}
        rate(p, sw + ".individual.short_term", ind.get("short_term"))
        rate(p, sw + ".individual.long_term", ind.get("long_term"))
        rate(p, sw + ".institution", s.get("institution"))
        text(p, sw + ".basis", s.get("basis"))


CHECKS = {
    "income-tax": check_income_tax,
    "tds": check_tds,
    "vat": check_vat,
    "depreciation-pools": check_depreciation,
    "nepse-broker-commission": check_commission,
    "nepse-fees": check_fees,
    "nepse-capital-gains-tax": check_capital_gains,
}


# ── Run ──────────────────────────────────────────────────────────

def dump(d):
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def main():
    write = "--write" in sys.argv[1:]
    p = Problems()
    entries, seen = [], {}
    paths = sorted(f for f in V1.rglob("*.json") if f != INDEX)
    for path in paths:
        rel = path.relative_to(V1).as_posix()
        raw = path.read_text(encoding="utf-8")
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            p(rel, f"not valid JSON ({e})")
            continue
        if not isinstance(d, dict):
            p(rel, "should be a JSON object")
            continue
        if raw != dump(d):
            if write:
                path.write_text(dump(d), encoding="utf-8")
            else:
                p(rel, "not in the standard format (2-space indent); run python3 scripts/check.py --write")
        check_common(p, rel, d, path)
        check = CHECKS.get(d.get("dataset"))
        if check:
            check(p, rel, d)
        else:
            p(rel, f'no checks for dataset {d.get("dataset")!r}; add a checker to CHECKS in scripts/check.py')
        key = (d.get("dataset"), d.get("fiscal_year"))
        if key in seen:
            p(rel, f"same dataset and fiscal year as {seen[key]}")
        seen[key] = rel
        entry = {"path": rel, "dataset": d.get("dataset")}
        if "fiscal_year" in d:
            entry["fiscal_year"] = d["fiscal_year"]
        entry["updated"] = d.get("updated")
        entries.append(entry)

    index = {"updated": max((e["updated"] for e in entries if isinstance(e["updated"], str)), default=None), "files": entries}
    if write:
        INDEX.write_text(dump(index), encoding="utf-8")
    elif not INDEX.exists() or json.loads(INDEX.read_text(encoding="utf-8")) != index:
        p("index.json", "out of date with the files; run python3 scripts/check.py --write")

    if p:
        print(f"{len(p)} problem{'s' if len(p) != 1 else ''}:", *p, sep="\n  ")
        sys.exit(1)
    print(f"OK: {len(paths)} files checked{', index.json written' if write else ''}")


if __name__ == "__main__":
    main()
