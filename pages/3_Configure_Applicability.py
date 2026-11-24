import json
import re
from datetime import date, datetime

import streamlit as st

from connection import get_connection


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
            "execution_mode",
            "frequency",
            "run_day_of_week",
            "run_day_of_month",
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
            "execution_mode",
            "frequency",
            "run_day_of_week",
            "run_day_of_month",
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
    parameters = {}
    rendering_errors = []
    reference_column_cache = {}

    if not parameter_definition:
        st.info(
            "This test does not require configurable parameters."
        )

        return {}, []

    definition_lookup = {
        str(
            item.get(
                "name",
                "",
            )
        ).strip().upper(): item
        for item in parameter_definition
        if isinstance(item, dict)
    }

    for parameter in parameter_definition:
        if not isinstance(parameter, dict):
            rendering_errors.append(
                "Each parameter definition must be a JSON object."
            )
            continue

        parameter_name = str(
            parameter.get(
                "name",
                "",
            )
        ).strip().upper()

        parameter_type = str(
            parameter.get(
                "type",
                "",
            )
        ).strip().upper()

        depends_on = str(
            parameter.get(
                "depends_on",
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

        help_text = parameter.get(
            "help"
        )

        allowed_data_types = parameter.get(
            "allowed_data_types",
            [],
        )

        if not parameter_name:
            rendering_errors.append(
                "A parameter definition is missing its name."
            )
            continue

        if parameter_type not in SUPPORTED_PARAMETER_TYPES:
            rendering_errors.append(
                f"{parameter_name} uses unsupported type "
                f"{parameter_type or '(blank)'}."
            )
            continue

        widget_key = create_parameter_widget_key(
            selected_test,
            parameter_name,
        )

        parameter_column_metadata = (
            source_column_metadata
        )

        # -------------------------------------------------
        # Resolve dependent reference-asset columns
        # -------------------------------------------------

        if depends_on:
            dependency_definition = (
                definition_lookup.get(
                    depends_on
                )
            )

            dependency_type = str(
                (
                    dependency_definition
                    or {}
                ).get(
                    "type",
                    "",
                )
            ).strip().upper()

            if dependency_type == "ASSET":
                reference_value = parameters.get(
                    depends_on
                )

                if not reference_value:
                    parameters[parameter_name] = None

                    st.info(
                        f"Select "
                        f"{depends_on.replace('_', ' ').title()} "
                        f"before configuring {label}."
                    )

                    continue

                reference_asset = (
                    get_selected_asset_from_parameter(
                        reference_value,
                        asset_options,
                    )
                )

                if not reference_asset:
                    parameters[parameter_name] = None

                    rendering_errors.append(
                        f"Unable to resolve the selected "
                        f"{depends_on.replace('_', ' ').title()}."
                    )

                    continue

                reference_id = reference_asset[
                    "asset_id"
                ]

                if reference_id not in reference_column_cache:
                    try:
                        reference_column_cache[
                            reference_id
                        ] = get_object_columns(
                            cursor=cursor,
                            database_name=(
                                reference_asset[
                                    "database_name"
                                ]
                            ),
                            schema_name=(
                                reference_asset[
                                    "schema_name"
                                ]
                            ),
                            object_name=(
                                reference_asset[
                                    "object_name"
                                ]
                            ),
                        )

                    except Exception as reference_error:
                        parameters[parameter_name] = None

                        rendering_errors.append(
                            f"Unable to load reference columns "
                            f"for {label}: {reference_error}"
                        )

                        continue

                parameter_column_metadata = (
                    reference_column_cache[
                        reference_id
                    ]
                )

        filtered_columns = filter_columns_by_data_type(
            parameter_column_metadata,
            allowed_data_types,
        )

        available_column_names = get_column_names(
            filtered_columns
        )

        # -------------------------------------------------
        # COLUMN
        # -------------------------------------------------

        if parameter_type == "COLUMN":
            if not available_column_names:
                parameters[parameter_name] = None

                rendering_errors.append(
                    f"No eligible columns were found for {label}."
                )
                continue

            selected_column = st.selectbox(
                label,
                options=[
                    None,
                    *available_column_names,
                ],
                format_func=lambda value: (
                    f"Select {label.lower()}"
                    if value is None
                    else value
                ),
                key=widget_key,
                help=help_text,
            )

            parameters[parameter_name] = selected_column

            if selected_column:
                selected_type = get_column_data_type(
                    filtered_columns,
                    selected_column,
                )

                if selected_type:
                    st.caption(
                        f"Snowflake datatype: {selected_type}"
                    )

        # -------------------------------------------------
        # MULTI COLUMN
        # -------------------------------------------------

        elif parameter_type == "MULTI_COLUMN":
            if not available_column_names:
                parameters[parameter_name] = []

                rendering_errors.append(
                    f"No eligible columns were found for {label}."
                )
                continue

            parameters[parameter_name] = st.multiselect(
                label,
                options=available_column_names,
                key=widget_key,
                help=(
                    help_text
                    or "Select one or more columns."
                ),
            )

        # -------------------------------------------------
        # COLUMN VALUES
        # -------------------------------------------------

        elif parameter_type == "COLUMN_VALUES":
            source_parameter = str(
                parameter.get(
                    "source_column",
                    "COLUMN",
                )
            ).strip().upper()

            source_column = parameters.get(
                source_parameter
            )

            if not source_column:
                parameters[parameter_name] = []

                st.info(
                    f"Select "
                    f"{source_parameter.replace('_', ' ').title()} "
                    f"before configuring {label}."
                )
                continue

            try:
                available_values = get_distinct_values(
                    cursor=cursor,
                    database_name=database_name,
                    schema_name=schema_name,
                    object_name=object_name,
                    column_name=source_column,
                    limit=parameter.get(
                        "limit",
                        200,
                    ),
                )

                parameters[parameter_name] = st.multiselect(
                    label,
                    options=available_values,
                    key=widget_key,
                    help=(
                        help_text
                        or "Select one or more allowed values."
                    ),
                )

                st.caption(
                    f"{len(available_values)} distinct values available."
                )

            except Exception as value_error:
                parameters[parameter_name] = []

                rendering_errors.append(
                    f"Unable to load values for {label}: "
                    f"{value_error}"
                )

        # -------------------------------------------------
        # ASSET
        # -------------------------------------------------

        elif parameter_type == "ASSET":
            allow_current = bool(
                parameter.get(
                    "allow_current_asset",
                    False,
                )
            )

            available_asset_ids = [
                asset_id
                for asset_id in asset_options
                if (
                    allow_current
                    or asset_id != current_asset_id
                )
            ]

            selected_asset_id = st.selectbox(
                label,
                options=[
                    None,
                    *available_asset_ids,
                ],
                format_func=lambda value: (
                    format_asset_option(
                        value,
                        asset_options,
                    )
                ),
                key=widget_key,
                help=(
                    help_text
                    or "Select a registered reference asset."
                ),
            )

            if selected_asset_id is None:
                parameters[parameter_name] = None
            else:
                reference_asset = asset_options[
                    selected_asset_id
                ]

                parameters[parameter_name] = (
                    build_asset_identifier(
                        reference_asset
                    )
                )

        # -------------------------------------------------
        # VALUE
        # -------------------------------------------------

        elif parameter_type == "VALUE":
            value_type = infer_value_type(
                parameter,
                parameter_name,
                parameters,
                source_column_metadata,
            )

            default_value = parameter.get(
                "default"
            )

            if value_type == "NUMBER":
                parameters[parameter_name] = st.number_input(
                    label,
                    value=float(
                        default_value
                        if default_value is not None
                        else 0.0
                    ),
                    step=float(
                        parameter.get(
                            "step",
                            1.0,
                        )
                    ),
                    key=widget_key,
                    help=help_text,
                )

            elif value_type == "INTEGER":
                parameters[parameter_name] = int(
                    st.number_input(
                        label,
                        value=int(
                            default_value
                            if default_value is not None
                            else 0
                        ),
                        step=1,
                        key=widget_key,
                        help=help_text,
                    )
                )

            elif value_type == "BOOLEAN":
                parameters[parameter_name] = st.selectbox(
                    label,
                    options=[
                        None,
                        True,
                        False,
                    ],
                    format_func=lambda value: (
                        "Select true or false"
                        if value is None
                        else str(value).upper()
                    ),
                    key=widget_key,
                    help=help_text,
                )

            elif value_type == "DATE":
                selected_date = st.date_input(
                    label,
                    value=parse_default_date(
                        default_value
                    ),
                    key=widget_key,
                    help=help_text,
                )

                parameters[parameter_name] = (
                    selected_date.isoformat()
                )

            elif value_type == "TIMESTAMP":
                parameters[parameter_name] = st.text_input(
                    label,
                    value=(
                        str(default_value)
                        if default_value is not None
                        else ""
                    ),
                    placeholder="9999-12-31 23:59:59",
                    key=widget_key,
                    help=(
                        help_text
                        or "Use YYYY-MM-DD HH:MM:SS."
                    ),
                )

            else:
                parameters[parameter_name] = st.text_input(
                    label,
                    value=(
                        str(default_value)
                        if default_value is not None
                        else ""
                    ),
                    key=widget_key,
                    help=(
                        help_text
                        or "Enter the required comparison value."
                    ),
                )

            st.caption(
                f"Value input type: {value_type}"
            )

        # -------------------------------------------------
        # NUMBER
        # -------------------------------------------------

        elif parameter_type == "NUMBER":
            arguments = {
                "label": label,
                "value": float(
                    parameter.get(
                        "default",
                        0.0,
                    )
                ),
                "step": float(
                    parameter.get(
                        "step",
                        1.0,
                    )
                ),
                "key": widget_key,
                "help": help_text,
            }

            if parameter.get("minimum") is not None:
                arguments["min_value"] = float(
                    parameter["minimum"]
                )

            if parameter.get("maximum") is not None:
                arguments["max_value"] = float(
                    parameter["maximum"]
                )

            parameters[parameter_name] = st.number_input(
                **arguments
            )

        # -------------------------------------------------
        # INTEGER
        # -------------------------------------------------

        elif parameter_type == "INTEGER":
            parameters[parameter_name] = int(
                st.number_input(
                    label,
                    min_value=int(
                        parameter.get(
                            "minimum",
                            -2147483648,
                        )
                    ),
                    max_value=int(
                        parameter.get(
                            "maximum",
                            2147483647,
                        )
                    ),
                    value=int(
                        parameter.get(
                            "default",
                            0,
                        )
                    ),
                    step=1,
                    key=widget_key,
                    help=help_text,
                )
            )

        # -------------------------------------------------
        # OPERATOR
        # -------------------------------------------------

        elif parameter_type == "OPERATOR":
            allowed_operators = parameter.get(
                "allowed_values",
                parameter.get(
                    "options",
                    DEFAULT_OPERATORS,
                ),
            )

            allowed_operators = [
                str(operator)
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .strip()
                for operator in allowed_operators
            ]

            invalid = [
                operator
                for operator in allowed_operators
                if operator not in DEFAULT_OPERATORS
            ]

            if invalid:
                parameters[parameter_name] = None

                rendering_errors.append(
                    f"{parameter_name} contains unsupported "
                    f"operators: {', '.join(invalid)}."
                )
                continue

            parameters[parameter_name] = st.selectbox(
                label,
                options=allowed_operators,
                key=widget_key,
                help=(
                    help_text
                    or "Select the failure comparison operator."
                ),
            )

        # -------------------------------------------------
        # REGEX PRESET
        # -------------------------------------------------

        elif parameter_type == "REGEX_PRESET":
            selected_preset = st.selectbox(
                label,
                options=list(
                    REGEX_PRESETS.keys()
                ),
                key=widget_key,
                help=(
                    help_text
                    or "Choose an approved regular expression."
                ),
            )

            parameters[parameter_name] = (
                REGEX_PRESETS[
                    selected_preset
                ]
            )

            st.code(
                parameters[parameter_name],
                language="text",
            )

    return parameters, rendering_errors


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
        st.subheader("1. Select Data Asset")

        database_options = sorted(
            {
                asset["database_name"]
                for asset in assets
            }
        )

        selected_database = st.selectbox(
            "Database",
            options=[
                None,
                *database_options,
            ],
            format_func=lambda value: (
                "Select a database"
                if value is None
                else value
            ),
            key="selected_database",
            on_change=reset_after_database_change,
        )

        selected_schema = None
        selected_asset = None

        if selected_database:
            schema_options = sorted(
                {
                    asset["schema_name"]
                    for asset in assets
                    if asset["database_name"]
                    == selected_database
                }
            )

            selected_schema = st.selectbox(
                "Schema",
                options=[
                    None,
                    *schema_options,
                ],
                format_func=lambda value: (
                    "Select a schema"
                    if value is None
                    else value
                ),
                key="selected_schema",
                on_change=reset_after_schema_change,
            )

        if selected_database and selected_schema:
            matching_assets = [
                asset
                for asset in assets
                if (
                    asset["database_name"]
                    == selected_database
                    and asset["schema_name"]
                    == selected_schema
                )
            ]

            object_options = {
                (
                    f"{asset['object_name']} "
                    f"({asset['object_type']})"
                ): asset
                for asset in matching_assets
            }

            selected_object = st.selectbox(
                "Table / Object",
                options=[
                    None,
                    *object_options.keys(),
                ],
                format_func=lambda value: (
                    "Select a table or view"
                    if value is None
                    else value
                ),
                key="selected_object",
                on_change=reset_after_object_change,
            )

            if selected_object:
                selected_asset = object_options[
                    selected_object
                ]

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

            st.divider()
            st.subheader("2. Select Test")

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
                st.subheader(
                    "3. Configure Test Parameters"
                )

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
                    st.subheader(
                        "4. Configure Applicability"
                    )

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

                    execution_mode = st.radio(
                        "Execution Mode",
                        [
                            "AUTO",
                            "MANUAL",
                        ],
                        horizontal=True,
                        key="execution_mode",
                    )

                    frequency = None
                    run_day_of_week = None
                    run_day_of_month = None

                    if execution_mode == "AUTO":
                        frequency = st.selectbox(
                            "Frequency",
                            [
                                "DAILY",
                                "WEEKLY",
                                "MONTHLY",
                            ],
                            key="frequency",
                        )

                        if frequency == "WEEKLY":
                            run_day_of_week = st.selectbox(
                                "Run Day",
                                [
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
                        "execution_mode": execution_mode,
                        "frequency": frequency,
                        "run_day_of_week": run_day_of_week,
                        "run_day_of_month": run_day_of_month,
                        "pass_lower_bound": pass_lower_bound,
                        "pass_upper_bound": pass_upper_bound,
                    }

                    st.divider()
                    st.subheader(
                        "5. Review and Create"
                    )

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
                                            EXECUTION_MODE,
                                            FREQUENCY,
                                            RUN_DAY_OF_WEEK,
                                            RUN_DAY_OF_MONTH,
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
                                            reviewed[
                                                "execution_mode"
                                            ],
                                            reviewed["frequency"],
                                            reviewed[
                                                "run_day_of_week"
                                            ],
                                            reviewed[
                                                "run_day_of_month"
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