import json
import re
from datetime import date, datetime

import streamlit as st

from connection import get_connection
from parameter_controls import (
    render_parameter_form as shared_render_parameter_form,
)


# =========================================================
# PAGE
# =========================================================

st.title("Configure Data Quality Test")

st.write(
    "Select an asset, choose a test, configure its parameters, "
    "and define how the test should run."
)

st.caption(
    "The form is generated dynamically from PARAMETER_DEFINITION "
    "in the DQ test catalogue."
)


# =========================================================
# CONTROLLED VALUES
# =========================================================

REGEX_PRESETS = {
    "Email address": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    "Digits only": r"^[0-9]+$",
    "Letters only": r"^[A-Za-z]+$",
    "Alphanumeric": r"^[A-Za-z0-9]+$",
    "Australian postcode": r"^[0-9]{4}$",
    "ISO date (YYYY-MM-DD)": (
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
    ),
}

SUPPORTED_PARAMETER_TYPES = {
    "COLUMN",
    "MULTI_COLUMN",
    "COLUMN_VALUES",
    "NUMBER",
    "INTEGER",
    "REGEX_PRESET",
    "ASSET",
    "VALUE",
    "OPERATOR",
}

DEFAULT_OPERATORS = [
    "=",
    "<>",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
]

TEXT_DATA_TYPES = {
    "TEXT",
    "VARCHAR",
    "CHAR",
    "CHARACTER",
    "STRING",
}

NUMBER_DATA_TYPES = {
    "NUMBER",
    "DECIMAL",
    "NUMERIC",
    "FLOAT",
    "DOUBLE",
    "DOUBLE PRECISION",
    "REAL",
    "INTEGER",
    "INT",
    "BIGINT",
    "SMALLINT",
    "BYTEINT",
}

INTEGER_DATA_TYPES = {
    "INTEGER",
    "INT",
    "BIGINT",
    "SMALLINT",
    "BYTEINT",
}

DATE_DATA_TYPES = {
    "DATE",
}

TIMESTAMP_DATA_TYPES = {
    "TIMESTAMP",
    "TIMESTAMP_NTZ",
    "TIMESTAMP_LTZ",
    "TIMESTAMP_TZ",
    "DATETIME",
}

BOOLEAN_DATA_TYPES = {
    "BOOLEAN",
    "BOOL",
}


# =========================================================
# SESSION STATE
# =========================================================

def clear_widget_keys(keys):
    for key in keys:
        st.session_state.pop(key, None)


def clear_dynamic_parameter_widgets():
    keys = [
        key
        for key in list(st.session_state.keys())
        if key.startswith("dq_parameter_")
    ]

    clear_widget_keys(keys)


def reset_test_parameters():
    clear_dynamic_parameter_widgets()

    clear_widget_keys(
        [
            "applicability_code",
            "frequency",
            "run_day_of_month",
            "run_month_of_year",
            "pass_lower_bound",
            "pass_upper_bound",
            "pending_applicability",
            "applicability_saved",
        ]
    )


def reset_applicability_configuration():
    clear_widget_keys(
        [
            "selected_test",
            "applicability_code",
            "frequency",
            "run_day_of_month",
            "run_month_of_year",
            "pass_lower_bound",
            "pass_upper_bound",
            "pending_applicability",
            "applicability_saved",
        ]
    )

    clear_dynamic_parameter_widgets()


def reset_after_database_change():
    clear_widget_keys(
        [
            "selected_schema",
            "selected_object",
        ]
    )

    reset_applicability_configuration()


def reset_after_schema_change():
    clear_widget_keys(
        [
            "selected_object",
        ]
    )

    reset_applicability_configuration()


def reset_after_object_change():
    reset_applicability_configuration()


# =========================================================
# GENERAL HELPERS
# =========================================================

def make_safe_code(value):
    safe_value = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        str(value).strip().upper(),
    )

    return safe_value.strip("_")


def generate_applicability_code(
    asset_code,
    object_name,
    test_code,
):
    asset_part = asset_code or object_name

    return make_safe_code(
        f"{asset_part}_{test_code}"
    )


def create_parameter_widget_key(
    selected_test,
    parameter_name,
):
    safe_test = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        str(selected_test).upper(),
    )

    safe_parameter = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        str(parameter_name).upper(),
    )

    return (
        f"dq_parameter_"
        f"{safe_test}_"
        f"{safe_parameter}"
    )


