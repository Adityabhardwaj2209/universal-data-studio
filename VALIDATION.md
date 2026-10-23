# Validation results

Executed on 23 October 2026 in the provided Linux workspace.

- 15 automated tests passed: numeric ID normalisation; nonmatching blank join keys; many-to-many row expansion; normalised join; calculated fields and division by zero; date differences; duplicate resolution/replay; missing numeric sum; owner-scoped snapshot reads/deletes and restart roundtrip; refresh schema changes and suggestions; safe Excel cells and PDF generation; three actual uploaded football datasets; Streamlit rendering and suggestion application; calculated-field preview/apply/undo; all six chart formats and export generation; snapshot save/open/delete UI.
- Compiled Python modules successfully.
- Generated a three-page football PDF using uploaded player summary data; rendered and visually reviewed all pages. Chart labels, European names, table continuation headers and pagination were legible.
- Simulated update installation into a temporary project: original app backup retained and a pre-existing private/accounts.db file remained byte-identical.

Limits: tests use Streamlit AppTest rather than a physical browser. Real pointer/touch drill-down selection is implemented but was not exercised with a physical browser. The Windows .cmd wrapper was inspected, not executed on Windows. No email was sent, no public deployment performed, and no user's private accounts/database were provided or modified. Test-generated databases are excluded from the bundle.
