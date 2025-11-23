import pandas as pd
import os
import re
def process_car_data(file_path):
    TITLE_COL = 'title'
    PRICE_COL = 'price_raw'

    if not os.path.exists(file_path):
        print(f"❌ File not found at: {file_path}")
        return

    print(f"⏳ Attempting to read file: {os.path.basename(file_path)}")

    try:
        if file_path.lower().endswith('.xlsx'):
            df = pd.read_excel(file_path, engine='openpyxl')
        elif file_path.lower().endswith('.xls'):
            df = pd.read_excel(file_path, engine='xlrd')
        elif file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    if TITLE_COL not in df.columns or PRICE_COL not in df.columns:
        print(f"❌ Columns '{TITLE_COL}' or '{PRICE_COL}' not found.")
        return

    print("⏳ Cleaning price format (removing spaces and commas)...")


    def clean_and_fix_price(value):
        if pd.isna(value):
            return None
        val_str = str(value)

        clean_digits = re.sub(r'[^\d]', '', val_str)
        if not clean_digits:
            return None
        return int(clean_digits)

    df['cleaned_price'] = df[PRICE_COL].apply(clean_and_fix_price)

    df = df.dropna(subset=['cleaned_price'])
    initial_count = len(df)
    df = df[df['cleaned_price'] >= 100000000]
    deleted_count = initial_count - len(df)
    print(f"🗑️ Removed {deleted_count} rows (price under 100 million).")

    df[PRICE_COL] = df['cleaned_price'].astype(int)

    print("⏳ Classifying cars based on price...")

    def classify_price(price):
        if price <= 400000000:
            return 1
        elif price <= 800000000:
            return 2
        else:
            return 3

    df['price_class'] = df[PRICE_COL].apply(classify_price)

    df = df.drop(columns=['cleaned_price'])

    keywords = [
        "پژو", "peugeot", "206", "207", "405", "pars", "پارس", "پرشیا",
        "سمند", "samand", "سورن", "soren", "دنا", "dena", "تارا", "tara",
        "رانا", "runna", "آریسان", "arisan", "پیکان", "paykan", "peykan",
        "151", "ری را", "ree ra", "roaman", "روا", "روآ",
        "پراید", "pride", "111", "131", "132", "141", "151", "نسیم", "صبا",
        "تیبا", "tiba", "ساینا", "saina", "کوییک", "quick", "quik", "kuick",
        "شاهین", "shahin", "اطلس", "atlas", "سهند", "sahand",
        "پارس تندر", "آریو", "ario", "وانت مزدا",
        "ساندرو", "sandero", "استپ وی", "stepway", "تندر", "tondar", "l90", "ال نود",
        "ال 90",
        "مگان", "megane", "رونیز", "roniz", "پیکاپ", "pickup",
        "زانتیا", "xantia", "سیتروئن", "citroen", "نیسان", "nissan", "زامیاد", "zamyad",
        "پادرا", "padra", "کارون", "karun", "اردی", "آردی", "RD", "RDI"
    ]

    print("⏳ Separating brands...")

    def check_car(text):
        if pd.isna(text):
            return False
        text_str = str(text).lower()
        return any(keyword in text_str for keyword in keywords)

    mask = df[TITLE_COL].apply(check_car)

    ikco_saipa_df = df[mask]
    others_df = df[~mask]

    try:
        output_ikco = "IKCO_Saipa_Cars.csv"
        output_others = "Other_Cars.csv"

        ikco_saipa_df.to_csv(output_ikco, index=False, encoding='utf-8-sig')
        others_df.to_csv(output_others, index=False, encoding='utf-8-sig')

        cwd = os.getcwd()
        print("-" * 30)
        print("✅ Operation Successful.")
        print(f"📝 Prices corrected and 'price_class' column added.")
        print(f"📊 Domestic Cars: {len(ikco_saipa_df)} | Other Cars: {len(others_df)}")
        print("-" * 30)
        print(f"📍 File 1: {os.path.join(cwd, output_ikco)}")
        print(f"📍 File 2: {os.path.join(cwd, output_others)}")

    except Exception as e:
        print(f"❌ Error saving files: {e}")

if __name__ == "__main__":
    input_path = input("Enter file path: ").strip().replace('"', '').replace("'", "")
    process_car_data(input_path)