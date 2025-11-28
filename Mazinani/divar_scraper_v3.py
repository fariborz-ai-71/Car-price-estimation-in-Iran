import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random
import os
import sys
import json

START_PRICE = 100_000_000
END_PRICE = 560_000_000
STEP_PRICE = 20_000_000
BASE_URL_TEMPLATE = "url"
MAX_ADS_TO_COLLECT = 10000
OUTPUT_CSV = "divar_ads.csv"
HEADLESS = False
MAX_CONCURRENT_TABS = 10

COLUMNS = [
    "title", "mileage_km", "year", "color",
    "brand_type", "insurance_until", "gearbox", "fuel_type", "price",
    "document_status", "engine_status", "chassis_status",
    "body_status", "description",
]


def clean_text(s):
    if s is None: return ""
    return " ".join(s.strip().split())


def get_seen_urls():
    if os.path.exists(OUTPUT_CSV):
        try:
            df_existing = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig", usecols=['url'])
            urls = set(df_existing['url'].dropna().astype(str).apply(lambda x: x.strip()).tolist())
            print(f"📂 Database Loaded: {len(urls)} ads already exist.")
            return urls
        except:
            return set()
    return set()


async def block_resources(route):
    """بلاک کردن تمام منابع غیرضروری برای کاهش مصرف ترافیک"""
    resource_type = route.request.resource_type
    url = route.request.url

    if resource_type in ["image", "media", "font"]:
        await route.abort()
    elif any(blocked in url for blocked in [
        "google-analytics", "googletagmanager", "doubleclick",
        "analytics", "tracking", "ads", "advertisement",
        "facebook.com", "twitter.com", "cdn.segment"
    ]):
        await route.abort()
    else:
        await route.continue_()


async def extract_ad_safe(ad_url, context, delay_start):
    await asyncio.sleep(delay_start)

    page = None
    result = {"url": ad_url}
    for col in COLUMNS: result.setdefault(col, "")

    try:
        page = await context.new_page()
        await page.route("**/*", block_resources)

        await page.goto(ad_url, wait_until="domcontentloaded", timeout=45000)

        title_el = await page.wait_for_selector("h1.kt-page-title__title", state="visible", timeout=20000)
        result["title"] = clean_text(await title_el.text_content())

        subtitle_el = await page.query_selector("div.kt-page-title__subtitle")
        result["location_time"] = clean_text(await subtitle_el.text_content()) if subtitle_el else ""

        group_cells = await page.query_selector_all("td.kt-group-row-item--info-row")
        if len(group_cells) >= 3:
            result["mileage_km"] = clean_text(await group_cells[0].text_content())
            result["year"] = clean_text(await group_cells[1].text_content())
            result["color"] = clean_text(await group_cells[2].text_content())

        other_specs = {}
        rows = await page.query_selector_all("div.kt-base-row--large")
        for row in rows:
            row_text = await row.inner_text()
            if not row_text: continue
            lines = row_text.split('\n')
            if len(lines) >= 2:
                key, val = lines[0].strip(), lines[-1].strip()
                if "برند" in key:
                    result["brand_type"] = val
                elif "بیمه" in key:
                    result["insurance_until"] = val
                elif "گیربکس" in key:
                    result["gearbox"] = val
                elif "سوخت" in key:
                    result["fuel_type"] = val
                elif "قیمت" in key:
                    result["price"] = val
                elif "سند" in key:
                    result["document_status"] = val
                elif "مالک" in key:
                    result["owner_count"] = val
                elif "شاسی" in key:
                    result["chassis_status"] = val
                elif "موتور" in key:
                    result["engine_status"] = val
                elif "بدنه" in key:
                    result["body_status"] = val
                else:
                    other_specs[key] = val
        result["other_specs"] = json.dumps(other_specs, ensure_ascii=False)

        desc_el = await page.query_selector("section.post-page__section--padded .kt-description-row__text--primary")
        result["description"] = clean_text(await desc_el.text_content()) if desc_el else ""

    except Exception as e:
        print(f"      ⚠️ Error extracting {ad_url}: {str(e)[:50]}")
    finally:
        if page:
            await page.close()

    return result


async def main():
    seen_urls = get_seen_urls()
    write_header = not os.path.exists(OUTPUT_CSV)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)

        context = await browser.new_context(
            viewport={'width': 1366, 'height': 1000},
            bypass_csp=True,
            java_script_enabled=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        list_page = await context.new_page()
        await list_page.route("**/*", block_resources)

        current_min_price = START_PRICE

        while current_min_price < END_PRICE:
            current_max_price = current_min_price + STEP_PRICE

            current_list_url = f"{BASE_URL_TEMPLATE}&price={current_min_price}-{current_max_price}"

            print(f"\n🔵 >>> Switching to Price Range: {current_min_price:,} - {current_max_price:,} Tomans")
            print(f"🔗 URL: {current_list_url}")

            try:
                await list_page.goto(current_list_url, wait_until="domcontentloaded")
                await list_page.wait_for_timeout(5000)
            except:
                print("Error loading list page, trying next range...")
                current_min_price += STEP_PRICE
                continue

            no_new_ads_counter = 0

            for scroll_step in range(15):
                if len(seen_urls) >= MAX_ADS_TO_COLLECT:
                    print("🎉 Reached Target Collection Size!")
                    await browser.close()
                    return

                current_batch_urls = []
                anchors = await list_page.query_selector_all("a[href^='/v/']")

                for a in anchors:
                    href = await a.get_attribute("href")
                    if href:
                        full_url = f"https://divar.ir{href}".strip()
                        if full_url not in seen_urls:
                            current_batch_urls.append(full_url)
                            seen_urls.add(full_url)

                if current_batch_urls:
                    print(f"   found {len(current_batch_urls)} new ads in this range. Extracting...")
                    no_new_ads_counter = 0

                    chunk_size = MAX_CONCURRENT_TABS
                    for i in range(0, len(current_batch_urls), chunk_size):
                        chunk = current_batch_urls[i:i + chunk_size]

                        print(f"      🔄 Processing {len(chunk)} ads in parallel...")

                        # تاخیر 1 ثانیه بین باز کردن هر تب
                        tasks = [
                            extract_ad_safe(url, context, idx * 1.0)
                            for idx, url in enumerate(chunk)
                        ]
                        results = await asyncio.gather(*tasks)

                        valid_results = [r for r in results if r and r["title"]]
                        if valid_results:
                            df = pd.DataFrame(valid_results, columns=COLUMNS)
                            df.to_csv(OUTPUT_CSV, mode='a', header=write_header, index=False, encoding="utf-8-sig")
                            write_header = False
                            print(f"   ✅ Saved {len(valid_results)}/{len(chunk)}. Total DB: {len(seen_urls)}")
                        else:
                            print(f"   ⚠️ No valid results from this chunk")

                        await asyncio.sleep(0.5)
                else:
                    no_new_ads_counter += 1
                    print(f"   No new ads ({no_new_ads_counter})...")

                if no_new_ads_counter >= 3:
                    print("   ⛔ End of this price range. Moving to next...")
                    break

                await list_page.keyboard.press("End")
                await asyncio.sleep(1.5)

            current_min_price += STEP_PRICE
            await asyncio.sleep(2)

        print("Done. All ranges scanned.")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())