import streamlit as st
from connection import get_connection

st.title("Create Test Version")

st.write("Create a new version for an existing data quality test.")

conn = None

try:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TEST_ID, TEST_CODE
        FROM DP_DEV_MTD.DATA_QUALITY.DQ_TEST
        ORDER BY TEST_CODE
    """)

    tests = cursor.fetchall()

    test_options = {
        f"{row[1]} (ID: {row[0]})": row[0]
        for row in tests
    }

    selected_test = st.selectbox(
        "Test",
        options=list(test_options.keys())
    )

    version = st.number_input(
        "Version",
        min_value=1,
        value=1
    )

    parameters = st.text_area(
        "Parameter Definition",
        placeholder='{"COLUMN": "string"}'
    )

    sql_template = st.text_area(
        "SQL Template",
        height=200
    )

    if st.button("Create Version"):

        test_id = test_options[selected_test]

        st.info(
            f"Ready to create version {version} "
            f"for TEST_ID {test_id}"
        )

finally:
    if conn:
        conn.close()