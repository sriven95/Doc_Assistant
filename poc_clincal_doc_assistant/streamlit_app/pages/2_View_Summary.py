import streamlit as st
import pandas as pd
import os
from utils.api_client import get_summary, check_service_health

st.set_page_config(
    page_title = "View Summary — Doc Assistant",
    page_icon  = "🔍",
    layout     = "wide",
)


def load_patient_ids() -> list:
    candidates = [
        os.path.normpath(os.path.join(os.getcwd(), "data", "output", "output.xlsx")),
        os.path.normpath(os.path.join(os.getcwd(), "..", "doc_assistant_summary", "data", "output", "output.xlsx")),
        os.path.normpath(os.path.join(os.getcwd(), "doc_assistant_summary", "data", "output", "output.xlsx")),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path:
        return []
    try:
        df = pd.read_excel(path, engine="openpyxl")
        if "person_id" in df.columns:
            return sorted(df["person_id"].dropna().astype(str).str.strip().unique().tolist())
    except Exception:
        pass
    return []


st.markdown("## 🔍 View Patient Summary")
st.markdown("Select a patient from the dropdown to view their full clinical summary.")
st.markdown("---")

if not check_service_health():
    st.error("⚠️ FastAPI service is not running. Start it first: `uvicorn app.main:app --reload --port 8000`")
    st.stop()

patient_ids = load_patient_ids()

if not patient_ids:
    st.warning("⚠️ No patients found yet. Please run **📋 Bulk Generate** first.")
    st.stop()

col1, col2 = st.columns([3, 1])
with col1:
    person_id = st.selectbox(
        "Select Patient",
        options=patient_ids,
        index=0,
        label_visibility="collapsed",
        help=f"{len(patient_ids)} patients available",
    )
with col2:
    st.button("🔍 View Summary", type="primary", use_container_width=True)

st.caption(f"📋 {len(patient_ids)} patients available in output file")
st.markdown("---")

if person_id:
    with st.spinner(f"Fetching summary for `{person_id}`..."):
        result = get_summary(person_id)

    if not result["success"]:
        st.error(f"❌ Error: {result['error']}")
        st.stop()

    data   = result["data"]
    status = data.get("status", "")

    if status == "not_found":
        st.warning(f"⚠️ No summary found for `{person_id}`. Run Bulk Generate first.")
        st.stop()

    st.markdown(f"### Patient: `{data.get('person_id', '')}`")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", data.get("event_count", 0))
    c2.metric("Model Used",   data.get("model_id", "N/A"))
    c3.metric("Generated At", str(data.get("generated_at", "N/A"))[:10])
    c4.metric("Last Updated", str(data.get("last_updated_at", "N/A"))[:10])

    st.markdown("---")

    st.markdown("#### 🩺 Main Subject")
    st.markdown(
        f'<div style="background:#EAF3DE;border-radius:10px;padding:16px 20px;'
        f'border:1px solid #C0DD97;margin-bottom:20px;">'
        f'{data.get("main_subject", "Not available.")}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("#### 📝 Summary Chain  *(newest → oldest)*")
    raw_chain = data.get("summary_chain", "")

    if raw_chain:
        for block in raw_chain.strip().split("\n\n"):
            if not block.strip():
                continue
            lines   = block.strip().split("\n", 1)
            label   = lines[0].strip() if lines else ""
            content = lines[1].strip() if len(lines) > 1 else ""

            if "Most Recent" in label:
                bc, bg, badge = "#2E6B10", "#EAF3DE", "🟢 Most Recent"
            elif "Oldest" in label:
                bc, bg, badge = "#854F0B", "#FAEEDA", "🟠 Oldest"
            else:
                bc, bg, badge = "#378ADD", "#E6F1FB", ""

            event_label = label.replace("[", "").replace("]", "")
            st.markdown(
                f'<div style="background:{bg};border-left:4px solid {bc};'
                f'border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:12px;">'
                f'<div style="font-size:12px;font-weight:600;color:{bc};margin-bottom:6px;">'
                f'{event_label} {badge}</div>'
                f'<div style="font-size:14px;color:#333;line-height:1.6;">{content}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No summary chain available.")

    st.markdown("---")
    with st.expander("📌 Processed Event IDs"):
        event_ids = data.get("processed_event_ids", [])
        if event_ids:
            cols = st.columns(min(len(event_ids), 6))
            for i, eid in enumerate(event_ids):
                cols[i % 6].markdown(
                    f'<span style="background:#E6F1FB;color:#185FA5;padding:3px 10px;'
                    f'border-radius:10px;font-size:12px;font-weight:500;">{eid}</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.write("No event IDs recorded.")
