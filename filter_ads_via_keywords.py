import pandas as pd

input_file = 'divar_ads_new.csv'
df = pd.read_csv(input_file)

keywords = [
    "حواله", "اقساط", "قسط", "نماینده رسمی",
    "نماینده", "کلکسیون", "کلکسیونی",
     "پیش پرداخت" , "نمایندگی رسمی" , "جانبازی" , "مشاور شما" , "به بالا ترین قیمت"
    "خریدار خودروی تصادفی", "خریدار خودروی فرسوده","خرید خودروی تصادفی","خرید خودروی تصادفی","کارشناس فروش","گالری"
    "اتوعلیپور","کریمی","افشار","اتوگالری","خرید خودروی شما","خرید خودروی شما","خریدار خودروی شما"
    "کد آگهی","کد اگهی","خریدخودرو","خریدتصادفی","علیپور","نمایندگی مجاز","عضو رسمی","اتحادیه","خانم","آقای","خسروانی"
]

mask = df['description'].str.contains('|'.join(keywords), na=False)

df_removed = df[mask]  
df_cleaned = df[~mask]
df_cleaned.to_csv('car_divar_cleaned.csv', index=False, encoding='utf-8-sig')
df_removed.to_csv('car_divar_removed.csv', index=False, encoding='utf-8-sig')
