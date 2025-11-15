#Meghdad,Jokar67@gmail.com

import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random
import os
import sys
import json # For handling the other_specs field

# --- CONFIGURATION ---
BASE_LIST_URL = "https://divar.ir/s/tehran/auto"
MAX_ADS_PER_BATCH = 10000       # Maximum new ads to process per page
PAGES_TO_SCAN = 10000           # Total number of pages to scan
DELAY_BETWEEN_ADS = (2, 5) # Random delay between ads, in seconds
OUTPUT_CSV = "divar_ads.csv"
HEADLESS = True             # True: run in background (recommended)

# Define the complete list of columns (column order in the final file)
COLUMNS = [
    "url", "title", "location_time", "mileage_km", "year", "color",
    "brand_type", "insurance_until", "gearbox", "fuel_type", "price",
    "document_status", "owner_count", "engine_status", "chassis_status",
    "body_status", "score_0", "description", "other_specs"
]

def clean_text(s):
    """Cleans text by stripping extra whitespace."""
    if s is None:
        return ""
    return " ".join(s.strip().split())

def get_seen_urls():
    """Reads existing URLs from the CSV file to prevent duplication."""
    if os.path.exists(OUTPUT_CSV):
        try:
            df_existing = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig", usecols=['url'])
            return set(df_existing['url'].dropna().astype(str).tolist())
        except Exception as e:
            print(f"Warning: Existing CSV file found but failed to read addresses: {e}. Scraping continues.", file=sys.stderr)
            return set()
    return set()

async def extract_ad(ad_url, browser):
    """Extracts data from a single ad with modified selectors."""
    ad_page = await browser.new_page()
    await ad_page.route("**/*", lambda route: route.abort() if route.request.resource_type == "image" else route.continue_())
    result = {"url": ad_url}
    
    # Ensure all keys are present in the result dictionary
    for col in COLUMNS:
        result.setdefault(col, "")
        
    try:
        await ad_page.goto(ad_url, wait_until="domcontentloaded", timeout=0)

        # Wait for full load (spinner to hide and title to appear)
        spinner_selector = "div.kt-spinner"
        first_data_selector = "h1.kt-page-title__title"
        for _ in range(0, 60):
            spinner = await ad_page.query_selector(spinner_selector)
            first_data = await ad_page.query_selector(first_data_selector)
            if spinner and (await spinner.is_visible()):
                try:
                    await spinner.wait_for_element_state("hidden", timeout=5000)
                except:
                    pass
            if first_data and (await first_data.is_visible()):
                break
            await asyncio.sleep(0.5)

        # Title and subtitle
        title_el = await ad_page.query_selector(first_data_selector)
        result["title"] = clean_text(await title_el.text_content()) if title_el else ""
        subtitle_el = await ad_page.query_selector("div.kt-page-title__subtitle")
        result["location_time"] = clean_text(await subtitle_el.text_content()) if subtitle_el else ""

        # Specs table (mileage, year, color)
        group_cells = await ad_page.query_selector_all("td.kt-group-row-item--info-row")
        if group_cells and len(group_cells) >= 3:
            result["mileage_km"] = clean_text(await group_cells[0].text_content()) if len(group_cells) > 0 else ""
            result["year"] = clean_text(await group_cells[1].text_content()) if len(group_cells) > 1 else ""
            result["color"] = clean_text(await group_cells[2].text_content()) if len(group_cells) > 2 else ""

        # Additional specs rows
        other_specs = {}
        rows = await ad_page.query_selector_all("div.kt-base-row--large")
        for row in rows:
            key_el = await row.query_selector(".kt-base-row__title, .kt-unexpandable-row__title")
            
            # Value search must include all three possible states (p.value, p.title, a.action)
            val_el = await row.query_selector(".kt-base-row__value, .kt-unexpandable-row__value, .kt-unexpandable-row__action")
            
            if key_el and val_el:
                key = clean_text(await key_el.text_content())
                val = clean_text(await val_el.text_content())
                
                # Fields specified in the main columns
                if "برند" in key or "تیپ" in key:
                    result["brand_type"] = val
                elif "مهلت بیمه" in key or "بیمه" in key:
                    result["insurance_until"] = val
                elif "گیربکس" in key:
                    result["gearbox"] = val
                elif "نوع سوخت" in key or "سوخت" in key:
                    result["fuel_type"] = val
                elif "قیمت" in key:
                    result["price"] = val
                elif "سند" in key:
                    result["document_status"] = val
                elif "تعداد مالک" in key or "مالک" in key:
                    result["owner_count"] = val
                else:
                    # Any other field goes to other_specs
                    other_specs[key] = val
        
        # Save miscellaneous specs as a JSON string
        result["other_specs"] = json.dumps(other_specs, ensure_ascii=False) if other_specs else ""

        # Parts status (engine, chassis, body)
        scores = await ad_page.query_selector_all("div.kt-score-row__score")
        if scores:
            result["engine_status"] = clean_text(await scores[0].text_content()) if len(scores) > 0 else ""
            result["chassis_status"] = clean_text(await scores[1].text_content()) if len(scores) > 1 else ""
            result["body_status"] = clean_text(await scores[2].text_content()) if len(scores) > 2 else ""
            if len(scores) == 1:
                result["score_0"] = clean_text(await scores[0].text_content())

        # --- Description extraction fix (PWA issue fix) ---
        # More specific search below the "توضیحات" title
        desc_el = await ad_page.query_selector("section.post-page__section--padded .kt-description-row__text--primary")
        result["description"] = clean_text(await desc_el.text_content()) if desc_el else ""

    except Exception as e:
        print(f"General error during ad extraction for {ad_url}: {e}", file=sys.stderr)
    finally:
        await ad_page.close()
    return result

