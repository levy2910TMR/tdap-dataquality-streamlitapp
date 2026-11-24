from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="DQ Platform MVP",
    page_icon="✅",
    layout="wide",
)


def home():
    st.title("Data Quality Platform")
    st.markdown(
        "Use the menu to manage tests, configure applicability, "
        "run tests, and view results."
    )


def results_unavailable():
    st.title("Data Quality Results")
    st.info("The results page is not currently available in this workspace.")


def available_pages(page_definitions):
    root = Path(__file__).parent
    return [
        st.Page(path, title=title)
        for path, title in page_definitions
        if (root / path).is_file()
    ]


navigation = {"": [st.Page(home, title="Home", default=True)]}

test_pages = available_pages([
    ("pages/1_Create_Test.py", "Create Test"),
    ("pages/2_Create_Version.py", "Create Version"),
])
if test_pages:
    navigation["Test Management"] = test_pages

applicability_pages = available_pages([
    ("pages/3_Configure_Applicability.py", "Configure Applicability"),
    ("pages/6_View_Applicabilities.py", "View Applicability"),
    ("pages/7_Applicability_Guide.py", "Applicability Guide"),
])
if applicability_pages:
    navigation["Applicability"] = applicability_pages

execution_pages = available_pages([
    ("pages/4_Run_Tests.py", "Run Tests"),
])
if execution_pages:
    navigation["Execution"] = execution_pages

navigation["Results"] = available_pages([
    ("pages/5_View_Results.py", "View Results"),
]) or [st.Page(results_unavailable, title="View Results")]

st.navigation(navigation).run()