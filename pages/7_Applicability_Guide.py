import streamlit as st


TEST_GUIDE = {
    "NOT_NULL": {
        "name": "Not Null",
        "purpose": "Count rows where a column is null.",
        "fields": "Choose the column that must have a value.",
        "example": "Column: CUSTOMER_ID",
    },
    "UNIQUENESS": {
        "name": "Uniqueness",
        "purpose": "Count duplicate occurrences across one or more columns.",
        "fields": "Select the columns whose combined values must be unique.",
        "example": "Columns: CUSTOMER_ID, EFFECTIVE_DATE",
    },
    "ACCEPTED_VALUES": {
        "name": "Accepted Values",
        "purpose": "Count non-null values outside an allowed set.",
        "fields": "Choose the column, then select its allowed values.",
        "example": "Column: STATUS; allowed values: ACTIVE, INACTIVE",
    },
    "REFERENTIAL_INTEGRITY": {
        "name": "Referential Integrity",
        "purpose": "Count non-null source values missing from a reference asset.",
        "fields": "Select the source column, reference asset, and matching reference column.",
        "example": "Source: CUSTOMER_ID; reference: CUSTOMER; reference column: ID",
    },
    "STRING_TRIM": {
        "name": "Whitespace Check",
        "purpose": "Count non-null text values with leading or trailing whitespace.",
        "fields": "Select the text column to check.",
        "example": "Column: CUSTOMER_NAME",
    },
    "STRING_LENGTH": {
        "name": "Maximum String Length",
        "purpose": "Count non-null text values longer than the maximum length.",
        "fields": "Select a text column and enter the maximum length in characters.",
        "example": "Column: CUSTOMER_NAME; maximum length: 100",
    },
    "NUMERIC_RANGE": {
        "name": "Numeric Range",
        "purpose": "Count non-null numeric values below the minimum or above the maximum.",
        "fields": "Select a numeric column and enter inclusive minimum and maximum values.",
        "example": "Column: AGE; minimum: 0; maximum: 120",
    },
    "DATE_ORDER": {
        "name": "Date / Timestamp Order",
        "purpose": "Count rows where the earlier date or time is after the later one.",
        "fields": "Choose two different date or timestamp columns. Null values are excluded.",
        "example": "Earlier column: START_DATE; later column: END_DATE",
    },
    "REGEX_VALIDATION": {
        "name": "Regex Validation",
        "purpose": "Count non-null text values that do not match an approved pattern.",
        "fields": "Select a text column and choose a regex preset.",
        "example": "Column: EMAIL; pattern: Email address",
    },
    "REQUIRED_RECORD": {
        "name": "Required Record",
        "purpose": "Return one failure if the required value is absent; otherwise return zero.",
        "fields": "Choose a column and enter a required value of the appropriate type.",
        "example": "Column: STATUS; required value: ACTIVE",
    },
    "SCD_VALIDITY": {
        "name": "SCD Current Record Validity",
        "purpose": "Count rows where the current flag and open-ended valid-to value disagree.",
        "fields": "Choose the current flag and valid-to columns, then enter the open-end value.",
        "example": "Current flag: IS_CURRENT; valid-to: VALID_TO; open end: 9999-12-31",
        "note": "The current form infers this input as a date from its label. Confirm that the resulting value matches the valid-to column's type and precision.",
    },
    "DATE_VALIDITY": {
        "name": "Date Validity",
        "purpose": "Count non-null values before the earliest valid date or after today.",
        "fields": "Select a date or timestamp column and enter the earliest valid date.",
        "example": "Date column: EVENT_DATE; earliest valid date: 2000-01-01",
    },
    "SCHEMA_CONVENTION": {
        "name": "Schema Data Type Convention",
        "purpose": "Count columns whose names match a pattern but whose data type differs from the expected type.",
        "fields": "Enter a column-name regular expression and the expected Snowflake data type.",
        "example": "Column name pattern: .*_ID; expected data type: NUMBER",
    },
    "COLUMN_COMPARISON": {
        "name": "Column Comparison",
        "purpose": "Count rows where two non-null columns satisfy the failure comparison.",
        "fields": "Choose two different columns and the operator that identifies a failure.",
        "example": "Left: START_DATE; failure operator: >; right: END_DATE",
    },
    "ABS_DIFFERENCE_THRESHOLD": {
        "name": "Absolute Difference Threshold",
        "purpose": "Count rows where the absolute difference satisfies the failure comparison.",
        "fields": "Choose two different numeric columns, a failure operator, and a threshold.",
        "example": "First: EXPECTED; second: ACTUAL; operator: >; threshold: 5",
    },
    "RATIO_THRESHOLD": {
        "name": "Ratio Threshold",
        "purpose": "Count rows where the numerator divided by the denominator satisfies the failure comparison.",
        "fields": "Choose different numerator and denominator columns, a failure operator, and a threshold.",
        "example": "Numerator: SALES; denominator: TARGET; operator: <; threshold: 0.8",
        "note": "Rows with null values or a zero denominator are excluded.",
    },
    "COUNT_DISTINCT_THRESHOLD": {
        "name": "Distinct Count Threshold",
        "purpose": "Count groups whose distinct value count satisfies the failure comparison.",
        "fields": "Choose group-by columns, the column to count, a failure operator, and a threshold.",
        "example": "Group by: CUSTOMER_ID; count: EMAIL; operator: >; threshold: 1",
    },
    "CROSS_TABLE_COLUMN_MATCH": {
        "name": "Cross-Table Column Match",
        "purpose": "Count source rows with no reference match or with different compared values.",
        "fields": "Select a reference asset, source and reference join columns, and source and reference comparison columns.",
        "example": "Join CUSTOMER_ID to ID; compare STATUS to CUSTOMER_STATUS",
        "note": "Multiple reference matches can produce multiple joined rows for one source row.",
    },
    "RATIO_VALUE_MATCH": {
        "name": "Ratio Derived Value Match",
        "purpose": "Count rows where a stored value differs from a scaled ratio beyond the tolerance.",
        "fields": "Choose stored, numerator, and denominator columns; enter a scale and tolerance.",
        "example": "Stored: PERCENT; numerator: SALES; denominator: TARGET; scale: 100; tolerance: 0.01",
        "note": "Rows with null inputs or a zero denominator are excluded.",
    },
    "SUM_VALUE_MATCH": {
        "name": "Sum Derived Value Match",
        "purpose": "Count rows where a stored value differs from the sum of three components beyond the tolerance.",
        "fields": "Choose the stored value and three component columns, then enter a tolerance.",
        "example": "Stored: TOTAL; components: PART_1, PART_2, PART_3; tolerance: 0.01",
    },
    "TIMESTAMP_DIFF_VALUE_MATCH": {
        "name": "Timestamp Difference Derived Value Match",
        "purpose": "Count joined rows where a stored duration differs from the reference timestamp difference beyond the tolerance.",
        "fields": "Select the reference asset, join columns, stored duration, reference start and end timestamps, and tolerance in seconds.",
        "example": "Join EVENT_ID to ID; stored: DURATION_SECONDS; timestamps: START_TS and END_TS; tolerance: 1",
        "note": "Only matching joined rows with non-null inputs are checked; the duration is calculated in seconds.",
    },
}