async def scrape_list_and_save(max_ads_per_batch=MAX_ADS_PER_BATCH, pages_to_scan=PAGES_TO_SCAN):
    
    # 1. Read previous URLs and set header flag
    seen_urls = get_seen_urls()
    print(f"Existing URLs in file: {len(seen_urls)} previous ads.")
    initial_count = len(seen_urls)
    collected_count = 0
    write_header = not os.path.exists(OUTPUT_CSV)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type == "image" else route.continue_())

        try:
            for page_num in range(1, pages_to_scan + 1):
                list_url = BASE_LIST_URL.format(page_num)
                print(f"\n🔹 Opening list page: {list_url} (Page {page_num}/{pages_to_scan})")
                await page.goto(list_url, wait_until="domcontentloaded", timeout=0)

                hrefs = []
                for _ in range(0, 30):
                    anchors = await page.query_selector_all("a[href^='/v/'], a[href^='/p/']")
                    if anchors:
                        for a in anchors:
                            href = await a.get_attribute("href")
                            if href:
                                full = href if href.startswith("http") else f"https://divar.ir{href}"
                                if full not in seen_urls:
                                    hrefs.append(full)
                    if hrefs:
                        break
                    await asyncio.sleep(1)

                print(f"  🔹 Number of new and unique URLs on page {page_num}: {len(hrefs)}")

                batch_processed_count = 0
                for href in hrefs:
                    if batch_processed_count >= max_ads_per_batch:
                        print(f"Reached the limit of {max_ads_per_batch} new ads for this page, moving to the next page")
                        break
                    
                    current_total = collected_count + initial_count
                    print(f"   🔹 Processing ad ({current_total + 1} / Page Limit: {initial_count + MAX_ADS_PER_BATCH*PAGES_TO_SCAN}): {href}")
                    
                    ad_data = await extract_ad(href, browser)
                    
                    if ad_data["title"] or ad_data["description"]: # If data is meaningful
                        
                        # --- Immediate data saving ---
                        single_df = pd.DataFrame([ad_data], columns=COLUMNS)
                        single_df.to_csv(
                            OUTPUT_CSV, 
                            mode='a',          # 'a' mode for Append
                            header=write_header,   # Write header only for the first time
                            index=False,
                            encoding="utf-8-sig"
                        )
                        
                        write_header = False 
                        collected_count += 1
                        batch_processed_count += 1
                        print(f"New ad successfully saved. New total: {collected_count + initial_count}")
                    else:
                         print(f"Ad was missing essential information (title/description): {href}")

                    seen_urls.add(href)
                    await asyncio.sleep(random.uniform(*DELAY_BETWEEN_ADS))

            print(f"\nPage scanning completed. {collected_count} new ads collected. Grand total: {collected_count + initial_count}")
            await browser.close()

        except Exception as e:
            print(f"General error during scraping: {e}", file=sys.stderr)
            await browser.close()
            # We keep this raise to display the stack trace if a serious error occurred
            raise

def save_after_run_demo():
    asyncio.run(scrape_list_and_save())
    print(f"Summary: Data has been saved to the file {OUTPUT_CSV}.")

if __name__ == "__main__":
    save_after_run_demo()
