import json
from datetime import date

import pandas as pd
import streamlit as st

from connection import get_connection
from parameter_controls import (
    get_object_columns,
    parse_parameter_definition,
    render_parameter_form,
)


st.title("Edit Applicability")


def load_editor_data():
    conn = get_connection()
    try:
        applicabilities = pd.read_sql(
            """
            SELECT
                A.APPLICABILITY_ID,
                A.APPLICABILITY_CODE,
                A.ASSET_ID,
                A.TEST_ID,
                TO_JSON(A.PARAMETERS) AS PARAMETERS_JSON,
                A.FREQUENCY,
                A.RUN_DAY_OF_MONTH,
                A.RUN_MONTH_OF_YEAR,
                A.PASS_LOWER_BOUND,
                A.PASS_UPPER_BOUND,
                A.STATUS
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY A
            ORDER BY A.APPLICABILITY_CODE, A.APPLICABILITY_ID
            """,
            conn,
        )
        assets = pd.read_sql(
            """
                 SELECT ASSET_ID, ASSET_CODE, DATABASE_NAME, SCHEMA_NAME,
                     OBJECT_NAME, OBJECT_TYPE, STATUS
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_ASSET
            ORDER BY DATABASE_NAME, SCHEMA_NAME, OBJECT_NAME
            """,
            conn,
        )
        tests = pd.read_sql(
            """
            SELECT TEST_ID, TEST_CODE, TEST_NAME, PARAMETER_DEFINITION
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_TEST
            ORDER BY TEST_CODE
            """,
            conn,
        )
        return applicabilities, assets, tests
    finally:
        conn.close()


def asset_label(asset):
    return (
        f"{asset['DATABASE_NAME']}.{asset['SCHEMA_NAME']}."
        f"{asset['OBJECT_NAME']} ({asset['OBJECT_TYPE']})"
    )


def test_label(test):
    return f"{test['TEST_NAME']} ({test['TEST_CODE']})"


