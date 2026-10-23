# Universal Data Studio

**Turn CSV and Excel files into configurable dashboards, reproducible transformations and shareable reports.**

Built with Python, Streamlit, Pandas and Altair. Includes a general-purpose analytics workspace and a sales reporting preset.

## Features

| Capability | What it does |
|---|---|
| Dataset profiler | Shows sample values, missing counts, uniqueness and suggested field types |
| Schema editor | Confirms types, identifier/category/measure roles, formats and aggregation defaults |
| Dynamic dashboards | Configurable filters, KPI cards and Bar, Line, Area, Donut, Scatter and Histogram charts |
| Dashboard suggestions | Suggests chart configurations for review based on available fields |
| Drill-down | Displays matching records when selecting grouped Bar, Line or Area chart marks |
| Multi-file joins | Left, inner and outer joins with unmatched-row and duplicate-key previews |
| Key normalisation | Optional case folding and numeric ID equivalence, with previews |
| Data cleaning | Preview and resolve duplicates by keeping rows or aggregating selected measures |
| Calculated fields | Addition, subtraction, multiplication, division, percentages and date differences |
| Transformation history | Replayable steps with undo and redo |
| Dataset snapshots | Account-scoped source data, schema, transformations, filters and chart configuration |
| Data refresh | Checks changed columns and previews replaying transformations on replacement data |
| Data dictionary | Editable field descriptions and units |
| Exports | Filtered CSV, multi-sheet Excel and PDF containing the selected chart |
| Sales preset | Sales validation, period comparisons, revenue targets and branded reports |

## Technology

- **Application:** Python and Streamlit
- **Data processing:** Pandas
- **Visualisation:** Altair and Vega-Lite
- **Storage:** SQLite
- **Excel:** OpenPyXL
- **PDF:** ReportLab
- **Chart rendering:** vl-convert-python

## Quick start — Windows CMD

Install Python, then open CMD in the project directory:

```cmd
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open **http://127.0.0.1:8501**, create a local account, and sign in. Keep the CMD window running; press `Ctrl+C` to stop the app.

### Start again later

```cmd
call .venv\Scripts\activate.bat
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Using Universal studio

1. Select **Universal studio** in the sidebar.
2. Upload a CSV or XLSX file and select the worksheet or CSV reading options.
3. Choose **Start a new dataset from this file**.
4. Review the profiler and confirm the schema.
5. Apply a dashboard suggestion or choose your own measures, grouping and calculations.
6. Preview transformations before applying them. Use undo/redo to revise changes.
7. Save a dataset snapshot or prepare PDF/Excel exports.

To reopen work without uploading again, use **Open saved dataset snapshots**. For related files, select **Connect datasets** and review the keys, normalisation options and estimated row count before building a join.

### Example: football player statistics

With fields such as `player_name`, `goals` and `assists`:

- Keep player IDs as **Identifier** fields.
- Mark goals and assists as numeric **Measures**.
- Create `goal_contributions` using **Add**, with `goals` and `assists` as inputs.
- Compare players using a bar chart.

Repeated source-statistic rows require review before aggregation. Files summarised to one row per player are easier to analyse reliably.

## Data handling

- Source uploads: CSV/XLSX rectangular tables, up to **20 MB**, **100,000 rows** and **300 fields**.
- Joins: capped at **200,000 output rows**.
- Blank join keys never match. Numeric ID normalisation is optional and removes leading zeros.
- Missing numeric values are preserved. Division by zero produces a missing value.
- Aggregation choices must reflect the dataset's grain; suggestions are heuristics.
- PDF previews include up to 40 rows and five fields per table. Excel includes the complete selected data.
- Scatter charts display up to 5,000 records; exports retain all selected records.

## Local storage and authentication

Local accounts, settings and snapshots are stored under `private/`. Snapshots are scoped to the signed-in account through application queries; local database files are not encrypted at rest.

Email verification is currently on hold. The included authentication workflow is intended for local development. Public hosting requires production authentication, access controls and a suitable storage/backup design.

Never commit `private/`, `.env`, `.streamlit/secrets.toml`, account databases or client datasets. The repository's ignore rules exclude these files.

## Tests

```cmd
python -m pip install pytest
python -m pytest tests -q
```

See [VALIDATION.md](VALIDATION.md) for checks executed on the integrated upgrade, including automated Streamlit checks and PDF rendering. External football fixtures are not bundled; the associated test skips when they are unavailable.

## Project structure

```text
app.py                         Application entry and workspace selection
src/universal.py               Dataset profiling and type conversion
src/studio_app.py              Integrated Universal studio interface
src/studio_core.py             Transformations, aggregation and snapshots
src/studio_exports.py          Universal Excel and PDF generation
src/relationships.py           Multi-file joins and key normalisation
src/account_ui.py              Local account workflow
src/workspace.py               Sales analytics workspace
src/assets/                    PDF font and attribution
tests/                         Automated checks
data/sample_sales.csv          Demonstration sales data
```

## Upgrade an existing installation

Extract an upgrade bundle into a **separate folder**, stop the running app, then run:

```cmd
INSTALL_UPDATE.cmd
```

For a custom target:

```cmd
INSTALL_UPDATE.cmd "D:\projects\sales-report-automation"
```

The installer backs up replaced code under `upgrade_backups/` and preserves existing private data. See [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md) for details. Restoring a code backup does not roll back Python package changes.

## Font attribution

PDF exports bundle DejaVu Sans. Its license is included in [src/assets/FONT_LICENSE.txt](src/assets/FONT_LICENSE.txt). Font coverage does not imply support for every script or complex-script shaping.

## Author

[Aditya Bhardwaj](https://github.com/Adityabhardwaj2209)
