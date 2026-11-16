import json

import streamlit as st

from connection import get_connection


st.title("Configure Applicability")

st.write(
    "Configure which data quality tests apply to a registered data asset."
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def quote_identifier(value):
    """
    Safely quote a Snowflake identifier.
    """
    return '"' + str(value).replace('"', '""') + '"'


def get_table_columns(cursor, database_name, schema_name, object_name):
    """
    Return the columns for the selected Snowflake table/view.
    """

    sql = f"""
        SELECT COLUMN_NAME
        FROM {quote_identifier(database_name)}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """

    cursor.execute(
        sql,
        (
            schema_name,
            object_name
        )
    )

    return [
        row[0]
        for row in cursor.fetchall()
    ]


# ---------------------------------------------------------
# Connect to Snowflake
# ---------------------------------------------------------

conn = None
cursor = None

try:
    conn = get_connection()
    cursor = conn.cursor()

    # ---------------------------------------------------------
    # Load active assets
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT
            ASSET_ID,
            ASSET_CODE,
            DATABASE_NAME,
            SCHEMA_NAME,
            OBJECT_NAME,
            OBJECT_TYPE,
            ASSET_DESCRIPTION
        FROM DP_DEV_MTD.DATA_QUALITY.DQ_ASSET
        WHERE STATUS = 'ACTIVE'
        ORDER BY
            DATABASE_NAME,
            SCHEMA_NAME,
            OBJECT_NAME
    """)

    assets = cursor.fetchall()

    if not assets:
        st.warning(
            "No active assets are currently configured."
        )
        st.stop()

    # =========================================================
    # 1. SELECT DATA ASSET
    # =========================================================

    st.subheader("1. Select Data Asset")

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------

    databases = sorted(
        set(
            row[2]
            for row in assets
        )
    )

    selected_database = st.selectbox(
        "Database",
        options=databases
    )

    # ---------------------------------------------------------
    # Schema
    # ---------------------------------------------------------

    schemas = sorted(
        set(
            row[3]
            for row in assets
            if row[2] == selected_database
        )
    )

    selected_schema = st.selectbox(
        "Schema",
        options=schemas
    )

    # ---------------------------------------------------------
    # Table / Object
    # ---------------------------------------------------------

    matching_assets = [
        row
        for row in assets
        if (
            row[2] == selected_database
            and row[3] == selected_schema
        )
    ]

    object_options = {
        f"{row[4]} ({row[5]})": row
        for row in matching_assets
    }

    selected_object = st.selectbox(
        "Table / Object",
        options=list(object_options.keys())
    )

    selected_asset_row = object_options[selected_object]

    asset_id = selected_asset_row[0]
    asset_code = selected_asset_row[1]
    database_name = selected_asset_row[2]
    schema_name = selected_asset_row[3]
    object_name = selected_asset_row[4]
    object_type = selected_asset_row[5]
    asset_description = selected_asset_row[6]

    # ---------------------------------------------------------
    # Asset details
    # ---------------------------------------------------------

    with st.expander("Asset Details"):

        st.write(
            f"**Asset ID:** {asset_id}"
        )

        st.write(
            f"**Asset Code:** {asset_code}"
        )

        st.write(
            f"**Database:** {database_name}"
        )

        st.write(
            f"**Schema:** {schema_name}"
        )

        st.write(
            f"**Object:** {object_name}"
        )

        st.write(
            f"**Object Type:** {object_type}"
        )

        if asset_description:
            st.write(
                f"**Description:** {asset_description}"
            )

    # ---------------------------------------------------------
    # Load columns from selected object
    # ---------------------------------------------------------

    columns = get_table_columns(
        cursor,
        database_name,
        schema_name,
        object_name
    )

    if not columns:
        st.warning(
            "No columns could be found for the selected object."
        )
        st.stop()

    st.divider()

    # =========================================================
    # 2. SELECT TEST
    # =========================================================

    cursor.execute("""
        SELECT
            TEST_ID,
            TEST_CODE
        FROM DP_DEV_MTD.DATA_QUALITY.DQ_TEST
        WHERE STATUS = 'ACTIVE'
        ORDER BY TEST_CODE
    """)

    tests = cursor.fetchall()

    if not tests:
        st.warning(
            "No active data quality tests are currently configured."
        )
        st.stop()

    test_options = {
        row[1]: row[0]
        for row in tests
    }

    st.subheader("2. Select Test")

    selected_test = st.selectbox(
        "Test",
        options=list(test_options.keys())
    )

    test_id = test_options[selected_test]

    st.caption(
        f"Test ID: {test_id}"
    )

    st.divider()

    # =========================================================
    # 3. CONFIGURE TEST PARAMETERS
    # =========================================================

    st.subheader("3. Configure Test Parameters")

    parameters = {}

    # ---------------------------------------------------------
    # NULL COUNT
    # ---------------------------------------------------------

    if selected_test == "NULL_COUNT":

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="null_count_column"
        )

        parameters = {
            "COLUMN": selected_column
        }

    # ---------------------------------------------------------
    # DUPLICATE COUNT
    # ---------------------------------------------------------

    elif selected_test == "DUPLICATE_COUNT":

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="duplicate_count_column"
        )

        parameters = {
            "COLUMN": selected_column
        }

    # ---------------------------------------------------------
    # RANGE CHECK
    # ---------------------------------------------------------

    elif selected_test in [
        "OUT_OF_RANGE_COUNT",
        "RANGE_CHECK"
    ]:

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="range_column"
        )

        col1, col2 = st.columns(2)

        with col1:
            min_value = st.number_input(
                "Minimum Value",
                value=0.0
            )

        with col2:
            max_value = st.number_input(
                "Maximum Value",
                value=100.0
            )

        parameters = {
            "COLUMN": selected_column,
            "MIN_VALUE": min_value,
            "MAX_VALUE": max_value
        }

    # ---------------------------------------------------------
    # DATE RANGE
    # ---------------------------------------------------------

    elif selected_test in [
        "DATE_RANGE",
        "INVALID_DATE_RANGE_COUNT"
    ]:

        col1, col2 = st.columns(2)

        with col1:
            start_column = st.selectbox(
                "Start Column",
                options=columns,
                key="date_start_column"
            )

        with col2:
            end_column = st.selectbox(
                "End Column",
                options=columns,
                key="date_end_column"
            )

        parameters = {
            "START_COLUMN": start_column,
            "END_COLUMN": end_column
        }

    # ---------------------------------------------------------
    # MAX LENGTH
    # ---------------------------------------------------------

    elif selected_test in [
        "MAX_LENGTH",
        "MAX_LENGTH_COUNT",
        "LENGTH_CHECK"
    ]:

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="length_column"
        )

        max_length = st.number_input(
            "Maximum Length",
            min_value=1,
            value=100,
            step=1
        )

        parameters = {
            "COLUMN": selected_column,
            "MAX_LENGTH": int(max_length)
        }

    # ---------------------------------------------------------
    # PATTERN / REGEX
    # ---------------------------------------------------------

    elif selected_test in [
        "PATTERN_CHECK",
        "REGEX_MISMATCH_COUNT",
        "REGEX_CHECK"
    ]:

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="pattern_column"
        )

        pattern = st.text_input(
            "Pattern",
            value=".*@.*",
            help="Regular expression used by the selected test."
        )

        parameters = {
            "COLUMN": selected_column,
            "PATTERN": pattern
        }

    # ---------------------------------------------------------
    # ALLOWED VALUES
    # ---------------------------------------------------------

    elif selected_test in [
        "INVALID_VALUE_COUNT",
        "ALLOWED_VALUES"
    ]:

        selected_column = st.selectbox(
            "Column",
            options=columns,
            key="allowed_values_column"
        )

        allowed_values_text = st.text_area(
            "Allowed Values",
            value="ACTIVE\nINACTIVE\nPENDING",
            help="Enter one allowed value per line."
        )

        allowed_values = [
            value.strip()
            for value in allowed_values_text.splitlines()
            if value.strip()
        ]

        parameters = {
            "COLUMN": selected_column,
            "ALLOWED_VALUES": allowed_values
        }

    # ---------------------------------------------------------
    # Unknown / new test
    # ---------------------------------------------------------

    else:

        st.info(
            "This test does not currently have a configured "
            "parameter form in the MVP."
        )

        raw_parameters = st.text_area(
            "Parameters (JSON)",
            value="{}",
            height=150
        )

        try:
            parameters = json.loads(
                raw_parameters
            )

        except json.JSONDecodeError:
            parameters = None

            st.error(
                "Parameters must contain valid JSON."
            )

    # ---------------------------------------------------------
    # Preview generated JSON
    # ---------------------------------------------------------

    if parameters is not None:

        with st.expander(
            "Generated Parameters",
            expanded=False
        ):
            st.json(parameters)

    st.divider()

    # =========================================================
    # 4. CONFIGURE APPLICABILITY
    # =========================================================

    st.subheader("4. Configure Applicability")

    applicability_code = st.text_input(
        "Applicability Code",
        placeholder="CUSTOMER_EMAIL_NULL_COUNT",
        help=(
            "Unique code identifying this application "
            "of the test to the selected asset."
        )
    )

    execution_mode = st.selectbox(
        "Execution Mode",
        options=[
            "AUTO",
            "MANUAL"
        ],
        index=0
    )

    # ---------------------------------------------------------
    # Scheduling
    # ---------------------------------------------------------

    frequency = None
    run_day_of_week = None
    run_day_of_month = None

    if execution_mode == "AUTO":

        frequency = st.selectbox(
            "Frequency",
            options=[
                "DAILY",
                "WEEKLY",
                "MONTHLY"
            ]
        )

        if frequency == "WEEKLY":

            run_day_of_week = st.selectbox(
                "Run Day",
                options=[
                    "MONDAY",
                    "TUESDAY",
                    "WEDNESDAY",
                    "THURSDAY",
                    "FRIDAY",
                    "SATURDAY",
                    "SUNDAY"
                ]
            )

        elif frequency == "MONTHLY":

            run_day_of_month = st.number_input(
                "Run Day of Month",
                min_value=1,
                max_value=31,
                value=1,
                step=1
            )

    # ---------------------------------------------------------
    # Pass bounds
    # ---------------------------------------------------------

    st.write("**Pass Criteria**")

    bound_col1, bound_col2 = st.columns(2)

    with bound_col1:

        pass_lower_bound = st.number_input(
            "Pass Lower Bound",
            value=0.0
        )

    with bound_col2:

        pass_upper_bound = st.number_input(
            "Pass Upper Bound",
            value=0.0
        )

    st.caption(
        "Example: lower bound 0 and upper bound 0 means "
        "the test only passes when the metric is exactly 0."
    )

    st.divider()

    # =========================================================
    # 5. VALIDATE / CREATE APPLICABILITY
    # =========================================================

    if st.button(
        "Create Applicability",
        type="primary"
    ):

        validation_errors = []

        if not applicability_code.strip():
            validation_errors.append(
                "Applicability Code is required."
            )

        if parameters is None:
            validation_errors.append(
                "Test parameters are invalid."
            )

        if (
            pass_lower_bound
            > pass_upper_bound
        ):
            validation_errors.append(
                "Pass Lower Bound cannot be greater "
                "than Pass Upper Bound."
            )

        if (
            selected_test
            in [
                "DATE_RANGE",
                "INVALID_DATE_RANGE_COUNT"
            ]
            and parameters is not None
            and parameters.get("START_COLUMN")
            == parameters.get("END_COLUMN")
        ):
            validation_errors.append(
                "Start Column and End Column must be different."
            )

        if (
            selected_test
            in [
                "INVALID_VALUE_COUNT",
                "ALLOWED_VALUES"
            ]
            and parameters is not None
            and not parameters.get("ALLOWED_VALUES")
        ):
            validation_errors.append(
                "At least one allowed value is required."
            )

        # -----------------------------------------------------
        # Show validation errors
        # -----------------------------------------------------

        if validation_errors:

            for error in validation_errors:
                st.error(error)

        else:

            st.success(
                "Applicability configuration is valid."
            )

            # -------------------------------------------------
            # Configuration Summary
            # -------------------------------------------------

            st.subheader("Configuration Summary")

            col1, col2 = st.columns(2)

            with col1:

                st.write("**Asset**")

                st.code(
                    f"{database_name}."
                    f"{schema_name}."
                    f"{object_name}"
                )

                st.write(
                    f"**Asset ID:** {asset_id}"
                )

                st.write(
                    f"**Asset Code:** {asset_code}"
                )

                st.write(
                    f"**Test:** {selected_test}"
                )

                st.write(
                    f"**Test ID:** {test_id}"
                )

            with col2:

                st.write("**Applicability**")

                st.write(
                    f"**Code:** {applicability_code}"
                )

                st.write(
                    f"**Execution Mode:** {execution_mode}"
                )

                if frequency:
                    st.write(
                        f"**Frequency:** {frequency}"
                    )

                if run_day_of_week:
                    st.write(
                        f"**Run Day:** {run_day_of_week}"
                    )

                if run_day_of_month:
                    st.write(
                        f"**Run Day:** {run_day_of_month}"
                    )

                st.write(
                    f"**Pass Bounds:** "
                    f"{pass_lower_bound} "
                    f"to {pass_upper_bound}"
                )

            st.write("**Parameters**")

            st.json(parameters)

            # -------------------------------------------------
            # Show exact PARAMETERS value
            # -------------------------------------------------

            parameters_json = json.dumps(
                parameters
            )

            st.caption("PARAMETERS value")

            st.code(
                parameters_json,
                language="json"
            )


# ---------------------------------------------------------
# Error Handling
# ---------------------------------------------------------

except Exception as e:

    st.error(
        f"Failed to load applicability configuration: {e}"
    )


# ---------------------------------------------------------
# Close Snowflake Connection
# ---------------------------------------------------------

finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()