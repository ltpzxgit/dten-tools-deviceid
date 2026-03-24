import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="DeviceID Report Generator", layout="wide")

st.title("📊 DeviceID Report Generator (Ultimate Stable)")

# =========================
# REGEX (Flexible มากขึ้น)
# =========================
REQ_ID_REGEX = r'(?:Request ID|RequestId|reqId|request-id)[=: ]+([0-9a-fA-F\-]{10,})'
DEVICE_REGEX = r'(?:deviceId|device_id|device-id)[=: ]+"?([A-Za-z0-9\-]+)"?'
DT_REGEX = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'


def extract(pattern, text):
    if pd.isna(text):
        return None
    try:
        m = re.search(pattern, str(text), re.IGNORECASE)
        return m.group(1) if m else None
    except:
        return None


def extract_dt(text):
    if pd.isna(text):
        return None
    try:
        m = re.search(DT_REGEX, str(text))
        return m.group(0) if m else None
    except:
        return None


def extract_result(msg):
    if pd.isna(msg):
        return "-"
    msg = str(msg).lower()
    if "success" in msg:
        return "Process completed successfully"
    elif "error" in msg or "fail" in msg:
        return "Error"
    return "-"


# =========================
# PROCESS LOG
# =========================
def process_log(df, log_type, service):

    # หา message column อัตโนมัติ
    msg_col = None
    for col in df.columns:
        if "message" in col.lower():
            msg_col = col
            break

    if not msg_col:
        st.error(f"❌ ไม่เจอ message column ใน {service}")
        st.write(df.columns)
        st.stop()

    df = df.copy()

    df["RequestID"] = df[msg_col].apply(lambda x: extract(REQ_ID_REGEX, x))
    df["DeviceID"] = df[msg_col].apply(lambda x: extract(DEVICE_REGEX, x))
    df["Datetime"] = df[msg_col].apply(extract_dt)
    df["Service"] = service

    # 🔥 กัน column หาย
    for col in ["RequestID", "DeviceID", "Datetime", "Service"]:
        if col not in df.columns:
            df[col] = None

    df = df[["RequestID", "DeviceID", "Datetime", msg_col, "Service"]]
    df = df.rename(columns={msg_col: log_type})

    return df


# =========================
# UI
# =========================
uploaded_files = st.file_uploader(
    "📥 Upload CSV (8 files)",
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

    if not req_list and not res_list:
        st.error("❌ ไม่มีไฟล์ request/response ที่ถูกต้อง")
        st.stop()

    df_req = pd.concat(req_list, ignore_index=True) if req_list else pd.DataFrame()
    df_res = pd.concat(res_list, ignore_index=True) if res_list else pd.DataFrame()

    # =========================
    # MERGE
    # =========================
    if not df_req.empty and not df_res.empty:
        df_all = pd.merge(
            df_req,
            df_res,
            on=["RequestID", "Service"],
            how="outer"
        )
    else:
        df_all = pd.concat([df_req, df_res], ignore_index=True)

    # =========================
    # SAFETY CHECK
    # =========================
    for col in ["RequestID", "DeviceID", "Service"]:
        if col not in df_all.columns:
            df_all[col] = None

    # combine message
    df_all["Message"] = df_all.get("Request", None).combine_first(df_all.get("Response", None))
    df_all["Result"] = df_all["Message"].apply(extract_result)
    df_all["HasLog"] = "Yes"

    # =========================
    # CLEAN DATA
    # =========================
    df_all = df_all.dropna(subset=["RequestID", "DeviceID"], how="any")

    if df_all.empty:
        st.error("❌ ไม่มีข้อมูลหลัง parse → regex อาจไม่ match")
        st.write("🔍 ตัวอย่างข้อมูล:")
        st.write(df_all.head())
        st.stop()

    st.write("🔍 Debug Preview", df_all.head())

    # =========================
    # PIVOT FLAG
    # =========================
    try:
        df_flag = df_all.pivot_table(
            index=["RequestID", "DeviceID"],
            columns="Service",
            values="HasLog",
            aggfunc="first"
        ).fillna("No").reset_index()
    except Exception as e:
        st.error(f"❌ Pivot flag error: {e}")
        st.stop()

    # =========================
    # PIVOT RESULT
    # =========================
    try:
        df_result = df_all.pivot_table(
            index=["RequestID", "DeviceID"],
            columns="Service",
            values="Result",
            aggfunc="first"
        ).reset_index()
    except Exception as e:
        st.error(f"❌ Pivot result error: {e}")
        st.stop()

    # =========================
    # MERGE
    # =========================
    df_final = pd.merge(df_flag, df_result, on=["RequestID", "DeviceID"], how="left")

    # =========================
    # RENAME
    # =========================
    rename_map = {
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
    }

    df_final = df_final.rename(columns=rename_map)

    # =========================
    # ADD COLUMN
    # =========================
    df_final.insert(0, "No.", range(1, len(df_final)+1))
    df_final["ProStatus"] = "PROD"
    df_final["Carrier"] = "TRUE"

    df_final = df_final.fillna("-")

    st.success("✅ Generate สำเร็จแล้ว")

    st.dataframe(df_final, use_container_width=True)

    # =========================
    # EXPORT
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

    with open(output_file, "rb") as f:
        st.download_button(
            "📥 Download Excel",
            f,
            file_name=output_file
        )
