
#Meghdad,Jokar67@gmail.com

import asyncio
import random
from playwright.async_api import async_playwright
import pandas as pd
import os
import sys

# --- CONFIGURATION ---
BASE_LIST_URL = "https://bama.ir/car"
MAX_ADS = 1000000
DELAY_MIN = 5
DELAY_MAX = 10
SCROLL_WAIT_TIME = 30 # Minimum 30 seconds wait after each scroll for new data to load
OUTPUT_CSV = "bama_ads.csv"
HEADLESS = True
# List of all expected columns for consistent CSV structure
COLUMNS = [
    "عنوان", "سال تولید", "گیربکس", "زمان آگهی", "موقعیت", "قیمت", "واحد پول",
    "شماره تماس", "کارکرد", "نوع سوخت", "وضعیت بدنه", "رنگ بدنه",
    "رنگ داخلی", "حجم موتور", "پیشرانه", "شتاب", "مصرف ترکیبی",
    "نزدیک‌ترین کارشناسی‌ها", "توضیحات", "url"
]

def clean_text(s):
    """Cleans text by stripping whitespace and joining on single spaces."""
    if s is None:
        return ""
    return " ".join(s.strip().split())

async def extract_ad_data(page):
    """Extracts detailed data from the open ad modal page."""
    result = {}
    try:
        # Title
        title_el = await page.query_selector("h1.bama-ad-detail-title__title")
        result["عنوان"] = clean_text(await title_el.text_content()) if title_el else ""

        # Year and Gearbox
        subtitles = await page.query_selector_all("div.bama-ad-detail-title__subtitle")
        # Selector for year might need adjustment if class names change frequently
        year_el = await page.query_selector("span.bama-ad-detail-title__subtitle[data-v-334b8c21]") 
        result["سال تولید"] = clean_text(await year_el.text_content()) if year_el else ""
        result["گیربکس"] = clean_text(await subtitles[1].text_content()) if len(subtitles) > 1 else ""

        # Ad Time and Location
        time_el = await page.query_selector("span.bama-ad-detail-title__ad-time")
        result["زمان آگهی"] = clean_text(await time_el.text_content()) if time_el else ""
        loc_el = await page.query_selector("span.address-text")
        result["موقعیت"] = clean_text(await loc_el.text_content()) if loc_el else ""

        # Price and Currency
        price_el = await page.query_selector("span.bama-ad-detail-price__price-text")
        currency_el = await page.query_selector("span.bama-ad-detail-price__price-toman")
        result["قیمت"] = clean_text(await price_el.text_content()) if price_el else ""
        result["واحد پول"] = clean_text(await currency_el.text_content()) if currency_el else ""

        # Phone Number
        phone_el = await page.query_selector("div.bama-call-to-seller span:nth-child(2)")
        result["شماره تماس"] = clean_text(await phone_el.text_content()) if phone_el else ""

        # Main Details (Mileage, Fuel Type, Body Status, etc.)
        details = await page.query_selector_all("div.bama-vehicle-detail-with-icon__detail-holder")
        for d in details:
            label_el = await d.query_selector("span")
            value_el = await d.query_selector("p")
            if label_el and value_el:
                key = clean_text(await label_el.text_content())
                val = clean_text(await value_el.text_content())
                if key == "کارکرد": result["کارکرد"] = val
                elif key == "نوع سوخت": result["نوع سوخت"] = val
                elif key == "وضعیت بدنه": result["وضعیت بدنه"] = val
                elif key == "رنگ بدنه": result["رنگ بدنه"] = val
                elif key == "رنگ داخلی": result["رنگ داخلی"] = val

        # Technical Specs
        tech_specs = await page.query_selector_all("div.bama-vehicle-detail-with-link__row")
        for spec in tech_specs:
            key_el = await spec.query_selector("span.bama-vehicle-detail-with-link__row-title")
            val_el = await spec.query_selector("span.bama-vehicle-detail-with-link__row-text")
            if key_el and val_el:
                key = clean_text(await key_el.text_content())
                val = clean_text(await val_el.text_content())
                if key == "حجم موتور": result["حجم موتور"] = val
                elif key == "پیشرانه": result["پیشرانه"] = val
                elif key == "شتاب": result["شتاب"] = val
                elif key == "مصرف ترکیبی": result["مصرف ترکیبی"] = val

        # Inspection and Description
        inspection_el = await page.query_selector("button.car-inspection-button span.car-inspection-button-title")
        result["نزدیک‌ترین کارشناسی‌ها"] = clean_text(await inspection_el.text_content()) if inspection_el else ""
        # The selector for description based on data attribute
        desc_el = await page.query_selector("p[data-v-8d081842]")
        result["توضیحات"] = clean_text(await desc_el.text_content()) if desc_el else ""

    except Exception as e:
        print(f"Unexpected error in data extraction: {e}", file=sys.stderr)

    return result

def get_seen_urls():
    """Reads the existing CSV file to get a set of already-scraped URLs."""
    if os.path.exists(OUTPUT_CSV):
        try:
            df_existing = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig", usecols=['url'])
            return set(df_existing['url'].dropna().astype(str).tolist())
        except Exception as e:
            print(f"Warning: Existing CSV file found but failed to read URLs: {e}. Scraping from scratch.", file=sys.stderr)
            return set()
    return set()