st.title("Applicability Guide")
st.write(
    "An applicability connects one data asset to one test and records "
    "the parameters and execution settings for that combination."
)

st.subheader("Create an applicability")
st.markdown(
    """
1. Open **Configure Applicability** and select an active database, schema, and table or object.
2. Select an active data quality test. The form displays the parameters required by that test.
3. Enter the parameters. For reference-asset tests, select the reference asset before its columns.
4. Enter a unique applicability code, execution mode, scheduling details if needed, and pass bounds.
5. Select **Review Configuration**, correct any validation errors, then select **Create Applicability**.
6. Open **View Applicabilities** to search for the saved configuration by test or asset.
    """
)

with st.expander("Applicability fields", expanded=True):
    st.markdown(
        """
- **Applicability code:** A unique identifier. The form suggests one from the asset and test; it converts it to uppercase and replaces non-alphanumeric characters with underscores.
- **Asset and test:** Select the asset to check and the test to apply. The app supplies their IDs when saving.
- **Parameters:** The values requested for the chosen test. They are saved as JSON; you do not need to type JSON in the form.
- **Execution mode:** Choose `MANUAL` or `AUTO`. For `AUTO`, select daily, weekly, or monthly frequency; weekly and monthly schedules require a day.
- **Pass lower and upper bounds:** Set the acceptable bounds for the test's result. The lower bound cannot exceed the upper bound. For tests that count failures, `0` and `0` express an expectation of no failures.
- **Status:** A newly created applicability is saved as `ACTIVE`.
        """
    )
    st.caption(
        "Automatic execution depends on the platform's scheduling setup; "
        "this form records the schedule."
    )

st.subheader("Test-by-test guide")
st.caption(
    "This reference is based on the supplied catalogue snapshot. "
    "Available tests and parameter definitions can change."
)

selected_code = st.selectbox(
    "Choose a test",
    options=list(TEST_GUIDE),
    format_func=lambda code: f"{TEST_GUIDE[code]['name']} ({code})",
)
guide = TEST_GUIDE[selected_code]
st.markdown(f"**What it checks:** {guide['purpose']}")
st.markdown(f"**What to enter:** {guide['fields']}")
st.markdown(f"**Example:** {guide['example']}")
if "note" in guide:
    st.info(guide["note"])

with st.expander("Tips for parameters and review"):
    st.markdown(
        """
- Column choices come from the selected asset. Some tests restrict choices to specific data types.
- Allowed values are selected from distinct values currently present in the selected column, up to the configured limit.
- A failure operator defines what the test counts as a failure. For example, `>` with a threshold of `5` counts values greater than `5`.
- Tolerances are expressed in the units of the calculated value, except timestamp difference tolerance, which is in seconds.
- Review the displayed JSON and schedule before creating. If you change the configuration after review, review it again.
- The tests listed here were active in the supplied snapshot. Inactive tests are not offered by the configuration form.
        """
    )