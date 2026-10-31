"""Authenticated Streamlit interface for the AI Student Support Agent."""
import json, re
import streamlit as st
from agent import answer, DB_PATH, TRACE_PATH
from security import (init_security, authenticate_student, authenticate_admin,
                      pending_approvals, review_approval, audit_rows, audit)

st.set_page_config(page_title="AI Student Support Agent", page_icon="🎓", layout="wide")
st.title("AI Student Support Agent")
st.caption("Secure student support • Fees • Scholarships • Exams • Timetables • Academic calendar")
if not DB_PATH.exists():
    st.error("college.db is missing. Run `python setup_db.py` first.")
    st.stop()
init_security()

if "identity" not in st.session_state:
    st.session_state.identity = None
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.session_state.identity is None:
    st.subheader("Sign in")
    mode = st.radio("Account type", ["Student", "Administrator"], horizontal=True)
    with st.form("login_form"):
        if mode == "Student":
            sid = st.text_input("Student ID", placeholder="e.g. S1004").strip().upper()
            password = st.text_input("Password", type="password")
        else:
            sid = "ADMIN"
            password = st.text_input("Administrator password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        valid = authenticate_student(sid, password) if mode == "Student" else authenticate_admin(password)
        if valid:
            st.session_state.identity = {"id":sid,"role":mode.lower()}
            st.session_state.messages = []
            st.rerun()
        else:
            st.error("Sign-in failed. Check the credentials and try again.")
    with st.expander("Demo credentials (classroom use only)"):
        st.markdown("- Student: `S1004` / `Demo@S1004` (Mahi sample record)\n- Other students: use `Demo@` followed by their ID, e.g. `Demo@S1001`.\n- Administrator: `AdminDemo!2026` (change via `ADMIN_DEMO_PASSWORD` before demonstration).")
    st.warning("These are demonstration credentials, not institutional authentication. Use SSO/MFA and centrally managed identity before production.")
    st.stop()

identity = st.session_state.identity
actor_id, role = identity["id"], identity["role"]
with st.sidebar:
    st.success(f"Signed in: {actor_id} ({role.title()})")
    if st.button("Sign out", use_container_width=True):
        st.session_state.identity = None
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.subheader("Try a question")
    samples = [
        "What is my current fee status?",
        "What is my scholarship status?",
        "Show Semester I exams.",
        "Show my Semester II timetable for Monday.",
        "What academic events are listed in November 2026?",
    ]
    if role == "student":
        samples += ["I request a fee due-date change to 2026-12-15 because of a payment issue.",
                    "Show fee status for S1001."]
    for q in samples:
        if st.button(q, use_container_width=True):
            st.session_state.pending_prompt = q

if role == "admin":
    st.subheader("Human approval queue")
    requests = pending_approvals()
    if not requests:
        st.info("No pending approval requests.")
    for req in requests:
        with st.container(border=True):
            st.markdown(f"**Request #{req['request_id']}** · {req['student_id']} · {req['action_type']}")
            st.write(f"Requested value: `{req['requested_value']}`")
            st.write(f"Reason: {req['reason']}")
            confirm = st.checkbox(f"I have reviewed request #{req['request_id']}", key=f"confirm_{req['request_id']}")
            left, right = st.columns(2)
            if left.button("Approve and execute", key=f"approve_{req['request_id']}", disabled=not confirm):
                result = review_approval(req["request_id"], actor_id, "Approved")
                st.success(result["message"] if result["ok"] else result["message"])
                st.rerun()
            if right.button("Reject (do not execute)", key=f"reject_{req['request_id']}", disabled=not confirm):
                result = review_approval(req["request_id"], actor_id, "Rejected")
                st.warning(result["message"])
                st.rerun()
    st.subheader("Audit evidence")
    st.dataframe(audit_rows(100), use_container_width=True, hide_index=True)
    st.stop()

st.info("Your signed-in identity is used by the application layer. Private-record tools enforce that the target student ID must match your account.")
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("trace"):
            with st.expander("Execution trace"):
                st.json(m["trace"])

prompt = st.chat_input("Ask the student support agent...")
if st.session_state.get("pending_prompt"):
    prompt = st.session_state.pop("pending_prompt")
if prompt:
    # Avoid keeping credentials in the chat transcript or sending them to the model.
    if re.search(r"\b(otp|one.time.password|password|passcode|pin)\b", prompt, re.I):
        safe_prompt = "[Sensitive credential-like message redacted from chat history and memory.]"
        st.session_state.messages.append({"role":"user","content":safe_prompt})
        reply = "Please do not share passwords, OTPs or PINs in chat. This message was not saved to profile memory or the trace log. If you need account help, use the institution's secure authentication channel."
        trace = {"status":"sensitive_input_blocked","tools_used":[],"latency_seconds":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"retrieved_evidence":[]}
        audit(actor_id,"student","credential_input_blocked",None,False,"NotRequired","Credential-like content blocked; content not retained")
    else:
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("Checking your request and relevant records..."):
            reply, trace = answer(prompt, actor_id, st.session_state.messages[:-1])
    with st.chat_message("assistant"):
        st.markdown(reply)
        with st.expander("Execution trace — no raw query text is stored"):
            st.json(trace)
    st.session_state.messages.append({"role":"assistant","content":reply,"trace":trace})

st.divider()
st.subheader("Latest run measurements")
if TRACE_PATH.exists():
    lines = TRACE_PATH.read_text(encoding="utf-8").splitlines()
    if lines:
        try:
            latest=json.loads(lines[-1]); cols=st.columns(4)
            cols[0].metric("Latency",f"{latest.get('latency_seconds',0)} s")
            cols[1].metric("Tool calls",len(latest.get("tools_used",[])))
            cols[2].metric("Tokens",latest.get("total_tokens",0))
            cols[3].metric("Retrieved sections",len(latest.get("retrieved_evidence",[])))
        except Exception: st.info("Trace file exists but latest record could not be read.")
else:
    st.info("No query trace has been recorded yet.")
