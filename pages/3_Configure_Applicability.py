import json

import streamlit as st

from connection import get_connection


st.title("Configure Applicability")

st.write(
    "Configure which data quality tests apply to a registered data asset."
)


# =========================================================
# SESSION STATE HELPERS
# =========================================================

def clear_widget_keys(keys):
    """
    Remove the supplied widget keys from Streamlit session state.
    """

    for key in keys:
        st.session_state.pop(key, None)


def reset_test_parameters():
    """
    Clear test-dependent parameter fields.
    """

    clear_widget_keys(
        [
            "null_count_column",
            "duplicate_count_column",
            "range_column",
            "range_min_value",
            "range_max_value",
            "date_start_column",
            "date_end_column",
            "length_column",
            "maximum_length",
            "pattern_column",
            "regex_pattern",
            "allowed_values_column",
            "allowed_values_text",
            "raw_parameters",
        ]
    )


def reset_applicability_configuration():
    """
    Clear the test and applicability configuration.
    """

    clear_widget_keys(
        [
            "selected_test",
            "applicability_code",
            "execution_mode",
            "frequency",
            "run_day_of_week",
            "run_day_of_month",
            "pass_lower_bound",
            "pass_upper_bound",
        ]
    )

    reset_test_parameters()


def reset_after_database_change():
    """
    Changing database resets schema, object, test and configuration.
    """

    clear_widget_keys(
        [
            "selected_schema",
            "selected_object",
        ]
    )

    reset_applicability_configuration()


def reset_after_schema_change():
    """
    Changing schema resets object, test and configuration.
    """

    clear_widget_keys(
        [
            "selected_object",
        ]
    )

    reset_applicability_configuration()


def reset_after_object_change():
    """
    Changing object resets test and configuration.
    """

    reset_applicability_configuration()


# =========================================================
# SNOWFLAKE CONNECTION
# =========================================================

conn = None
cursor = None

