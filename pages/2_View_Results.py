import json
from datetime import date, datetime, time, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from connection import get_connection


st.title("Data Quality Results")


@st.cache_data(ttl=60)
def load_reconciliation(start_date, end_date):
    conn = get_connection()
    try:
        return pd.read_sql(
            """
            SELECT
                E.EXECUTION_ID AS EXECUTION_RECORD_ID,
                R.RESULT_ID,
                COALESCE(E.REQUEST_ID, R.REQUEST_ID) AS REQUEST_ID,
                COALESCE(E.EXECUTION_ID, R.EXECUTION_ID) AS EXECUTION_ID,
                COALESCE(E.APPLICABILITY_ID, R.APPLICABILITY_ID)
                    AS APPLICABILITY_ID,
                A.APPLICABILITY_CODE,
                COALESCE(E.TEST_ID, R.TEST_ID) AS TEST_ID,
                T.TEST_CODE,
                T.TEST_NAME,
                COALESCE(E.ASSET_ID, R.ASSET_ID) AS ASSET_ID,
                S.ASSET_CODE,
                S.DATABASE_NAME,
                S.SCHEMA_NAME,
                S.OBJECT_NAME,
                E.PARAMETERS AS EXECUTION_PARAMETERS,
                R.METRIC_VALUE,
                COALESCE(
                    R.PASS_LOWER_BOUND,
                    E.PASS_LOWER_BOUND
                ) AS PASS_LOWER_BOUND,
                COALESCE(
                    R.PASS_UPPER_BOUND,
                    E.PASS_UPPER_BOUND
                ) AS PASS_UPPER_BOUND,
                E.STATUS AS EXECUTION_STATUS,
                R.DQ_OUTCOME AS RESULT_OUTCOME,
                E.ERROR_MESSAGE AS EXECUTION_ERROR,
                R.ERROR_MESSAGE AS RESULT_ERROR,
                E.GENERATED_SQL,
                E.START_TS AS EXECUTION_START_TS,
                E.END_TS AS EXECUTION_END_TS,
                E.CREATED_TS AS EXECUTION_CREATED_TS,
                R.START_TS AS RESULT_START_TS,
                R.END_TS AS RESULT_END_TS,
                R.CREATED_TS AS RESULT_CREATED_TS
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_EXECUTION E
            FULL OUTER JOIN DP_DEV_MTD.DATA_QUALITY.DQ_RESULT R
                ON E.EXECUTION_ID = R.EXECUTION_ID
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY A
                ON COALESCE(E.APPLICABILITY_ID, R.APPLICABILITY_ID)
                    = A.APPLICABILITY_ID
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_TEST T
                ON COALESCE(E.TEST_ID, R.TEST_ID) = T.TEST_ID
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_ASSET S
                ON COALESCE(E.ASSET_ID, R.ASSET_ID) = S.ASSET_ID
            WHERE COALESCE(
                    E.START_TS,
                    E.CREATED_TS,
                    R.START_TS,
                    R.CREATED_TS
                  ) >= %s
              AND COALESCE(
                    E.START_TS,
                    E.CREATED_TS,
                    R.START_TS,
                    R.CREATED_TS
                  ) < %s
            ORDER BY
                COALESCE(
                    E.START_TS,
                    E.CREATED_TS,
                    R.START_TS,
                    R.CREATED_TS
                ) DESC,
                COALESCE(E.EXECUTION_ID, R.EXECUTION_ID) DESC,
                R.RESULT_ID DESC
            """,
            conn,
            params=(start_date, end_date),
        )
    finally:
        conn.close()


if st.button("Refresh Results"):
    load_reconciliation.clear()
    st.rerun()

today = date.today()
date_columns = st.columns([1, 1, 2])
with date_columns[0]:
    start_day = st.date_input(
        "From",
        value=today - timedelta(days=29),
        max_value=today,
        key="results_start_date",
    )
with date_columns[1]:
    end_day = st.date_input(
        "To",
        value=today,
        min_value=start_day,
        max_value=today,
        key="results_end_date",
    )

