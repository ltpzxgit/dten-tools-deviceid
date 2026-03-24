import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="DeviceID Report Generator", layout="wide")

st.title("📊 DeviceID Report (เหมือน History File)")

# =========================
# REGEX
# =========================
REQ_ID_REGEX = r'Request ID:\s*([0-9a-fA-F\-]{36})'
DEVICE_REGEX = r'deviceId[=:]\s*"?([A-Za-z0-9\-]+)"?'
DT_REGEX = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'


def extract_request_id(text):
    if pd.isna(text):
        return None
    m = re.search(REQ_ID_REGEX, text)
    return m.group(1) if m else None


def extract_device(text):
    if pd.isna(text):
        return None
    m = re.search(DEVICE_REGEX, text)
    return m.group(1) if m else None


def extract_datetime(text):
    if pd.isna(text):
        return None
    m = re.search(DT_REGEX, text)
    return m.group(0) if m else None


def extract_result(msg):
    if pd.isna(msg):
        return "-"
    msg_lower = msg.lower()
    if "success" in msg_lower:
        return "Process completed successfully"
    elif "error" in msg_lower or "fail" in msg_lower:
        return "Error"
    return "-"


# =========================
# PROCESS LOG
# =========================
def process_log(df, log_type, service):
    df["RequestID"] = df["@message"].apply(extract_request_id)
    df["DeviceID"] = df["@message"].apply(extract_device)
    df["Datetime"] = df["@message"].apply(extract_datetime)
    df["Service"] = service

    df = df[["RequestID", "DeviceID", "Datetime", "@message", "Service"]]
    df = df.rename(columns={"@message": log_type})

    return df


# =========================
# UI
# =========================
uploaded_files = st.file_uploader(
    "📥 Upload 8 CSV files",
    type=["csv"],
    accept_multiple_files=True
)

if uploaded_files:

    req_list = []
    res_list = []

    for file in uploaded_files:
        name = file.name.lower()
        df = pd.read_csv(file)

        # detect service
        if "dten" in name and "tcap" not in name:
            service = "DTEN"
        elif "tcap" in name:
            service = "TCAP"
        elif "provisioningrequester" in name:
            service = "ProvisioningRequester"
        elif "provisioningresponder" in name:
            service = "ProvisioningResponder"
        else:
            service = "Unknown"

        if "request" in name:
            req_list.append(process_log(df, "Request", service))
        elif "response" in name:
            res_list.append(process_log(df, "Response", service))

    df_req = pd.concat(req_list, ignore_index=True)
    df_res = pd.concat(res_list, ignore_index=True)

    # =========================
    # MERGE REQUEST + RESPONSE
    # =========================
    df_all = pd.merge(
        df_req,
        df_res,
        on=["RequestID", "Service"],
        how="outer",
        suffixes=("_req", "_res")
    )

    df_all["Message"] = df_all["Request"].combine_first(df_all["Response"])
    df_all["Result"] = df_all["Message"].apply(extract_result)
    df_all["HasLog"] = "Yes"

    # =========================
    # PIVOT YES/NO
    # =========================
    df_flag = df_all.pivot_table(
        index=["RequestID", "DeviceID"],
        columns="Service",
        values="HasLog",
        aggfunc="first"
    ).fillna("No").reset_index()

    # =========================
    # PIVOT RESULT
    # =========================
    df_result = df_all.pivot_table(
        index=["RequestID", "DeviceID"],
        columns="Service",
        values="Result",
        aggfunc="first"
    ).reset_index()

    # =========================
    # MERGE
    # =========================
    df_final = pd.merge(df_flag, df_result, on=["RequestID", "DeviceID"], how="left")

    # =========================
    # RENAME COLUMN (ตามรูป)
    # =========================
    df_final = df_final.rename(columns={
        "RequestID": "Request ID",
        "DeviceID": "deviceId",

        "DTEN_x": "DTENLinkage sent to TCAP",
        "TCAP_x": "DTENTCAPLinkage sent to AIS",
        "ProvisioningRequester_x": "ProvisioningRequester sent to AIS",
        "ProvisioningResponder_x": "ProvisioningResponder received from AIS",

        "DTEN_y": "DTENLinkage Result",
        "TCAP_y": "DTENTCAPLinkage Result",
        "ProvisioningRequester_y": "ProvisioningRequester Result",
        "ProvisioningResponder_y": "ProvisioningResponder Result",
    })

    # =========================
    # ADD FIXED COLUMN
    # =========================
    df_final.insert(0, "No.", range(1, len(df_final)+1))
    df_final["ProStatus"] = "PROD"
    df_final["Carrier"] = "TRUE"

    # =========================
    # FILL NULL
    # =========================
    df_final = df_final.fillna("-")

    # =========================
    # ORDER COLUMN
    # =========================
    df_final = df_final[[
        "No.",
        "Request ID",
        "deviceId",
        "ProStatus",
        "Carrier",
        "DTENLinkage Result",
        "DTENLinkage sent to TCAP",
        "DTENTCAPLinkage Result",
        "DTENTCAPLinkage sent to AIS",
        "ProvisioningRequester Result",
        "ProvisioningRequester sent to AIS",
        "ProvisioningResponder Result",
        "ProvisioningResponder received from AIS"
    ]]

    st.success("✅ ได้ Report แบบเดียวกับ History แล้ว")

    st.dataframe(df_final, use_container_width=True)

    # =========================
    # EXPORT EXCEL
    # =========================
    output_file = "device_history.xlsx"

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        df_final.to_excel(writer, sheet_name="deviceId List", index=False)

        workbook = writer.book
        worksheet = writer.sheets["deviceId List"]

        worksheet.set_column("A:A", 6)
        worksheet.set_column("B:B", 40)
        worksheet.set_column("C:C", 20)
        worksheet.set_column("D:E", 12)
        worksheet.set_column("F:M", 30)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter("A1:M1")

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#FFF2CC",
            "border": 1
        })

        for col_num, value in enumerate(df_final.columns.values):
            worksheet.write(0, col_num, value, header_format)

    with open(output_file, "rb") as f:
        st.download_button(
            "📥 Download Excel",
            f,
            file_name=output_file
        )