def parameter_is_empty(value):
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, list):
        return len(value) == 0

    if isinstance(value, dict):
        return len(value) == 0

    return False


def quote_identifier(value):
    return '"' + str(value).replace('"', '""') + '"'


def parse_parameter_definition(raw_definition):
    if raw_definition is None:
        return []

    if isinstance(raw_definition, list):
        return raw_definition

    if isinstance(raw_definition, dict):
        return [raw_definition]

    if isinstance(raw_definition, str):
        if not raw_definition.strip():
            return []

        parsed = json.loads(
            raw_definition
        )

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            return [parsed]

    raise ValueError(
        "PARAMETER_DEFINITION must contain a JSON array or object."
    )


def format_test_option(
    test_code,
    test_options,
):
    if test_code is None:
        return "Select a test"

    metadata = test_options.get(
        test_code,
        {},
    )

    test_name = metadata.get(
        "test_name"
    )

    if test_name:
        return f"{test_name} · {test_code}"

    return test_code


# =========================================================
# COLUMN HELPERS
# =========================================================

def get_object_columns(
    cursor,
    database_name,
    schema_name,
    object_name,
):
    database = quote_identifier(
        database_name
    )

    sql = f"""
        SELECT
            COLUMN_NAME,
            UPPER(DATA_TYPE) AS DATA_TYPE,
            ORDINAL_POSITION
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE UPPER(TABLE_SCHEMA) = UPPER(%s)
          AND UPPER(TABLE_NAME) = UPPER(%s)
        ORDER BY ORDINAL_POSITION
    """

    cursor.execute(
        sql,
        (
            schema_name,
            object_name,
        ),
        timeout=30,
    )

    return [
        {
            "name": row[0],
            "data_type": (
                str(row[1]).upper()
                if row[1] is not None
                else None
            ),
            "ordinal_position": row[2],
        }
        for row in cursor.fetchall()
    ]


def get_column_names(column_metadata):
    return [
        column["name"]
        for column in column_metadata
    ]


def get_column_data_type(
    column_metadata,
    column_name,
):
    if not column_name:
        return None

    for column in column_metadata:
        if (
            str(column["name"]).upper()
            == str(column_name).upper()
        ):
            return column["data_type"]

    return None


def filter_columns_by_data_type(
    column_metadata,
    allowed_data_types,
):
    if not allowed_data_types:
        return column_metadata

    allowed_types = {
        str(data_type).strip().upper()
        for data_type in allowed_data_types
    }

    return [
        column
        for column in column_metadata
        if (
            column["data_type"]
            and column["data_type"].upper()
            in allowed_types
        )
    ]


def get_distinct_values(
    cursor,
    database_name,
    schema_name,
    object_name,
    column_name,
    limit=200,
):
    database = quote_identifier(
        database_name
    )

    schema = quote_identifier(
        schema_name
    )

    object_ = quote_identifier(
        object_name
    )

    column = quote_identifier(
        column_name
    )

    safe_limit = min(
        max(int(limit), 1),
        500,
    )

    sql = f"""
        SELECT DISTINCT
            TO_VARCHAR({column}) AS COLUMN_VALUE
        FROM {database}.{schema}.{object_}
        WHERE {column} IS NOT NULL
        ORDER BY COLUMN_VALUE
        LIMIT {safe_limit}
    """

    cursor.execute(
        sql,
        timeout=30,
    )

    return [
        row[0]
        for row in cursor.fetchall()
        if row[0] is not None
    ]


# =========================================================
# ASSET HELPERS
# =========================================================

def get_active_assets(cursor):
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

    rows = cursor.fetchall()

    return {
        row[0]: {
            "asset_id": row[0],
            "asset_code": row[1],
            "database_name": row[2],
            "schema_name": row[3],
            "object_name": row[4],
            "object_type": row[5],
            "asset_description": row[6],
        }
        for row in rows
    }


def build_asset_identifier(asset):
    return (
        f"{asset['database_name']}."
        f"{asset['schema_name']}."
        f"{asset['object_name']}"
    )


def format_asset_option(
    asset_id,
    asset_options,
):
    if asset_id is None:
        return "Select a reference asset"

    asset = asset_options.get(
        asset_id
    )

    if not asset:
        return str(asset_id)

    return (
        f"{asset['database_name']}."
        f"{asset['schema_name']}."
        f"{asset['object_name']} "
        f"({asset['object_type']})"
    )


