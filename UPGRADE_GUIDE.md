# Universal Studio integrated upgrade

Stop your running app. Extract this ZIP into a separate folder, such as Downloads\Universal_Studio_Complete. Do not extract it over the running project.

From Windows CMD in the extracted folder run:

    INSTALL_UPDATE.cmd

For a custom project path:

    INSTALL_UPDATE.cmd "D:\my-project\sales-report-automation"

The script installs dependencies into the existing project environment, backs up replaced code under upgrade_backups, installs the update, and launches the app on http://127.0.0.1:8501. It does not replace private accounts, credentials or databases. Python package changes are not reverted by restoring a code backup.

Sign in, select Universal studio in the sidebar. The previous sales workflow and Any-data explorer remain available.

## All ten features

1. **Dashboard suggestions**: after confirming the schema, review and apply up to four heuristic chart suggestions. KPI operations are explicitly selectable. Suggestions are not domain facts.
2. **Dataset snapshots**: save source rows, schema, operations, filters, chart settings and dictionary. Open a snapshot at the top of Universal studio without uploading a file. Every read/delete is account scoped.
3. **Join-key normalisation**: Connect datasets supports case folding and optional numeric-ID equivalence with previews. Numeric conversion removes leading zeros. Blank keys do not match. Many-to-many expansion is reported before building the join.
4. **Duplicate resolution**: select keys, inspect duplicate rows, preview keep-first/keep-last or aggregation, then apply. Aggregation intentionally retains only keys and selected measures.
5. **Calculated fields**: add, subtract, multiply, divide, percentage and date difference using selected fields. No arbitrary expressions/eval. Zero division becomes missing. Preview before applying.
6. **Universal exports**: filtered CSV; Excel with data, schema, dictionary, history and grouped values; paginated PDF with the current chart and readable data previews. PDF tables are limited to 40 records and five fields; Excel includes complete selected data. The bundled DejaVu font supports common European text and the rupee glyph, not every script or complex-script shaping.
7. **Data refresh**: preview missing/new columns and row counts, validate conversions, replay operations, then explicitly apply. Missing required columns block refresh. New columns are preserved but ignored until the schema is edited. Editing schema resets transformations/settings.
8. **Drill-down**: select bars or points on grouped Bar/Line/Area charts to display matching records. Scatter supports zoom/pan and displays up to 5,000 records. Donut/histogram have no linked detail selection in this version.
9. **Data dictionary**: field descriptions and units editable; included in snapshots and Excel.
10. **Undo/history**: transformations are explicit operations replayed from the converted source; undo and redo are supported. Apply a new operation after undo to clear redo. History is included in snapshots and Excel.

## Scope and limits

CSV/XLSX rectangular tables, up to 20 MB, 100,000 source rows and 300 fields. Joins capped at 200,000 output rows. IDs retain text; keys are not fuzzy-matched. Missing measurements remain missing. Schema and aggregation choices need review, especially for repeated sports-statistic sources. The studio stores snapshots locally in private/studio_v2.db; it is not encrypted at rest. Existing local authentication remains a local-development workflow; email verification remains on hold.

The original user datasets are not bundled in this ZIP. Existing snapshots from the sales workspace remain in that workspace. Universal v2 snapshots use a separate database.

## Validation

Run automated checks with:

    python -m pip install pytest
    python -m pytest tests -q

See VALIDATION.md for checks executed on this bundle.
