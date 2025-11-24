import pandas as pd
import os
import re
import numpy as np
import sys
from typing import List, Dict, Callable

# ==========================================
# 1. تنظیمات و کلمات کلیدی (CONFIG)
# ==========================================

# تنظیمات فیلتر کردن ردیف‌های نامعتبر
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

# لیست برندهای داخلی
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

# نام ستون‌ها
COL_TITLE = 'title'
COL_PRICE = 'price'
COL_YEAR = 'year'
COL_MILEAGE = 'mileage_km'
COL_DESCRIPTION = 'description'

# پارامترهای منطقی
CURRENT_YEAR = 1404
MIN_AGE_FOR_CHECK = 5
MIN_KM_PER_YEAR = 1000
MIN_PRICE_THRESHOLD = 100_000_000


# ==========================================
# 2. توابع پایه (BASIC HELPERS)
# ==========================================

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
    if pd.isna(value): return None
    val_str = str(value)
    clean_digits = re.sub(r'[^\d]', '', val_str)
    if not clean_digits: return None
    return int(clean_digits)


def classify_price(price):
    if price <= 400_000_000:
        return 1
    elif price <= 800_000_000:
        return 2
    else:
        return 3


def check_domestic_brand(text):
    if pd.isna(text): return False
    text_str = str(text).lower()
    return any(keyword in text_str for keyword in DOMESTIC_BRANDS)


# ==========================================
# 3. توابع استخراج ویژگی (FEATURE EXTRACTION)
# ==========================================

def normalize_persian_text_for_features(text: str) -> str:
    """نرمال‌سازی متن مخصوص استخراج ویژگی (حذف نیم‌فاصله و یکسان‌سازی ی و ک)"""
    if text is None: return ""
    if isinstance(text, float) and np.isnan(text): return ""
    s = str(text)
    s = s.replace("\u200c", " ").replace("‌", " ")  # نیم فاصله
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = normalize_numbers(s)
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def contains_any(text: str, patterns: List[str]) -> bool:
    return any(p in text for p in patterns)


def build_text_all(row: pd.Series) -> str:
    """ترکیب تمام ستون‌های متنی برای جستجوی فیچرها"""
    # لیست ستون‌های احتمالی که متن دارند
    possible_cols = ["title", "body_status", "engine_status", "chassis_status", "description", "text_all"]
    parts = []
    for col in possible_cols:
        if col in row.index:
            parts.append(row[col])

    return normalize_persian_text_for_features(" ".join([str(p) for p in parts if pd.notna(p)]))


# --- توابع تشخیص وضعیت بدنه و فنی ---
def feat_darb_rang(r): t = r["_processed_text"]; p = ["یک درب رنگ", "1 درب رنگ", "۱ درب رنگ", "دو درب رنگ", "2 درب رنگ",
                                                      "۲ درب رنگ", "در جلو رنگ", "در عقب رنگ", "درب رنگ",
                                                      "در رنگ"]; return int(contains_any(t, p))


def feat_darb_taviz(r): t = r["_processed_text"]; p = ["درب تعویض", "در تعویض", "درها تعویض", "درها عوض شده",
                                                       "درب عوض شده"]; return int(contains_any(t, p))


def feat_darb_bedun_rang(r): t = r["_processed_text"]; p = ["درب بدون رنگ", "در بدون رنگ", "درب ها بدون رنگ",
                                                            "درها بدون رنگ", "درب بی رنگ", "در بی رنگ"]; return int(
    contains_any(t, p))


def feat_kaput_taviz(r): t = r["_processed_text"]; p = ["کاپوت تعویض", "تعویض کاپوت", "کاپوت عوض شده"]; return int(
    contains_any(t, p))


def feat_kaput_bedun_rang(r): t = r["_processed_text"]; p = ["کاپوت بدون رنگ", "کاپوت بی رنگ",
                                                             "بدون رنگ کاپوت"]; return int(contains_any(t, p))


