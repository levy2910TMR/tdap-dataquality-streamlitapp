import json
import re
from datetime import date, datetime

import streamlit as st


REGEX_PRESETS = {
    "Email address": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    "Digits only": r"^[0-9]+$",
    "Letters only": r"^[A-Za-z]+$",
    "Alphanumeric": r"^[A-Za-z0-9]+$",
    "Australian postcode": r"^[0-9]{4}$",
    "ISO date (YYYY-MM-DD)": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
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

DEFAULT_OPERATORS = ["=", "<>", "!=", ">", ">=", "<", "<="]
NUMBER_DATA_TYPES = {
    "NUMBER", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE",
    "DOUBLE PRECISION", "REAL", "INTEGER", "INT", "BIGINT",
    "SMALLINT", "BYTEINT",
}
INTEGER_DATA_TYPES = {"INTEGER", "INT", "BIGINT", "SMALLINT", "BYTEINT"}
DATE_DATA_TYPES = {"DATE"}
TIMESTAMP_DATA_TYPES = {
    "TIMESTAMP", "TIMESTAMP_NTZ", "TIMESTAMP_LTZ", "TIMESTAMP_TZ",
    "DATETIME",
}
BOOLEAN_DATA_TYPES = {"BOOLEAN", "BOOL"}


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
        parsed = json.loads(raw_definition)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    raise ValueError(
        "PARAMETER_DEFINITION must contain a JSON array or object."
    )


def get_object_columns(cursor, database_name, schema_name, object_name):
    database = quote_identifier(database_name)
    cursor.execute(
        f"""
        SELECT COLUMN_NAME, UPPER(DATA_TYPE) AS DATA_TYPE, ORDINAL_POSITION
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE UPPER(TABLE_SCHEMA) = UPPER(%s)
          AND UPPER(TABLE_NAME) = UPPER(%s)
        ORDER BY ORDINAL_POSITION
        """,
        (schema_name, object_name),
        timeout=30,
    )
    return [
        {
            "name": row[0],
            "data_type": str(row[1]).upper() if row[1] is not None else None,
            "ordinal_position": row[2],
        }
        for row in cursor.fetchall()
    ]


def get_column_names(column_metadata):
    return [column["name"] for column in column_metadata]


def get_column_data_type(column_metadata, column_name):
    if not column_name:
        return None
    for column in column_metadata:
        if str(column["name"]).upper() == str(column_name).upper():
            return column["data_type"]
    return None


def filter_columns_by_data_type(column_metadata, allowed_data_types):
    if not allowed_data_types:
        return column_metadata
    allowed_types = {
        str(value).strip().upper()
        for value in allowed_data_types
    }
    return [
        column for column in column_metadata
        if column["data_type"] and column["data_type"].upper() in allowed_types
    ]


def get_distinct_values(
    cursor,
    database_name,
    schema_name,
    object_name,
    column_name,
    limit=200,
):
    database = quote_identifier(database_name)
    schema = quote_identifier(schema_name)
    object_ = quote_identifier(object_name)
    column = quote_identifier(column_name)
    safe_limit = min(max(int(limit), 1), 500)
    cursor.execute(
        f"""
        SELECT DISTINCT TO_VARCHAR({column}) AS COLUMN_VALUE
        FROM {database}.{schema}.{object_}
        WHERE {column} IS NOT NULL
        ORDER BY COLUMN_VALUE
        LIMIT {safe_limit}
        """,
        timeout=30,
    )
    return [row[0] for row in cursor.fetchall() if row[0] is not None]


def build_asset_identifier(asset):
    return (
        f"{asset['database_name']}.{asset['schema_name']}."
        f"{asset['object_name']}"
    )


def format_asset_option(asset_id, asset_options):
    if asset_id is None:
        return "Select a reference asset"
    asset = asset_options.get(asset_id)
    if not asset:
        return str(asset_id)
    return (
        f"{asset['database_name']}.{asset['schema_name']}."
        f"{asset['object_name']} ({asset['object_type']})"
    )


def get_selected_asset_from_parameter(parameter_value, asset_options):
    if parameter_value is None:
        return None
    parameter_fqn = str(parameter_value).upper()
    for asset in asset_options.values():
        if build_asset_identifier(asset).upper() == parameter_fqn:
            return asset
    return None


def infer_value_type(
    parameter,
    parameter_name,
    parameters,
    source_column_metadata,
):
    explicit_type = parameter.get("value_type")
    if explicit_type:
        return str(explicit_type).strip().upper()
    depends_on = str(parameter.get("depends_on", "")).strip().upper()
    if depends_on:
        dependent_type = get_column_data_type(
            source_column_metadata,
            parameters.get(depends_on),
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
    combined_name = f"{parameter_name} {parameter.get('label', '')}".upper()
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
            return date.fromisoformat(default_value[:10])
        except ValueError:
            pass
    return date.today()


def _widget_key(selected_test, parameter_name, key_prefix, context=""):
    parts = [key_prefix, selected_test, context, parameter_name]
    safe_parts = [
        re.sub(r"[^A-Za-z0-9_]+", "_", str(part).upper()).strip("_")
        for part in parts
        if part
    ]
    return "dq_parameter_" + "_".join(safe_parts)


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
    initial_parameters=None,
    key_prefix="",
):
    parameters = {}
    rendering_errors = []
    reference_column_cache = {}
    initial_parameters = {
        str(name).strip().upper(): value
        for name, value in (initial_parameters or {}).items()
    }

    if not parameter_definition:
        st.info("This test does not require configurable parameters.")
        return {}, []

    definition_lookup = {
        str(item.get("name", "")).strip().upper(): item
        for item in parameter_definition
        if isinstance(item, dict)
    }

    for parameter in parameter_definition:
        if not isinstance(parameter, dict):
            rendering_errors.append(
                "Each parameter definition must be a JSON object."
            )
            continue

        parameter_name = str(parameter.get("name", "")).strip().upper()
        parameter_type = str(parameter.get("type", "")).strip().upper()
        depends_on = str(parameter.get("depends_on", "")).strip().upper()
        label = (
            parameter.get("label")
            or parameter_name.replace("_", " ").title()
        )
        help_text = parameter.get("help")
        allowed_data_types = parameter.get("allowed_data_types", [])

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

        dependency_context = ""
        parameter_column_metadata = source_column_metadata
        if depends_on:
            dependency_definition = definition_lookup.get(depends_on, {})
            dependency_type = str(
                dependency_definition.get("type", "")
            ).strip().upper()
            if dependency_type == "ASSET":
                reference_value = parameters.get(depends_on)
                if not reference_value:
                    parameters[parameter_name] = None
                    st.info(
                        f"Select {depends_on.replace('_', ' ').title()} "
                        f"before configuring {label}."
                    )
                    continue
                reference_asset = get_selected_asset_from_parameter(
                    reference_value, asset_options
                )
                if not reference_asset:
                    parameters[parameter_name] = None
                    rendering_errors.append(
                        f"Unable to resolve the selected "
                        f"{depends_on.replace('_', ' ').title()}."
                    )
                    continue
                reference_id = reference_asset["asset_id"]
                dependency_context = f"asset_{reference_id}"
                if reference_id not in reference_column_cache:
                    try:
                        reference_column_cache[reference_id] = (
                            get_object_columns(
                                cursor,
                                reference_asset["database_name"],
                                reference_asset["schema_name"],
                                reference_asset["object_name"],
                            )
                        )
                    except Exception as error:
                        parameters[parameter_name] = None
                        rendering_errors.append(
                            f"Unable to load reference columns for "
                            f"{label}: {error}"
                        )
                        continue
                parameter_column_metadata = reference_column_cache[
                    reference_id
                ]

        if parameter_type == "COLUMN_VALUES":
            source_parameter = str(
                parameter.get("source_column", "COLUMN")
            ).strip().upper()
            dependency_context = (
                f"{dependency_context}_"
                f"{parameters.get(source_parameter, '')}"
            )

        widget_key = _widget_key(
            selected_test,
            parameter_name,
            key_prefix,
            dependency_context,
        )
        filtered_columns = filter_columns_by_data_type(
            parameter_column_metadata,
            allowed_data_types,
        )
        available_column_names = get_column_names(filtered_columns)
        saved_value = initial_parameters.get(parameter_name)

        if parameter_type == "COLUMN":
            if not available_column_names:
                parameters[parameter_name] = None
                rendering_errors.append(
                    f"No eligible columns were found for {label}."
                )
                continue
            options = [None, *available_column_names]
            initial = saved_value if saved_value in options else None
            selected_column = st.selectbox(
                label,
                options=options,
                index=options.index(initial),
                format_func=lambda value: (
                    f"Select {label.lower()}"
                    if value is None
                    else value
                ),
                key=widget_key,
                help=help_text,
            )
            parameters[parameter_name] = selected_column
            selected_type = get_column_data_type(
                filtered_columns,
                selected_column,
            )
            if selected_column and selected_type:
                st.caption(f"Snowflake datatype: {selected_type}")

        elif parameter_type == "MULTI_COLUMN":
            if not available_column_names:
                parameters[parameter_name] = []
                rendering_errors.append(
                    f"No eligible columns were found for {label}."
                )
                continue
            initial = saved_value if isinstance(saved_value, list) else []
            parameters[parameter_name] = st.multiselect(
                label,
                options=available_column_names,
                default=[
                    value for value in initial
                    if value in available_column_names
                ],
                key=widget_key,
                help=help_text or "Select one or more columns.",
            )

        elif parameter_type == "COLUMN_VALUES":
            source_parameter = str(
                parameter.get("source_column", "COLUMN")
            ).strip().upper()
            source_column = parameters.get(source_parameter)
            if not source_column:
                parameters[parameter_name] = []
                st.info(
                    f"Select {source_parameter.replace('_', ' ').title()} "
                    f"before configuring {label}."
                )
                continue
            try:
                available_values = get_distinct_values(
                    cursor,
                    database_name,
                    schema_name,
                    object_name,
                    source_column,
                    parameter.get("limit", 200),
                )
                initial = saved_value if isinstance(saved_value, list) else []
                parameters[parameter_name] = st.multiselect(
                    label,
                    options=available_values,
                    default=[
                        value for value in initial
                        if value in available_values
                    ],
                    key=widget_key,
                    help=help_text or "Select one or more allowed values.",
                )
                st.caption(
                    f"{len(available_values)} distinct values available."
                )
            except Exception as error:
                parameters[parameter_name] = []
                rendering_errors.append(
                    f"Unable to load values for {label}: {error}"
                )

        elif parameter_type == "ASSET":
            allow_current = bool(parameter.get("allow_current_asset", False))
            available_asset_ids = [
                asset_id for asset_id in asset_options
                if allow_current or asset_id != current_asset_id
            ]
            saved_asset = get_selected_asset_from_parameter(
                saved_value,
                asset_options,
            )
            initial = saved_asset["asset_id"] if saved_asset else None
            options = [None, *available_asset_ids]
            if initial not in options:
                initial = None
            selected_asset_id = st.selectbox(
                label,
                options=options,
                index=options.index(initial),
                format_func=lambda value: format_asset_option(
                    value,
                    asset_options,
                ),
                key=widget_key,
                help=help_text or "Select a registered reference asset.",
            )
            parameters[parameter_name] = (
                build_asset_identifier(asset_options[selected_asset_id])
                if selected_asset_id is not None
                else None
            )

        elif parameter_type == "VALUE":
            value_type = infer_value_type(
                parameter, parameter_name, parameters, source_column_metadata
            )
            default_value = (
                saved_value
                if saved_value is not None
                else parameter.get("default")
            )
            if value_type == "NUMBER":
                parameters[parameter_name] = st.number_input(
                    label,
                    value=float(
                        default_value if default_value is not None else 0.0
                    ),
                    step=float(parameter.get("step", 1.0)),
                    key=widget_key,
                    help=help_text,
                )
            elif value_type == "INTEGER":
                parameters[parameter_name] = int(st.number_input(
                    label,
                    value=int(
                        default_value if default_value is not None else 0
                    ),
                    step=1,
                    key=widget_key,
                    help=help_text,
                ))
            elif value_type == "BOOLEAN":
                options = [None, True, False]
                initial = default_value if default_value in options else None
                parameters[parameter_name] = st.selectbox(
                    label,
                    options=options,
                    index=options.index(initial),
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
                    value=parse_default_date(default_value),
                    key=widget_key,
                    help=help_text,
                )
                parameters[parameter_name] = selected_date.isoformat()
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
                    help=help_text or "Use YYYY-MM-DD HH:MM:SS.",
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
                    help=help_text or "Enter the required comparison value.",
                )
            st.caption(f"Value input type: {value_type}")

        elif parameter_type == "NUMBER":
            arguments = {
                "label": label,
                "value": float(
                    saved_value
                    if saved_value is not None
                    else parameter.get("default", 0.0)
                ),
                "step": float(parameter.get("step", 1.0)),
                "key": widget_key,
                "help": help_text,
            }
            if parameter.get("minimum") is not None:
                arguments["min_value"] = float(parameter["minimum"])
            if parameter.get("maximum") is not None:
                arguments["max_value"] = float(parameter["maximum"])
            parameters[parameter_name] = st.number_input(**arguments)

        elif parameter_type == "INTEGER":
            parameters[parameter_name] = int(st.number_input(
                label,
                min_value=int(parameter.get("minimum", -2147483648)),
                max_value=int(parameter.get("maximum", 2147483647)),
                value=int(
                    saved_value
                    if saved_value is not None
                    else parameter.get("default", 0)
                ),
                step=1,
                key=widget_key,
                help=help_text,
            ))

        elif parameter_type == "OPERATOR":
            operators = parameter.get(
                "allowed_values",
                parameter.get("options", DEFAULT_OPERATORS),
            )
            operators = [
                str(operator).replace("&lt;", "<").replace("&gt;", ">")
                .strip()
                for operator in operators
            ]
            invalid = [
                operator for operator in operators
                if operator not in DEFAULT_OPERATORS
            ]
            if invalid:
                parameters[parameter_name] = None
                rendering_errors.append(
                    f"{parameter_name} contains unsupported operators: "
                    f"{', '.join(invalid)}."
                )
                continue
            initial = saved_value if saved_value in operators else operators[0]
            parameters[parameter_name] = st.selectbox(
                label,
                options=operators,
                index=operators.index(initial),
                key=widget_key,
                help=help_text or "Select the failure comparison operator.",
            )

        elif parameter_type == "REGEX_PRESET":
            preset_by_pattern = {
                pattern: name
                for name, pattern in REGEX_PRESETS.items()
            }
            initial = preset_by_pattern.get(
                saved_value,
                next(iter(REGEX_PRESETS)),
            )
            preset_names = list(REGEX_PRESETS)
            selected_preset = st.selectbox(
                label,
                options=preset_names,
                index=preset_names.index(initial),
                key=widget_key,
                help=help_text or "Choose an approved regular expression.",
            )
            parameters[parameter_name] = REGEX_PRESETS[selected_preset]
            st.code(parameters[parameter_name], language="text")

    return parameters, rendering_errors
