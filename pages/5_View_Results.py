import pandas as pd
import streamlit as st

from connection import get_connection


st.title("Data Quality Results")

st.write(
    "Review data quality outcomes by request, test, asset, and execution."
)


@st.cache_data(ttl=60)
def load_results():
    conn = None

    try:
        conn = get_connection()

        query = """
            SELECT
                R.RESULT_ID,
                R.REQUEST_ID,
                R.EXECUTION_ID,
                R.APPLICABILITY_ID,
                A.APPLICABILITY_CODE,
                R.TEST_ID,
                T.TEST_CODE,
                R.ASSET_ID,
                S.ASSET_CODE,
                S.DATABASE_NAME,
                S.SCHEMA_NAME,
                S.OBJECT_NAME,
                R.METRIC_VALUE,
                R.PASS_LOWER_BOUND,
                R.PASS_UPPER_BOUND,
                R.DQ_OUTCOME,
                R.ERROR_MESSAGE,
                R.START_TS,
                R.END_TS,
                R.CREATED_TS
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_RESULT R

            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_TEST T
                ON R.TEST_ID = T.TEST_ID

            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_ASSET S
                ON R.ASSET_ID = S.ASSET_ID

            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY A
                ON R.APPLICABILITY_ID = A.APPLICABILITY_ID

            ORDER BY
                R.CREATED_TS DESC,
                R.RESULT_ID DESC
        """

        return pd.read_sql(query, conn)

    finally:
        if conn:
            conn.close()


def format_number(value):
    if pd.isna(value):
        return None

    return float(value)


