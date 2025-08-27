# Configuration for TradeWatch Telegram Bot

# Allegro settings
ALLEGRO_BASE_URL = "https://allegro.pl/oferta/"

# Column names to search for link numbers
LINK_NUMBER_COLUMNS = ['Link.1', 'Link', 'link', 'LINK']

# TradeWatch file settings
TRADEWATCH_FILE_PATTERN = "TradeWatch*.xlsx"
TRADEWATCH_SHEET_NAME = 0  # First sheet

# Output file names
OUTPUT_FILE_MERGED_TRADEWATCH = "merged_tradewatch_result.xlsx"
OUTPUT_FILE_WITH_CALCULATIONS = "merged_by_ean_result_with_calculations.xlsx"
OUTPUT_FILE_TRADEWATCH_ONLY = "tradewatch_only_result.xlsx"

# File exclusions
EXCLUDED_FILE_PREFIXES = ["merged_", "result_", "~$"]

# Possible GTIN/EAN column names
POSSIBLE_GTIN_COLUMNS = ['GTIN', 'EAN', 'ean', 'gtin', 'EAN13', 'EAN-13']

# Desired column order for output
DESIRED_COLUMN_ORDER = [
    'Lp', 'EAN', 'Price', 'Price PL', 'Cena min.', 'Profit', 'ROI', 
    'Link', 'Top oferta', 'Dost. szt.', 'Ilość aukcji', 
    'Transakcje (30 dni)', 'Product Link'
]