def get_selected_asset_from_parameter(
    parameter_value,
    asset_options,
):
    if parameter_value is None:
        return None

    parameter_fqn = str(
        parameter_value
    ).upper()

    for asset in asset_options.values():
        if (
            build_asset_identifier(asset).upper()
            == parameter_fqn
        ):
            return asset

    return None


# =========================================================
# VALUE HELPERS
# =========================================================

def infer_value_type(
    parameter,
    parameter_name,
    parameters,
    source_column_metadata,
):
    explicit_type = parameter.get(
        "value_type"
    )

    if explicit_type:
        return str(
            explicit_type
        ).strip().upper()

    depends_on = str(
        parameter.get(
            "depends_on",
            "",
        )
    ).strip().upper()

    if depends_on:
        dependent_column = parameters.get(
            depends_on
        )

        dependent_type = get_column_data_type(
            source_column_metadata,
            dependent_column,
        )

        if dependent_type in INTEGER_DATA_TYPES:
            return "INTEGER"

        if dependent_type in NUMBER_DATA_TYPES:
            return "NUMBER"

        if dependent_type in DATE_DATA_TYPES:
            return "DATE"

        if dependent_type in TIMESTAMP_DATA_TYPES:
            return "TIMESTAMP"

        if dependent_type in BOOLEAN_DATA_TYPES:
            return "BOOLEAN"

    combined_name = (
        f"{parameter_name} "
        f"{parameter.get('label', '')}"
    ).upper()

    if "TIMESTAMP" in combined_name:
        return "TIMESTAMP"

    if "DATE" in combined_name:
        return "DATE"

    return "TEXT"


def parse_default_date(default_value):
    if isinstance(default_value, datetime):
        return default_value.date()

    if isinstance(default_value, date):
        return default_value

    if isinstance(default_value, str):
        try:
            return date.fromisoformat(
                default_value[:10]
            )
        except ValueError:
            pass

    return date.today()


# =========================================================
# DATABASE VALIDATION
# =========================================================

