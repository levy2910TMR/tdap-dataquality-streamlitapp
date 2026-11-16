import streamlit as st
from connection import get_connection

st.title("Create Test")

st.write("Create a new data quality test definition.")

with st.form("create_test_form"):

    test_code = st.text_input(
        "Test Code",
        placeholder="NULL_COUNT"
    )

    test_name = st.text_input(
        "Test Name",
        placeholder="Null Count"
    )

    description = st.text_area(
        "Description",
        placeholder="Checks the number of null values in a column."
    )

    sql_template = st.text_area(
        "SQL Template",
        height=200,
        placeholder="SELECT COUNT(*) FROM {{TABLE}} WHERE {{COLUMN}} IS NULL"
    )

    submitted = st.form_submit_button("Create Test")

if submitted:

    if not test_code or not test_name or not sql_template:
        st.error("Test Code, Test Name and SQL Template are required.")

    else:
        conn = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            sql = """
                INSERT INTO DP_DEV_MTD.DATA_QUALITY.DQ_TEST
                    (TEST_CODE, TEST_NAME, DESCRIPTION, SQL_TEMPLATE)
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                sql,
                (
                    test_code,
                    test_name,
                    description,
                    sql_template
                )
            )

            conn.commit()

            st.success(f"Test '{test_code}' created successfully.")

        except Exception as e:
            st.error(f"Failed to create test: {e}")

        finally:
            if conn:
                conn.close()