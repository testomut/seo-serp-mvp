"""All settings in one place. Change the market here (e.g. "uk" / "google.co.uk")."""

COUNTRY = "ca"              # Google country code
GOOGLE_DOMAIN = "google.ca"
LANGUAGE = "en"
DEVICE = "mobile"           # "mobile" or "desktop"
TOP_N = 10                  # how many results to keep per keyword

KEYWORDS_FILE = "keywords.csv"
BRANDS_FILE = "data/brands.txt"
SAMPLE_SERP_FILE = "data/sample_serp.json"
DB_FILE = "data/serp.db"
EXCEL_FILE = "results.xlsx"

PAGE_TEXT_LIMIT = 12000     # characters of page text sent to the LLM
LLM_PAUSE_SECONDS = 5       # pause between LLM calls (free Gemini has a per-minute limit)
