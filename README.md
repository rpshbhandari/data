# Rupesh Bhandari Data

Nepal's tax and market rates as JSON at **[data.rupeshbhandari.com.np](https://data.rupeshbhandari.com.np/)**: income tax slabs, TDS and VAT rates, depreciation pools and NEPSE charges. Each file says when it was last checked and where its figures come from. The calculators on [tools.rupeshbhandari.com.np](https://tools.rupeshbhandari.com.np/) read these files, and anyone else can fetch them too (GitHub Pages sends `Access-Control-Allow-Origin: *`).

## Using the API

Every file is a plain `GET` with no key, under `https://data.rupeshbhandari.com.np/v1/`. Start with `index.json`, which lists every file:

```bash
curl https://data.rupeshbhandari.com.np/v1/index.json
```

The [site's front page](https://data.rupeshbhandari.com.np/) is the API documentation. It covers every endpoint and its response fields, with curl, JavaScript and Python examples, and a **Send request** button that shows the live response.

Python's built-in `urllib` is turned away by Cloudflare unless it sends its own `User-Agent` header; `requests`, `httpx`, curl, browsers and other clients work as they are.

## Layout

```
v1/index.json                          Every file below, with its dataset, fiscal year and date last checked
v1/tax/income/2080-81.json … 2083-84.json   Income tax slabs, deduction limits and the women's rebate, one file per fiscal year
v1/tax/tds/2083-84.json                TDS rates by type of payment
v1/tax/vat/2083-84.json                VAT rates
v1/tax/depreciation/pools.json         Schedule 2 pool rates and the rules for additions
v1/market/nepse/commission.json        Broker commission schedules, by the date each took effect
v1/market/nepse/fees.json              SEBON fee and DP charge
v1/market/nepse/capital-gains-tax.json Capital gains tax on listed shares, by the date each rate took effect
index.html                             The site's front page and API documentation; ENDPOINTS in its script describes each dataset's fields
scripts/check.py                       Checks every file and keeps v1/index.json in step (run before pushing)
scripts/serve.py                       Serves the repo on localhost:8001 with CORS, for a local copy of the tools site
```

## How the files are written

- Every file has `dataset`, `updated` (the date the figures were last checked against their source, `YYYY-MM-DD`) and `sources` (a list of `{ "title", "url" }`; `url` is optional).
- Rates are percentages: `13` means 13%, and `0.015` means 0.015%.
- Amounts are whole rupees. A slab with `"to": null` (or `"up_to": null`) has no upper limit.
- Shares that have no exact decimal are fractions in a string: `"1/3"`, `"2/3"`, `"1/4"`.
- Fiscal-year files are named after the year (`2083-84.json` holds `"fiscal_year": "2083/84"`) and say when the year starts in both calendars: `"starts": { "bs": "2083-04-01", "ad": "2026-07-17" }`.
- Dates for rate changes within a year (`from`, `to`) are AD dates.
- `v1` is the version in the address. A change that would break someone reading the files, such as renaming a field, goes in `v2/` rather than editing `v1/`.

## Adding a fiscal year or changing a rate

1. For a new fiscal year, copy last year's file to the new name and change what the Finance Act changed. Never edit a past year's file except to fix a mistake: people's calculations for that year depend on it.
2. For a rate that changes partway through a year (NEPSE commission, capital gains tax), add a new dated entry to `schedules` and close the previous one, so past trade dates keep their old rate.
3. Set `updated` to today and list the source (Gazette notice, IRD booklet, SEBON circular).
4. Run the check, which also rewrites `v1/index.json`:

```bash
python3 scripts/check.py --write
```

The calculators and the API page pick up a new fiscal year from `v1/index.json` without any change to their pages. A new kind of dataset also needs a checker in `CHECKS` in `scripts/check.py` and an entry in `ENDPOINTS` in `index.html` describing its fields; the check fails until both exist.

## Checks

`scripts/check.py` fails if a file is missing its date or sources, a rate is outside 0–100%, slabs don't join up or don't end with an open top slab, schedules overlap or leave a gap, a fiscal year doesn't match its file name, `v1/index.json` is out of date, or a dataset isn't documented in `index.html`. A file for a new kind of dataset fails until it has its own checker in `CHECKS`. The deploy workflow runs the same check and stops if it fails.

## Run it locally

```bash
python3 scripts/serve.py
```

Then visit <http://localhost:8001>. A local copy of the tools site (on port 8000) reads the files from here instead of from data.rupeshbhandari.com.np.

## Who reads which file

| File | Read by |
| --- | --- |
| `tax/income/*.json` | [Nepal Salary Tax Calculator](https://tools.rupeshbhandari.com.np/finance/salary-tax/) |
| `tax/tds/`, `tax/vat/` | Not yet; the [VAT and TDS Calculator](https://tools.rupeshbhandari.com.np/finance/vat-tds/) still keeps its own copy |
| `tax/depreciation/pools.json` | Not yet; the [Depreciation Schedule](https://tools.rupeshbhandari.com.np/finance/depreciation/) still keeps its own copy |
| `market/nepse/*.json` | Not yet; the [NEPSE Share Calculator](https://tools.rupeshbhandari.com.np/finance/nepse-calculator/) still keeps its own copy |