try:
    applicabilities, assets, tests = load_editor_data()
    for frame in (applicabilities, assets, tests):
        frame.columns = [column.upper() for column in frame.columns]

    if applicabilities.empty:
        st.info("There are no applicability configurations to edit.")
    else:
        records = {
            int(row["APPLICABILITY_ID"]): row
            for row in applicabilities.to_dict("records")
        }
        selected_id = st.selectbox(
            "Applicability",
            options=list(records),
            format_func=lambda item_id: (
                f"{item_id} · {records[item_id]['APPLICABILITY_CODE']}"
            ),
            key="editor_applicability_id",
        )
        record = records[selected_id]

        asset_records = assets.to_dict("records")
        asset_ids = [int(asset["ASSET_ID"]) for asset in asset_records]
        asset_by_id = {
            int(asset["ASSET_ID"]): asset for asset in asset_records
        }
        test_records = tests.to_dict("records")
        test_ids = [int(test["TEST_ID"]) for test in test_records]
        test_by_id = {
            int(test["TEST_ID"]): test for test in test_records
        }

        if not asset_ids or not test_ids:
            st.error("Assets and tests must exist before editing this record.")
        else:
            asset_id = int(record["ASSET_ID"])
            test_id = int(record["TEST_ID"])
            if asset_id not in asset_by_id or test_id not in test_by_id:
                st.error(
                    "The asset or test linked to this applicability "
                    "is no longer available."
                )
            else:
                widget_suffix = str(selected_id)
                st.subheader("Configuration")

                original_asset_id = int(record["ASSET_ID"])
                original_test_id = int(record["TEST_ID"])
                code = st.text_input(
                    "Applicability Code",
                    value=record["APPLICABILITY_CODE"],
                    key=f"edit_code_{widget_suffix}",
                )

                asset_id = st.selectbox(
                    "Data Asset",
                    options=asset_ids,
                    index=asset_ids.index(original_asset_id),
                    format_func=lambda item_id: asset_label(
                        asset_by_id[item_id]
                    ),
                    key=f"edit_asset_{widget_suffix}",
                )
                test_id = st.selectbox(
                    "Data Quality Test",
                    options=test_ids,
                    index=test_ids.index(original_test_id),
                    format_func=lambda item_id: test_label(
                        test_by_id[item_id]
                    ),
                    key=f"edit_test_{widget_suffix}",
                )

                initial_parameters = {}
                if (
                    asset_id == original_asset_id
                    and test_id == original_test_id
                ):
                    try:
                        saved_parameters = json.loads(
                            record["PARAMETERS_JSON"] or "{}"
                        )
                        if isinstance(saved_parameters, dict):
                            initial_parameters = saved_parameters
                        else:
                            st.error("Saved PARAMETERS must be a JSON object.")
                    except (TypeError, json.JSONDecodeError) as error:
                        st.error(f"Saved PARAMETERS are invalid JSON: {error}")

                selected_asset = asset_by_id[asset_id]
                selected_test = test_by_id[test_id]
                asset_options = {
                    item_id: {
                        "asset_id": item_id,
                        "asset_code": asset["ASSET_CODE"],
                        "database_name": asset["DATABASE_NAME"],
                        "schema_name": asset["SCHEMA_NAME"],
                        "object_name": asset["OBJECT_NAME"],
                        "object_type": asset["OBJECT_TYPE"],
                    }
                    for item_id, asset in asset_by_id.items()
                    if str(asset["STATUS"]).upper() == "ACTIVE"
                }

                try:
                    parameter_definition = parse_parameter_definition(
                        selected_test["PARAMETER_DEFINITION"]
                    )
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    parameter_definition = []
                    st.error(f"Unable to read test parameters: {error}")

                metadata_conn = get_connection()
                try:
                    metadata_cursor = metadata_conn.cursor()
                    source_column_metadata = get_object_columns(
                        metadata_cursor,
                        selected_asset["DATABASE_NAME"],
                        selected_asset["SCHEMA_NAME"],
                        selected_asset["OBJECT_NAME"],
                    )
                    parameters, rendering_errors = render_parameter_form(
                        cursor=metadata_cursor,
                        selected_test=selected_test["TEST_CODE"],
                        parameter_definition=parameter_definition,
                        source_column_metadata=source_column_metadata,
                        database_name=selected_asset["DATABASE_NAME"],
                        schema_name=selected_asset["SCHEMA_NAME"],
                        object_name=selected_asset["OBJECT_NAME"],
                        asset_options=asset_options,
                        current_asset_id=asset_id,
                        initial_parameters=initial_parameters,
                        key_prefix=(
                            f"edit_{widget_suffix}_{asset_id}_{test_id}"
                        ),
                    )
                finally:
                    metadata_conn.close()

                for error in rendering_errors:
                    st.warning(error)

                frequencies = ["DAILY", "MONTHLY", "YEARLY"]
                current_frequency = record["FREQUENCY"]
                if current_frequency not in frequencies:
                    current_frequency = None
                frequency = st.selectbox(
                    "Frequency",
                    options=frequencies,
                    index=(
                        frequencies.index(current_frequency)
                        if current_frequency is not None
                        else None
                    ),
                    placeholder="Select a frequency",
                    key=f"edit_frequency_{widget_suffix}",
                )
                run_day_of_month = None
                run_month_of_year = None
                if frequency in ("MONTHLY", "YEARLY"):
                    current_day = record["RUN_DAY_OF_MONTH"]
                    if pd.isna(current_day):
                        current_day = 1
                    run_day_of_month = st.number_input(
                        "Run Day of Month",
                        min_value=1,
                        max_value=31,
                        value=int(current_day),
                        key=f"edit_monthday_{widget_suffix}",
                    )
                if frequency == "YEARLY":
                    current_month = record["RUN_MONTH_OF_YEAR"]
                    if pd.isna(current_month):
                        current_month = 1
                    run_month_of_year = st.number_input(
                        "Run Month of Year",
                        min_value=1,
                        max_value=12,
                        value=int(current_month),
                        key=f"edit_month_{widget_suffix}",
                    )

                bound_columns = st.columns(2)
                bounds = {}
                for column, field, label in (
                    (bound_columns[0], "LOWER", "Pass Lower Bound"),
                    (bound_columns[1], "UPPER", "Pass Upper Bound"),
                ):
                    value_key = (
                        "PASS_LOWER_BOUND"
                        if field == "LOWER"
                        else "PASS_UPPER_BOUND"
                    )
                    existing_value = record[value_key]
                    with column:
                        enabled = st.checkbox(
                            f"Set {label.lower()}",
                            value=existing_value is not None,
                            key=f"edit_{field.lower()}_enabled_"
                            f"{widget_suffix}",
                        )
                        bounds[field] = None
                        if enabled:
                            bounds[field] = st.number_input(
                                label,
                                value=float(existing_value or 0),
                                key=f"edit_{field.lower()}_value_"
                                f"{widget_suffix}",
                            )

                status_options = list(
                    dict.fromkeys(
                        [
                            record["STATUS"] or "ACTIVE",
                            "ACTIVE",
                            "INACTIVE",
                        ]
                    )
                )
                status = st.selectbox(
                    "Status",
                    options=status_options,
                    index=status_options.index(
                        record["STATUS"] or "ACTIVE"
                    ),
                    key=f"edit_status_{widget_suffix}",
                )

                save = st.button(
                    "Save Changes",
                    type="primary",
                    use_container_width=True,
                    key=f"edit_save_{widget_suffix}",
                )

                if save:
                    try:
                        parsed_parameters = parameters
                        if not isinstance(parsed_parameters, dict):
                            raise ValueError(
                                "Parameters must be a JSON object."
                            )
                        if rendering_errors:
                            raise ValueError(
                                "Resolve parameter configuration issues "
                                "before saving."
                            )
                        normalized_code = code.strip().upper()
                        if not normalized_code:
                            raise ValueError(
                                "Applicability Code is required."
                            )
                        if frequency is None:
                            raise ValueError("Select a frequency.")
                        if frequency == "YEARLY":
                            try:
                                date(2000, run_month_of_year, run_day_of_month)
                            except ValueError:
                                raise ValueError(
                                    "The yearly run day is not valid for "
                                    "the selected month."
                                )
                        if (
                            bounds["LOWER"] is not None
                            and bounds["UPPER"] is not None
                            and bounds["LOWER"] > bounds["UPPER"]
                        ):
                            raise ValueError(
                                "Pass Lower Bound cannot exceed "
                                "Pass Upper Bound."
                            )

                        conn = get_connection()
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                SELECT COUNT(*)
                                FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY
                                WHERE APPLICABILITY_CODE = %s
                                  AND APPLICABILITY_ID <> %s
                                """,
                                (normalized_code, selected_id),
                            )
                            if cursor.fetchone()[0]:
                                raise ValueError(
                                    "That Applicability Code is already "
                                    "in use."
                                )

                            cursor.execute(
                                """
                                UPDATE DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY
                                SET APPLICABILITY_CODE = %s,
                                    ASSET_ID = %s,
                                    TEST_ID = %s,
                                    PARAMETERS = PARSE_JSON(%s),
                                    FREQUENCY = %s,
                                    RUN_DAY_OF_MONTH = %s,
                                    RUN_MONTH_OF_YEAR = %s,
                                    PASS_LOWER_BOUND = %s,
                                    PASS_UPPER_BOUND = %s,
                                    STATUS = %s,
                                    UPDATED_TS = CURRENT_TIMESTAMP(),
                                    UPDATED_BY = CURRENT_USER()
                                WHERE APPLICABILITY_ID = %s
                                """,
                                (
                                    normalized_code,
                                    asset_id,
                                    test_id,
                                    json.dumps(parsed_parameters),
                                    frequency,
                                    run_day_of_month,
                                    run_month_of_year,
                                    bounds["LOWER"],
                                    bounds["UPPER"],
                                    status,
                                    selected_id,
                                ),
                            )
                            conn.commit()
                            st.success("Applicability updated.")
                        finally:
                            conn.close()
                    except (json.JSONDecodeError, ValueError) as error:
                        st.error(str(error))
                    except Exception as error:
                        st.error(f"Failed to update applicability: {error}")

except Exception as error:
    st.error(f"Failed to load applicability editor: {error}")
