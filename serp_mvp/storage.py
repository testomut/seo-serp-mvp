"""Step 4: save everything to a local SQLite database and export it to results.xlsx.

Two tables:
- positions: one row per (date, keyword, position). Re-running on the same day replaces that day's rows,
  so there are never duplicates, and every new day adds to the position history.
- sites: one row per unique URL with its label. A URL is labelled once and reused on later runs.
"""
import json
import sqlite3
from datetime import datetime

from openpyxl import Workbook

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


def urls_to_check(db, run_date, llm_available):
    """URLs from today's results that have no label yet.
    If an LLM is available now, also re-check URLs that were labelled only by rules before."""
    rows = db.execute("""
        SELECT DISTINCT p.url FROM positions p
        LEFT JOIN sites s ON s.url = p.url
        WHERE p.run_date = ? AND (s.url IS NULL OR (? AND s.method = 'rules'))
    """, (run_date, llm_available)).fetchall()
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
     "Пусто в колонке даты - в тот день сайта в топ-10 не было.", ""],
]


def sites_table(db):
    """Rows for the "Sites" tab: header first, relevant sites on top."""
    rows = [["URL", "Domain", "Relevant", "Type", "Brands", "Contact", "Reason", "Checked by",
             "Best position", "Keywords"]]
    for row in db.execute("""
        SELECT s.*, MIN(p.position) AS best_position, GROUP_CONCAT(DISTINCT p.keyword) AS keywords
        FROM sites s JOIN positions p ON p.url = s.url
        GROUP BY s.url ORDER BY s.relevant DESC, best_position
    """):
        rows.append([row["url"], row["domain"], row["relevant"], row["site_type"],
                     ", ".join(json.loads(row["brands"])), row["contact"], row["reason"], row["method"],
                     row["best_position"], row["keywords"]])
    return rows


def positions_table(db):
    """Rows for the "Positions" tab: one row per keyword + URL, one column per date."""
    dates = [r["run_date"] for r in db.execute("SELECT DISTINCT run_date FROM positions ORDER BY run_date")]
    rows = [["Keyword", "URL", "Domain"] + dates]
    table = {}
    for r in db.execute("SELECT * FROM positions"):
        key = (r["keyword"], r["url"], r["domain"])
        table.setdefault(key, {})[r["run_date"]] = r["position"]
    for (keyword, url, domain), by_date in sorted(table.items()):
        rows.append([keyword, url, domain] + [by_date.get(d, "") for d in dates])
    return rows


def export_excel(db, path):
    workbook = Workbook()
    sites = workbook.active
    sites.title = "Sites"
    for row in sites_table(db):
        sites.append(row)
    history = workbook.create_sheet("Positions")
    for row in positions_table(db):
        history.append(row)
    help_tab = workbook.create_sheet("Help", 0)  # first tab
    for row in HELP_TABLE:
        help_tab.append(row)
    workbook.save(path)
