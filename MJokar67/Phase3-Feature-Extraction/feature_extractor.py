#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Feature Extraction Engine (Persian auto ads)
- Streaming CSV read
- Preprocessing / Normalization
- Rule-based + Regex extraction
- Confidence scoring and severity classification
- Save to JSONL, CSV, SQLite
Usage:
    python feature_extractor.py --input input.csv --out-json out.jsonl --out-sqlite out.db
"""

import csv
import re
import json
import sqlite3
import argparse
import unicodedata
from typing import Dict, List, Any, Optional

# ---------------------------
# 0) Configs: lexicon, patterns, severity rules
# ---------------------------

LEXICON = {
    "paint_full": [
        r"دور\s?رنگ",
        r"تمام(اً|ی)?\s?رنگ",
        r"کامل\s?رنگ",
        r"اتاق\s?رنگ",
        r"تمام\s?رنگ",
    ],
    "paint_partial": [
        r"رنگ\s?شدگ",
        r"رنگ\s?شده",
        r"رنگ\s?دارد",
        r"رنگ\s?دار",
        r"کمی\s?رنگ",
    ],
    "no_paint": [
        r"بدون\s?رنگ",
        r"بی[\- ]?رنگ",
        r"صافکاری\s?بدون\s?رنگ",
        r"بدنه\s?سالم",
        r"در\s?حد\s?نو",
    ],
    "scratch": [r"خط\s?و\s?خش", r"خراش", r"خش(\s|$)", r"لکه\s?خوردگی"],
    "dent": [r"تو\s?رفتگی", r"تورفتگی", r"فرو\s?رفتگی", r"فرورفتگی", r"له\s?شدگی"],
    "replaced": [r"تعویض", r"تعویض\s?شده", r"تعویض\s?گردیده", r"تعویض\s?شده\s?است"],
    "parts": [
        r"درب",
        r"گلگیر",
        r"سپر",
        r"کاپوت",
        r"صندوق",
        r"سقف",
        r"شاسی",
        r"اتاق",
        r"بامپر",
    ],
    "chassis_ok": [
        r"شاسی\s?سالم",
        r"شاسی\s?ضربه\s?ندارد",
        r"شاسی\s?بدون\s?ضربه",
        r"شاسی\s?خوب",
    ],
    "chassis_damaged": [
        r"شاسی\s?(ضربه|آسیب|کج|خمیدگی|خمیده|در\س؟رفت)",
        r"ضربه\s?به\s?شاسی",
    ],
    "accident_words": [r"تصادف", r"حادثه", r"سقوط", r"ضربه\s?شدید", r"ضربه"],
    "engine_ok": [r"موتور\s?سالم", r"فنی\s?سالم", r"بدون\s?مشکل\s?فنی"],
    "engine_problem": [
        r"موتور\s?(تعمیری|ضربه|مشکل|میکس)",
        r"مشکل\s?فنی",
        r"بدون\s?استارت",
    ],
}

COMPILED_LEXICON = {
    k: [re.compile(p, re.IGNORECASE | re.UNICODE) for p in v]
    for k, v in LEXICON.items()
}

PART_PATTERN = re.compile(
    r"(?P<part>درب|گلگیر|سپر|کاپوت|صندوق|سقف|شاسی|اتاق|بامپر)"
    r"(?:\s+)?(?:جلو|عقب|راست|چپ|سمت|طرف)?\s*"
    r"(?:تعویض|رنگ|صافکاری|تعمیر|تعویض\s?شده|رنگ\s?شده)?",
    re.IGNORECASE | re.UNICODE,
)

PART_REPLACED_PATTERN = re.compile(
    r"(?P<part>درب|گلگیر|سپر|کاپوت|صندوق|سقف|بامپر)(?:\s+)"
    r"(?:تعویض|تعویض\s?شده|تعویض\s?گردیده)",
    re.IGNORECASE | re.UNICODE,
)

SEVERITY_MAJOR = [
    r"ضربه\s?شدید",
    r"تصادف\s?سنگین",
    r"کامل\s?تعویض",
    r"تعویض\s?کامل",
    r"دور\s?رنگ",
    r"کامل\s?رنگ",
    r"اتاق\s?تعویض",
]
SEVERITY_MODERATE = [r"تعویض", r"تعمیر", r"صافکاری", r"تو\s?رفتگی", r"ضربه"]
SEVERITY_MINOR = [
    r"خط\s?و\s?خش\s?جزئی",
    r"خش\s?جزئی",
    r"کمی\s",
    r"لکه",
    r"تو\s?رفتگی\s?کوچک",
]

SEV_MAJOR_RE = re.compile("|".join(SEVERITY_MAJOR), re.IGNORECASE | re.UNICODE)
SEV_MODERATE_RE = re.compile("|".join(SEVERITY_MODERATE), re.IGNORECASE | re.UNICODE)
SEV_MINOR_RE = re.compile("|".join(SEVERITY_MINOR), re.IGNORECASE | re.UNICODE)

CONF_WEIGHTS = {"regex_exact": 1.0, "keyword": 0.6, "multi_evidence": 0.8}

# ---------------------------
# 1) Text normalization / preprocessing
# ---------------------------


def normalize_persian_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.strip()
    s = (
        s.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ؤ", "و")
        .replace("إ", "ا")
        .replace("أ", "ا")
    )
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ـ—–\-]", " ", s)
    s = s.replace("\u200c", " ").replace("\u200d", " ")
    s = re.sub(r"[!؟؟]+", " ", s)
    s = re.sub(r"[\.\,\؛\:]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.lower().strip()


# ---------------------------
# 2) Core extraction helpers
# ---------------------------


def find_lexicon_matches(text: str) -> Dict[str, List[str]]:
    matches: Dict[str, List[str]] = {}
    for key, regex_list in COMPILED_LEXICON.items():
        found = []
        for rx in regex_list:
            found.extend(
                [normalize_persian_text(m.group(0)) for m in rx.finditer(text)]
            )
        if found:
            matches[key] = list(dict.fromkeys(found))
    return matches


def find_parts_replaced(text: str) -> List[str]:
    parts = [
        normalize_persian_text(m.group("part"))
        for m in PART_REPLACED_PATTERN.finditer(text)
    ]
    return list(dict.fromkeys(parts))


def find_parts_mentioned(text: str) -> List[str]:
    parts = [
        normalize_persian_text(m.group("part")) for m in PART_PATTERN.finditer(text)
    ]
    return list(dict.fromkeys(parts))


def severity_from_text(text: str) -> str:
    if SEV_MAJOR_RE.search(text):
        return "major"
    if SEV_MODERATE_RE.search(text):
        return "moderate"
    if SEV_MINOR_RE.search(text):
        return "minor"
    return "none"


def compute_confidence(evidence: Dict[str, Any]) -> float:
    score, weight_total = 0.0, 0.0
    for k, v in evidence.items():
        if k.startswith("exact_"):
            w = CONF_WEIGHTS["regex_exact"]
        elif k.startswith("kw_"):
            w = CONF_WEIGHTS["keyword"]
        elif k.startswith("multi_"):
            w = CONF_WEIGHTS["multi_evidence"]
        else:
            continue
        score += w * v
        weight_total += w * (1 if v > 0 else 0)
    if weight_total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, score / weight_total)), 3)


# ---------------------------
# 3) Feature extraction per text
# ---------------------------


def extract_features_from_text(text: str) -> Dict[str, Any]:
    """
    استخراج فیچرها از متن فارسی.
    شامل رنگ، آسیب بدنه، قطعات تعویض شده، وضعیت شاسی و موتور و تشخیص تصادف
    """
    norm = normalize_persian_text(text)
    
    # استخراج مطابق لغت‌نامه
    lex_matches = find_lexicon_matches(norm)
    
    # قطعات تعویض شده و ذکر شده
    parts_replaced = find_parts_replaced(norm)
    parts_mentioned = find_parts_mentioned(norm)
    
    # تشخیص تصادف و وضعیت شاسی / موتور
    accident = any(rx.search(norm) for rx in COMPILED_LEXICON.get("accident_words", []))
    chassis_ok = any(rx.search(norm) for rx in COMPILED_LEXICON.get("chassis_ok", []))
    chassis_dmg = any(rx.search(norm) for rx in COMPILED_LEXICON.get("chassis_damaged", []))
    engine_ok = any(rx.search(norm) for rx in COMPILED_LEXICON.get("engine_ok", []))
    engine_problem = any(rx.search(norm) for rx in COMPILED_LEXICON.get("engine_problem", []))

    # وضعیت رنگ
    paint_full = any(re.search(p, norm) for p in LEXICON["paint_full"])
    paint_partial = any(re.search(p, norm) for p in LEXICON["paint_partial"])
    paint_none = any(re.search(p, norm) for p in LEXICON["no_paint"])
    
    # خط و خش / فرو رفتگی
    scratches = any(re.search(p, norm) for p in LEXICON["scratch"])
    dents = any(re.search(p, norm) for p in LEXICON["dent"])

    # شدت آسیب
    severity = severity_from_text(norm)
    if severity == "major":
        body_damage = "major"
    elif severity == "moderate":
        body_damage = "moderate"
    elif severity == "minor":
        body_damage = "moderate" if dents and scratches else "minor"
    else:
        if parts_replaced or paint_full:
            body_damage = "moderate"
        elif paint_partial or scratches or dents:
            body_damage = "minor"
        else:
            body_damage = "none"

    # وضعیت رنگ نهایی
    paint_status = (
        "full"
        if paint_full
        else ("partial" if paint_partial else ("none" if paint_none else "unknown"))
    )

    # محاسبه confidence
    evidence = {
        "exact_paint_full": int(paint_full),
        "exact_paint_partial": int(paint_partial),
        "exact_paint_none": int(paint_none),
        "kw_scratches": int(scratches),
        "kw_dents": int(dents),
        "exact_parts_replaced": len(parts_replaced),
        "kw_parts_mentioned": len(parts_mentioned),
        "kw_chassis_ok": int(chassis_ok),
        "kw_chassis_dmg": int(chassis_dmg),
        "kw_engine_ok": int(engine_ok),
        "kw_engine_problem": int(engine_problem),
        "multi_accident": int(accident),
    }
    confidence = compute_confidence(evidence)

    # نرمال‌سازی قطعات
    replaced_parts_norm = list(dict.fromkeys([normalize_persian_text(p) for p in parts_replaced]))
    parts_mentioned_norm = list(dict.fromkeys([normalize_persian_text(p) for p in parts_mentioned]))

    # شدت خط و خش و فرورفتگی
    scratches_sev = "major" if scratches and severity == "major" else ("minor" if scratches else "none")
    dents_sev = "major" if dents and severity == "major" else ("minor" if dents else "none")

    features = {
        "paint_status": paint_status,
        "body_damage": body_damage,
        "replaced_parts": replaced_parts_norm,
        "parts_mentioned": parts_mentioned_norm,
        "scratches": scratches_sev,
        "dents": dents_sev,
        "chassis_condition": "damaged" if chassis_dmg else ("healthy" if chassis_ok else "unknown"),
        "technical": "problem" if engine_problem else ("ok" if engine_ok else "unknown"),
        "accident_mention": accident,
        "confidence": confidence,
        "raw_found": lex_matches,
    }

    return features


# ---------------------------
# 3b) Convert features to boolean flags per part
# ---------------------------


def features_to_boolean_flags(features: dict) -> dict:
    """
    تبدیل فیچرهای استخراج شده به فلگ‌های بولین سه‌حالته برای هر قطعه:
    رنگ شده / بدون رنگ / تعویض
    هر پارت مستقل از سایر پارت‌ها بررسی می‌شود.
    """
    flags = {}
    parts = ["درب", "گلگیر", "سپر", "کاپوت", "صندوق", "سقف", "شاسی", "اتاق", "بامپر"]

    paint_status = features.get("paint_status", "unknown")
    replaced_parts = features.get("replaced_parts", [])
    parts_mentioned = features.get("parts_mentioned", [])

    for part in parts:
        # تعویض: فقط اگر همان پارت در replaced_parts باشد
        flags[f"{part}_تعویض"] = 1 if part in replaced_parts else 0

        # رنگ: فقط اگر همان پارت در parts_mentioned باشد و paint_status full/partial باشد
        flags[f"{part}_رنگ"] = 1 if part in parts_mentioned and paint_status in ["full", "partial"] else 0

        # بدون رنگ: فقط اگر همان پارت در parts_mentioned باشد و paint_status none باشد
        flags[f"{part}_بدون_رنگ"] = 1 if part in parts_mentioned and paint_status == "none" else 0

    return flags



# ---------------------------
# 4) IO & Processing pipeline
# ---------------------------


def process_csv_stream(
    input_csv: str,
    desc_col: str = "description",
    out_json: Optional[str] = None,
    out_csv: Optional[str] = None,
    out_sqlite: Optional[str] = None,
    out_flags_csv: Optional[str] = None,  # اضافه شد
    batch_size: int = 200,
):
    json_fp = open(out_json, "w", encoding="utf-8") if out_json else None
    csv_fp = open(out_csv, "w", encoding="utf-8", newline="") if out_csv else None
    flags_fp = (
        open(out_flags_csv, "w", encoding="utf-8", newline="")
        if out_flags_csv
        else None
    )
    sqlite_conn = sqlite3.connect(out_sqlite) if out_sqlite else None

    csv_writer = None
    if csv_fp:
        csv_writer = csv.writer(csv_fp)
        csv_writer.writerow(
            [
                "row_number",
                desc_col,
                "paint_status",
                "body_damage",
                "replaced_parts",
                "parts_mentioned",
                "scratches",
                "dents",
                "chassis_condition",
                "technical",
                "accident_mention",
                "confidence",
            ]
        )

    flags_writer = None
    flag_cols = []
    if flags_fp:
        flag_cols = sorted(
            [
                f"{part}_{s}"
                for part in [
                    "درب",
                    "گلگیر",
                    "سپر",
                    "کاپوت",
                    "صندوق",
                    "سقف",
                    "شاسی",
                    "اتاق",
                    "بامپر",
                ]
                for s in ["رنگ", "بدون_رنگ", "تعویض"]
            ]
        )
        flags_writer = csv.writer(flags_fp)
        flags_writer.writerow(["row_number"] + flag_cols)

    if sqlite_conn:
        cur = sqlite_conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                row_number INTEGER,
                description TEXT,
                paint_status TEXT,
                body_damage TEXT,
                replaced_parts TEXT,
                parts_mentioned TEXT,
                scratches TEXT,
                dents TEXT,
                chassis_condition TEXT,
                technical TEXT,
                accident_mention INTEGER,
                confidence REAL,
                raw_found_json TEXT
            )
        """
        )
        sqlite_conn.commit()

    with open(input_csv, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if desc_col not in reader.fieldnames:
            raise ValueError(
                f"Description column '{desc_col}' not found in CSV. Columns: {reader.fieldnames}"
            )

        batch = []
        processed = 0
        for row_number, row in enumerate(reader, start=1):
            raw_desc = row.get(desc_col, "") or ""
            features = extract_features_from_text(raw_desc)
            record = {"row_number": row_number, "description": raw_desc, **features}

            if json_fp:
                json_fp.write(json.dumps(record, ensure_ascii=False) + "\n")

            if csv_writer:
                csv_writer.writerow(
                    [
                        record["row_number"],
                        record["description"],
                        record["paint_status"],
                        record["body_damage"],
                        (
                            ",".join(record["replaced_parts"])
                            if record["replaced_parts"]
                            else ""
                        ),
                        (
                            ",".join(record["parts_mentioned"])
                            if record["parts_mentioned"]
                            else ""
                        ),
                        record["scratches"],
                        record["dents"],
                        record["chassis_condition"],
                        record["technical"],
                        1 if record["accident_mention"] else 0,
                        record["confidence"],
                    ]
                )

            if flags_writer:
                part_flags = features_to_boolean_flags(features)
                flags_writer.writerow(
                    [row_number] + [part_flags[col] for col in flag_cols]
                )

            if sqlite_conn:
                raw_json = json.dumps(record.get("raw_found", {}), ensure_ascii=False)
                batch.append(
                    (
                        record["row_number"],
                        record["description"],
                        record["paint_status"],
                        record["body_damage"],
                        json.dumps(record["replaced_parts"], ensure_ascii=False),
                        json.dumps(record["parts_mentioned"], ensure_ascii=False),
                        record["scratches"],
                        record["dents"],
                        record["chassis_condition"],
                        record["technical"],
                        1 if record["accident_mention"] else 0,
                        record["confidence"],
                        raw_json,
                    )
                )

            processed += 1
            if sqlite_conn and len(batch) >= batch_size:
                cur.executemany(
                    """
                    INSERT INTO features (row_number, description, paint_status, body_damage,
                        replaced_parts, parts_mentioned, scratches, dents, chassis_condition,
                        technical, accident_mention, confidence, raw_found_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    batch,
                )
                sqlite_conn.commit()
                batch.clear()

        if sqlite_conn and batch:
            cur.executemany(
                """
                INSERT INTO features (row_number, description, paint_status, body_damage,
                    replaced_parts, parts_mentioned, scratches, dents, chassis_condition,
                    technical, accident_mention, confidence, raw_found_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                batch,
            )
            sqlite_conn.commit()
            batch.clear()

    if json_fp:
        json_fp.close()
    if csv_fp:
        csv_fp.close()
    if flags_fp:
        flags_fp.close()
    if sqlite_conn:
        sqlite_conn.close()

    print(
        f"Processed {processed} rows. Outputs written: {out_json or '-'}, {out_csv or '-'}, {out_sqlite or '-'}, {out_flags_csv or '-'}"
    )


# ---------------------------
# 5) CLI
# ---------------------------


def build_argparser():
    p = argparse.ArgumentParser(
        description="Feature Extraction Engine for car descriptions (Persian)."
    )
    p.add_argument("--input", "-i", required=True, help="Input CSV file path")
    p.add_argument(
        "--desc-col",
        "-d",
        default="description",
        help="Description column name (default: description)",
    )
    p.add_argument("--out-json", help="Output JSONL file (one JSON per line)")
    p.add_argument("--out-csv", help="Output CSV summary file")
    p.add_argument("--out-sqlite", help="Output SQLite DB file")
    p.add_argument(
        "--batch-size", type=int, default=200, help="SQLite batch insert size"
    )
    p.add_argument(
        "--out-flags-csv", help="Output CSV file with boolean flags per part"
    )
    return p


def main():
    parser = build_argparser()
    args = parser.parse_args()
    process_csv_stream(
        input_csv=args.input,
        desc_col=args.desc_col,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_sqlite=args.out_sqlite,
        out_flags_csv=args.out_flags_csv,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