def feat_darb_sandogh_rang(r): t = r["_processed_text"]; p = ["درب صندوق رنگ", "در صندوق رنگ", "صندوق رنگ"]; return int(
    contains_any(t, p) and "صندوق بدون رنگ" not in t and "صندوق بی رنگ" not in t)


def feat_darb_sandogh_bedun_rang(r): t = r["_processed_text"]; p = ["درب صندوق بدون رنگ", "در صندوق بدون رنگ",
                                                                    "صندوق بدون رنگ", "صندوق بی رنگ"]; return int(
    contains_any(t, p))


def feat_shasi_zarbe(r): t = r["_processed_text"]; p = ["شاسی ضربه", "ضربه به شاسی", "شاسی خورده", "شاسی کج",
                                                        "شاسی آسیب", "شاسی شکسته"]; return int(contains_any(t, p))


def feat_shasi_pelomp(r): t = r["_processed_text"]; p = ["شاسی پلمپ", "پلمپ شاسی", "سالم و پلمپ"]; return int(
    contains_any(t, p))


def feat_shasi_salem(r): t = r["_processed_text"]; p = ["شاسی سالم", "شاسی ها سالم", "شاسی بی ضربه", "شاسی ها بی ضربه",
                                                        "شاسی دست نخورده"]; return int(contains_any(t, p))


def feat_saghf_rang(r): t = r["_processed_text"]; p = ["سقف رنگ", "رنگ سقف"]; return int(
    contains_any(t, p) and "سقف بدون رنگ" not in t and "سقف بی رنگ" not in t)


def feat_saghf_bedun_rang(r): t = r["_processed_text"]; p = ["سقف بدون رنگ", "سقف بی رنگ"]; return int(
    contains_any(t, p))


def feat_sotun_salem(r): t = r["_processed_text"]; p = ["ستون سالم", "ستون ها سالم", "ستون بی ضربه", "ستون ها بی ضربه",
                                                        "ستون دست نخورده"]; return int(contains_any(t, p))


def feat_sotun_zarbe(r): t = r["_processed_text"]; p = ["ستون ضربه", "ضربه به ستون", "ستون کج", "ستون آسیب",
                                                        "ستون ها ضربه"]; return int(contains_any(t, p))


def feat_golgir_rang(r): t = r["_processed_text"]; p = ["گلگیر رنگ", "رنگ گلگیر"]; return int(
    contains_any(t, p) and "گلگیر بدون رنگ" not in t and "گلگیر بی رنگ" not in t)


def feat_golgir_bedun_rang(r): t = r["_processed_text"]; p = ["گلگیر بدون رنگ", "گلگیر بی رنگ"]; return int(
    contains_any(t, p))


def feat_golgir_taviz(r): t = r["_processed_text"]; p = ["گلگیر تعویض", "تعویض گلگیر", "گلگیر عوض شده"]; return int(
    contains_any(t, p))


def feat_fanni_salem(r): t = r["_processed_text"]; p = ["فنی سالم", "از نظر فنی سالم", "از لحاظ فنی سالم"]; return int(
    contains_any(t, p))


def feat_fanni_niyaz_tamir(r): t = r["_processed_text"]; p = ["فنی نیاز به تعمیر", "نیاز به تعمیر فنی", "مشکل فنی",
                                                              "ایراد فنی", "خرج فنی"]; return int(contains_any(t, p))


def feat_fanni_tamir_shode(r): t = r["_processed_text"]; p = ["فنی تعمیر شده", "فنی تازه تعمیر", "تعمیر اساسی فنی",
                                                              "تعمیر کلی فنی"]; return int(
    contains_any(t, p) or ("فنی" in t and "تعمیر" in t))


def feat_gearbox_salem(r): t = r["_processed_text"]; p = ["گیربکس سالم", "گیر بکس سالم", "گیربکس بدون مشکل",
                                                          "گیربکس بی صدا"]; return int(contains_any(t, p))


