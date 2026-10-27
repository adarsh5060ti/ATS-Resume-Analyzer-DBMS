"""One-click, read-only browser view of the synthetic faculty SQLite database."""

from datetime import datetime
import html
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import webbrowser
import shutil

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "instance" / "faculty_demo.db"
GENERATOR = ROOT / "scripts" / "create_faculty_demo_db.py"


def notify(title, message, error=False):
    try:
        import tkinter as tk
        from tkinter import messagebox

        window = tk.Tk()
        window.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, message)
        window.destroy()
    except Exception:
        print(f"{title}: {message}")


def ensure_database():
    if DATABASE.exists():
        return True
    project_python = ROOT / ".venv" / "Scripts" / "python.exe"
    system_python = shutil.which("python") or str(Path(sys.executable).with_name("python.exe"))
    python = str(project_python if project_python.exists() else system_python)
    result = subprocess.run(
        [python, str(GENERATOR)], cwd=ROOT, capture_output=True, text=True,
        timeout=180, check=False,
    )
    if result.returncode != 0 or not DATABASE.exists():
        details = (result.stderr or result.stdout or "No further details.").strip()
        notify(
            "Faculty demo database could not be created",
            "Open the project folder and install its requirements once with:\n\n"
            "python -m pip install -r requirements.txt\n\n"
            f"Details:\n{details[-1800:]}",
            error=True,
        )
        return False
    return True


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def ident(name):
    return '"' + name.replace('"', '""') + '"'


