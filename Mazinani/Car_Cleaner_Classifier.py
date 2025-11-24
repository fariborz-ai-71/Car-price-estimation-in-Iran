import pandas as pd
import os
import re

FILTER_GROUPS = {
    "installment_credit": ["قسط", "اقساط", "اقساطی", "اقسلط", "تسهیلات", "لیزینگ", "شرایطی", "اعتباری", "بازپرداخت"],
    "agency_corporate": ["نمایندگی", "نمایشگاه", "نمایشگاهی", "کد آگهی", "گالری", "سازمانی", "عاملیت", "اتوگالری",
                         "کارشناس فروش", "اتو گالری", "سابقه", "درخشان", "خریدار", r"عضو\s?رسمی"],
    "document_referral": ["حواله", r"دعوت\s?نامه", r"سند.?آماده", r"سند.?آزاد", r"ثبت.?نام", "قرارداد"],
    "unknown_price": ["توافقی", "قیمت روز"],
    "commercial_bulk": ["محصولات", "عمده", "همکار", "تولیدات", "مجموعه", "شرکت", "سازمان"],
    "zero_km_immediate": ["تحویل فوری", "موجودی", "تحویل", "آماده تحویل"],
    "swap_barter": ["مشاوره", "جانبازی", "تهاتر"],
    "auction_bidding": ["مزایده", "فرسوده", "تصادفی", "حراج"],
}

ALL_FILTER_KEYWORDS = []
for k in FILTER_GROUPS.values():
    ALL_FILTER_KEYWORDS.extend(k)
FILTER_REGEX = re.compile(f"({'|'.join(ALL_FILTER_KEYWORDS)})", flags=re.IGNORECASE)

DOMESTIC_BRANDS = [
    "پژو", "peugeot", "206", "207", "405", "pars", "پارس", "پرشیا",
    "سمند", "samand", "سورن", "soren", "دنا", "dena", "تارا", "tara",
    "رانا", "runna", "آریسان", "arisan", "پیکان", "paykan", "peykan",
    "151", "ری را", "ree ra", "roaman", "روا", "روآ",
    "پراید", "pride", "111", "131", "132", "141", "نسیم", "صبا",
    "تیبا", "tiba", "ساینا", "saina", "کوییک", "quick", "quik", "kuick",
    "شاهین", "shahin", "اطلس", "atlas", "سهند", "sahand",
    "پارس تندر", "آریو", "ario", "وانت مزدا", "کوئیک",
    "ساندرو", "sandero", "استپ وی", "stepway", "تندر", "tondar", "l90", "ال نود", "ال 90",
    "مگان", "megane", "رونیز", "roniz", "پیکاپ", "pickup",
    "زانتیا", "xantia", "سیتروئن", "citroen", "نیسان", "nissan", "زامیاد", "zamyad",
    "پادرا", "padra", "کارون", "karun", "اردی", "آردی", "RD", "RDI"
]

# تنظیمات ستون‌ها
COL_TITLE = 'title'
COL_PRICE = 'price'
COL_YEAR = 'year'
COL_MILEAGE = 'mileage_km'

# تنظیمات منطقی
CURRENT_YEAR = 1404
MIN_AGE_FOR_CHECK = 5
MIN_KM_PER_YEAR = 1000
MIN_PRICE_THRESHOLD = 100_000_000  # 100 Million

def normalize_numbers(text):
    """تبدیل اعداد فارسی/عربی به انگلیسی و حذف کاراکترهای اضافه"""
    if not isinstance(text, str):
        return text
    mapping = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    text = text.translate(str.maketrans(mapping))
    for char in [',', '،', '٬', '\u200f']:
        text = text.replace(char, '')
    return text


def clean_and_fix_price(value):
    if pd.isna(value):
        return None
    val_str = str(value)
    clean_digits = re.sub(r'[^\d]', '', val_str)
    if not clean_digits:
        return None
    return int(clean_digits)


def classify_price(price):
    if price <= 400_000_000:
        return 1
    elif price <= 800_000_000:
        return 2
    else:
        return 3


def check_domestic_brand(text):

    if pd.isna(text):
        return False
    text_str = str(text).lower()
    return any(keyword in text_str for keyword in DOMESTIC_BRANDS)