def feat_gearbox_niyaz_tamir(r): t = r["_processed_text"]; p = ["گیربکس نیاز به تعمیر", "گیر بکس نیاز به تعمیر",
                                                                "گیربکس خرج", "گیر بکس خرج", "گیربکس خراب",
                                                                "مشکل گیربکس", "ایراد گیربکس"]; return int(
    contains_any(t, p))


def feat_yek_lakke_rang(r): t = r["_processed_text"]; p = ["یک لکه رنگ", "1 لکه رنگ", "۱ لکه رنگ"]; return int(
    contains_any(t, p))


def feat_do_lakke_rang(r): t = r["_processed_text"]; p = ["دو لکه رنگ", "2 لکه رنگ", "۲ لکه رنگ"]; return int(
    contains_any(t, p))


def feat_dor_rang(r): t = r["_processed_text"]; p = ["دور رنگ", "دوررنگ", "تمام رنگ", "تمام‌رنگ",
                                                     "تمام رنگی"]; return int(contains_any(t, p))


def get_feature_functions() -> Dict[str, Callable[[pd.Series], int]]:
    """
    این دیکشنری نام ستون در فایل خروجی (کلید) را به تابع مربوطه (مقدار) وصل می‌کند.
    نام ستون‌ها در اینجا فارسی شده است.
    """
    return {
        "درب رنگ": feat_darb_rang,
        "درب تعویض": feat_darb_taviz,
        "درب بدون رنگ": feat_darb_bedun_rang,
        "کاپوت تعویض": feat_kaput_taviz,
        "کاپوت بدون رنگ": feat_kaput_bedun_rang,
        "درب صندوق رنگ": feat_darb_sandogh_rang,
        "درب صندوق بدون رنگ": feat_darb_sandogh_bedun_rang,
        "شاسی ضرب‌خوردگی": feat_shasi_zarbe,
        "شاسی پلمپ": feat_shasi_pelomp,
        "شاسی سالم": feat_shasi_salem,
        "سقف رنگ": feat_saghf_rang,
        "سقف بدون رنگ": feat_saghf_bedun_rang,
        "ستون سالم": feat_sotun_salem,
        "ستون ضرب‌خوردگی": feat_sotun_zarbe,
        "گلگیر رنگ": feat_golgir_rang,
        "گلگیر بدون رنگ": feat_golgir_bedun_rang,
        "گلگیر تعویض": feat_golgir_taviz,
        "فنی سالم": feat_fanni_salem,
        "فنی نیاز به تعمیر": feat_fanni_niyaz_tamir,
        "فنی تعمیر شده": feat_fanni_tamir_shode,
        "گیربکس سالم": feat_gearbox_salem,
        "گیربکس نیاز به تعمیر": feat_gearbox_niyaz_tamir,
        "یک لکه رنگ": feat_yek_lakke_rang,
        "دو لکه رنگ": feat_do_lakke_rang,
        "دور رنگ": feat_dor_rang,
    }


# ==========================================
# 4. منطق اصلی (PIPELINE)
# ==========================================

