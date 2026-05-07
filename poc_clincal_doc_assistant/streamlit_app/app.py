import streamlit as st
from utils.api_client import check_service_health, check_ai_service_health

st.set_page_config(
    page_title            = "Doc Assistant — Summary Service",
    page_icon             = "🏥",
    layout                = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown("""
<style>
    .main-title       { font-size:28px; font-weight:600; color:#1a1a2e; margin-bottom:4px; }
    .main-subtitle    { font-size:15px; color:#666; margin-bottom:24px; }
    .status-pill      { display:inline-block; padding:4px 14px; border-radius:20px; font-size:13px; font-weight:500; }
    .pill-green       { background:#EAF3DE; color:#3B6D11; }
    .pill-red         { background:#FCEBEB; color:#A32D2D; }
    .metric-card      { background:#f8f9fa; border-radius:10px; padding:16px; border:1px solid #e5e5e5; text-align:center; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Doc Assistant")
    st.markdown("**Clinical Documentation Platform**")
    st.markdown("---")

    st.markdown("#### Service Status")

    # Summary service (port 8000)
    summary_healthy = check_service_health()
    if summary_healthy:
        st.markdown('<span class="status-pill pill-green">● Summary Service (8000)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill pill-red">● Summary Service (8000)</span>', unsafe_allow_html=True)
        st.caption("Start: `uvicorn app.main:app --port 8000`")

    st.markdown("")

    # AI Layer service (port 8002)
    ai_healthy = check_ai_service_health()
    if ai_healthy:
        st.markdown('<span class="status-pill pill-green">● AI Layer Service (8002)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill pill-red">● AI Layer Service (8002)</span>', unsafe_allow_html=True)
        st.caption("Start: `uvicorn app.main:app --port 8002`")

    st.markdown("---")
    st.markdown("#### Navigation")
    st.markdown("- 📋 **Bulk Generate** — Process all patients")
    st.markdown("- 🔍 **View Summary** — Search a patient")
    st.markdown("- 🔄 **Update Summary** — Add new event")
    st.markdown("- 💬 **Doc Assistant Chat** — Ask questions about a patient")
    st.markdown("---")

# ── Home page ──────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🏥 Doc Assistant — Clinical Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">AI-powered clinical note summarization and patient Q&A using Gemini Flash 2.5</div>', unsafe_allow_html=True)
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="metric-card">
        <div style="font-size:32px">📋</div>
        <div style="font-size:15px;font-weight:500;margin-top:8px">Bulk Generate</div>
        <div style="font-size:12px;color:#666;margin-top:4px">Process all patients from Excel in one go</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <div style="font-size:32px">🔍</div>
        <div style="font-size:15px;font-weight:500;margin-top:8px">View Summary</div>
        <div style="font-size:12px;color:#666;margin-top:4px">Search and view any patient's summary</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <div style="font-size:32px">🔄</div>
        <div style="font-size:15px;font-weight:500;margin-top:8px">Update Summary</div>
        <div style="font-size:12px;color:#666;margin-top:4px">Add a new event when patient returns</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="metric-card">
        <div style="font-size:32px">💬</div>
        <div style="font-size:15px;font-weight:500;margin-top:8px">Doc Assistant Chat</div>
        <div style="font-size:12px;color:#666;margin-top:4px">Ask questions about a patient using AI</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("#### How to use")
st.markdown("""
1. Make sure both **services are running** (check sidebar status)
2. Go to **📋 Bulk Generate** to process your entire Excel file first
3. Once complete, go to **🔍 View Summary** to search any patient
4. When a patient returns with a new event, use **🔄 Update Summary**
5. Use **💬 Doc Assistant Chat** to ask clinical questions about any patient
""")

# Warnings if services are down
if not summary_healthy:
    st.error("⚠️ Summary Service is not running. Start it: `uvicorn app.main:app --reload --port 8000`")
if not ai_healthy:
    st.warning("⚠️ AI Layer Service is not running. Start it: `uvicorn app.main:app --reload --port 8002`")