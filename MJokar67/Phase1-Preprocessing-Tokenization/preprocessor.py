import re
import csv
import json
import sys
import os
from collections import Counter

# ------------------- Mapping Tables ----------------------
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
EN_DIGITS = "0123456789"
digits_map = str.maketrans(PERSIAN_DIGITS, EN_DIGITS)

ARABIC_TO_PERSIAN = {
    "ي": "ی",
    "ى": "ی",
    "ئ": "ی",
    "ك": "ک",
    "ۀ": "ه",
    "ة": "ه",
    "ؤ": "و",
    "أ": "ا",
    "إ": "ا",
    "ٱ": "ا",
}

REMOVE_CHARS = ["\u200c", "\u200f"]  # ZWNJ, RTL mark
WORD_PATTERN = re.compile(r"[آ-ی]+")


# ------------------- Normalization -----------------------
def normalize_farsi(text: str) -> str:
    """Fix Arabic chars, convert digits, remove ZWNJ, fix spacing."""
    if not text:
        return ""
    for a, p in ARABIC_TO_PERSIAN.items():
        text = text.replace(a, p)
    for bad in REMOVE_CHARS:
        text = text.replace(bad, " ")
    text = text.translate(digits_map)
    text = re.sub(r"[^\w\sآ-ی]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ------------------- Keyword Extraction -----------------------
def extract_keywords(text: str):
    return WORD_PATTERN.findall(text)


# ------------------- CSV Processing -------------------------
def clean_csv_all_columns(
    input_csv: str,
    output_dir: str,
):
    """Normalize all text columns, extract keywords and characters from entire CSV."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(input_csv))[0]

    output_csv = os.path.join(output_dir, f"{base_name}_clean.csv")
    keywords_file = os.path.join(output_dir, "keywords.txt")
    chars_file = os.path.join(output_dir, "characters_used.txt")
    stats_json = os.path.join(output_dir, "stats.json")

    word_counter = Counter()
    char_set = set()

    with open(input_csv, "r", encoding="utf-8", errors="replace") as f_in, open(
        output_csv, "w", encoding="utf-8", newline=""
    ) as f_out:

        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            for col in reader.fieldnames:
                raw = str(row.get(col, ""))
                cleaned = normalize_farsi(raw)
                row[col] = cleaned
                # جمع‌آوری کیوردها و کاراکترها از تمام ستون‌ها
                word_counter.update(extract_keywords(cleaned))
                char_set.update(cleaned)
            writer.writerow(row)

    # ---------------- Output: keywords.txt ----------------
    with open(keywords_file, "w", encoding="utf-8") as fp:
        for w in sorted(word_counter.keys()):
            fp.write(w + "\n")

    # ---------------- Output: characters_used.txt ----------------
    with open(chars_file, "w", encoding="utf-8") as fp:
        for ch in sorted(char_set):
            fp.write(f"{ch}\tU+{ord(ch):04X}\n")

    # ---------------- Output: stats.json ----------------
    with open(stats_json, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "total_keywords": len(word_counter),
                "most_common_100": word_counter.most_common(100),
                "total_unique_characters": len(char_set),
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✓ Clean CSV saved to: {output_csv}")
    print(f"✓ keywords.txt saved to: {keywords_file}")
    print(f"✓ characters_used.txt saved to: {chars_file}")
    print(f"✓ stats.json saved to: {stats_json}")


# ------------------- CLI Entry --------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cleaner_all.py input.csv output_directory")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_dir = sys.argv[2]

    clean_csv_all_columns(input_csv, output_dir)
