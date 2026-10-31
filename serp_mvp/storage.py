"""Step 4: save everything to a local SQLite database and export it to results.xlsx.

Two tables:
- positions: one row per (date, keyword, position). Re-running on the same day replaces that day's rows,
  so there are never duplicates, and every new day adds to the position history.
- sites: one row per unique URL with its label. A URL is labelled once and reused on later runs.
- searches: one row per (date, keyword): "ok" with the number of results, or "failed". So a failed search is
  shown as "no data", not as "the site dropped out of the top".
"""
import json
import sqlite3
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

import config
from serp_mvp import rules
from serp_mvp.rules import domain_of


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            run_date TEXT, keyword TEXT, position INTEGER, url TEXT, domain TEXT, title TEXT, source TEXT,
            PRIMARY KEY (run_date, keyword, position)
        );
        CREATE TABLE IF NOT EXISTS sites (
            url TEXT PRIMARY KEY, domain TEXT, relevant TEXT, site_type TEXT, brands TEXT,
            contact TEXT, reason TEXT, method TEXT, checked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS searches (
            run_date TEXT, keyword TEXT, status TEXT, results INTEGER,
            PRIMARY KEY (run_date, keyword)
        );
    """)
    return db


def save_positions(db, run_date, keyword, results, source):
    with db:  # one transaction: delete + insert happen together or not at all
        db.execute("DELETE FROM positions WHERE run_date = ? AND keyword = ?", (run_date, keyword))
        for r in results:
            db.execute(
                "INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_date, keyword, r["position"], r["url"], domain_of(r["url"]), r["title"], source),
            )
        db.execute("INSERT OR REPLACE INTO searches VALUES (?, ?, 'ok', ?)", (run_date, keyword, len(results)))


def save_failed_search(db, run_date, keyword):
    """Remember the failure, but never overwrite a successful search made earlier the same day."""
    with db:
        db.execute("INSERT OR IGNORE INTO searches VALUES (?, ?, 'failed', 0)", (run_date, keyword))


def urls_to_check(db, run_date, llm_available):
    """URLs from today's results that have no label yet. If an LLM is available now, also re-check URLs
    labelled by rules or by an older prompt (method doesn't end with the current LABEL_VERSION)."""
    rows = db.execute("""
        SELECT DISTINCT p.url FROM positions p
        LEFT JOIN sites s ON s.url = p.url
        WHERE p.run_date = ? AND (s.url IS NULL OR (? AND s.method NOT LIKE ?))
    """, (run_date, llm_available, f"%, {config.LABEL_VERSION}")).fetchall()
    return [row["url"] for row in rows]


def save_site(db, url, label):
    relevant = {True: "yes", False: "no", None: "unknown"}[label["relevant"]]
    with db:
        db.execute(
            "INSERT OR REPLACE INTO sites VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (url, domain_of(url), relevant, label["site_type"], json.dumps(label["brands"]),
             label["contact"], label["reason"], label["method"], datetime.now().isoformat(timespec="seconds")),
        )


HELP_TABLE = [
    ["Колонка", "Что значит"],
    ["Sites - Все уникальные сайты из выдачи. Подходящие сверху, внутри - по лучшей позиции.", ""],
    ["URL / Domain", "Адрес найденной страницы и сайт."],
    ["Relevant", "Подходит ли сайт для размещения наших брендов. yes - обзорник, рейтинг или сайт с бонусами; "
                 "no - сайт казино, Википедия, форум, новости, регулятор; "
                 "unknown - сайт не открылся (защита от ботов), стоит проверить вручную."],
    ["Type", "Тип сайта: review (обзоры, рейтинги, бонусы), casino (сайт самого казино), wiki, news, forum, "
             "regulator, other, unknown."],
    ["Brands", "Казино-бренды, упомянутые на странице."],
    ["Contact", "Email или страница Contact для связи с владельцем сайта. Пусто - не найдено."],
    ["Reason", "Короткое объяснение, почему так решено."],
    ["Checked by", "Кто размечал: gemini (ИИ, точнее) или rules (простые правила, если ИИ недоступен "
                   "или страница не открылась). Такие сайты перепроверяются ИИ при следующем прогоне."],
    ["Best position", "Лучшее место сайта в Google среди всех ключей."],
    ["Keywords", "По каким ключам сайт найден."],
    ["Keywords - Ключи для поиска. Менеджер редактирует эту вкладку сам, изменения подхватываются "
     "на следующем прогоне.", ""],
    ["keyword", "Фраза, которую ищем в Google (Канада, мобильная выдача)."],
    ["cluster", "Группа ключа, для удобства."],
    ["active", "yes - искать, no - не искать (история сохраняется)."],
    ["Positions - История позиций: строка - ключ + URL, колонки - даты прогонов. "
     "Пусто в колонке даты - в тот день сайта в топ-10 не было. "
     "no data - поиск по ключу в тот день не удался, о позиции ничего не известно.", ""],
]


def sites_table(db):
    """Rows for the "Sites" tab: header first, relevant sites on top.
    Brand spellings are unified here, so older rows get cleaned up too ("Tonybet Casino" -> "TonyBet")."""
    rows = [["URL", "Domain", "Relevant", "Type", "Brands", "Contact", "Reason", "Checked by",
             "Best position", "Keywords"]]
    sites = db.execute("""
        SELECT s.*, MIN(p.position) AS best_position, GROUP_CONCAT(DISTINCT p.keyword) AS keywords
        FROM sites s JOIN positions p ON p.url = s.url
        GROUP BY s.url ORDER BY s.relevant DESC, best_position
    """).fetchall()
    names = rules.brand_names([json.loads(row["brands"]) for row in sites], rules.load_brands())
    for row in sites:
        brands = dict.fromkeys(names[rules.brand_key(b)] for b in json.loads(row["brands"]))  # unique, in order
        rows.append([row["url"], row["domain"], row["relevant"], row["site_type"],
                     ", ".join(brands), row["contact"], row["reason"], row["method"],
                     row["best_position"], row["keywords"]])
    return rows


def positions_table(db):
    """Rows for the "Positions" tab: one row per keyword + URL, one column per date."""
    dates = [r["run_date"] for r in db.execute(
        "SELECT run_date FROM positions UNION SELECT run_date FROM searches ORDER BY run_date")]
    rows = [["Keyword", "URL", "Domain"] + dates]
    failed = {(r["keyword"], r["run_date"]) for r in db.execute("SELECT * FROM searches WHERE status = 'failed'")}
    table = {}
    for r in db.execute("SELECT * FROM positions"):
        key = (r["keyword"], r["url"], r["domain"])
        table.setdefault(key, {})[r["run_date"]] = r["position"]
    for (keyword, url, domain), by_date in sorted(table.items()):
        empty = lambda d: "no data" if (keyword, d) in failed else ""
        rows.append([keyword, url, domain] + [by_date.get(d, empty(d)) for d in dates])
    return rows


# Column widths for the Excel file; columns not listed get 12
WIDTHS = {"Help": [40, 100], "Sites": [45, 25, 10, 10, 40, 35, 50, 25, 8, 40], "Positions": [30, 50, 25]}


def export_excel(db, path):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in [("Help", HELP_TABLE), ("Sites", sites_table(db)), ("Positions", positions_table(db))]:
        tab = workbook.create_sheet(title)
        for row in rows:
            tab.append(row)
        # Readable view: bold frozen header, filters, column widths, long text wrapped
        tab.freeze_panes = "A2"
        tab.auto_filter.ref = tab.dimensions
        for cell in tab[1]:
            cell.font = Font(bold=True)
        for column in tab.iter_cols(min_row=2):
            for cell in column:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for number, column in enumerate(tab.columns):
            width = WIDTHS[title][number] if number < len(WIDTHS[title]) else 12
            tab.column_dimensions[column[0].column_letter].width = width
    workbook.save(path)
