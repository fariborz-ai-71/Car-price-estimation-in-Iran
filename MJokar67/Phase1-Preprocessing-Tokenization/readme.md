CSV Cleaner and Keyword Extractor (All Columns)

This Python script normalizes all text columns in a CSV file containing Persian text, extracts keywords and characters from the entire dataset, and generates summary statistics.

It is ideal for preprocessing Persian car advertisement datasets or any Persian text dataset for further analysis or machine learning tasks.

Features

Full CSV Normalization

Fixes Arabic characters (e.g., "ي" → "ی").

Converts Persian digits to English digits.

Removes zero-width non-joiners (ZWNJ) and RTL marks.

Removes punctuation and extra whitespace.

Keyword Extraction

Extracts all Persian words from every column.

Saves unique keywords in keywords.txt, sorted alphabetically.

Character Extraction

Collects all characters appearing in the dataset.

Saves them in characters_used.txt with Unicode codes.

Statistics

Generates stats.json with:

Total number of unique keywords.

Top 100 most common keywords.

Total unique characters.

Outputs

Clean CSV: All text columns normalized, structure preserved.

keywords.txt: Alphabetically sorted keywords from all columns.

characters_used.txt: Characters and Unicode points used in dataset.

stats.json: Summary statistics for keyword and character counts.

Command-Line Interface (CLI)

Input and output directories are provided via command-line arguments.

Automatically creates output directory if it does not exist.

Usage:

python3 preprocessor.py <input_csv_path> <output_directory>


Output Files in <output_directory>:

Clean CSV: car_bama_1_clean.csv

Unique keywords: keywords.txt

Unique characters: characters_used.txt

Stats summary: stats.json

Notes

All text columns in the CSV are processed, not just a single description column.

Keywords and characters are extracted from all text in the CSV.

Useful for feature extraction, text analysis, and ML preprocessing.