try:
    # ---------------------------------------------------------
    # Refresh controls
    # ---------------------------------------------------------

    refresh_col, info_col = st.columns(
        [1, 5],
        vertical_alignment="center"
    )

    with refresh_col:
        if st.button("Refresh Results"):
            st.cache_data.clear()
            st.rerun()

    with info_col:
        st.caption(
            "Results are cached for 60 seconds. "
            "Use Refresh Results after running a new request."
        )

    # ---------------------------------------------------------
    # Load results
    # ---------------------------------------------------------

    df = load_results()

    if df.empty:
        st.info("No data quality results are available.")
        st.stop()

    # Snowflake/pandas may return uppercase column names.
    df.columns = [
        column.upper()
        for column in df.columns
    ]

    # ---------------------------------------------------------
    # Filters
    # ---------------------------------------------------------

    st.subheader("Filters")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    all_request_ids = sorted(
        df["REQUEST_ID"].dropna().unique().tolist(),
        reverse=True
    )

    all_outcomes = sorted(
        df["DQ_OUTCOME"].dropna().unique().tolist()
    )

    all_assets = sorted(
        df["ASSET_CODE"].dropna().unique().tolist()
    )

    all_tests = sorted(
        df["TEST_CODE"].dropna().unique().tolist()
    )

    with filter_col1:
        selected_request_ids = st.multiselect(
            "Request ID",
            options=all_request_ids,
            default=[]
        )

    with filter_col2:
        selected_outcomes = st.multiselect(
            "Outcome",
            options=all_outcomes,
            default=all_outcomes
        )

    with filter_col3:
        selected_assets = st.multiselect(
            "Asset",
            options=all_assets,
            default=[]
        )

    selected_tests = st.multiselect(
        "Test",
        options=all_tests,
        default=[]
    )

    filtered_df = df.copy()

    if selected_request_ids:
        filtered_df = filtered_df[
            filtered_df["REQUEST_ID"].isin(
                selected_request_ids
            )
        ]

    if selected_outcomes:
        filtered_df = filtered_df[
            filtered_df["DQ_OUTCOME"].isin(
                selected_outcomes
            )
        ]
    else:
        filtered_df = filtered_df.iloc[0:0]

    if selected_assets:
        filtered_df = filtered_df[
            filtered_df["ASSET_CODE"].isin(
                selected_assets
            )
        ]

    if selected_tests:
        filtered_df = filtered_df[
            filtered_df["TEST_CODE"].isin(
                selected_tests
            )
        ]

    # ---------------------------------------------------------
    # Summary metrics
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Summary")

    total_count = len(filtered_df)

    pass_count = len(
        filtered_df[
            filtered_df["DQ_OUTCOME"] == "PASS"
        ]
    )

    fail_count = len(
        filtered_df[
            filtered_df["DQ_OUTCOME"] == "FAIL"
        ]
    )

    error_count = len(
        filtered_df[
            filtered_df["DQ_OUTCOME"] == "ERROR"
        ]
    )

    completed_count = pass_count + fail_count

    pass_rate = (
        pass_count / completed_count * 100
        if completed_count > 0
        else 0
    )

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = (
        st.columns(5)
    )

    metric_col1.metric(
        "Total Results",
        total_count
    )

    metric_col2.metric(
        "Passed",
        pass_count
    )

    metric_col3.metric(
        "Failed",
        fail_count
    )

    metric_col4.metric(
        "Errors",
        error_count
    )

    metric_col5.metric(
        "Pass Rate",
        f"{pass_rate:.1f}%"
    )

    st.caption(
        "Pass rate is calculated from PASS and FAIL outcomes only. "
        "Technical ERROR outcomes are shown separately."
    )

    # ---------------------------------------------------------
    # Outcome breakdown
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Outcome Breakdown")

    outcome_summary = (
        filtered_df["DQ_OUTCOME"]
        .value_counts()
        .rename_axis("DQ_OUTCOME")
        .reset_index(name="RESULT_COUNT")
    )

    if not outcome_summary.empty:
        chart_data = outcome_summary.set_index(
            "DQ_OUTCOME"
        )

        st.bar_chart(
            chart_data,
            y="RESULT_COUNT"
        )

    # ---------------------------------------------------------
    # Result table
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Execution Results")

    if filtered_df.empty:
        st.warning(
            "No results match the selected filters."
        )

    else:
        display_columns = [
            "RESULT_ID",
            "REQUEST_ID",
            "EXECUTION_ID",
            "APPLICABILITY_CODE",
            "TEST_CODE",
            "ASSET_CODE",
            "METRIC_VALUE",
            "PASS_LOWER_BOUND",
            "PASS_UPPER_BOUND",
            "DQ_OUTCOME",
            "START_TS",
            "END_TS"
        ]

        available_display_columns = [
            column
            for column in display_columns
            if column in filtered_df.columns
        ]

        display_df = filtered_df[
            available_display_columns
        ].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "RESULT_ID": st.column_config.NumberColumn(
                    "Result ID",
                    format="%d"
                ),
                "REQUEST_ID": st.column_config.NumberColumn(
                    "Request ID",
                    format="%d"
                ),
                "EXECUTION_ID": st.column_config.NumberColumn(
                    "Execution ID",
                    format="%d"
                ),
                "APPLICABILITY_CODE": (
                    st.column_config.TextColumn(
                        "Applicability"
                    )
                ),
                "TEST_CODE": st.column_config.TextColumn(
                    "Test"
                ),
                "ASSET_CODE": st.column_config.TextColumn(
                    "Asset"
                ),
                "METRIC_VALUE": (
                    st.column_config.NumberColumn(
                        "Metric Value",
                        format="%.6f"
                    )
                ),
                "PASS_LOWER_BOUND": (
                    st.column_config.NumberColumn(
                        "Lower Bound",
                        format="%.6f"
                    )
                ),
                "PASS_UPPER_BOUND": (
                    st.column_config.NumberColumn(
                        "Upper Bound",
                        format="%.6f"
                    )
                ),
                "DQ_OUTCOME": st.column_config.TextColumn(
                    "Outcome"
                ),
                "START_TS": (
                    st.column_config.DatetimeColumn(
                        "Started",
                        format="DD/MM/YYYY HH:mm:ss"
                    )
                ),
                "END_TS": (
                    st.column_config.DatetimeColumn(
                        "Finished",
                        format="DD/MM/YYYY HH:mm:ss"
                    )
                )
            }
        )

    # ---------------------------------------------------------
    # Error details
    # ---------------------------------------------------------

    error_df = filtered_df[
        filtered_df["DQ_OUTCOME"] == "ERROR"
    ].copy()

    if not error_df.empty:
        st.divider()
        st.subheader("Technical Errors")

        st.error(
            f"{len(error_df)} technical error result(s) "
            "match the selected filters."
        )

        for _, row in error_df.iterrows():
            test_code = row.get("TEST_CODE", "Unknown test")
            result_id = row.get("RESULT_ID", "Unknown")
            request_id = row.get("REQUEST_ID", "Unknown")
            error_message = row.get(
                "ERROR_MESSAGE",
                "No error message was captured."
            )

            expander_title = (
                f"Result {result_id} | "
                f"Request {request_id} | "
                f"{test_code}"
            )

            with st.expander(expander_title):
                st.write(
                    f"**Applicability:** "
                    f"{row.get('APPLICABILITY_CODE', '')}"
                )

                st.write(
                    f"**Asset:** "
                    f"{row.get('ASSET_CODE', '')}"
                )

                st.write(
                    f"**Physical Object:** "
                    f"{row.get('DATABASE_NAME', '')}."
                    f"{row.get('SCHEMA_NAME', '')}."
                    f"{row.get('OBJECT_NAME', '')}"
                )

                st.code(
                    str(error_message),
                    language=None
                )

except Exception as e:
    st.error(
        f"Failed to load data quality results: {e}"
    )