try:
    results = load_reconciliation(
        datetime.combine(start_day, time.min),
        datetime.combine(end_day + timedelta(days=1), time.min),
    )
    results.columns = [column.upper() for column in results.columns]

    if results.empty:
        st.info("No executions or results were recorded in this date range.")
    else:
        timestamp_columns = [
            "EXECUTION_START_TS",
            "EXECUTION_END_TS",
            "EXECUTION_CREATED_TS",
            "RESULT_START_TS",
            "RESULT_END_TS",
            "RESULT_CREATED_TS",
        ]
        for column in timestamp_columns:
            results[column] = pd.to_datetime(
                results[column], errors="coerce"
            )

        results["RESULT_TS"] = results["EXECUTION_START_TS"].fillna(
            results["EXECUTION_CREATED_TS"]
        ).fillna(
            results["RESULT_START_TS"]
        ).fillna(
            results["RESULT_CREATED_TS"]
        )
        results["START_TS"] = results["EXECUTION_START_TS"].fillna(
            results["RESULT_START_TS"]
        )
        results["END_TS"] = results["EXECUTION_END_TS"].fillna(
            results["RESULT_END_TS"]
        )
        results["EXECUTION_FOUND"] = results[
            "EXECUTION_RECORD_ID"
        ].notna()
        results["RESULT_FOUND"] = results["RESULT_ID"].notna()
        results["COVERAGE_STATUS"] = "COMPLETE"
        results.loc[
            results["EXECUTION_FOUND"] & ~results["RESULT_FOUND"],
            "COVERAGE_STATUS",
        ] = "MISSING OUTCOME"
        results.loc[
            ~results["EXECUTION_FOUND"] & results["RESULT_FOUND"],
            "COVERAGE_STATUS",
        ] = "ORPHAN OUTCOME"
        results["ASSET"] = results[
            ["DATABASE_NAME", "SCHEMA_NAME", "OBJECT_NAME"]
        ].fillna("").agg(".".join, axis=1)
        results["DURATION_SECONDS"] = (
            results["END_TS"] - results["START_TS"]
        ).dt.total_seconds().round(2)

        results_tab, trends_tab, coverage_tab = st.tabs(
            ["Results", "Table Trends", "Execution Coverage"]
        )

        with results_tab:
            st.subheader("Recorded results")
            result_rows = results.loc[results["RESULT_FOUND"]].copy()

            if result_rows.empty:
                st.info("No result records were found in this date range.")
            else:
                latest_only = st.checkbox(
                    "Latest result per applicability",
                    value=False,
                    key="results_latest_only",
                )
                if latest_only:
                    result_rows = (
                        result_rows.sort_values(
                            ["RESULT_TS", "RESULT_ID"],
                            ascending=False,
                            na_position="last",
                        )
                        .drop_duplicates("APPLICABILITY_ID", keep="first")
                    )

                filter_columns = st.columns([1, 1, 1, 2])
                outcomes = sorted(
                    result_rows["RESULT_OUTCOME"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                test_codes = sorted(
                    result_rows["TEST_CODE"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                assets = sorted(
                    result_rows.loc[
                        result_rows["ASSET"] != "", "ASSET"
                    ].unique().tolist()
                )

                with filter_columns[0]:
                    selected_outcome = st.selectbox(
                        "Outcome",
                        options=["All", *outcomes],
                        key="results_outcome_filter",
                    )
                with filter_columns[1]:
                    selected_test = st.selectbox(
                        "Test",
                        options=["All", *test_codes],
                        key="results_test_filter",
                    )
                with filter_columns[2]:
                    selected_asset = st.selectbox(
                        "Asset",
                        options=["All", *assets],
                        key="results_asset_filter",
                    )
                with filter_columns[3]:
                    search = st.text_input(
                        "Search",
                        placeholder="Applicability, execution, test, or asset",
                        key="results_search",
                    )

                def apply_result_filters(frame):
                    if selected_outcome != "All":
                        frame = frame.loc[
                            frame["RESULT_OUTCOME"].astype(str)
                            == selected_outcome
                        ]
                    if selected_test != "All":
                        frame = frame.loc[
                            frame["TEST_CODE"].astype(str) == selected_test
                        ]
                    if selected_asset != "All":
                        frame = frame.loc[frame["ASSET"] == selected_asset]
                    if search.strip():
                        searchable = frame[
                            [
                                "APPLICABILITY_CODE",
                                "EXECUTION_ID",
                                "TEST_CODE",
                                "TEST_NAME",
                                "ASSET_CODE",
                                "ASSET",
                            ]
                        ].fillna("").astype(str)
                        matches = searchable.apply(
                            lambda column: column.str.contains(
                                search.strip(), case=False, regex=False
                            )
                        ).any(axis=1)
                        frame = frame.loc[matches]
                    return frame.copy()

                filtered_results = apply_result_filters(result_rows)

                outcome_values = (
                    filtered_results["RESULT_OUTCOME"]
                    .astype(str)
                    .str.upper()
                )
                passed_count = int(
                    outcome_values.isin(["PASS", "PASSED"]).sum()
                )
                result_count = filtered_results["RESULT_ID"].nunique()
                run_count = filtered_results["EXECUTION_ID"].nunique()

                result_metrics = st.columns(3)
                result_metrics[0].metric("Executions", int(run_count))
                result_metrics[1].metric("Results", int(result_count))
                result_metrics[2].metric(
                    "Passed", f"{passed_count} / {result_count}"
                )

                if filtered_results.empty:
                    st.info("No results match the selected filters.")
                else:
                    display = filtered_results.rename(
                        columns={
                            "EXECUTION_ID": "EXECUTION ID",
                            "APPLICABILITY_CODE": "APPLICABILITY",
                            "TEST_CODE": "TEST",
                            "METRIC_VALUE": "METRIC",
                            "PASS_LOWER_BOUND": "LOWER BOUND",
                            "PASS_UPPER_BOUND": "UPPER BOUND",
                            "RESULT_OUTCOME": "OUTCOME",
                            "DURATION_SECONDS": "DURATION (S)",
                            "START_TS": "STARTED",
                            "RESULT_ERROR": "ERROR",
                        }
                    )
                    st.dataframe(
                        display[
                            [
                                "STARTED",
                                "EXECUTION ID",
                                "APPLICABILITY",
                                "TEST",
                                "ASSET",
                                "OUTCOME",
                                "METRIC",
                                "LOWER BOUND",
                                "UPPER BOUND",
                                "DURATION (S)",
                                "ERROR",
                            ]
                        ],
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "ERROR": st.column_config.TextColumn(
                                "ERROR", width="large"
                            ),
                            "STARTED": st.column_config.DatetimeColumn(
                                "STARTED", format="YYYY-MM-DD HH:mm:ss"
                            ),
                        },
                    )

                    st.subheader("Execution details")
                    execution_ids = (
                        filtered_results["EXECUTION_ID"]
                        .dropna()
                        .drop_duplicates()
                        .tolist()
                    )
                    execution_ids.sort(
                        key=lambda execution_id: (
                            filtered_results.loc[
                                filtered_results["EXECUTION_ID"]
                                == execution_id,
                                "RESULT_TS",
                            ].max(),
                            execution_id,
                        ),
                        reverse=True,
                    )
                    execution_labels = {}
                    for execution_id in execution_ids:
                        execution_result = filtered_results.loc[
                            filtered_results["EXECUTION_ID"]
                            == execution_id
                        ].iloc[0]
                        execution_labels[execution_id] = (
                            f"Execution {int(execution_id)} · "
                            f"{execution_result['APPLICABILITY_CODE']} · "
                            f"{execution_result['RESULT_OUTCOME']}"
                        )
                    selected_execution_id = st.selectbox(
                        "Select an execution",
                        options=execution_ids,
                        format_func=lambda execution_id: (
                            execution_labels[execution_id]
                        ),
                        key="results_execution_detail_id",
                    )
                    selected_detail = filtered_results.loc[
                        filtered_results["EXECUTION_ID"]
                        == selected_execution_id
                    ].iloc[0]

                    context_columns = st.columns(3)
                    context_columns[0].write(
                        f"**Applicability:** "
                        f"{selected_detail['APPLICABILITY_CODE']}"
                    )
                    context_columns[1].write(
                        f"**Test:** {selected_detail['TEST_NAME']} "
                        f"({selected_detail['TEST_CODE']})"
                    )
                    context_columns[2].write(
                        f"**Asset:** {selected_detail['ASSET']}"
                    )

                    detail_columns = st.columns(3)
                    detail_columns[0].write(
                        f"**Execution status:** "
                        f"{selected_detail['EXECUTION_STATUS'] or 'Unknown'}"
                    )
                    detail_columns[1].write(
                        f"**Result outcome:** "
                        f"{selected_detail['RESULT_OUTCOME'] or 'Unknown'}"
                    )
                    detail_columns[2].write(
                        f"**Request ID:** {selected_detail['REQUEST_ID']}"
                    )

                    detail_columns = st.columns(3)
                    detail_columns[0].write(
                        f"**Metric:** {selected_detail['METRIC_VALUE']}"
                    )
                    detail_columns[1].write(
                        f"**Pass lower bound:** "
                        f"{selected_detail['PASS_LOWER_BOUND']}"
                    )
                    detail_columns[2].write(
                        f"**Pass upper bound:** "
                        f"{selected_detail['PASS_UPPER_BOUND']}"
                    )

                    timing_columns = st.columns(3)
                    for column, label, field in (
                        (timing_columns[0], "Started", "EXECUTION_START_TS"),
                        (timing_columns[1], "Ended", "EXECUTION_END_TS"),
                        (
                            timing_columns[2],
                            "Recorded",
                            "EXECUTION_CREATED_TS",
                        ),
                    ):
                        timestamp = selected_detail[field]
                        formatted_timestamp = (
                            timestamp.strftime("%Y-%m-%d %H:%M:%S")
                            if pd.notna(timestamp)
                            else "Not recorded"
                        )
                        column.write(
                            f"**{label}:** {formatted_timestamp}"
                        )

                    for error_label, error_value in (
                        (
                            "Execution error",
                            selected_detail["EXECUTION_ERROR"],
                        ),
                        ("Result error", selected_detail["RESULT_ERROR"]),
                    ):
                        if pd.notna(error_value) and str(error_value).strip():
                            st.error(f"{error_label}: {error_value}")

                    execution_parameters = selected_detail[
                        "EXECUTION_PARAMETERS"
                    ]
                    if isinstance(execution_parameters, str):
                        try:
                            execution_parameters = json.loads(
                                execution_parameters
                            )
                        except json.JSONDecodeError:
                            pass
                    elif execution_parameters is None or (
                        not isinstance(execution_parameters, (dict, list))
                        and pd.isna(execution_parameters)
                    ):
                        execution_parameters = {}

                    st.write("**Executed parameters**")
                    st.json(execution_parameters)

                    generated_sql = selected_detail["GENERATED_SQL"]
                    st.write("**Generated SQL**")
                    if pd.notna(generated_sql) and str(generated_sql).strip():
                        st.code(str(generated_sql), language="sql")
                    else:
                        st.info(
                            "No generated SQL is stored for this execution."
                        )

        with trends_tab:
            st.subheader("Table trends")
            trend_results = results.loc[
                results["RESULT_FOUND"] & results["ASSET_ID"].notna()
            ].copy()
            if trend_results.empty:
                st.info("No table results were recorded in this date range.")
            else:
                asset_labels = {}
                for _, row in trend_results.iterrows():
                    asset_id = row["ASSET_ID"]
                    asset_name = row["ASSET"]
                    if not asset_name.strip("."):
                        asset_name = f"Asset {asset_id}"
                    asset_labels[asset_id] = f"{asset_name} (ID {asset_id})"

                selected_asset_id = st.selectbox(
                    "Table",
                    options=sorted(
                        asset_labels, key=lambda item: asset_labels[item]
                    ),
                    format_func=lambda item: asset_labels[item],
                    key="trend_asset_id",
                )
                table_results = trend_results.loc[
                    trend_results["ASSET_ID"] == selected_asset_id
                ].copy()
                table_results["METRIC_VALUE"] = pd.to_numeric(
                    table_results["METRIC_VALUE"], errors="coerce"
                )
                table_results = table_results.dropna(
                    subset=["RESULT_TS", "METRIC_VALUE"]
                )

                if table_results.empty:
                    st.info("No numeric metrics are available for this table.")
                else:
                    table_results["TEST_GROUP"] = table_results.apply(
                        lambda row: (
                            str(row["TEST_ID"])
                            if pd.notna(row["TEST_ID"])
                            else "Unknown"
                        ),
                        axis=1,
                    )
                    test_labels = {}
                    for _, row in table_results.iterrows():
                        test_name = row["TEST_NAME"]
                        test_code = row["TEST_CODE"]
                        if pd.notna(test_name) and str(test_name).strip():
                            label = str(test_name)
                        else:
                            label = "Unknown test"
                        if pd.notna(test_code) and str(test_code).strip():
                            label = f"{label} ({test_code})"
                        test_labels[row["TEST_GROUP"]] = (
                            f"{label} - ID {row['TEST_GROUP']}"
                        )

                    selected_test_group = st.selectbox(
                        "Test type",
                        options=["All", *sorted(
                            test_labels, key=lambda item: test_labels[item]
                        )],
                        format_func=lambda item: (
                            "All" if item == "All" else test_labels[item]
                        ),
                        key="trend_test_group",
                    )
                    table_results["APPLICABILITY_LABEL"] = table_results.apply(
                        lambda row: (
                            f"{row['APPLICABILITY_CODE']} "
                            f"(ID {row['APPLICABILITY_ID']})"
                            if pd.notna(row["APPLICABILITY_ID"])
                            and pd.notna(row["APPLICABILITY_CODE"])
                            and str(row["APPLICABILITY_CODE"]).strip()
                            else (
                                f"Applicability {row['APPLICABILITY_ID']}"
                                if pd.notna(row["APPLICABILITY_ID"])
                                else f"Unlinked result {row['RESULT_ID']}"
                            )
                        ),
                        axis=1,
                    )
                    groups = (
                        sorted(test_labels, key=lambda item: test_labels[item])
                        if selected_test_group == "All"
                        else [selected_test_group]
                    )
                    for test_group in groups:
                        st.subheader(test_labels[test_group])
                        chart_data = table_results.loc[
                            table_results["TEST_GROUP"] == test_group
                        ].sort_values("RESULT_TS")
                        chart = alt.Chart(chart_data).mark_line(
                            point=True
                        ).encode(
                            x=alt.X("RESULT_TS:T", title="Run time"),
                            y=alt.Y("METRIC_VALUE:Q", title="Metric value"),
                            color=alt.Color(
                                "APPLICABILITY_LABEL:N", title="Applicability"
                            ),
                            tooltip=[
                                alt.Tooltip(
                                    "APPLICABILITY_LABEL:N",
                                    title="Applicability",
                                ),
                                alt.Tooltip("RESULT_TS:T", title="Run time"),
                                alt.Tooltip("METRIC_VALUE:Q", title="Metric"),
                                alt.Tooltip(
                                    "RESULT_OUTCOME:N", title="Outcome"
                                ),
                                alt.Tooltip("RESULT_ID:N", title="Result ID"),
                            ],
                        )
                        st.altair_chart(chart, use_container_width=True)

        with coverage_tab:
            st.subheader("Execution-to-result reconciliation")
            execution_rows = results.loc[
                results["EXECUTION_FOUND"]
            ]
            result_rows = results.loc[results["RESULT_FOUND"]]
            execution_count = execution_rows[
                "EXECUTION_RECORD_ID"
            ].nunique()
            covered_execution_count = execution_rows.loc[
                execution_rows["RESULT_FOUND"], "EXECUTION_RECORD_ID"
            ].nunique()
            missing_outcome_count = execution_rows.loc[
                ~execution_rows["RESULT_FOUND"], "EXECUTION_RECORD_ID"
            ].nunique()
            orphan_outcome_count = result_rows.loc[
                ~result_rows["EXECUTION_FOUND"], "RESULT_ID"
            ].nunique()
            result_count = result_rows["RESULT_ID"].nunique()
            coverage_percent = (
                covered_execution_count / execution_count * 100
                if execution_count
                else 0
            )

            coverage_metrics = st.columns(5)
            coverage_metrics[0].metric("Executions", execution_count)
            coverage_metrics[1].metric("Result records", result_count)
            coverage_metrics[2].metric(
                "Execution coverage", f"{coverage_percent:.1f}%"
            )
            coverage_metrics[3].metric(
                "Missing results", missing_outcome_count
            )
            coverage_metrics[4].metric(
                "Orphan results", orphan_outcome_count
            )
            st.caption(
                "An execution is covered when at least one result shares its "
                "execution ID. Orphan results have no matching execution."
            )

            coverage_statuses = sorted(
                results["COVERAGE_STATUS"].unique().tolist()
            )
            selected_coverage = st.selectbox(
                "Coverage status",
                options=["All", *coverage_statuses],
                key="coverage_status_filter",
            )
            coverage_search = st.text_input(
                "Search coverage",
                placeholder="Execution, applicability, test, or asset",
                key="coverage_search",
            )
            coverage_rows = results.copy()
            if selected_coverage != "All":
                coverage_rows = coverage_rows.loc[
                    coverage_rows["COVERAGE_STATUS"] == selected_coverage
                ]
            if coverage_search.strip():
                searchable = coverage_rows[
                    [
                        "EXECUTION_ID",
                        "RESULT_ID",
                        "APPLICABILITY_CODE",
                        "TEST_CODE",
                        "ASSET_CODE",
                        "ASSET",
                    ]
                ].fillna("").astype(str)
                matches = searchable.apply(
                    lambda column: column.str.contains(
                        coverage_search.strip(), case=False, regex=False
                    )
                ).any(axis=1)
                coverage_rows = coverage_rows.loc[matches]

            if coverage_rows.empty:
                st.info("No coverage records match the selected filters.")
            else:
                coverage_display = coverage_rows.rename(
                    columns={
                        "EXECUTION_ID": "EXECUTION ID",
                        "RESULT_ID": "RESULT ID",
                        "COVERAGE_STATUS": "COVERAGE STATUS",
                        "EXECUTION_STATUS": "EXECUTION STATUS",
                        "RESULT_OUTCOME": "RESULT OUTCOME",
                        "APPLICABILITY_CODE": "APPLICABILITY",
                        "TEST_CODE": "TEST",
                        "START_TS": "STARTED",
                        "EXECUTION_ERROR": "EXECUTION ERROR",
                        "RESULT_ERROR": "RESULT ERROR",
                    }
                )
                st.dataframe(
                    coverage_display[
                        [
                            "COVERAGE STATUS",
                            "EXECUTION STATUS",
                            "RESULT OUTCOME",
                            "STARTED",
                            "EXECUTION ID",
                            "RESULT ID",
                            "REQUEST_ID",
                            "APPLICABILITY",
                            "TEST",
                            "ASSET",
                            "EXECUTION ERROR",
                            "RESULT ERROR",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "EXECUTION ERROR": st.column_config.TextColumn(
                            "EXECUTION ERROR", width="large"
                        ),
                        "RESULT ERROR": st.column_config.TextColumn(
                            "RESULT ERROR", width="large"
                        ),
                        "STARTED": st.column_config.DatetimeColumn(
                            "STARTED", format="YYYY-MM-DD HH:mm:ss"
                        ),
                    },
                )
except Exception as error:
    st.error(f"Failed to load data quality results: {error}")