# --- Main function scrape_list with new logic ---
async def scrape_list(max_ads=MAX_ADS):
    collected_count = 0
    
    seen_urls = get_seen_urls()
    initial_seen_count = len(seen_urls)
    print(f"Existing URLs in file: {initial_seen_count} previous ads.")

    write_header = not os.path.exists(OUTPUT_CSV)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()

        print(f"Starting scraping from: {BASE_LIST_URL}")
        await page.goto(BASE_LIST_URL, wait_until="networkidle", timeout=0)
        
        scrolled_times = 0

        while collected_count + initial_seen_count < max_ads:
            
            # --- 1. Identify existing ads in the Viewport ---
            all_ad_elements = await page.query_selector_all("a.bama-ad.listing")
            current_total_ads_on_page = len(all_ad_elements)
            
            # Find new ads that have not been processed yet (their link is not in seen_urls)
            new_ads_to_process = []
            
            for ad_elem in all_ad_elements:
                href = await ad_elem.get_attribute("href")
                full_url = f"https://bama.ir{href}"
                
                if full_url not in seen_urls:
                    # We store the element (ad_elem) directly to click on it later
                    new_ads_to_process.append((ad_elem, full_url))
            
            print(f"Ads on the page (Total): {current_total_ads_on_page}. New ads to process: {len(new_ads_to_process)}.")
            
            # --- 2. Process existing new ads (before scroll) ---
            
            if new_ads_to_process:
                
                print(f"Processing {len(new_ads_to_process)} new ads before scroll.")
                
                for ad_elem, ad_url in new_ads_to_process:
                    if collected_count + initial_seen_count >= max_ads:
                        print("Reached maximum allowed ads (MAX_ADS). Stopping process.")
                        await browser.close()
                        return
                    
                    try:
                        current_total = collected_count + initial_seen_count
                        print(f"🔹 Processing ad ({current_total + 1}/{max_ads}): {ad_url}")
                        
                        # Open the ad modal
                        await ad_elem.click()
                        # Wait for the modal to fully load
                        await page.wait_for_selector("div.bama-ad-detail-modal__close-button", timeout=10000)

                        # Extract data
                        data = await extract_ad_data(page)
                        data["url"] = ad_url
                        
                        # --- APPEND DATA TO CSV IMMEDIATELY ---
                        single_df = pd.DataFrame([data], columns=COLUMNS)
                        single_df.to_csv(
                            OUTPUT_CSV, 
                            mode='a',
                            header=write_header,
                            index=False,
                            encoding="utf-8-sig"
                        )
                        
                        write_header = False 
                        collected_count += 1
                        seen_urls.add(ad_url) # Add to the set of seen URLs
                        
                        print(f"Ad successfully saved to file. New total: {collected_count + initial_seen_count}")

                        # Close the modal and add delay
                        close_btn = await page.query_selector("div.bama-ad-detail-modal__close-button")
                        if close_btn:
                            await close_btn.click()
                            # Random delay between ad processing
                            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                    except Exception as e:
                        print(f"Error processing ad {ad_url}: {e}", file=sys.stderr)
                        # Attempt to close modal in case of error
                        try:
                            close_btn = await page.query_selector("div.bama-ad-detail-modal__close-button")
                            if close_btn: await close_btn.click()
                        except: pass
                        await asyncio.sleep(1) 
                
                # Continue the while loop to check for new ads that might have loaded during this batch processing
                continue 

            # --- 3. If no new ads found in the viewport, scroll down ---
            
            print(f"No new ads found to process. Scrolling down (Scroll number {scrolled_times + 1})...")
            
            previous_height = await page.evaluate("() => document.body.scrollHeight")
            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            scrolled_times += 1
            
            # --- 4. 30-second wait logic for complete loading ---
            
            print(f"Waiting a minimum of {SCROLL_WAIT_TIME} seconds for new data to load...")
            
            # This loop waits for a minimum of 30 seconds, checking in the meantime if new ads have loaded.
            # If the total number of ads remains constant during these 30 seconds, it means loading is complete.
            
            current_ad_count = current_total_ads_on_page
            stable_count = 0
            
            for i in range(SCROLL_WAIT_TIME):
                await asyncio.sleep(1) # Wait 1 second
                
                new_ad_count = len(await page.query_selector_all("a.bama-ad.listing"))
                
                if new_ad_count > current_ad_count:
                    print(f"New ad loaded. Count: {new_ad_count}. Waiting for stabilization...")
                    current_ad_count = new_ad_count
                    stable_count = 0 # Reset stabilization counter
                elif new_ad_count == current_ad_count and new_ad_count > previous_height:
                    stable_count += 1 # Ad count remained stable
                    if stable_count >= 5: # If stable for 5 consecutive seconds (or more), assume loading is complete
                        print(f"New loading after scroll stabilized. ({new_ad_count} total ads).")
                        break
                
                if i == SCROLL_WAIT_TIME - 1:
                    print("New data loading completed after 30 seconds wait (or no new data loaded).")

            new_height = await page.evaluate("() => document.body.scrollHeight")
            
            # --- 5. Final stop condition ---
            if new_height == previous_height and current_ad_count == current_total_ads_on_page:
                print("End of page. No new content to load.")
                break
                
        print(f"Process complete. {collected_count} new ads collected. Total: {collected_count + initial_seen_count}")
        await browser.close()


def main():
    asyncio.run(scrape_list())

if __name__ == "__main__":
    main()
