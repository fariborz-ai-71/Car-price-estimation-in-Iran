import pandas as pd
import re
import os
import sys

# --- 1. Comprehensive Regex Pattern for Filtering ---
# This pattern includes all expressions related to installment, dealership, referral, negotiated price, zero kilometer, exchange, and services.
# --- ۱. تعریف کلمات کلیدی به صورت ساختاریافته در یک دیکشنری ---
# این ساختار ویرایش (اضافه/حذف) کلمات را آسان‌تر می‌کند.
FILTER_GROUPS = {
    # گروه ۱: فروش قسطی / اعتباری / تسهیلات
    "installment_credit": [
        "قسط",
        "اقساط",
        "اقساطی",
        "اقسلط",
        "تسهیلات",
        "لیزینگ",
        "شرایطی",
        "اعتباری",
        "بازپرداخت",
    ],
    # گروه ۲: آگهی نمایندگی / سازمانی / گالری
    "agency_corporate": [
        "نمایندگی",
        "نمایشگاه",
        "نمایشگاهی",
        "گالری",
        "اتو[A-Za-zآ-ی]*",
        "سازمانی",
        "شرکتی",
        "عاملیت",
        r"عضو\s?رسمی",
    ],
    # گروه ۳: حواله‌ای / اسناد
    "document_referral": [
        "حواله",
        r"دعوت\s?نامه",
        r"سند.?آماده",
        r"سند.?آزاد",
        r"ثبت.?نام",
        "قرارداد",
    ],
    # گروه ۴: قیمت نامشخص / توافقی
    "unknown_price": ["توافقی", "فقط تماس", "تماس بگیرید", "قیمت روز"],
    # گروه ۵: آگهی تبلیغاتی / عمده
    "commercial_bulk": [
        "محصولات",
        "عمده",
        "همکار",
        "تولیدات",
        "مجموعه",
        "شرکت",
        "سازمان",
    ],
    # گروه ۶: خودرو صفر کیلومتر / تحویل فوری
    "zero_km_immediate": [
        r"صفر\s?کیلومتر",
        "صفر",
        "تحویل فوری",
        "موجودی",
        "آماده تحویل",
    ],
    # گروه ۷: معاوضه و تهاتر
    "swap_barter": ["معاوضه", "تهاتر"],
    # گروه ۸: مزایده و حراج
    "auction_bidding": ["مزایده", "حراج"],
    # گروه ۹: لوازم یدکی و خدمات
    # "spare_parts_service": ["لوازم", "قطعات", "تعمیرگاه"]
}

# --- ۲. ساخت الگوی جامع Regex ---
# همه لیست‌ها را به یک لیست واحد تبدیل کرده و با کاراکتر OR (|) به هم متصل می‌کند.
ALL_KEYWORDS = []
for keywords in FILTER_GROUPS.values():
    ALL_KEYWORDS.extend(keywords)

REGEX_STRING = "|".join(ALL_KEYWORDS)

# کامپایل Regex نهایی
REGEX_PATTERN = re.compile(f"({REGEX_STRING})", flags=re.IGNORECASE)


def process_csv_data(
    input_csv_path: str,
    output_clean_csv_path: str,
    output_rejected_log_path: str,
    text_column_name: str,
):
    """
    Cleans the input CSV file based on the Regex pattern and saves the results in two separate files.
    """
    print(f"Loading input CSV file: {input_csv_path}")

    try:
        df = pd.read_csv(input_csv_path, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"Error: File {input_csv_path} not found.")
        return
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return

    if text_column_name not in df.columns:
        print(f"Error: Column '{text_column_name}' not found in CSV for filtering.")
        print(f"Available columns: {list(df.columns)}")
        return

    rejected_records = []

    print("Applying regex filter to records...")

    # Iterate over rows and apply filtering
    for index, row in df.iterrows():
        text_to_check = str(row[text_column_name])

        # Find all matching expressions
        matches = REGEX_PATTERN.findall(text_to_check)

        if matches:
            # Save rejected record info for reporting
            rejected_records.append(
                {
                    "Record_ID_In_Original_File": index,
                    "Matched_Keywords": ", ".join(sorted(list(set(matches)))),
                }
            )

    # Get indices of rejected records
    rejected_indices = [
        record["Record_ID_In_Original_File"] for record in rejected_records
    ]

    # Keep only clean rows
    clean_df = df.drop(index=rejected_indices)

    # Save rejected records log to CSV# Save rejected records log to CSV (sorted by Matched_Keywords)
    rejected_df = pd.DataFrame(rejected_records)
    rejected_df.sort_values(by="Matched_Keywords", inplace=True)
    rejected_df.to_csv(output_rejected_log_path, index=False, encoding="utf-8-sig")
    print(f"Rejected records log saved to: {output_rejected_log_path}")

    # Save clean CSV file
    clean_df.to_csv(output_clean_csv_path, index=False, encoding="utf-8-sig")
    print(f"Clean CSV file (valid records) saved to: {output_clean_csv_path}")

    # Summary
    print("\n--- Summary ---")
    print(f"Total records: {len(df)}")
    print(f"Rejected records: {len(rejected_records)}")
    print(f"Valid records: {len(clean_df)}")


# --- Main Execution Section ---
if __name__ == "__main__":

    # Ensure correct number of command line arguments
    if len(sys.argv) < 3:
        print(
            "Error: Input CSV path and output directory path must be provided as arguments."
        )
        print(f"Usage: python {sys.argv[0]} <input_csv_path> <output_directory_path>")
        sys.exit(1)

    # Get command line arguments
    INPUT_FILE = sys.argv[1]
    OUTPUT_DIR = sys.argv[2]

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            print(f"Output directory '{OUTPUT_DIR}' created.")
        except Exception as e:
            print(f"Error creating output directory: {e}")
            sys.exit(1)

    # Generate output file paths
    base_name = os.path.splitext(os.path.basename(INPUT_FILE))[0]
    OUTPUT_CLEAN_FILE = os.path.join(OUTPUT_DIR, f"{base_name}_clean.csv")
    OUTPUT_REJECTED_LOG_FILE = os.path.join(OUTPUT_DIR, f"{base_name}_rejected_log.csv")

    # Column containing text to filter
    TARGET_COLUMN = "description"

    process_csv_data(
        input_csv_path=INPUT_FILE,
        output_clean_csv_path=OUTPUT_CLEAN_FILE,
        output_rejected_log_path=OUTPUT_REJECTED_LOG_FILE,
        text_column_name=TARGET_COLUMN,
    )
