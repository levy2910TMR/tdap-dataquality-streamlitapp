import streamlit as st
from connection import get_connection

st.title("Run Data Quality Tests")

st.write("Create and execute a data quality request.")

run_type = st.radio(
    "Run Type",
    ["Automated Applicabilities", "Manual Selection"]
)

if run_type == "Automated Applicabilities":

    st.info(
        "Runs the active applicability configurations "
        "configured for automatic execution."
    )

    if st.button(
        "Run Tests",
        type="primary"
    ):

        conn = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Replace parameters with the final
            # SP_CREATE_DQ_REQUEST signature.

            cursor.execute("""
                CALL DP_DEV_MTD.DATA_QUALITY.SP_CREATE_DQ_REQUEST()
            """)

            result = cursor.fetchone()

            st.success("DQ request created successfully.")

            if result:
                st.write("Procedure result:")
                st.write(result[0])

        except Exception as e:
            st.error(f"DQ execution failed: {e}")

        finally:
            if conn:
                conn.close()


else:

    st.warning(
        "Manual test selection will be added "
        "after the automated MVP flow is complete."
    )