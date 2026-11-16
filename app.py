import streamlit as st

st.set_page_config(
    page_title="DQ Platform MVP",
    page_icon="✅",
    layout="wide"
)

st.title("Data Quality Platform")

st.markdown("""
### Welcome 👋

Use the menu on the left to manage and execute data quality tests.

**Test Management**
- Create Tests
- Create Test Versions

**Configuration**
- Configure Applicability

**Execution**
- Run Data Quality Tests

**Monitoring**
- View Results
""")

st.info(
    "This is the MVP interface for the TDAP Data Quality Platform."
)