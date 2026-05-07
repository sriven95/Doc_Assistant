import streamlit as st
import time
from utils.api_client import generate_summaries, get_job_status, check_service_health

st.set_page_config(
    page_title = "Bulk Generate — Doc Assistant",
    page_icon  = "📋",
    layout     = "wide",
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 📋 Bulk Summary Generation")
st.markdown("Process all patients in the input Excel file and generate summaries in one go.")
st.markdown("---")

# ── Service check ──────────────────────────────────────────────────────────────
if not check_service_health():
    st.error("⚠️ FastAPI service is not running. Start it first: `uvicorn app.main:app --reload --port 8000`")
    st.stop()

# ── Info box ───────────────────────────────────────────────────────────────────
st.info(
    "**What this does:** Reads every row from your input Excel, "
    "groups them by patient (person_id), and generates a summary chain "
    "(newest event → oldest event) for each patient using Gemini Flash 2.5. "
    "Results are saved to the output Excel automatically."
)

st.markdown("---")

# ── File path override ─────────────────────────────────────────────────────────
with st.expander("⚙️ Advanced — override input file path (optional)"):
    custom_path = st.text_input(
        "Input file path",
        placeholder="Leave blank to use default: data/input/input.xlsx",
        help="Only change this if your file is in a different location.",
    )

st.markdown("---")

# ── Generate button ────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 3])
with col1:
    start_clicked = st.button(
        "🚀 Generate All Summaries",
        type    = "primary",
        use_container_width = True,
    )

if start_clicked:
    file_path = custom_path.strip() if custom_path.strip() else None

    with st.spinner("Starting bulk generation job..."):
        result = generate_summaries(file_path)

    if not result["success"]:
        st.error(f"❌ Failed to start: {result['error']}")
        st.stop()

    job_data = result["data"]
    job_id   = job_data.get("job_id")

    st.success(f"✅ Job started! Job ID: `{job_id}`")
    st.markdown("---")

    # ── Live progress polling ──────────────────────────────────────────────────
    st.markdown("#### Progress")

    progress_bar    = st.progress(0)
    status_text     = st.empty()
    metrics_row     = st.empty()
    completed_flag  = False

    for _ in range(300):   # poll for up to 5 minutes (300 x 1s)
        time.sleep(1)
        poll = get_job_status(job_id)

        if not poll["success"]:
            st.warning(f"Could not poll status: {poll['error']}")
            break

        data      = poll["data"]
        status    = data.get("status", "unknown")
        total     = data.get("total_patients", 0)
        processed = data.get("processed", 0)
        failed    = data.get("failed", 0)
        message   = data.get("message", "")

        # Update progress bar
        if total > 0:
            pct = int((processed / total) * 100)
            progress_bar.progress(min(pct, 100))
        else:
            progress_bar.progress(0)

        # Update status text
        status_text.markdown(
            f"**Status:** `{status.upper()}` — "
            f"**Processed:** {processed} / {total} patients — "
            f"**Failed:** {failed}"
        )

        # Show metrics
        with metrics_row.container():
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Status",    status.capitalize())
            m2.metric("Total",     total)
            m3.metric("Processed", processed)
            m4.metric("Failed",    failed)

        if status == "completed":
            progress_bar.progress(100)
            st.markdown("---")
            st.success(f"🎉 Done! {message}")
            if failed > 0:
                st.warning(f"⚠️ {failed} patients failed. Check logs for details.")
            completed_flag = True
            break

        elif status == "failed":
            st.error(f"❌ Job failed: {message}")
            break

    if not completed_flag and status not in ["completed", "failed"]:
        st.warning("⏱️ Job is still running. Check status manually with the job ID above.")

    # ── Save job ID in session state for reference ─────────────────────────────
    st.session_state["last_job_id"] = job_id

# ── Show last job ID if available ─────────────────────────────────────────────
if "last_job_id" in st.session_state and not start_clicked:
    st.markdown("---")
    st.caption(f"Last job ID: `{st.session_state['last_job_id']}`")
