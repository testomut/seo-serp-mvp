"""Google Sheets: the manager's view of the results and the place where keywords are edited.

Optional. Enabled when GOOGLE_SHEET_ID and GOOGLE_CREDENTIALS_FILE are set (see README).
Tabs: "Keywords" (edited by the manager), "Sites" and "Positions" (rewritten after every run).
"""
import csv
import os

import gspread

import config
from serp_mvp import storage


def enabled():
    return bool(os.getenv("GOOGLE_SHEET_ID") and os.getenv("GOOGLE_CREDENTIALS_FILE"))


def sheet_url():
    return f"https://docs.google.com/spreadsheets/d/{os.getenv('GOOGLE_SHEET_ID')}"


def open_spreadsheet():
    client = gspread.service_account(filename=os.getenv("GOOGLE_CREDENTIALS_FILE"))
    return client.open_by_key(os.getenv("GOOGLE_SHEET_ID"))


def get_tab(spreadsheet, title):
    """Return the tab with this title, creating an empty one if it doesn't exist."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=100, cols=20)


def keywords_tab():
    """The "Keywords" tab. On the very first run it is filled from keywords.csv."""
    tab = get_tab(open_spreadsheet(), "Keywords")
    if not tab.acell("A1").value:  # an empty tab returns [[]], so check the first cell instead
        with open(config.KEYWORDS_FILE, encoding="utf-8") as file:
            tab.update(values=list(csv.reader(file)), range_name="A1")
    return tab


def read_keywords():
    return [row["keyword"] for row in keywords_tab().get_all_records()
            if str(row["active"]).strip().lower() == "yes"]


def add_keyword(keyword):
    keywords_tab().append_row([keyword, "", "yes"])


def deactivate_keyword(keyword):
    """Set active = no. Returns False if the keyword is not in the tab."""
    tab = keywords_tab()
    cell = tab.find(keyword, in_column=1)
    if cell is None:
        return False
    tab.update_cell(cell.row, 3, "no")
    return True


def write_results(db):
    spreadsheet = open_spreadsheet()
    tables = [("Help", storage.HELP_TABLE), ("Sites", storage.sites_table(db)),
              ("Positions", storage.positions_table(db))]
    for title, rows in tables:
        tab = get_tab(spreadsheet, title)
        tab.clear()
        rows = [["" if value is None else value for value in row] for row in rows]
        tab.update(values=rows, range_name="A1")
    spreadsheet.worksheet("Help").update_index(0)  # keep the description as the first tab
