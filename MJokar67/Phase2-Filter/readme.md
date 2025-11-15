CSV Filter Script for Persian Car Ads

This Python script is designed to filter car advertisement CSV files based on predefined Persian keywords, removing rows that match certain patterns (e.g., installment sales, dealership, swap, auction, zero-kilometer, etc.) and generating a log of rejected records.

It is particularly useful for preprocessing car listing datasets (e.g., from Divar, Bama, etc.) before feature extraction or machine learning tasks.

Features

Structured Keyword Filtering

Keywords are organized into groups (installment, agency, documents, commercial, zero-km, swap, auction).

Adding or removing keywords is easy via the FILTER_GROUPS dictionary.

Comprehensive Regex

All keywords are combined into a single regex pattern for fast matching.

Case-insensitive matching.

Outputs

Clean CSV: Only valid rows that do not match any of the filter keywords.

Rejected Log CSV: Contains Record_ID_In_Original_File and Matched_Keywords for all filtered rows, sorted by matched keywords.

Command-Line Interface (CLI)

Input and output paths are specified via command-line arguments.

Automatically creates output directory if it does not exist.

Usage:

python3 filter.py <input_csv_path> <output_directory_path>

Output Files

Given car_bama_1.csv as input:

Cleaned CSV: Divar-1/Out/car_bama_1_clean.csv

Rejected log CSV: Divar-1/Out/car_bama_1_rejected_log.csv

CSV Requirements

The script expects a column named "description" (case-insensitive) containing ad text.

All other columns are preserved in the output.