def applicability_code_exists(
    cursor,
    applicability_code,
):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY
        WHERE UPPER(APPLICABILITY_CODE) = UPPER(%s)
        """,
        (
            applicability_code,
        ),
    )

    return cursor.fetchone()[0] > 0


# =========================================================
# GENERIC PARAMETER RENDERER
# =========================================================

def render_parameter_form(
    cursor,
    selected_test,
    parameter_definition,
    source_column_metadata,
    database_name,
    schema_name,
    object_name,
    asset_options,
    current_asset_id,
):
    return shared_render_parameter_form(
        cursor=cursor,
        selected_test=selected_test,
        parameter_definition=parameter_definition,
        source_column_metadata=source_column_metadata,
        database_name=database_name,
        schema_name=schema_name,
        object_name=object_name,
        asset_options=asset_options,
        current_asset_id=current_asset_id,
    )


# =========================================================
# VALIDATION
# =========================================================

def validate_parameters(
    parameter_definition,
    parameters,
):
    errors = []

    for parameter in parameter_definition:
        if not isinstance(parameter, dict):
            continue

        parameter_name = str(
            parameter.get(
                "name",
                "",
            )
        ).strip().upper()

        label = (
            parameter.get("label")
            or parameter_name.replace(
                "_",
                " ",
            ).title()
        )

        if (
            bool(parameter.get("required", False))
            and parameter_is_empty(
                parameters.get(
                    parameter_name
                )
            )
        ):
            errors.append(
                f"{label} is required."
            )

    if (
        parameters.get("MIN_VALUE") is not None
        and parameters.get("MAX_VALUE") is not None
        and parameters["MIN_VALUE"]
        > parameters["MAX_VALUE"]
    ):
        errors.append(
            "Minimum Value cannot be greater than Maximum Value."
        )

    comparison_pairs = [
        (
            "START_COLUMN",
            "END_COLUMN",
            "Start Column and End Column",
        ),
        (
            "EARLIER_COLUMN",
            "LATER_COLUMN",
            "Earlier Column and Later Column",
        ),
        (
            "LEFT_COLUMN",
            "RIGHT_COLUMN",
            "Left Column and Right Column",
        ),
        (
            "NUMERATOR_COLUMN",
            "DENOMINATOR_COLUMN",
            "Numerator Column and Denominator Column",
        ),
    ]

    for left_name, right_name, description in comparison_pairs:
        if (
            parameters.get(left_name)
            and parameters.get(right_name)
            and parameters[left_name]
            == parameters[right_name]
        ):
            errors.append(
                f"{description} must be different."
            )

    return errors


# =========================================================
# MAIN
# =========================================================

conn = None
cursor = None

try:
    conn = get_connection()
    cursor = conn.cursor()

    asset_options = get_active_assets(
        cursor
    )

    assets = list(
        asset_options.values()
    )

    if not assets:
        st.warning(
            "No active assets are currently configured."
        )

    else:
        cursor.execute(
            """
            SELECT
                TEST_ID,
                TEST_CODE,
                TEST_NAME,
                TEST_DESCRIPTION,
                PARAMETER_DEFINITION
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_TEST
            WHERE STATUS = 'ACTIVE'
            ORDER BY TEST_CODE
            """
        )

        tests = cursor.fetchall()

        test_options = {
            row[1]: {
                "test_id": row[0],
                "test_name": row[2],
                "test_description": row[3],
                "parameter_definition": row[4],
            }
            for row in tests
        }

        asset_column, test_column = st.columns(2)

        with asset_column:
            selected_asset_id = st.selectbox(
                "Data Asset",
                options=[
                    None,
                    *asset_options.keys(),
                ],
                format_func=lambda value: (
                    "Select a data asset"
                    if value is None
                    else format_asset_option(
                        value,
                        asset_options,
                    )
                ),
                key="selected_asset_id",
                on_change=reset_test_parameters,
            )

        with test_column:
            selected_test = st.selectbox(
                "Data Quality Test",
                options=[
                    None,
                    *test_options.keys(),
                ],
                format_func=lambda value: (
                    format_test_option(
                        value,
                        test_options,
                    )
                ),
                key="selected_test",
                on_change=reset_test_parameters,
            )

        selected_asset = asset_options.get(
            selected_asset_id
        )

        if selected_asset:
            asset_id = selected_asset["asset_id"]
            asset_code = selected_asset["asset_code"]
            database_name = selected_asset["database_name"]
            schema_name = selected_asset["schema_name"]
            object_name = selected_asset["object_name"]

            st.success(
                f"Selected: {database_name}."
                f"{schema_name}.{object_name}"
            )

            if selected_test:
                metadata = test_options[
                    selected_test
                ]

                test_id = metadata["test_id"]
                test_name = metadata["test_name"]

                st.write(f"### {test_name}")

                if metadata["test_description"]:
                    st.write(
                        metadata[
                            "test_description"
                        ]
                    )

                parameter_definition = (
                    parse_parameter_definition(
                        metadata[
                            "parameter_definition"
                        ]
                    )
                )

                source_column_metadata = get_object_columns(
                    cursor=cursor,
                    database_name=database_name,
                    schema_name=schema_name,
                    object_name=object_name,
                )

                st.divider()
                st.subheader("Test Parameters")

                parameters, rendering_errors = (
                    render_parameter_form(
                        cursor=cursor,
                        selected_test=selected_test,
                        parameter_definition=(
                            parameter_definition
                        ),
                        source_column_metadata=(
                            source_column_metadata
                        ),
                        database_name=database_name,
                        schema_name=schema_name,
                        object_name=object_name,
                        asset_options=asset_options,
                        current_asset_id=asset_id,
                    )
                )

                for error in rendering_errors:
                    st.warning(error)

                if not rendering_errors:
                    st.divider()
                    st.subheader("Applicability Settings")

                    default_code = (
                        generate_applicability_code(
                            asset_code,
                            object_name,
                            selected_test,
                        )
                    )

                    if (
                        "applicability_code"
                        not in st.session_state
                    ):
                        st.session_state[
                            "applicability_code"
                        ] = default_code

                    applicability_code = st.text_input(
                        "Applicability Code",
                        key="applicability_code",
                    )

                    frequency = st.selectbox(
                        "Frequency",
                        ["DAILY", "MONTHLY", "YEARLY"],
                        key="frequency",
                    )
                    run_day_of_month = None
                    run_month_of_year = None

                    if frequency in ("MONTHLY", "YEARLY"):
                        run_day_of_month = st.number_input(
                            "Run Day of Month",
                            min_value=1,
                            max_value=31,
                            value=1,
                            step=1,
                            key="run_day_of_month",
                        )

                    if frequency == "YEARLY":
                        run_month_of_year = st.number_input(
                            "Run Month of Year",
                            min_value=1,
                            max_value=12,
                            value=1,
                            step=1,
                            key="run_month_of_year",
                        )

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

                    current_configuration = {
                        "applicability_code": make_safe_code(
                            applicability_code
                        ),
                        "asset_id": asset_id,
                        "test_id": test_id,
                        "parameters": parameters,
                        "frequency": frequency,
                        "run_day_of_month": run_day_of_month,
                        "run_month_of_year": run_month_of_year,
                        "pass_lower_bound": pass_lower_bound,
                        "pass_upper_bound": pass_upper_bound,
                    }

                    st.divider()
                    st.subheader("Review and Create")

                    if st.button(
                        "Review Configuration",
                        type="primary",
                        use_container_width=True,
                    ):
                        validation_errors = (
                            validate_parameters(
                                parameter_definition,
                                parameters,
                            )
                        )

                        code = make_safe_code(
                            applicability_code
                        )

                        if not code:
                            validation_errors.append(
                                "Applicability Code is required."
                            )
                        elif applicability_code_exists(
                            cursor,
                            code,
                        ):
                            validation_errors.append(
                                "The Applicability Code already exists."
                            )

                        if (
                            pass_lower_bound
                            > pass_upper_bound
                        ):
                            validation_errors.append(
                                "Pass Lower Bound cannot be greater "
                                "than Pass Upper Bound."
                            )

                        if frequency == "YEARLY":
                            try:
                                date(2000, run_month_of_year, run_day_of_month)
                            except ValueError:
                                validation_errors.append(
                                    "The yearly run day is not valid for the selected month."
                                )

                        if validation_errors:
                            st.session_state.pop(
                                "pending_applicability",
                                None,
                            )

                            for error in validation_errors:
                                st.error(error)
                        else:
                            current_configuration[
                                "applicability_code"
                            ] = code

                            st.session_state[
                                "pending_applicability"
                            ] = current_configuration

                    reviewed = st.session_state.get(
                        "pending_applicability"
                    )

                    if reviewed:
                        configuration_is_current = (
                            reviewed
                            == current_configuration
                        )

                        st.json(reviewed)

                        if not configuration_is_current:
                            st.warning(
                                "The configuration changed after "
                                "review. Review it again."
                            )

                        elif st.button(
                            "Create Applicability",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                if applicability_code_exists(
                                    cursor,
                                    reviewed[
                                        "applicability_code"
                                    ],
                                ):
                                    st.error(
                                        "The Applicability Code "
                                        "already exists."
                                    )
                                else:
                                    cursor.execute(
                                        """
                                        INSERT INTO DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY
                                        (
                                            APPLICABILITY_CODE,
                                            ASSET_ID,
                                            TEST_ID,
                                            PARAMETERS,
                                            FREQUENCY,
                                            RUN_DAY_OF_MONTH,
                                            RUN_MONTH_OF_YEAR,
                                            PASS_LOWER_BOUND,
                                            PASS_UPPER_BOUND,
                                            STATUS
                                        )
                                        SELECT
                                            %s,
                                            %s,
                                            %s,
                                            PARSE_JSON(%s),
                                            %s,
                                            %s,
                                            %s,
                                            %s,
                                            %s,
                                            'ACTIVE'
                                        """,
                                        (
                                            reviewed[
                                                "applicability_code"
                                            ],
                                            reviewed["asset_id"],
                                            reviewed["test_id"],
                                            json.dumps(
                                                reviewed[
                                                    "parameters"
                                                ]
                                            ),
                                            reviewed["frequency"],
                                            reviewed[
                                                "run_day_of_month"
                                            ],
                                            reviewed[
                                                "run_month_of_year"
                                            ],
                                            reviewed[
                                                "pass_lower_bound"
                                            ],
                                            reviewed[
                                                "pass_upper_bound"
                                            ],
                                        ),
                                    )

                                    conn.commit()

                                    st.success(
                                        "Applicability created successfully."
                                    )

                            except Exception as insert_error:
                                conn.rollback()

                                st.error(
                                    "Failed to create applicability: "
                                    f"{insert_error}"
                                )

except Exception as error:
    st.error(
        "Failed to load applicability configuration: "
        f"{error}"
    )

finally:
    if cursor is not None:
        cursor.close()

    if conn is not None:
        conn.close()