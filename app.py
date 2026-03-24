import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Log → History Generator", layout="wide")

st.title("📊 Log to Device History Tool")

# =========================
# REGEX
# =========================
REQ_ID_REGEX = r'Request ID:\s*([0-9a-fA-F\-]{36})'
DEVICE_REGEX = r'deviceId[=:]\s*"?([A-Za-z0-9\-]+)"?'
DT_REGEX = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'


# =========================
# EXTRACT FUNCTIONS
# =========================
def extract_request_id(text):
    if pd.isna(text):
        return None
    match = re.search(REQ_ID_REGEX, text)
    return match.group(1) if match else None


def extract_device(text):
    if pd.isna(text):
        return None
    match = re.search(DEVICE_REGEX, text)
    return match.group(1) if match else None


def extract_datetime(text):
    if pd.isna(text):
        return None
    match = re.search(DT_REGEX, text)
    return match.group(0) if match else None


# =========================
# PROCESS FILE
# =========================
def process_log(df, log_type):
    df["RequestID"] = df["@message"].apply(extract_request_id)
    df["Datetime"] = df["@message"].apply(extract_datetime)
    df["DeviceID"] = df["@message"].apply(extract_device)

    df = df[["RequestID", "Datetime", "DeviceID", "@message"]]
    df = df.rename(columns={"@message": log_type})

    return df


# =========================
# UI
# =========================
uploaded_files = st.file_uploader(
    "📥 Upload 8 CSV files (request/response)",
    type=["csv"],
    accept_multiple_files=True
)

if uploaded_files:

    all_requests = []
    all_responses = []

    for file in uploaded_files:
        df = pd.read_csv(file)

        if "request" in file.name.lower():
            df_req = process_log(df, "Request")
            all_requests.append(df_req)

        elif "response" in file.name.lower():
            df_res = process_log(df, "Response")
            all_responses.append(df_res)

    # =========================
    # MERGE ALL
    # =========================
    df_req_all = pd.concat(all_requests, ignore_index=True)
    df_res_all = pd.concat(all_responses, ignore_index=True)

    df_merge = pd.merge(
        df_req_all,
        df_res_all,
        on="RequestID",
        how="outer",
        suffixes=("_req", "_res")
    )

    # =========================
    # FINAL FORMAT
    # =========================
    df_merge["Datetime"] = df_merge["Datetime_req"].combine_first(df_merge["Datetime_res"])
    df_merge["DeviceID"] = df_merge["DeviceID_req"].combine_first(df_merge["DeviceID_res"])

    df_final = df_merge[[
        "Datetime",
        "DeviceID",
        "Request",
        "Response"
    ]]

    df_final = df_final.sort_values(by="Datetime")

    st.success("✅ Transform สำเร็จ")

    st.dataframe(df_final, use_container_width=True)

    # =========================
    # DOWNLOAD
    # =========================
    csv = df_final.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download History CSV",
        csv,
        file_name="device_history.csv",
        mime="text/csv"
    )
