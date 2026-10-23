from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib

import pandas as pd
import streamlit as st

from .processor import validate_sales, REQUIRED


def fingerprint(frame):
    return hashlib.sha256(
        frame.to_csv(index=False).encode("utf-8")
    ).hexdigest()


def correction_editor(clean, issues):
    if issues.empty:
        return clean, issues

    valid_original = clean.copy()
    valid_original["Date"] = valid_original["Date"].dt.strftime("%Y-%m-%d")

    raw = pd.concat(
        [
            valid_original[["Source_Row"] + REQUIRED],
            issues[["Source_Row"] + REQUIRED],
        ],
        ignore_index=True,
    ).sort_values("Source_Row").reset_index(drop=True)

    identity = fingerprint(raw)[:16]
    prefix = "correction_" + identity
    committed = st.session_state.get(prefix + "_committed")
    current_clean, current_issues = (
        committed if committed is not None else (clean, issues)
    )

    with st.expander(
        "Fix data issues",
        expanded=committed is None,
    ):
        st.write(
            "Edit the flagged rows below. Preview validation before applying."
        )
        st.caption(
            "Dates: YYYY-MM-DD. Quantity: positive whole number. "
            "Unit price: non-negative number. "
            "An exact duplicate row can be excluded."
        )

        if len(issues) > 5000:
            st.warning(
                "More than 5,000 rows need review. "
                "Correct the source file and upload again."
            )
            return current_clean, current_issues

        editable = issues[
            ["Source_Row"] + REQUIRED + ["Issues"]
        ].copy()
        for field in REQUIRED:
            editable[field] = editable[field].fillna("").astype(str)
        editable["Exclude"] = False

        edited = st.data_editor(
            editable,
            disabled=["Source_Row", "Issues"],
            hide_index=True,
            num_rows="fixed",
            key=prefix + "_editor",
            column_config={
                "Exclude": st.column_config.CheckboxColumn(
                    "Exclude row",
                    help="Remove this row from the working dataset.",
                ),
                "Issues": st.column_config.TextColumn(
                    "Original validation issues"
                ),
            },
        )

        changes = []
        for index in editable.index:
            row_number = int(editable.loc[index, "Source_Row"])
            for field in REQUIRED:
                before = str(editable.loc[index, field])
                after = str(edited.loc[index, field])
                if before != after:
                    changes.append({
                        "Source row": row_number,
                        "Field": field,
                        "Before": before,
                        "After": after,
                    })
            if bool(edited.loc[index, "Exclude"]):
                changes.append({
                    "Source row": row_number,
                    "Field": "Exclude",
                    "Before": "Included",
                    "After": "Excluded",
                })

        if changes:
            st.write("Your pending changes")
            st.dataframe(pd.DataFrame(changes), hide_index=True)
        else:
            st.caption("No edits made yet.")

        edit_signature = fingerprint(edited)

        if st.button(
            "Preview and revalidate",
            key=prefix + "_preview_button",
        ):
            candidate = raw.copy()
            for _, row in edited.iterrows():
                mask = candidate["Source_Row"].eq(row["Source_Row"])
                if bool(row["Exclude"]):
                    candidate = candidate.loc[~mask].copy()
                else:
                    for field in REQUIRED:
                        candidate.loc[mask, field] = str(row[field])

            if candidate.empty:
                st.warning("Keep at least one sales row.")
                st.session_state.pop(prefix + "_preview", None)
            else:
                ordered = candidate.sort_values("Source_Row")
                source_numbers = ordered["Source_Row"].astype(int).tolist()

                with TemporaryDirectory() as temporary:
                    source = Path(temporary) / "corrected.csv"
                    ordered[REQUIRED].to_csv(source, index=False)
                    next_clean, next_issues = validate_sales(source)

                row_map = {
                    position + 2: original
                    for position, original in enumerate(source_numbers)
                }
                next_clean["Source_Row"] = (
                    next_clean["Source_Row"].map(row_map)
                )
                next_issues["Source_Row"] = (
                    next_issues["Source_Row"].map(row_map)
                )

                st.session_state[prefix + "_preview"] = {
                    "signature": edit_signature,
                    "clean": next_clean,
                    "issues": next_issues,
                }

        preview = st.session_state.get(prefix + "_preview")
        if preview and preview["signature"] == edit_signature:
            st.write("Validation preview")
            a, b = st.columns(2)
            a.metric("Valid sales rows", len(preview["clean"]))
            b.metric("Rows still needing review", len(preview["issues"]))

            if not preview["issues"].empty:
                st.dataframe(preview["issues"], hide_index=True)
            else:
                st.success("All remaining rows passed validation.")

            st.caption(
                "Applying updates dashboard totals, charts and downloads. "
                "Rows still needing review remain excluded from totals."
            )
            if st.button(
                "Apply corrections",
                key=prefix + "_apply",
                disabled=preview["clean"].empty,
            ):
                st.session_state[prefix + "_committed"] = (
                    preview["clean"], preview["issues"]
                )
                st.rerun()
        elif preview:
            st.info("Edits changed. Preview and revalidate again.")

        if committed is not None:
            st.success("Corrections applied to this session.")
            st.caption(
                "You can revise the original flagged rows above and apply again."
            )

    return current_clean, current_issues