def make_html():
    import sqlite3

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    tables = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    views = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    triggers = connection.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
    ).fetchall()

    total_rows = 0
    sections = []
    relationships = []
    for table in tables:
        name = table["name"]
        quoted = ident(name)
        columns = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
        indexes = connection.execute(f"PRAGMA index_list({quoted})").fetchall()
        count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        total_rows += count

        header = "".join(f"<th>{esc(column['name'])}</th>" for column in columns)
        data_rows = []
        for row in connection.execute(f"SELECT * FROM {quoted} LIMIT 100"):
            cells = []
            for column in columns:
                value = row[column["name"]]
                if column["name"] == "password_hash":
                    value = "[stored hash hidden]"
                cells.append(f"<td>{esc(value)}</td>")
            data_rows.append("<tr>" + "".join(cells) + "</tr>")
        if not data_rows:
            data_rows.append(f'<tr><td colspan="{max(1, len(columns))}" class="empty">No rows in this table.</td></tr>')

        details = []
        for column in columns:
            flags = []
            if column["pk"]:
                flags.append("PK")
            if column["notnull"]:
                flags.append("NOT NULL")
            if column["dflt_value"] is not None:
                flags.append("DEFAULT " + str(column["dflt_value"]))
            details.append(
                "<tr>" +
                f"<td>{esc(column['name'])}</td><td>{esc(column['type'] or 'SQLite inferred')}</td>"+
                f"<td>{esc(', '.join(flags) or 'nullable')}</td></tr>"
            )
        fk_text = []
        for fk in foreign_keys:
            relationship = (
                f"{name}.{fk['from']} → {fk['table']}.{fk['to']}"
            )
            relationships.append(relationship)
            fk_text.append(f"<li>{esc(relationship)}</li>")
        index_text = [esc(index["name"]) for index in indexes]
        create_sql = table["sql"] or ""
        sections.append(
            '<section class="table-card">'
            f'<div class="table-title"><h2>{esc(name)}</h2><span>{count} row(s)</span></div>'
            '<details><summary>Columns, keys, indexes, and constraints</summary>'
            '<table class="meta"><thead><tr><th>Column</th><th>Type</th><th>Key / constraints</th></tr></thead>'
            f'<tbody>{"".join(details)}</tbody></table>'
            f'<p><b>Indexes:</b> {", ".join(index_text) if index_text else "none"}</p>'
            '<details class="sql"><summary>SQLite table definition</summary>'
            f'<pre>{esc(create_sql)}</pre></details></details>'
            '<div class="scroll"><table><thead><tr>' + header + '</tr></thead><tbody>' +
            "".join(data_rows) + '</tbody></table></div></section>'
        )

    object_sections = []
    for label, objects, show_table in (("Views", views, False), ("Triggers", triggers, True)):
        cards = []
        for item in objects:
            name = item["name"]
            associated = f"<span>on {esc(item['tbl_name'])}</span>" if show_table else ""
            sql = item["sql"] or ""
            preview = ""
            if label == "Views":
                rows = connection.execute(f"SELECT * FROM {ident(name)} LIMIT 20").fetchall()
                if rows:
                    cols = rows[0].keys()
                    preview = '<div class="scroll"><table><thead><tr>' + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr></thead><tbody>"
                    preview += "".join("<tr>" + "".join(f"<td>{esc(row[c])}</td>" for c in cols) + "</tr>" for row in rows)
                    preview += "</tbody></table></div>"
            cards.append(
                f'<article class="object-card"><h3>{esc(name)} {associated}</h3>{preview}'
                f'<details><summary>Definition</summary><pre>{esc(sql)}</pre></details></article>'
            )
        object_sections.append(
            f'<section><h2>{label}</h2>' + ("".join(cards) if cards else '<p class="empty">None found.</p>') + '</section>'
        )

    relation_list = "".join(f"<li>{esc(item)}</li>" for item in relationships)
    connection.close()
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATSAnalyzer Faculty Database</title><style>
:root{{--navy:#123b5d;--teal:#0fa6a8;--ink:#24384c;--line:#dbe4eb;--pale:#f3f8fb}}
*{{box-sizing:border-box}}body{{margin:0;background:#f2f6f9;color:var(--ink);font:15px/1.5 Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(115deg,#123b5d,#0e5375);color:#fff;padding:28px max(22px,calc((100vw - 1200px)/2))}}
header h1{{margin:0 0 7px;font-size:28px}}header p{{margin:5px 0;color:#e8f5fa}}
main{{max-width:1200px;margin:22px auto;padding:0 18px}}.notice{{padding:14px 18px;background:#e9f8f5;border-left:5px solid var(--teal);border-radius:8px;margin-bottom:18px}}
.summary{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 22px}}.pill{{background:white;border:1px solid var(--line);border-radius:9px;padding:12px 16px;min-width:145px;box-shadow:0 2px 8px #18384c0a}}
.pill b{{display:block;color:var(--navy);font-size:20px}}section{{margin:22px 0}}h2{{color:var(--navy);margin:8px 0 12px}}.table-card,.object-card{{background:#fff;border:1px solid var(--line);border-radius:12px;margin:14px 0;padding:16px;box-shadow:0 3px 12px #18384c0a}}
.table-title{{display:flex;justify-content:space-between;align-items:center;gap:12px}}.table-title h2{{margin:0}}.table-title span{{color:#526779;background:#eaf2f7;border-radius:20px;padding:4px 10px;font-size:13px}}
.scroll{{overflow:auto;margin-top:12px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th{{background:var(--navy);color:white;text-align:left;white-space:nowrap}}td,th{{border:1px solid var(--line);padding:8px 10px;vertical-align:top}}tbody tr:nth-child(even){{background:#f7fafc}}td{{max-width:420px;overflow-wrap:anywhere}}.meta{{margin:10px 0}}
summary{{cursor:pointer;color:#087f86;font-weight:600;padding:5px 0}}details{{margin-top:10px}}pre{{overflow:auto;background:#142b3d;color:#e6f2f8;padding:14px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}
.empty{{color:#65798a;font-style:italic}}footer{{text-align:center;color:#65798a;padding:24px}}@media print{{body{{background:#fff}}.table-card,.object-card{{box-shadow:none;break-inside:avoid}}header{{background:#123b5d!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body><header><h1>ATSAnalyzer - Faculty Database Walkthrough</h1>
<p>SQLite database: <b>{esc(DATABASE.name)}</b> | Generated {esc(timestamp)}</p>
<p>Local academic demo data only. This is separate from the live website and contains no real candidate information.</p></header>
<main><div class="notice"><b>Privacy note:</b> Public website uploads are temporary and are not saved in the application database. This local file is a synthetic demonstration copy. Password hashes are hidden in this view.</div>
<div class="summary"><div class="pill"><b>{len(tables)}</b>relational tables</div><div class="pill"><b>{total_rows}</b>total rows</div>
<div class="pill"><b>{len(views)}</b>view(s)</div><div class="pill"><b>{len(triggers)}</b>trigger(s)</div><div class="pill"><b>{esc(integrity)}</b>SQLite integrity</div></div>
<section><h2>Foreign-key relationships</h2><div class="table-card"><ul>{relation_list}</ul></div></section>
<section><h2>Tables and sample rows</h2>{''.join(sections)}</section>
{''.join(object_sections)}
<footer>Use <b>Ctrl+P</b> to print or save this walkthrough as a PDF.</footer></main></body></html>'''


def main():
    if not ensure_database():
        return
    try:
        page = make_html()
        output = Path(tempfile.gettempdir()) / "ATSAnalyzer_Faculty_Database.html"
        output.write_text(page, encoding="utf-8")
        if "--no-open" not in sys.argv:
            webbrowser.open(output.resolve().as_uri())
        print(f"Database overview ready: {output}")
    except Exception as exc:
        notify("Could not display the faculty database", str(exc), error=True)


if __name__ == "__main__":
    main()
