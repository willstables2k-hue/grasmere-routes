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
        m = re.search(r"/companies/([0-9a-f-]{36})", page.url)
        if m:
            return m.group(1)
        hrefs = page.eval_on_selector_all(
            'a[href*="/companies/"]',
            'els => els.map(e => e.getAttribute("href"))',
        )
        for href in hrefs:
            m = re.search(r"/companies/([0-9a-f-]{36})", href or "")
            if m:
                return m.group(1)
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

        # The post-login page is Fresho's customer-ordering portal. The KPI
        # dashboard pipeline proves that /orderanalytics/companies/<id>/sales
        # works for the supplier side, so jump there.
        supplier_url = f"{FRESHO_URL}/orderanalytics/companies/{company_id}/sales"
        print(f"[explore] navigating to supplier side: {supplier_url}")
        try:
            page.goto(supplier_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(5)
        except Exception as e:  # noqa: BLE001
            print(f"[explore] supplier nav failed: {e}")
        print(f"[explore] supplier URL landed at: {page.url}\n")

        # Dump EVERY link (no keyword filter). Sort by href for stable output.
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
        print(f"[explore] {len(sorted_links)} distinct nav links on the supplier dashboard:")
        for L in sorted_links:
            print(f"  text={L['text']!r}")
            print(f"    href={L['href']}")
            if L["title"]:
                print(f"    title={L['title']}")
            print()

        # Also dump buttons that might be exports (no <a> required)
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
            print(f"[explore] {len(export_btns)} export-looking buttons:")
            for B in export_btns:
                print(f"  text={B['text']!r}  class={B['klass']!r}  title={B['title']!r}")
            print()

        screenshot = ROOT / "scripts" / "fresho_explore_screenshot.png"
        page.screenshot(path=str(screenshot), full_page=True)
        print(f"[explore] screenshot saved at {screenshot}")
        print()
        print("[explore] Browser stays open for 10 minutes.")
        print("[explore] Navigate to wherever you normally export the delivery_runs")
        print("[explore] file. Note the URL in the address bar and the export button.")
        try:
            time.sleep(600)
        except KeyboardInterrupt:
            pass
        browser.close()


def _try_download(page, tmp_dir: Path) -> Path | None:
    """Click any plausible download/export button and capture the file."""
    selectors = [
        '.test-download-button',
        'button:has-text("XLSX")',
        'a:has-text("XLSX")',
        'button:has-text("Excel")',
        'button:has-text("Export")',
        'a:has-text("Export")',
        'button:has-text("Download")',
        'a:has-text("Download")',
        '[data-testid*="export"]',
        '[data-testid*="download"]',
        '[title*="Export"]',
    ]
    for sel in selectors:
        try:
            with page.expect_download(timeout=15000) as dl:
                page.click(sel, timeout=3000)
            d = dl.value
            out = tmp_dir / d.suggested_filename
            d.save_as(str(out))
            print(f"  ✓ downloaded ({sel}): {d.suggested_filename}")
            return out
        except Exception:
            continue
    return None


def pull_one_day(target_date: date, headed: bool = False) -> dict:
    """Log in, navigate to the delivery_runs page for `target_date`, download,
    parse, push to Supabase via import_orders. Returns the import summary."""
    from playwright.sync_api import sync_playwright

    email = os.environ.get("FRESHO_EMAIL") or "will@grasmere-farm.co.uk"
    password = os.environ["FRESHO_PASSWORD"]
    template = os.environ.get(
        "FRESHO_DELIVERY_URL_TEMPLATE", DEFAULT_DELIVERY_URL_TEMPLATE
    )

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
            print(f"[pull] logged in · company_id = {company_id}")

            url_path = template.format(company_id=company_id, date=target_date.isoformat())
            url = FRESHO_URL + (url_path if url_path.startswith("/") else "/" + url_path)
            print(f"[pull] {target_date} → GET {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(4)

            downloaded = _try_download(page, tmp_dir)
            if not downloaded:
                shot = tmp_dir / f"failed_{target_date}.png"
                page.screenshot(path=str(shot), full_page=True)
                persist = ROOT / "scripts" / shot.name
                shutil.copy(str(shot), str(persist))
                browser.close()
                raise RuntimeError(
                    f"No download button found at {url}. Screenshot: {persist}\n"
                    "Run with --explore to identify the right URL pattern."
                )
            payload = downloaded.read_bytes()
            browser.close()

    rows, parse_errors = parse_orders_excel(payload)
    print(f"[pull] parsed {len(rows)} orders · {len(parse_errors)} parse errors")
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
