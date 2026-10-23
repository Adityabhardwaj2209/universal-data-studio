from io import BytesIO
import hashlib

import pandas as pd
import streamlit as st


def prepare_join_keys(frame, columns):
    keys = frame[columns].copy()
    for column in columns:
        keys[column] = keys[column].astype("string").str.strip()
        keys[column] = keys[column].mask(keys[column].eq(""))
    return keys


def join_tables(left, right, left_keys, right_keys, how):
    left = left.copy()
    right = right.copy()
    names = [f"__join_key_{i}__" for i in range(len(left_keys))]
    if any(name in left.columns or name in right.columns for name in names):
        raise ValueError("Reserved join-key column name found.")

    left_values = prepare_join_keys(left, left_keys)
    right_values = prepare_join_keys(right, right_keys)

    for index, name in enumerate(names):
        left[name] = left_values.iloc[:, index]
        right[name] = right_values.iloc[:, index]

    valid_left = left[names].notna().all(axis=1)
    valid_right = right[names].notna().all(axis=1)

    left_valid = left.loc[valid_left]
    right_valid = right.loc[valid_right]

    lc = left_valid.groupby(names).size().rename("Left rows")
    rc = right_valid.groupby(names).size().rename("Right rows")
    counts = pd.concat([lc, rc], axis=1).fillna(0).astype("int64")

    matched = counts["Left rows"].gt(0) & counts["Right rows"].gt(0)
    matched_rows = int(
        (counts.loc[matched, "Left rows"] * counts.loc[matched, "Right rows"]).sum()
    )
    unmatched_left = int(
        counts.loc[counts["Right rows"].eq(0), "Left rows"].sum()
    ) + int((~valid_left).sum())
    unmatched_right = int(
        counts.loc[counts["Left rows"].eq(0), "Right rows"].sum()
    ) + int((~valid_right).sum())

    estimates = {
        "inner": matched_rows,
        "left": matched_rows + unmatched_left,
        "outer": matched_rows + unmatched_left + unmatched_right,
    }
    information = {
        "estimated_rows": estimates[how],
        "unmatched_left": unmatched_left,
        "unmatched_right": unmatched_right,
        "left_duplicate_rows": int(left_valid.duplicated(names, keep=False).sum()),
        "right_duplicate_rows": int(right_valid.duplicated(names, keep=False).sum()),
        "many_to_many": bool(
            ((counts["Left rows"] > 1) & (counts["Right rows"] > 1)).any()
        ),
    }

    def execute():
        if estimates[how] > 200000:
            raise ValueError("Join exceeds the 200,000-row safety limit.")

        # Invalid keys never match. Preserve them as unmatched rows.
        left_number = 0
        right_number = 0
        left_keys_valid = set(
            tuple(row) for row in left_valid[names].itertuples(index=False, name=None)
        )
        right_keys_valid = set(
            tuple(row) for row in right_valid[names].itertuples(index=False, name=None)
        )
        occupied = left_keys_valid | right_keys_valid

        for row_index in left.index[~valid_left]:
            while True:
                token = tuple(
                    f"__missing_left_{left_number}_{i}__" for i in range(len(names))
                )
                left_number += 1
                if token not in occupied:
                    occupied.add(token)
                    break
            for name, value in zip(names, token):
                left.loc[row_index, name] = value

        for row_index in right.index[~valid_right]:
            while True:
                token = tuple(
                    f"__missing_right_{right_number}_{i}__" for i in range(len(names))
                )
                right_number += 1
                if token not in occupied:
                    occupied.add(token)
                    break
            for name, value in zip(names, token):
                right.loc[row_index, name] = value

        # Namespace source fields so duplicate column names stay unambiguous.
        left_renames = {c: "left." + c for c in left.columns if c not in names}
        right_renames = {c: "right." + c for c in right.columns if c not in names}
        result = left.rename(columns=left_renames).merge(
            right.rename(columns=right_renames),
            on=names,
            how=how,
            indicator="join_status",
        ).drop(columns=names)
        assert len(result) == estimates[how], "Join row count mismatch."
        return result

    return information, execute


