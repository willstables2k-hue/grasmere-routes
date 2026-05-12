"""Pull a day's `delivery_runs` Excel from Fresho and push it to Supabase.

Designed to run on a local machine (Windows Task Scheduler, cron, or by
hand). Streamlit Community Cloud can't reliably host a headless browser;
this script runs locally and writes to the same Supabase that Streamlit
Cloud reads from.

Usage
-----

  # First-time exploration — opens Fresho headed, lists every "delivery /
  # run / dispatch / manifest" link on the post-login page so we can identify
  # the exact delivery_runs URL pattern. Run once, then set
  # FRESHO_DELIVERY_URL_TEMPLATE in the .env from what you see.
  python scripts/fresho_pull.py --explore

  # Default: download today's deliveries
  python scripts/fresho_pull.py

  # Specific date
  python scripts/fresho_pull.py --date 2026-04-30

  # Window
  python scripts/fresho_pull.py --from 2026-04-28 --to 2026-04-30

Environment variables
---------------------
  FRESHO_EMAIL                       Same as the KPI dashboard pipeline
  FRESHO_PASSWORD                    Same as the KPI dashboard pipeline
  BRAIN_DB_URL                       Supabase Postgres connection string
  FRESHO_DELIVERY_URL_TEMPLATE       Templated URL for the delivery export
                                     (with `{company_id}` + `{date}` placeholders).
                                     Defaults to a best-guess; override after
                                     running --explore.
  MAPBOX_TOKEN                       Optional; falls back to postcodes.io.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# Allow running this script without `pip install -e .`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grasmere_routes.orders_import import import_orders, parse_orders_excel  # noqa: E402


def _parse_orders_csv(payload: bytes):
    """Adapter: Fresho's 'CSV' format option emits a comma-separated file
    with the same columns as the XLSX. Convert it to a DataFrame that the
    same parser code path expects."""
    import io as _io
    import pandas as _pd
    df = _pd.read_csv(_io.BytesIO(payload))
    buf = _io.BytesIO()
    df.to_excel(buf, index=False)
    return parse_orders_excel(buf.getvalue())

FRESHO_URL = "https://app.fresho.com"

# Force unbuffered stdout so progress shows immediately when running
# from a scheduled task or `run_in_background` Bash call.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
DEFAULT_DELIVERY_URL_TEMPLATE = (
    # Best-guess based on Fresho's order-management URL conventions; override
    # via FRESHO_DELIVERY_URL_TEMPLATE once you confirm the real pattern.
    "/order-management/companies/{company_id}/delivery-runs?date={date}"
)


def _login_and_get_company(page, email: str, password: str) -> str:
    """Reproduces the login flow proven in scripts/fresho_export.py."""
    page.goto(FRESHO_URL, wait_until="networkidle")
    if "login" not in page.url and "signin" not in page.url:
        page.goto(f"{FRESHO_URL}/login", wait_until="networkidle")
    page.fill('input[type="email"], input[name="email"]', email)
    page.fill('input[type="password"], input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(
        lambda url: "login" not in url and "signin" not in url,
        timeout=20000,
    )
    page.wait_for_load_state("domcontentloaded", timeout=10000)
    time.sleep(3)

    def _find_company_id() -> str | None:
        # URL-based path is always safe — try it first.
        m = re.search(r"/companies/([0-9a-f-]{36})", page.url)
        if m:
            return m.group(1)
        # DOM-based fallback: SPA can be mid-navigation, so retry a few times.
        for attempt in range(5):
            try:
                hrefs = page.eval_on_selector_all(
                    'a[href*="/companies/"]',
                    'els => els.map(e => e.getAttribute("href"))',
                )
                for href in hrefs:
                    m = re.search(r"/companies/([0-9a-f-]{36})", href or "")
                    if m:
                        return m.group(1)
                # No matching links yet — wait and try again
                time.sleep(1)
            except Exception:  # context destroyed mid-eval; wait + retry
                time.sleep(1)
                continue
        return None

    company_id = _find_company_id()
    if not company_id:
        try:
            page.wait_for_selector('a[href*="/companies/"]', timeout=10000)
            company_id = _find_company_id()
        except Exception:  # noqa: BLE001
            pass
    if not company_id:
        raise RuntimeError(
            "Could not determine Fresho company ID. Run with --explore --headed."
        )
    return company_id


def explore_links(headed: bool = True) -> None:
    """Open Fresho, jump to the supplier-side dashboard (the KPI dashboard
    proves this URL exists), dump every nav link, screenshot it, and keep
    the browser open for manual inspection.

    All print statements stay ASCII-safe so Windows code-page 1252 doesn't
    crash mid-output.
    """
    from playwright.sync_api import sync_playwright

    email = os.environ.get("FRESHO_EMAIL") or "will@grasmere-farm.co.uk"
    password = os.environ["FRESHO_PASSWORD"]

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=not headed)
        except Exception:
            browser = p.chromium.launch(headless=not headed)
        page = browser.new_context(
            accept_downloads=True, viewport={"width": 1440, "height": 900}
        ).new_page()

        company_id = _login_and_get_company(page, email, password)
        print(f"\n[explore] logged in -> company_id = {company_id}")
        print(f"[explore] post-login URL (customer side): {page.url}")

        # Visit the supplier-side pages we now know exist (from the previous
        # explore run we discovered Operations / Purchases / Sales under
        # /orderanalytics/companies/<id>/). Dump links + screenshot for each.
        pages_to_crawl = [
            ("selling_deliveries", f"{FRESHO_URL}/companies/{company_id}/selling/deliveries"),
            ("supplier_orders", f"{FRESHO_URL}/supplier/orders?company_id={company_id}&mode=sell"),
            ("supplier_reports", f"{FRESHO_URL}/supplier/reports?company_id={company_id}&mode=sell"),
        ]

        for label, url in pages_to_crawl:
            print(f"\n[explore] === {label} ===")
            print(f"[explore] navigating: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(5)
            except Exception as e:  # noqa: BLE001
                print(f"[explore] nav failed: {e}")
                continue
            print(f"[explore] landed at: {page.url}")

            links = page.eval_on_selector_all(
                "a",
                "els => els.map(e => ({"
                "text: (e.innerText || '').trim().slice(0, 80),"
                "href: e.getAttribute('href') || '',"
                "title: e.getAttribute('title') || ''"
                "}))",
            )
            unique = {(L["text"], L["href"]): L for L in links if L["href"]}
            sorted_links = sorted(unique.values(), key=lambda x: x["href"])
            print(f"[explore] {len(sorted_links)} distinct links on {label}:")
            for L in sorted_links:
                t = L["text"][:50]
                h = L["href"]
                title_suffix = f"  title={L['title']!r}" if L["title"] else ""
                print(f"  text={t!r:<54}  href={h}{title_suffix}")

            buttons = page.eval_on_selector_all(
                "button",
                "els => els.map(e => ({"
                "text: (e.innerText || '').trim().slice(0, 80),"
                "title: e.getAttribute('title') || '',"
                "klass: e.getAttribute('class') || ''"
                "}))",
            )
            export_btns = [
                b for b in buttons
                if any(k in (b["text"] + b["title"] + b["klass"]).lower()
                       for k in ("export", "download", "csv", "xlsx", "deliver", "run", "dispatch"))
            ]
            if export_btns:
                print(f"[explore] {len(export_btns)} export-looking buttons on {label}:")
                for B in export_btns:
                    print(f"  text={B['text']!r}  class={B['klass']!r}  title={B['title']!r}")

            shot = ROOT / "scripts" / f"fresho_explore_{label}.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"[explore] screenshot: {shot}")
            except Exception as e:  # noqa: BLE001
                print(f"[explore] screenshot failed: {e}")

            # Form-structure dump — only really informative on the deliveries
            # page, but cheap to do everywhere.
            inputs = page.eval_on_selector_all(
                "input",
                "els => els.map(e => ({"
                "type: e.type, name: e.name, id: e.id, "
                "placeholder: e.placeholder || '', value: e.value || ''"
                "}))",
            )
            interesting_inputs = [
                i for i in inputs
                if i["type"] in ("date", "text", "search") and (i["name"] or i["id"] or i["placeholder"])
            ]
            if interesting_inputs:
                print(f"[explore] {len(interesting_inputs)} form inputs on {label}:")
                for I in interesting_inputs:
                    print(
                        f"  type={I['type']:8s}  name={I['name']!r}  id={I['id']!r}  "
                        f"placeholder={I['placeholder']!r}  value={I['value']!r}"
                    )

            selects = page.eval_on_selector_all(
                "select",
                "els => els.map(e => ({"
                "name: e.name, id: e.id, "
                "options: Array.from(e.options).map(o => ({value: o.value, text: o.text.trim().slice(0,50)}))"
                "}))",
            )
            if selects:
                print(f"[explore] {len(selects)} <select> elements on {label}:")
                for S in selects:
                    print(f"  name={S['name']!r}  id={S['id']!r}")
                    for o in S["options"][:10]:
                        print(f"    option value={o['value']!r}  text={o['text']!r}")
                    if len(S["options"]) > 10:
                        print(f"    ... +{len(S['options']) - 10} more")

        print()
        print("[explore] Browser stays open for 10 minutes.")
        print("[explore] If you spot the delivery_runs export above, paste the URL.")
        try:
            time.sleep(600)
        except KeyboardInterrupt:
            pass
        browser.close()


def pull_one_day(target_date: date, headed: bool = False) -> dict:
    """Log in, drive the /selling/deliveries form for `target_date`, capture
    the downloaded file, parse, push to Supabase via import_orders.

    Form discovery (locked in via --explore on 2026-05-12):
      page   : /companies/<id>/selling/deliveries
      date   : <input id="delivery_date" type="date" value="YYYY-MM-DD">
      format : <select name="format">  options: PDF, CSV
      run    : <select name="delivery_run_code"> options: '' (All Delivery Runs)
               + every legacy run code. We leave it as ''
      button : <button class="col-sm-auto btn btn-primary">Export</button>
    """
    from playwright.sync_api import sync_playwright

    email = os.environ.get("FRESHO_EMAIL") or "will@grasmere-farm.co.uk"
    password = os.environ["FRESHO_PASSWORD"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=not headed)
            except Exception:
                browser = p.chromium.launch(headless=not headed)
            ctx = browser.new_context(
                accept_downloads=True, viewport={"width": 1440, "height": 900}
            )
            page = ctx.new_page()
            company_id = _login_and_get_company(page, email, password)
            print(f"[pull] logged in -> company_id = {company_id}")

            url = f"{FRESHO_URL}/companies/{company_id}/selling/deliveries"
            print(f"[pull] {target_date} -> GET {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector('#delivery_date', timeout=15000)
            page.wait_for_selector('select[name="format"]', timeout=10000)
            time.sleep(1)

            iso = target_date.isoformat()
            print(f"[pull] filling delivery_date = {iso}")
            page.fill('#delivery_date', iso)
            page.select_option('select[name="format"]', 'CSV')

            # Single Export button on this page (class .btn-primary).
            # Clicking it opens a "Delivery runs report" modal that shows
            # "Generating report" then "Done." plus a clickable filename
            # link/button. The download fires only when that link is clicked.
            print("[pull] clicking Export...")
            try:
                page.click('button.btn-primary:has-text("Export")', timeout=10000)
                print("[pull] waiting for report to generate (Done.)...")
                # First wait for the "Done." status — proves the report finished
                page.wait_for_selector('text=Done.', timeout=180000)
                print("[pull] report ready, locating download link...")
                # Try several selector strategies — the link wrapping varies
                candidates = [
                    'a:has-text("delivery_runs")',
                    'a[href*="delivery_runs"]',
                    'a[download]',
                    '[role="link"]:has-text("delivery_runs")',
                    'button:has-text("delivery_runs")',
                    'a:has-text(".csv")',
                ]
                link = None
                for sel in candidates:
                    try:
                        loc = page.locator(sel).first
                        loc.wait_for(state="visible", timeout=2000)
                        link = loc
                        print(f"[pull] matched selector: {sel}")
                        break
                    except Exception:
                        continue
                if link is None:
                    # Diagnostic dump
                    diag = page.eval_on_selector_all(
                        'a, button, [role="link"], [role="button"], div',
                        "els => els.map(e => ({"
                        "tag: e.tagName, "
                        "text: (e.innerText||'').trim().slice(0,80), "
                        "href: e.getAttribute('href')||'', "
                        "klass: (e.getAttribute('class')||'').slice(0,50), "
                        "download: e.hasAttribute('download')"
                        "})).filter(x => x.text.includes('delivery_runs') || x.text.includes('.csv') || x.href.includes('delivery_runs'))",
                    )
                    print("[pull] elements containing 'delivery_runs' or '.csv':")
                    for d in diag[:20]:
                        print(f"  {d}")
                    raise RuntimeError("download link not found in modal")
                print("[pull] clicking download link...")
                with page.expect_download(timeout=30000) as dl:
                    link.click()
                download = dl.value
                fname = download.suggested_filename
                out = tmp_dir / fname
                download.save_as(str(out))
                print(f"[pull] downloaded: {fname}")
                payload = out.read_bytes()
                ext = out.suffix.lower()
            except Exception as e:  # noqa: BLE001
                shot = ROOT / "scripts" / f"failed_{target_date}.png"
                try:
                    page.screenshot(path=str(shot), full_page=True)
                    print(f"[pull] screenshot saved: {shot}")
                except Exception:
                    pass
                browser.close()
                raise RuntimeError(f"Export failed: {e}")
            browser.close()

    # Parse — Fresho's "CSV" option historically downloads .xlsx (the file
    # already in the repo from a manual export is .xlsx). Detect by extension.
    if ext == ".csv":
        rows, parse_errors = _parse_orders_csv(payload)
    else:
        rows, parse_errors = parse_orders_excel(payload)
    print(f"[pull] parsed {len(rows)} orders ({ext}) · {len(parse_errors)} parse errors")
    if not rows:
        return {"orders_inserted": 0, "orders_updated": 0, "rows_parsed": 0}
    summary = import_orders(rows)
    print(
        f"[pull] {summary.orders_inserted} new · {summary.orders_updated} updated · "
        f"{summary.customers_created} new customers · {summary.customers_geocoded} geocoded · "
        f"{summary.customers_missing_geocode} missing geocode"
    )
    return {
        "orders_inserted": summary.orders_inserted,
        "orders_updated": summary.orders_updated,
        "customers_created": summary.customers_created,
        "rows_parsed": summary.rows_parsed,
        "errors": summary.errors,
        "parse_errors": parse_errors,
    }


def _date_range(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull delivery_runs from Fresho into Supabase"
    )
    parser.add_argument(
        "--explore",
        action="store_true",
        help="Open Fresho headed and list candidate delivery URLs (no download)",
    )
    parser.add_argument("--date", help="Single date YYYY-MM-DD (defaults to today)")
    parser.add_argument("--from", dest="from_", help="Range start YYYY-MM-DD")
    parser.add_argument("--to", dest="to_", help="Range end YYYY-MM-DD")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    args = parser.parse_args()

    if not os.environ.get("FRESHO_PASSWORD"):
        print("[error] FRESHO_PASSWORD not set", file=sys.stderr)
        return 2
    # FRESHO_EMAIL is optional — defaults to will@grasmere-farm.co.uk to match
    # the KPI dashboard pipeline's hard-coded login.

    if args.explore:
        # --explore doesn't touch the DB, so no BRAIN_DB_URL needed
        explore_links(headed=True)
        return 0

    if not os.environ.get("BRAIN_DB_URL"):
        print("[error] BRAIN_DB_URL not set (target Supabase connection)", file=sys.stderr)
        return 2

    if args.from_ and args.to_:
        start = datetime.strptime(args.from_, "%Y-%m-%d").date()
        end = datetime.strptime(args.to_, "%Y-%m-%d").date()
        for d in _date_range(start, end):
            try:
                pull_one_day(d, headed=args.headed)
            except Exception as e:  # noqa: BLE001
                print(f"[pull] {d}: {e}")
        return 0

    target = (
        datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    )
    try:
        pull_one_day(target, headed=args.headed)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"[pull] failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