try:
    conn = get_connection()
    cursor = conn.cursor()

    # =====================================================
    # LOAD ACTIVE ASSETS
    # =====================================================

    cursor.execute(
        """
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
        """
    )

    assets = cursor.fetchall()

    if not assets:
        st.warning(
            "No active assets are currently configured."
        )

    else:
        # =================================================
        # 1. SELECT DATA ASSET
        # =================================================

        st.subheader("1. Select Data Asset")

        # -------------------------------------------------
        # Database
        # -------------------------------------------------

        databases = sorted(
            {
                row[2]
                for row in assets
                if row[2] is not None
            }
        )

        selected_database = st.selectbox(
            "Database",
            options=[None] + databases,
            format_func=lambda value: (
                "Select a database"
                if value is None
                else value
            ),
            key="selected_database",
            on_change=reset_after_database_change,
        )

        selected_schema = None
        selected_object = None
        selected_asset_row = None

        # -------------------------------------------------
        # Schema
        # -------------------------------------------------

        if selected_database is not None:
            schemas = sorted(
                {
                    row[3]
                    for row in assets
                    if (
                        row[2] == selected_database
                        and row[3] is not None
                    )
                }
            )

            if schemas:
                selected_schema = st.selectbox(
                    "Schema",
                    options=[None] + schemas,
                    format_func=lambda value: (
                        "Select a schema"
                        if value is None
                        else value
                    ),
                    key="selected_schema",
                    on_change=reset_after_schema_change,
                )

            else:
                st.warning(
                    "No active schemas were found for "
                    "the selected database."
                )

        # -------------------------------------------------
        # Table / Object
        # -------------------------------------------------

        if (
            selected_database is not None
            and selected_schema is not None
        ):
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

            if object_options:
                selected_object = st.selectbox(
                    "Table / Object",
                    options=[None] + list(
                        object_options.keys()
                    ),
                    format_func=lambda value: (
                        "Select a table or view"
                        if value is None
                        else value
                    ),
                    key="selected_object",
                    on_change=reset_after_object_change,
                )

                if selected_object is not None:
                    selected_asset_row = (
                        object_options[selected_object]
                    )

            else:
                st.warning(
                    "No active objects were found for the "
                    "selected database and schema."
                )

        # =================================================
        # CONTINUE AFTER ASSET SELECTION
        # =================================================

        if selected_asset_row is not None:
            asset_id = selected_asset_row[0]
            asset_code = selected_asset_row[1]
            database_name = selected_asset_row[2]
            schema_name = selected_asset_row[3]
            object_name = selected_asset_row[4]
            object_type = selected_asset_row[5]
            asset_description = selected_asset_row[6]

            st.success(
                f"Selected asset: "
                f"{database_name}."
                f"{schema_name}."
                f"{object_name}"
            )

            with st.expander(
                "Asset Details",
                expanded=False,
            ):
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

            st.divider()

            # =================================================
            # 2. SELECT TEST
            # =================================================

            cursor.execute(
                """
                SELECT
                    TEST_ID,
                    TEST_CODE
                FROM DP_DEV_MTD.DATA_QUALITY.DQ_TEST
                WHERE STATUS = 'ACTIVE'
                ORDER BY TEST_CODE
                """
            )

            tests = cursor.fetchall()

            if not tests:
                st.warning(
                    "No active data quality tests are "
                    "currently configured."
                )

            else:
                # Correct mapping:
                # TEST_CODE -> TEST_ID
                test_options = {
                    row[1]: row[0]
                    for row in tests
                }

                st.subheader("2. Select Test")

                selected_test = st.selectbox(
                    "Test",
                    options=[None] + list(
                        test_options.keys()
                    ),
                    format_func=lambda value: (
                        "Select a test"
                        if value is None
                        else value
                    ),
                    key="selected_test",
                    on_change=reset_test_parameters,
                )

                # =================================================
                # CONTINUE AFTER TEST SELECTION
                # =================================================

                if selected_test is not None:
                    test_id = test_options[selected_test]

                    st.caption(
                        f"Test ID: {test_id}"
                    )

                    st.divider()

                    # =============================================
                    # 3. CONFIGURE TEST PARAMETERS
                    # =============================================

                    st.subheader(
                        "3. Configure Test Parameters"
                    )

                    parameters = {}

                    # ---------------------------------------------
                    # NULL COUNT
                    # ---------------------------------------------

                    if selected_test == "NULL_COUNT":
                        selected_column = st.text_input(
                            "Column",
                            placeholder="EMAIL",
                            key="null_count_column",
                        )

                        parameters = {
                            "COLUMN": selected_column.strip(),
                        }

                    # ---------------------------------------------
                    # DUPLICATE COUNT
                    # ---------------------------------------------

                    elif selected_test == "DUPLICATE_COUNT":
                        selected_column = st.text_input(
                            "Column",
                            placeholder="CUSTOMER_ID",
                            key="duplicate_count_column",
                        )

                        parameters = {
                            "COLUMN": selected_column.strip(),
                        }

                    # ---------------------------------------------
                    # RANGE CHECK
                    # ---------------------------------------------

                    elif selected_test in [
                        "OUT_OF_RANGE_COUNT",
                        "RANGE_CHECK",
                    ]:
                        selected_column = st.text_input(
                            "Column",
                            placeholder="AGE",
                            key="range_column",
                        )

                        range_col1, range_col2 = st.columns(2)

                        with range_col1:
                            min_value = st.number_input(
                                "Minimum Value",
                                value=0.0,
                                key="range_min_value",
                            )

                        with range_col2:
                            max_value = st.number_input(
                                "Maximum Value",
                                value=100.0,
                                key="range_max_value",
                            )

                        parameters = {
                            "COLUMN": selected_column.strip(),
                            "MIN_VALUE": min_value,
                            "MAX_VALUE": max_value,
                        }

                    # ---------------------------------------------
                    # DATE RANGE
                    # ---------------------------------------------

                    elif selected_test in [
                        "DATE_RANGE",
                        "INVALID_DATE_RANGE_COUNT",
                    ]:
                        date_col1, date_col2 = st.columns(2)

                        with date_col1:
                            start_column = st.text_input(
                                "Start Column",
                                placeholder="START_DATE",
                                key="date_start_column",
                            )

                        with date_col2:
                            end_column = st.text_input(
                                "End Column",
                                placeholder="END_DATE",
                                key="date_end_column",
                            )

                        parameters = {
                            "START_COLUMN": start_column.strip(),
                            "END_COLUMN": end_column.strip(),
                        }

                    # ---------------------------------------------
                    # MAX LENGTH
                    # ---------------------------------------------

                    elif selected_test in [
                        "MAX_LENGTH",
                        "MAX_LENGTH_COUNT",
                        "LENGTH_CHECK",
                    ]:
                        selected_column = st.text_input(
                            "Column",
                            placeholder="CUSTOMER_NAME",
                            key="length_column",
                        )

                        max_length = st.number_input(
                            "Maximum Length",
                            min_value=1,
                            value=100,
                            step=1,
                            key="maximum_length",
                        )

                        parameters = {
                            "COLUMN": selected_column.strip(),
                            "MAX_LENGTH": int(max_length),
                        }

                    # ---------------------------------------------
                    # REGEX / PATTERN
                    # ---------------------------------------------

                    elif selected_test in [
                        "PATTERN_CHECK",
                        "REGEX_MISMATCH_COUNT",
                        "REGEX_CHECK",
                    ]:
                        selected_column = st.text_input(
                            "Column",
                            placeholder="EMAIL",
                            key="pattern_column",
                        )

                        pattern = st.text_input(
                            "Pattern",
                            value=".*@.*",
                            help=(
                                "Regular expression used by "
                                "the selected test."
                            ),
                            key="regex_pattern",
                        )

                        parameters = {
                            "COLUMN": selected_column.strip(),
                            "PATTERN": pattern,
                        }

                    # ---------------------------------------------
                    # ALLOWED VALUES
                    # ---------------------------------------------

                    elif selected_test in [
                        "INVALID_VALUE_COUNT",
                        "ALLOWED_VALUES",
                    ]:
                        selected_column = st.text_input(
                            "Column",
                            placeholder="STATUS",
                            key="allowed_values_column",
                        )

                        allowed_values_text = st.text_area(
                            "Allowed Values",
                            value=(
                                "ACTIVE\n"
                                "INACTIVE\n"
                                "PENDING"
                            ),
                            help=(
                                "Enter one allowed value "
                                "per line."
                            ),
                            key="allowed_values_text",
                        )

                        allowed_values = [
                            value.strip()
                            for value
                            in allowed_values_text.splitlines()
                            if value.strip()
                        ]

                        parameters = {
                            "COLUMN": selected_column.strip(),
                            "ALLOWED_VALUES": allowed_values,
                        }

                    # ---------------------------------------------
                    # UNKNOWN / NEW TEST
                    # ---------------------------------------------

                    else:
                        st.info(
                            "This test does not currently have "
                            "a dedicated parameter form. Enter "
                            "its parameters as JSON."
                        )

                        raw_parameters = st.text_area(
                            "Parameters (JSON)",
                            value="{}",
                            height=150,
                            key="raw_parameters",
                        )

                        try:
                            parameters = json.loads(
                                raw_parameters
                            )

                            if not isinstance(
                                parameters,
                                dict,
                            ):
                                parameters = None

                                st.error(
                                    "Parameters must be a JSON "
                                    "object, for example "
                                    '{"COLUMN": "EMAIL"}.'
                                )

                        except json.JSONDecodeError:
                            parameters = None

                            st.error(
                                "Parameters must contain "
                                "valid JSON."
                            )

                    # ---------------------------------------------
                    # Preview parameters
                    # ---------------------------------------------

                    if parameters is not None:
                        with st.expander(
                            "Generated Parameters",
                            expanded=False,
                        ):
                            st.json(parameters)

                    st.divider()

                    # =============================================
                    # 4. CONFIGURE APPLICABILITY
                    # =============================================

                    st.subheader(
                        "4. Configure Applicability"
                    )

                    applicability_code = st.text_input(
                        "Applicability Code",
                        placeholder=(
                            "CUSTOMER_EMAIL_NULL_COUNT"
                        ),
                        help=(
                            "Unique code identifying this "
                            "test and asset configuration."
                        ),
                        key="applicability_code",
                    )

                    execution_mode = st.selectbox(
                        "Execution Mode",
                        options=[
                            "AUTO",
                            "MANUAL",
                        ],
                        index=0,
                        key="execution_mode",
                    )

                    # ---------------------------------------------
                    # Scheduling
                    # ---------------------------------------------

                    frequency = None
                    run_day_of_week = None
                    run_day_of_month = None

                    if execution_mode == "AUTO":
                        frequency = st.selectbox(
                            "Frequency",
                            options=[
                                "DAILY",
                                "WEEKLY",
                                "MONTHLY",
                            ],
                            key="frequency",
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
                                    "SUNDAY",
                                ],
                                key="run_day_of_week",
                            )

                        elif frequency == "MONTHLY":
                            run_day_of_month = st.number_input(
                                "Run Day of Month",
                                min_value=1,
                                max_value=31,
                                value=1,
                                step=1,
                                key="run_day_of_month",
                            )

                    # ---------------------------------------------
                    # Pass criteria
                    # ---------------------------------------------

                    st.write("**Pass Criteria**")

                    bound_col1, bound_col2 = st.columns(2)

                    with bound_col1:
                        pass_lower_bound = st.number_input(
                            "Pass Lower Bound",
                            value=0.0,
                            key="pass_lower_bound",
                        )

                    with bound_col2:
                        pass_upper_bound = st.number_input(
                            "Pass Upper Bound",
                            value=0.0,
                            key="pass_upper_bound",
                        )

                    st.caption(
                        "Example: a lower bound of 0 and upper "
                        "bound of 0 means the metric must equal "
                        "0 for the test to pass."
                    )

                    st.divider()

                    # =============================================
                    # 5. VALIDATE CONFIGURATION
                    # =============================================

                    if st.button(
                        "Create Applicability",
                        type="primary",
                    ):
                        validation_errors = []

                        # -----------------------------------------
                        # Applicability Code
                        # -----------------------------------------

                        if not applicability_code.strip():
                            validation_errors.append(
                                "Applicability Code is required."
                            )

                        # -----------------------------------------
                        # Parameters
                        # -----------------------------------------

                        if parameters is None:
                            validation_errors.append(
                                "Test parameters are invalid."
                            )

                        # -----------------------------------------
                        # Column parameters
                        # -----------------------------------------

                        single_column_tests = [
                            "NULL_COUNT",
                            "DUPLICATE_COUNT",
                            "OUT_OF_RANGE_COUNT",
                            "RANGE_CHECK",
                            "MAX_LENGTH",
                            "MAX_LENGTH_COUNT",
                            "LENGTH_CHECK",
                            "PATTERN_CHECK",
                            "REGEX_MISMATCH_COUNT",
                            "REGEX_CHECK",
                            "INVALID_VALUE_COUNT",
                            "ALLOWED_VALUES",
                        ]

                        if (
                            selected_test in single_column_tests
                            and parameters is not None
                            and not parameters.get("COLUMN")
                        ):
                            validation_errors.append(
                                "Column is required."
                            )

                        # -----------------------------------------
                        # Pass bounds
                        # -----------------------------------------

                        if (
                            pass_lower_bound
                            > pass_upper_bound
                        ):
                            validation_errors.append(
                                "Pass Lower Bound cannot be "
                                "greater than Pass Upper Bound."
                            )

                        # -----------------------------------------
                        # Range validation
                        # -----------------------------------------

                        if (
                            selected_test in [
                                "OUT_OF_RANGE_COUNT",
                                "RANGE_CHECK",
                            ]
                            and parameters is not None
                            and (
                                parameters.get("MIN_VALUE")
                                > parameters.get("MAX_VALUE")
                            )
                        ):
                            validation_errors.append(
                                "Minimum Value cannot be greater "
                                "than Maximum Value."
                            )

                        # -----------------------------------------
                        # Date range validation
                        # -----------------------------------------

                        if (
                            selected_test in [
                                "DATE_RANGE",
                                "INVALID_DATE_RANGE_COUNT",
                            ]
                            and parameters is not None
                        ):
                            if not parameters.get(
                                "START_COLUMN"
                            ):
                                validation_errors.append(
                                    "Start Column is required."
                                )

                            if not parameters.get(
                                "END_COLUMN"
                            ):
                                validation_errors.append(
                                    "End Column is required."
                                )

                            if (
                                parameters.get("START_COLUMN")
                                and parameters.get("END_COLUMN")
                                and parameters.get(
                                    "START_COLUMN"
                                )
                                == parameters.get(
                                    "END_COLUMN"
                                )
                            ):
                                validation_errors.append(
                                    "Start Column and End Column "
                                    "must be different."
                                )

                        # -----------------------------------------
                        # Allowed values
                        # -----------------------------------------

                        if (
                            selected_test in [
                                "INVALID_VALUE_COUNT",
                                "ALLOWED_VALUES",
                            ]
                            and parameters is not None
                            and not parameters.get(
                                "ALLOWED_VALUES"
                            )
                        ):
                            validation_errors.append(
                                "At least one allowed value "
                                "is required."
                            )

                        # -----------------------------------------
                        # Pattern
                        # -----------------------------------------

                        if (
                            selected_test in [
                                "PATTERN_CHECK",
                                "REGEX_MISMATCH_COUNT",
                                "REGEX_CHECK",
                            ]
                            and parameters is not None
                            and not str(
                                parameters.get(
                                    "PATTERN",
                                    "",
                                )
                            ).strip()
                        ):
                            validation_errors.append(
                                "Pattern is required."
                            )

                        # =========================================
                        # VALIDATION RESULT
                        # =========================================

                        if validation_errors:
                            for error in validation_errors:
                                st.error(error)

                        else:
                            st.success(
                                "Applicability configuration "
                                "is valid."
                            )

                            # -------------------------------------
                            # Configuration summary
                            # -------------------------------------

                            st.subheader(
                                "Configuration Summary"
                            )

                            summary_col1, summary_col2 = (
                                st.columns(2)
                            )

                            with summary_col1:
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
                                    f"**Asset Code:** "
                                    f"{asset_code}"
                                )

                                st.write(
                                    f"**Test:** {selected_test}"
                                )

                                st.write(
                                    f"**Test ID:** {test_id}"
                                )

                            with summary_col2:
                                st.write(
                                    "**Applicability**"
                                )

                                st.write(
                                    f"**Code:** "
                                    f"{applicability_code}"
                                )

                                st.write(
                                    f"**Execution Mode:** "
                                    f"{execution_mode}"
                                )

                                if frequency:
                                    st.write(
                                        f"**Frequency:** "
                                        f"{frequency}"
                                    )

                                if run_day_of_week:
                                    st.write(
                                        f"**Run Day:** "
                                        f"{run_day_of_week}"
                                    )

                                if run_day_of_month:
                                    st.write(
                                        f"**Run Day:** "
                                        f"{run_day_of_month}"
                                    )

                                st.write(
                                    f"**Pass Bounds:** "
                                    f"{pass_lower_bound} to "
                                    f"{pass_upper_bound}"
                                )

                            st.write("**Parameters**")
                            st.json(parameters)

                            parameters_json = json.dumps(
                                parameters
                            )

                            st.caption("PARAMETERS value")

                            st.code(
                                parameters_json,
                                language="json",
                            )

                            st.info(
                                "This currently validates and "
                                "previews the configuration. "
                                "It does not insert a row into "
                                "DQ_APPLICABILITY yet."
                            )


# =========================================================
# ERROR HANDLING
# =========================================================

except Exception as e:
    st.error(
        f"Failed to load applicability configuration: {e}"
    )


# =========================================================
# CLOSE CONNECTION
# =========================================================

finally:
    if cursor is not None:
        cursor.close()

    if conn is not None:
        conn.close()