def process_pipeline(file_path):
    print("=" * 50)

    if not os.path.exists(file_path):
        print(f"❌ فایل یافت نشد: {file_path}")
        return

    print(f"⏳ در حال خواندن فایل: {os.path.basename(file_path)}")
    try:
        if file_path.lower().endswith('.xlsx'):
            df = pd.read_excel(file_path, engine='openpyxl')
        elif file_path.lower().endswith('.xls'):
            df = pd.read_excel(file_path, engine='xlrd')
        elif file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"❌ خطا در خواندن فایل: {e}")
        return

    print("🔢 در حال استانداردسازی اعداد (تبدیل فارسی به انگلیسی)...")
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(normalize_numbers)

    print("🔍 در حال اعمال فیلترهای هوشمند...")

    text_col = 'description'
    if text_col not in df.columns:
        if 'text_all' in df.columns:
            text_col = 'text_all'
        elif COL_TITLE in df.columns:
            text_col = COL_TITLE
        else:
            print("⚠️ ستون توضیحات یافت نشد، فیلتر کلمات روی تمام دیتافریم اعمال نمی‌شود.")
            text_col = None

    rejected_records = []
    rows_to_drop = []

    for index, row in df.iterrows():
        rejection_reason = ""

        if text_col and text_col in row:
            text_check = str(row[text_col])
            matches = FILTER_REGEX.findall(text_check)
            if matches:
                rejection_reason = f"Keywords: {', '.join(sorted(list(set(matches))))}"

        if not rejection_reason and COL_YEAR in df.columns and COL_MILEAGE in df.columns:
            try:
                year_val = str(row[COL_YEAR]).strip()
                mileage_val = str(row[COL_MILEAGE]).strip()

                if year_val.isdigit() and mileage_val.replace('.', '', 1).isdigit():
                    age = CURRENT_YEAR - int(float(year_val))
                    mileage = float(mileage_val)

                    if age >= MIN_AGE_FOR_CHECK:
                        min_expected = age * MIN_KM_PER_YEAR
                        if mileage < min_expected:
                            rejection_reason = f"Unrealistic Mileage (Age: {age}, KM: {mileage})"
            except:
                pass

        if rejection_reason:
            rejected_records.append({
                "Original_Index": index,
                "Reason": rejection_reason,
                "Snippet": str(row[text_col])[:50] if text_col else "N/A"
            })
            rows_to_drop.append(index)

    if rows_to_drop:
        df = df.drop(rows_to_drop)
        print(f"🗑️ تعداد {len(rows_to_drop)} رکورد نامعتبر حذف شد.")

    if COL_PRICE not in df.columns:
        print(f"❌ ستون قیمت '{COL_PRICE}' یافت نشد. پردازش متوقف شد.")
        return

    print("💰 در حال تمیزکاری قیمت‌ها...")
    df['cleaned_price'] = df[COL_PRICE].apply(clean_and_fix_price)

    df = df.dropna(subset=['cleaned_price'])

    before_price_filter = len(df)
    df = df[df['cleaned_price'] >= MIN_PRICE_THRESHOLD]
    print(f"🗑️ تعداد {before_price_filter - len(df)} رکورد به دلیل قیمت زیر ۱۰۰ میلیون حذف شد.")

    df[COL_PRICE] = df['cleaned_price'].astype(int)  # جایگزینی ستون اصلی
    df['price_class'] = df[COL_PRICE].apply(classify_price)
    df = df.drop(columns=['cleaned_price'])

    if COL_TITLE not in df.columns:
        print(f"❌ ستون عنوان '{COL_TITLE}' برای تشخیص برند یافت نشد.")
        return

    print("🚗 در حال تفکیک خودروهای داخلی و خارجی...")
    mask_domestic = df[COL_TITLE].apply(check_domestic_brand)

    df_domestic = df[mask_domestic]
    df_others = df[~mask_domestic]

    output_dir = os.path.join(os.path.dirname(file_path), "outputs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(file_path))[0]

    path_domestic = os.path.join(output_dir, f"{base_name}_IKCO_Saipa.csv")
    path_others = os.path.join(output_dir, f"{base_name}_Others.csv")
    path_rejected = os.path.join(output_dir, f"{base_name}_Rejected_Log.csv")

    try:
        df_domestic.to_csv(path_domestic, index=False, encoding='utf-8-sig')
        df_others.to_csv(path_others, index=False, encoding='utf-8-sig')

        if rejected_records:
            pd.DataFrame(rejected_records).to_csv(path_rejected, index=False, encoding='utf-8-sig')
            print(f"⚠️ فایل لاگ حذف‌شده‌ها: {path_rejected}")

        print("\n✅ عملیات با موفقیت انجام شد.")
        print(f"📊 خودروهای داخلی: {len(df_domestic)}")
        print(f"📊 سایر خودروها: {len(df_others)}")
        print(f"📂 پوشه خروجی: {output_dir}")

    except Exception as e:
        print(f"❌ خطا در ذخیره فایل‌ها: {e}")

if __name__ == "__main__":
    raw_input = input("📂 مسیر فایل ورودی (Excel/CSV) را وارد کنید: ").strip().replace('"', '').replace("'", "")
    process_pipeline(raw_input)
    input("\n🏁 اینتر بزنید تا خارج شوید...")