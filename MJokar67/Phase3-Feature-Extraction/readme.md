Persian Car Ads Feature Extraction Engine

This Python script is a feature extraction engine designed for Persian car advertisements. It reads a CSV file containing car listings, preprocesses and normalizes the text, and extracts structured features about vehicle condition, damage, parts, paint, and accidents.

The extracted features can be exported to JSONL, CSV, or SQLite, and boolean flags per part can also be generated for detailed analysis.

Features

Text Normalization / Preprocessing

Fixes Arabic characters to standard Persian.

Removes diacritics, zero-width characters, and special punctuation.

Standardizes whitespace and common symbols.

Converts text to lowercase for uniform processing.

Rule-based & Regex Feature Extraction

Uses a lexicon of keywords/regex for detecting:

Full, partial, or no paint.

Scratches and dents.

Replaced or mentioned car parts.

Chassis and engine conditions.

Accident mentions.

Supports severity classification: major, moderate, minor.

Confidence Scoring

Computes a confidence score for each record based on evidence weights.

Evidence includes regex matches, keyword hits, and multi-source verification.

Boolean Flags Per Part

Generates three-state flags for each car part:

Painted / Not painted / Replaced

Supports detailed analysis per part.

Streaming CSV Processing

Handles large CSV files efficiently without loading entire dataset into memory.

Supports batch insertion into SQLite for performance.

Flexible Output Formats

JSONL: Each record as a single JSON object.

CSV: Summary of all features.

SQLite: Stores all records with structured columns.

Flags CSV: Boolean flags per part for detailed analysis.

Command-Line Usage:

python feature_extractor.py --input input.csv --out-json out.jsonl --out-csv out.csv --out-sqlite out.db --out-flags-csv flags.csv

Arguments:

--input / -i: Input CSV file path.

--desc-col / -d: Column name containing car description text (default: description).

--out-json: JSONL output file (one JSON per line).

--out-csv: Summary CSV file output.

--out-sqlite: SQLite database file for storing structured records.

--out-flags-csv: CSV file with boolean flags per part.

--batch-size: Batch size for SQLite inserts (default: 200).


python feature_extractor.py \
    --input car_ads.csv \
    --desc-col description \
    --out-json car_features.jsonl \
    --out-csv car_features.csv \
    --out-sqlite car_features.db \
    --out-flags-csv car_flags.csv

Files

JSONL: Raw features and structured extraction for each row.

CSV Summary: Key features extracted from each record.

SQLite DB: All features stored in a relational database with support for querying.

Flags CSV: Boolean flags for each part indicating paint/replacement status.

Notes

Designed for Persian-language car ads; regexes and lexicons are tuned for common Persian terms.

Supports partial/full damage, replaced parts, scratches, dents, paint, and technical conditions.

Can be integrated into ML pipelines for feature engineering, classification, or analytics.

Efficient for large datasets using streaming and batch processing.
