import pandas as pd
import streamlit as st

from connection import get_connection


st.title("Data Quality Applicabilities")


def load_applicabilities():
    conn = None

    try:
        conn = get_connection()
        query = """
            SELECT
                A.APPLICABILITY_ID,
                A.APPLICABILITY_CODE,
                A.CREATED_TS,
                A.UPDATED_TS,
                A.STATUS,
                T.TEST_CODE,
                T.TEST_NAME,
                S.ASSET_CODE,
                S.DATABASE_NAME,
                S.SCHEMA_NAME,
                S.OBJECT_NAME,
                A.PARAMETERS,
                A.FREQUENCY,
                A.RUN_DAY_OF_MONTH,
                A.RUN_MONTH_OF_YEAR,
                A.PASS_LOWER_BOUND,
                A.PASS_UPPER_BOUND
            FROM DP_DEV_MTD.DATA_QUALITY.DQ_APPLICABILITY A
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_TEST T
                ON A.TEST_ID = T.TEST_ID
            LEFT JOIN DP_DEV_MTD.DATA_QUALITY.DQ_ASSET S
                ON A.ASSET_ID = S.ASSET_ID
            ORDER BY A.APPLICABILITY_CODE, A.APPLICABILITY_ID
        """
        return pd.read_sql(query, conn)
    finally:
        if conn is not None:
            conn.close()


def filter_applicabilities(df, search):
    search = search.strip()
    if not search:
        return df

    columns = [
        "APPLICABILITY_CODE",
        "TEST_CODE",
        "TEST_NAME",
        "ASSET_CODE",
        "DATABASE_NAME",
        "SCHEMA_NAME",
        "OBJECT_NAME",
    ]
    searchable = df[columns].fillna("").astype(str)
    asset_name = searchable["DATABASE_NAME"].str.cat(
        [searchable["SCHEMA_NAME"], searchable["OBJECT_NAME"]],
        sep=".",
    )
    matches = asset_name.str.contains(search, case=False, regex=False)
    for column in columns:
        matches |= searchable[column].str.contains(
            search, case=False, regex=False
        )
    return df.loc[matches]


if st.button("Refresh Applicabilities"):
    st.rerun()

try:
    applicabilities = load_applicabilities()
    applicabilities.columns = [
        column.upper() for column in applicabilities.columns
    ]

    search = st.text_input(
        "Search by test or asset",
        placeholder="Test name or code, asset code or object name",
    )

    if applicabilities.empty:
        st.info("No applicability configurations are available.")
    else:
        filtered = filter_applicabilities(applicabilities, search)
        st.caption(f"Showing {len(filtered)} of {len(applicabilities)} applicabilities")
        if filtered.empty:
            st.info("No applicability configurations match your search.")
        else:
            st.dataframe(filtered, hide_index=True)
except Exception as error:
    st.error(f"Failed to load applicability configurations: {error}")