def process_pipeline(file_path):
    print("=" * 50)

    # --- مرحله ۱: بارگذاری ---
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

    # --- مرحله ۲: استانداردسازی اعداد ---
    print("🔢 در حال استانداردسازی اعداد...")
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(normalize_numbers)

    # --- مرحله ۳: فیلترینگ (حذف اسپم) ---
    print("🔍 در حال فیلتر کردن آگهی‌های نامربوط...")

    # پیدا کردن ستون توضیحات
    text_col = COL_DESCRIPTION
    if text_col not in df.columns:
        if 'text_all' in df.columns:
            text_col = 'text_all'
        elif COL_TITLE in df.columns:
            text_col = COL_TITLE
        else:
            text_col = None

    rejected_records = []
    rows_to_drop = []

    for index, row in df.iterrows():
        rejection_reason = ""

        # بررسی کلمات ممنوعه
        if text_col and text_col in row:
            matches = FILTER_REGEX.findall(str(row[text_col]))
            if matches:
                rejection_reason = f"Keywords: {', '.join(sorted(list(set(matches))))}"

        # بررسی کارکرد غیرمنطقی
        if not rejection_reason and COL_YEAR in df.columns and COL_MILEAGE in df.columns:
            try:
                year_val = str(row[COL_YEAR]).strip()
                mileage_val = str(row[COL_MILEAGE]).strip()
                if year_val.isdigit() and mileage_val.replace('.', '', 1).isdigit():
                    age = CURRENT_YEAR - int(float(year_val))
                    mileage = float(mileage_val)
                    if age >= MIN_AGE_FOR_CHECK:
                        if mileage < (age * MIN_KM_PER_YEAR):
                            rejection_reason = f"Unrealistic Mileage (Age: {age}, KM: {mileage})"
            except:
                pass

        if rejection_reason:
            rejected_records.append({"Index": index, "Reason": rejection_reason})
            rows_to_drop.append(index)

    if rows_to_drop:
        df = df.drop(rows_to_drop)
        print(f"🗑️ حذف {len(rows_to_drop)} رکورد نامعتبر.")

    # --- مرحله ۴: پردازش قیمت ---
    print("💰 تمیزکاری قیمت‌ها...")
    if COL_PRICE in df.columns:
        df['cleaned_price'] = df[COL_PRICE].apply(clean_and_fix_price)
        df = df.dropna(subset=['cleaned_price'])
        df = df[df['cleaned_price'] >= MIN_PRICE_THRESHOLD]
        df[COL_PRICE] = df['cleaned_price'].astype(int)
        df['price_class'] = df[COL_PRICE].apply(classify_price)
        df = df.drop(columns=['cleaned_price'])
    else:
        print("⚠️ ستون قیمت پیدا نشد، از فیلتر قیمت صرف‌نظر شد.")

    # --- مرحله ۵: استخراج ویژگی‌ها (FEATURE EXTRACTION) ---
    print("🧪 در حال استخراج ویژگی‌های فنی از متن (Feature Extraction)...")

    # ساخت یک ستون موقت ترکیبی برای جستجو (شامل عنوان، توضیحات و وضعیت‌ها)
    df["_processed_text"] = df.apply(build_text_all, axis=1)

    feature_funcs = get_feature_functions()
    for col_name_persian, func in feature_funcs.items():
        # اعمال تابع روی هر ردیف و ذخیره با نام فارسی
        df[col_name_persian] = df.apply(func, axis=1).astype(int)

    # حذف ستون موقت پردازش متن برای تمیز ماندن خروجی
    df = df.drop(columns=["_processed_text"])
    print(f"✅ تعداد {len(feature_funcs)} ستون ویژگی جدید (با نام فارسی) اضافه شد.")

    # --- مرحله ۶: جداسازی و ذخیره ---
    print("🚗 جداسازی برندها و ذخیره‌سازی...")

    if COL_TITLE in df.columns:
        mask_domestic = df[COL_TITLE].apply(check_domestic_brand)
        df_domestic = df[mask_domestic]
        df_others = df[~mask_domestic]
    else:
        df_domestic = df
        df_others = pd.DataFrame()

    output_dir = os.path.join(os.path.dirname(file_path), "outputs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(file_path))[0]

    # ذخیره با encoding='utf-8-sig' برای نمایش صحیح فارسی در اکسل
    df_domestic.to_csv(os.path.join(output_dir, f"{base_name}_IKCO_Saipa_Featured.csv"), index=False,
                       encoding='utf-8-sig')
    df_others.to_csv(os.path.join(output_dir, f"{base_name}_Others_Featured.csv"), index=False, encoding='utf-8-sig')

    if rejected_records:
        pd.DataFrame(rejected_records).to_csv(os.path.join(output_dir, f"{base_name}_Rejected_Log.csv"), index=False,
                                              encoding='utf-8-sig')

    print("\n🏁 عملیات پایان یافت.")
    print(f"📂 خروجی در پوشه: {output_dir}")


if __name__ == "__main__":
    path = input("📂 مسیر فایل ورودی را وارد کنید: ").strip().replace('"', '').replace("'", "")
    process_pipeline(path)