def read_table(upload, side):
    payload = upload.getvalue()
    if len(payload) > 20 * 1024 * 1024:
        raise ValueError("Each file must be smaller than 20 MB.")
    if upload.name.lower().endswith(".xlsx"):
        with pd.ExcelFile(BytesIO(payload)) as book:
            sheet = st.selectbox(
                side + " worksheet", book.sheet_names, key=side + "_sheet"
            )
            frame = pd.read_excel(
                book, sheet_name=sheet, dtype=str, keep_default_na=False
            )
    else:
        separator = st.selectbox(
            side + " CSV separator", [",", ";", "\t"],
            key=side + "_separator",
        )
        frame = pd.read_csv(
            BytesIO(payload), sep=separator,
            dtype=str, keep_default_na=False,
        )

    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.empty or frame.columns.duplicated().any():
        raise ValueError("Use a non-empty table with unique column names.")
    if len(frame) > 100000:
        raise ValueError("Each source table is limited to 100,000 rows.")
    return frame.reset_index(drop=True)


def render_relationships():
    st.subheader("Connect two datasets")
    st.caption(
        "Keys are compared as trimmed text. Blank keys never match. "
        "Values such as 39 and 39.0 remain different."
    )
    a, b = st.columns(2)
    left_upload = a.file_uploader(
        "Left table", type=["csv", "xlsx"], key="join_left"
    )
    right_upload = b.file_uploader(
        "Right table", type=["csv", "xlsx"], key="join_right"
    )
    if not left_upload or not right_upload:
        return

    try:
        left = read_table(left_upload, "Left")
        right = read_table(right_upload, "Right")

        a, b = st.columns(2)
        left_keys = a.multiselect("Left keys", list(left.columns))
        right_keys = b.multiselect("Right keys", list(right.columns))
        how = st.selectbox(
            "Join type", ["left", "inner", "outer"],
            help="Left: keep all left rows. Inner: matches only. Outer: keep both sides.",
        )
        if not left_keys or len(left_keys) != len(right_keys):
            st.info("Select the same number of keys on each side, in matching order.")
            return

        info, execute = join_tables(left, right, left_keys, right_keys, how)
        a, b, c = st.columns(3)
        a.metric("Estimated result rows", info["estimated_rows"])
        b.metric("Unmatched left rows", info["unmatched_left"])
        c.metric("Unmatched right rows", info["unmatched_right"])

        st.write({
            "Left rows with repeated keys": info["left_duplicate_rows"],
            "Right rows with repeated keys": info["right_duplicate_rows"],
        })

        if info["many_to_many"]:
            st.warning(
                "Many-to-many relationship: repeated keys on both sides "
                "will multiply rows and can inflate totals."
            )
        accepted = st.checkbox(
            "I reviewed the matching keys and expected row count."
        )
        if st.button(
            "Build joined table",
            disabled=not accepted or info["estimated_rows"] > 200000,
        ):
            with st.spinner("Joining tables..."):
                result = execute()
            signature = hashlib.sha256(
                left_upload.getvalue() + right_upload.getvalue()
                + str((left_keys, right_keys, how, left.shape, right.shape)).encode()
                + left.to_csv(index=False).encode()
                + right.to_csv(index=False).encode()
            ).hexdigest()
            st.session_state["join_result"] = (signature, result)

        current_signature = hashlib.sha256(
            left_upload.getvalue() + right_upload.getvalue()
            + str((left_keys, right_keys, how, left.shape, right.shape)).encode()
            + left.to_csv(index=False).encode()
            + right.to_csv(index=False).encode()
        ).hexdigest()
        saved = st.session_state.get("join_result")
        if saved and saved[0] == current_signature:
            result = saved[1]
            st.success(f"Joined table ready: {len(result):,} rows.")
            st.dataframe(result.head(200), hide_index=True)
            from .report import excel_safe
            st.download_button(
                "Download joined CSV",
                excel_safe(result).to_csv(index=False).encode("utf-8-sig"),
                "joined_dataset.csv", "text/csv",
            )
            st.caption(
                "Download this file, then select Profile a dataset "
                "and upload it to confirm its schema and build charts."
            )

    except Exception as error:
        st.error(f"Unable to join these tables: {error}")
