import streamlit as st
import pandas as pd
import os
from utils.api_client import (
    chat_start,
    chat_ask,
    chat_clear_session,
    check_ai_service_health,
)

st.set_page_config(
    page_title = "Doc Assistant Chat",
    page_icon  = "💬",
    layout     = "wide",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .user-bubble {
        background: #E6F1FB;
        border-radius: 12px 12px 2px 12px;
        padding: 12px 16px;
        margin: 6px 0 6px 60px;
        font-size: 14px;
        color: #0C447C;
        border: 1px solid #B5D4F4;
    }
    .assistant-bubble {
        background: #f8f9fa;
        border-radius: 12px 12px 12px 2px;
        padding: 12px 16px;
        margin: 6px 60px 6px 0;
        font-size: 14px;
        color: #1a1a1a;
        border: 1px solid #e5e5e5;
        border-left: 4px solid #2E6B10;
    }
    .source-chip {
        display: inline-block;
        background: #EEEDFE;
        color: #3C3489;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        margin: 2px;
        font-weight: 500;
    }
    .session-bar {
        background: #EAF3DE;
        border: 1px solid #C0DD97;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 12px;
        color: #3B6D11;
        margin-bottom: 12px;
    }
    .summary-box {
    background: #EAF3DE;
    border-radius: 10px;
    padding: 14px 18px;
    border: 1px solid #C0DD97;
    font-size: 13px;
    color: #333;
    line-height: 1.65;
    white-space: pre-wrap;      /* ← preserves line breaks */
    word-wrap: break-word;      /* ← prevents overflow */
    overflow: visible;          /* ← shows full content */
    max-height: none;           /* ← removes any height limit */
    display: block;             /* ← ensures full block display */
}
</style>
""", unsafe_allow_html=True)


# ── Helper — load patient IDs from output Excel ────────────────────────────────
def load_patient_ids() -> list:
    candidates = [
        os.path.normpath(os.path.join(os.getcwd(), "data", "output", "output.xlsx")),
        os.path.normpath(os.path.join(os.getcwd(), "..", "doc_assistant_qa", "data", "output", "output.xlsx")),
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


# ── Init session state ─────────────────────────────────────────────────────────
if "chat_person_id"    not in st.session_state:
    st.session_state.chat_person_id    = None
if "chat_validated"    not in st.session_state:
    st.session_state.chat_validated    = False
if "chat_summary"      not in st.session_state:
    st.session_state.chat_summary      = None
if "chat_messages"     not in st.session_state:
    st.session_state.chat_messages     = []
if "chat_session_ttl"  not in st.session_state:
    st.session_state.chat_session_ttl  = 0
if "chat_input_mode"   not in st.session_state:
    st.session_state.chat_input_mode   = "dropdown"


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 💬 Doc Assistant — Patient Q&A")
st.markdown("Select or type a patient ID, validate to load their summary, then ask questions.")
st.markdown("---")

# ── Service health check ───────────────────────────────────────────────────────
if not check_ai_service_health():
    st.error(
        "⚠️ AI Layer service is not running. "
        "Start it first: `uvicorn app.main:app --reload --port 8002`"
    )
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Patient Selection & Validation
# Only shown until patient is validated
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.chat_validated:

    patient_ids = load_patient_ids()

    # Toggle — dropdown or type manually
    mode_col1, mode_col2 = st.columns([1, 3])
    with mode_col1:
        input_mode = st.radio(
            "Input mode",
            options = ["Select from list", "Type manually"],
            index   = 0,
            label_visibility = "collapsed",
            horizontal = True,
        )

    st.markdown("")

    # ── Input ─────────────────────────────────────────────────────────────────
    if input_mode == "Select from list":
        if not patient_ids:
            st.warning("⚠️ No patients found in output file. Run Bulk Generate first.")
            st.stop()

        col1, col2 = st.columns([3, 1])
        with col1:
            selected_id = st.selectbox(
                "Select Patient ID",
                options          = patient_ids,
                index            = 0,
                label_visibility = "collapsed",
                help             = f"{len(patient_ids)} patients available",
            )
        with col2:
            validate_clicked = st.button(
                "✅ Validate & Load",
                type                = "primary",
                use_container_width = True,
            )
        st.caption(f"📋 {len(patient_ids)} patients available")
        person_id_to_validate = selected_id

    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            typed_id = st.text_input(
                "Type Patient ID",
                placeholder      = "e.g. P0001",
                label_visibility = "collapsed",
            )
        with col2:
            validate_clicked = st.button(
                "✅ Validate & Load",
                type                = "primary",
                use_container_width = True,
                disabled            = not typed_id.strip(),
            )
        person_id_to_validate = typed_id.strip()

    # ── Validation ────────────────────────────────────────────────────────────
    if validate_clicked and person_id_to_validate:
        with st.spinner(f"Validating and loading summary for `{person_id_to_validate}`..."):
            result = chat_start(person_id_to_validate)

        if not result["success"]:
            st.error(f"❌ {result['error']}")
            st.stop()

        data   = result["data"]
        status = data.get("status", "")

        if status == "no_summary":
            st.error(
                f"❌ No summary found for `{person_id_to_validate}`. "
                "Please run the Summary Generation service first."
            )
            st.stop()

        # Store validated state
        st.session_state.chat_person_id   = person_id_to_validate
        st.session_state.chat_validated   = True
        st.session_state.chat_summary     = data.get("summary", {})
        st.session_state.chat_session_ttl = data.get("session_ttl_sec", 900)
        st.session_state.chat_messages    = []

        st.success(f"✅ Patient `{person_id_to_validate}` loaded. You can now ask questions below.")
        st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Chat Interface (only shown after validation)
# ══════════════════════════════════════════════════════════════════════════════

person_id = st.session_state.chat_person_id
summary   = st.session_state.chat_summary or {}

# ── Patient header + session info ──────────────────────────────────────────────
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown(f"### Patient: `{person_id}`")
with header_col2:
    if st.button("🔄 Change Patient", use_container_width=True):
        # Clear session and go back to selection
        chat_clear_session(person_id)
        st.session_state.chat_person_id  = None
        st.session_state.chat_validated  = False
        st.session_state.chat_summary    = None
        st.session_state.chat_messages   = []
        st.rerun()

ttl_min = st.session_state.chat_session_ttl // 60
st.markdown(
    f'<div class="session-bar">'
    f'🟢 Session active — 15 min window | '
    f'Messages: {len(st.session_state.chat_messages)} | '
    f'Patient: {person_id}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Summary display (collapsible) ──────────────────────────────────────────────
with st.expander("🩺 Patient Summary — click to expand", expanded=True):
    main_subject = summary.get("main_subject", "")
    if main_subject:
        st.markdown("**🩺 Overall Patient Picture**")
        st.markdown(
            f'<div class="summary-box">{main_subject}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    raw_chain = summary.get("summary_chain", "")
    if raw_chain:
        st.markdown("**Summary Chain *(newest → oldest)***")
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
                f'border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px;">'
                f'<div style="font-size:11px;font-weight:600;color:{bc};margin-bottom:4px;">'
                f'{event_label} {badge}</div>'
                f'<div style="font-size:13px;color:#333;line-height:1.5;">{content}</div></div>',
                unsafe_allow_html=True,
            )

st.markdown("---")

# ── Conversation history ───────────────────────────────────────────────────────
st.markdown("#### 💬 Conversation")

if not st.session_state.chat_messages:
    st.markdown(
        '<div style="text-align:center;padding:24px;color:#aaa;font-size:13px;">'
        'No messages yet. Ask your first question below.</div>',
        unsafe_allow_html=True,
    )
else:
    for msg in st.session_state.chat_messages:
        role    = msg.get("role", "user")
        content = msg.get("content", "")
        sources = msg.get("sources", [])

        if role == "user":
            st.markdown(
                f'<div class="user-bubble">👤 {content}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="assistant-bubble">🤖 {content}</div>',
                unsafe_allow_html=True,
            )
            # Show source citations if available
            if sources:
                chips = "".join([
                    f'<span class="source-chip">📄 {s.get("event_id","?")} — {s.get("doc_type","?")}</span>'
                    for s in sources
                ])
                st.markdown(
                    f'<div style="margin:-4px 60px 8px 0;">{chips}</div>',
                    unsafe_allow_html=True,
                )

# ── Suggested questions ────────────────────────────────────────────────────────
# if not st.session_state.chat_messages:
#     st.markdown("**Quick questions to start:**")
#     q_cols = st.columns(3)
#     suggestions = [
#         "What SDOH risks does this patient have?",
#         "Who is the emergency contact?",
#         "Has this patient had home health before?",
#         "What is the discharge plan?",
#         "Are there any financial or insurance concerns?",
#         "What is the patient's housing situation?",
#     ]
#     for i, suggestion in enumerate(suggestions):
#         if q_cols[i % 3].button(suggestion, key=f"sug_{i}", use_container_width=True):
#             # Directly trigger API call — no form needed
#             st.session_state.chat_messages.append({
#                 "role"   : "user",
#                 "content": suggestion,
#             })
#             with st.spinner("Thinking..."):
#                 result = chat_ask(person_id, suggestion)
#             if not result["success"]:
#                 st.session_state.chat_messages.append({
#                     "role"   : "assistant",
#                     "content": f"⚠️ Error: {result['error']}",
#                     "sources": [],
#                 })
#             else:
#                 data = result["data"]
#                 st.session_state.chat_messages.append({
#                     "role"   : "assistant",
#                     "content": data.get("answer", "No answer returned."),
#                     "sources": data.get("sources", []),
#                 })
#                 st.session_state.chat_session_ttl = data.get("session_ttl_sec", 0)

# st.markdown("")

# ── Question input ─────────────────────────────────────────────────────────────
with st.form(key="chat_form", clear_on_submit=True):
    q_col1, q_col2 = st.columns([5, 1])
    with q_col1:
        user_question = st.text_input(
            "Ask a question",
            placeholder      = "e.g. What SDOH risks does this patient have?",
            label_visibility = "collapsed",
            value            = st.session_state.pop("pending_question", ""),
        )
    with q_col2:
        ask_submitted = st.form_submit_button(
            "Send ➤",
            type                = "primary",
            use_container_width = True,
        )

# ── Handle question submission ─────────────────────────────────────────────────
if ask_submitted and user_question.strip():
    question = user_question.strip()

    # Add user message immediately
    st.session_state.chat_messages.append({
        "role"   : "user",
        "content": question,
    })

    with st.spinner("Thinking..."):
        result = chat_ask(person_id, question)

    if not result["success"]:
        st.session_state.chat_messages.append({
            "role"   : "assistant",
            "content": f"⚠️ Error: {result['error']}",
            "sources": [],
        })
    else:
        data    = result["data"]
        answer  = data.get("answer", "No answer returned.")
        sources = data.get("sources", [])
        ttl     = data.get("session_ttl_sec", 0)

        st.session_state.chat_messages.append({
            "role"   : "assistant",
            "content": answer,
            "sources": sources,
        })
        st.session_state.chat_session_ttl = ttl

    st.rerun()

# ── Clear conversation button ──────────────────────────────────────────────────
if st.session_state.chat_messages:
    st.markdown("")
    if st.button("🗑️ Clear Conversation", use_container_width=False):
        chat_clear_session(person_id)
        result = chat_start(person_id)
        if result["success"]:
            st.session_state.chat_summary    = result["data"].get("summary", {})
            st.session_state.chat_session_ttl = result["data"].get("session_ttl_sec", 900)
        st.session_state.chat_messages = []
        st.rerun()
