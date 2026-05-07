import streamlit as st
from utils.api_client import update_summary, get_summary, check_service_health

st.set_page_config(
    page_title = "Update Summary — Doc Assistant",
    page_icon  = "🔄",
    layout     = "wide",
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 🔄 Update Patient Summary")
st.markdown(
    "When a patient returns with a new clinical event, "
    "enter their Person ID and the new Event ID to update their summary."
)
st.markdown("---")

# ── Service check ──────────────────────────────────────────────────────────────
if not check_service_health():
    st.error("⚠️ FastAPI service is not running. Start it first: `uvicorn app.main:app --reload --port 8000`")
    st.stop()

# ── Info ───────────────────────────────────────────────────────────────────────
st.info(
    "**What happens:** The service checks if the event is already processed. "
    "If it is new, it fetches all events for this patient, places the new event at the top "
    "(most recent), and fully regenerates the summary using Gemini Flash 2.5."
)

st.markdown("---")

# ── Input form ─────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    person_id = st.text_input(
        "Person ID",
        placeholder = "e.g. P123",
        help        = "The patient's unique identifier",
    )

with col2:
    event_id = st.text_input(
        "New Event ID",
        placeholder = "e.g. E999",
        help        = "The new clinical event to incorporate into the summary",
    )

st.markdown("")

col_btn, _ = st.columns([1, 3])
with col_btn:
    update_clicked = st.button(
        "🔄 Update Summary",
        type                = "primary",
        use_container_width = True,
        disabled            = not (person_id.strip() and event_id.strip()),
    )

st.markdown("---")

# ── Handle update ──────────────────────────────────────────────────────────────
if update_clicked:
    if not person_id.strip() or not event_id.strip():
        st.warning("Please enter both Person ID and Event ID.")
        st.stop()

    with st.spinner(
        f"Updating summary for `{person_id.strip()}` with event `{event_id.strip()}`..."
    ):
        result = update_summary(person_id.strip(), event_id.strip())

    if not result["success"]:
        st.error(f"❌ Error: {result['error']}")
        st.stop()

    data   = result["data"]
    status = data.get("status", "")

    # ── Status banners ─────────────────────────────────────────────────────────
    if status == "updated":
        st.success(
            f"✅ Summary updated! "
            f"New event `{event_id.strip()}` added at the top. "
            f"Total events: **{data.get('event_count', 0)}**"
        )

    elif status == "created":
        st.success(
            f"✅ No existing summary found — created a fresh one for `{person_id.strip()}`. "
            f"Total events: **{data.get('event_count', 0)}**"
        )

    elif status == "already_processed":
        st.warning(
            f"⚠️ Event `{event_id.strip()}` was already included in this patient's summary. "
            "No update needed."
        )

    elif status == "failed":
        st.error(f"❌ Failed: {data.get('message', 'Unknown error.')}")
        st.stop()

    st.markdown("---")

    # ── Display updated summary ────────────────────────────────────────────────
    st.markdown(f"### Updated Summary — Patient `{data.get('person_id', '')}`")

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events",  data.get("event_count", 0))
    c2.metric("Model Used",    data.get("model_id", "N/A"))
    c3.metric("Created At",    str(data.get("generated_at", "N/A"))[:10])
    c4.metric("Last Updated",  str(data.get("last_updated_at", "N/A"))[:10])

    st.markdown("---")

    # Main subject
    st.markdown("#### 🩺 Main Subject")
    st.markdown(
        f"""
        <div style="background:#EAF3DE;border-radius:10px;padding:16px 20px;
                    border:1px solid #C0DD97;margin-bottom:20px;">
            {data.get("main_subject", "Not available.")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Summary chain
    st.markdown("#### 📝 Updated Summary Chain  *(newest → oldest)*")

    raw_chain = data.get("summary_chain", "")
    if raw_chain:
        blocks = raw_chain.strip().split("\n\n")
        for block in blocks:
            if not block.strip():
                continue

            lines   = block.strip().split("\n", 1)
            label   = lines[0].strip() if lines else ""
            content = lines[1].strip() if len(lines) > 1 else ""

            if "Most Recent" in label:
                border_color = "#2E6B10"
                bg_color     = "#EAF3DE"
                badge        = "🟢 Most Recent"
                # Highlight the newly added event
                is_new = event_id.strip() in label
                if is_new:
                    badge += " ✨ Newly Added"
            elif "Oldest" in label:
                border_color = "#854F0B"
                bg_color     = "#FAEEDA"
                badge        = "🟠 Oldest"
                is_new       = False
            else:
                border_color = "#378ADD"
                bg_color     = "#E6F1FB"
                badge        = ""
                is_new       = False

            event_label = label.replace("[", "").replace("]", "")

            st.markdown(
                f"""
                <div style="background:{bg_color};
                            border-left:4px solid {border_color};
                            border-radius:0 8px 8px 0;
                            padding:14px 16px;margin-bottom:12px;
                            {'box-shadow: 0 0 0 2px #2E6B10;' if is_new else ''}">
                    <div style="font-size:12px;font-weight:600;
                                color:{border_color};margin-bottom:6px;">
                        {event_label} {badge}
                    </div>
                    <div style="font-size:14px;color:#333;line-height:1.6;">
                        {content}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No summary chain available.")

    # Processed event IDs
    st.markdown("---")
    with st.expander("📌 All Processed Event IDs"):
        event_ids = data.get("processed_event_ids", [])
        if event_ids:
            cols = st.columns(min(len(event_ids), 6))
            for i, eid in enumerate(event_ids):
                color = "#2E6B10" if eid == event_id.strip() else "#185FA5"
                bg    = "#EAF3DE" if eid == event_id.strip() else "#E6F1FB"
                cols[i % 6].markdown(
                    f'<span style="background:{bg};color:{color};padding:3px 10px;'
                    f'border-radius:10px;font-size:12px;font-weight:500;">{eid}</span>',
                    unsafe_allow_html=True,
                )
