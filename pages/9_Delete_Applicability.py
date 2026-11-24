import pandas as pd
import streamlit as st

from connection import get_connection


st.title("Delete Applicability")
st.warning(
    "Deletion is permanent. Confirm the selected applicability carefully."
)


def load_applicabilities():
    conn = get_connection()
    try:
        return pd.read_sql(
            """
            SELECT
                A.APPLICABILITY_ID,
                A.APPLICABILITY_CODE,
                T.TEST_CODE,
                S.DATABASE_NAME,
                S.SCHEMA_NAME,
                S.OBJECT_NAME
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY A
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_TEST T
                ON A.TEST_ID = T.TEST_ID
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_ASSET S
                ON A.ASSET_ID = S.ASSET_ID
            ORDER BY A.APPLICABILITY_CODE, A.APPLICABILITY_ID
            """,
            conn,
        )
    finally:
        conn.close()


try:
    applicabilities = load_applicabilities()
    applicabilities.columns = [
        column.upper() for column in applicabilities.columns
    ]

    if applicabilities.empty:
        st.info("There are no applicability configurations to delete.")
    else:
        records = {
            int(row["APPLICABILITY_ID"]): row
            for row in applicabilities.to_dict("records")
        }
        applicability_ids = list(records)
        selection_key = "delete_applicability_" + "_".join(
            str(item_id) for item_id in applicability_ids
        )
        selected_id = st.selectbox(
            "Applicability",
            options=applicability_ids,
            format_func=lambda item_id: (
                f"{item_id} · {records[item_id]['APPLICABILITY_CODE']}"
            ),
            key=selection_key,
        )
        record = records[selected_id]
        asset_name = ".".join(
            str(record[column] or "")
            for column in (
                "DATABASE_NAME",
                "SCHEMA_NAME",
                "OBJECT_NAME",
            )
        )
        st.write(f"**Test:** {record['TEST_CODE'] or 'Unknown'}")
        st.write(f"**Asset:** {asset_name}")

        confirmation = st.text_input(
            "Type DELETE to confirm",
            key=f"delete_confirmation_{selected_id}",
        )
        if st.button(
            "Delete Applicability",
            type="primary",
            disabled=confirmation.strip().casefold() != "delete",
        ):
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY
                    WHERE APPLICABILITY_ID = %s
                    """,
                    (selected_id,),
                )
                conn.commit()
                st.success("Applicability deleted.")
                st.rerun()
            except Exception as error:
                conn.rollback()
                st.error(f"Failed to delete applicability: {error}")
            finally:
                conn.close()
except Exception as error:
    st.error(f"Failed to load applicability deletion page: {error}")
