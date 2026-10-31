"""AI Student Support Agent: tool-using Groq chat loop, SQLite tools, retrieval and tracing."""
from __future__ import annotations
import json, os, re, sqlite3, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from security import (init_security, authorize_student_record, audit, request_due_date_change)

load_dotenv()
BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "college.db"
POLICY_PATH = BASE / "policy_handbook.md"
TRACE_PATH = BASE / "traces.jsonl"
MEMORY_PATH = BASE / "student_memory.json"
init_security()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_memory():
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text("{}", encoding="utf-8")

def load_memory(session_id: str) -> dict:
    init_memory()
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        return data.get(session_id, {})
    except (json.JSONDecodeError, OSError):
        return {}

def save_memory(session_id: str, key: str, value: str) -> str:
    """Persist only low-risk profile facts explicitly volunteered by the student."""
    allowed = {"preferred_name", "programme", "semester"}
    if key not in allowed:
        return "This information is not eligible for persistent profile memory."
    if re.search(r"\b(password|medical|diagnosis|religion|caste|bank account|card number|otp)\b", value, re.I):
        return "Sensitive information was not stored."
    init_memory()
    data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    profile = data.setdefault(session_id, {})
    profile[key] = value[:120]
    MEMORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f"Saved {key} in this chat profile."

def retrieve_policy(query: str, top_k: int = 3) -> list[dict]:
    """Small lexical chunk retriever: only matching paragraphs are returned."""
    if not POLICY_PATH.exists():
        return []
    raw = POLICY_PATH.read_text(encoding="utf-8")
    chunks = [p.strip() for p in re.split(r"\n(?=## )", raw) if p.strip()]
    qterms = set(re.findall(r"[a-z0-9]+", query.lower())) - {"what","is","the","can","i","my","for","a","to","on"}
    scored = []
    for chunk in chunks:
        terms = set(re.findall(r"[a-z0-9]+", chunk.lower()))
        score = len(qterms & terms)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "text": c[:2500]} for s, c in scored[:top_k]]

def tool_fee_status(student_id: str, actor_id: str) -> dict:
    if not authorize_student_record(actor_id, student_id, "get_fee_status"):
        return {"found": False, "blocked": True, "message": "Access denied: you may view only your own fee record."}
    with db() as con:
        row = con.execute("SELECT student_id,name,total_fee,paid,due_date FROM students WHERE student_id=?",
                          (student_id.strip().upper(),)).fetchone()
    if not row: return {"found": False, "message": f"No student record for {student_id}."}
    audit(actor_id, "student", "get_fee_status", student_id, True, "NotRequired", "Own fee record accessed")
    return {"found": True, **dict(row), "pending": row["total_fee"] - row["paid"]}

def tool_scholarship_status(student_id: str, actor_id: str) -> dict:
    if not authorize_student_record(actor_id, student_id, "get_scholarship_status"):
        return {"found": False, "blocked": True, "message": "Access denied: you may view only your own scholarship record."}
    with db() as con:
        row = con.execute("""SELECT s.student_id,s.name,sc.scholarship_name,sc.amount,sc.status,
                            sc.academic_year,sc.remarks
                            FROM students s LEFT JOIN scholarships sc ON s.student_id=sc.student_id
                            WHERE s.student_id=?""", (student_id.strip().upper(),)).fetchone()
    if row: audit(actor_id, "student", "get_scholarship_status", student_id, True, "NotRequired", "Own scholarship record accessed")
    return dict(row) if row else {"found": False, "message": f"No student record for {student_id}."}

def tool_raise_ticket(student_id: str, issue: str, actor_id: str) -> dict:
    if not authorize_student_record(actor_id, student_id, "raise_support_ticket"):
        return {"created": False, "blocked": True, "message": "Access denied: you may raise a ticket only for your own account."}
    with db() as con:
        found = con.execute("SELECT 1 FROM students WHERE student_id=?", (student_id.strip().upper(),)).fetchone()
        if not found: return {"created": False, "message": "Student ID not found; ticket not created."}
        cur = con.execute("INSERT INTO tickets(student_id,issue) VALUES (?,?)", (student_id.strip().upper(), issue))
        con.commit()
        audit(actor_id, "student", "raise_support_ticket", student_id, True, "NotRequired", "Support ticket created", {"ticket_id": cur.lastrowid})
    return {"created": True, "ticket_id": cur.lastrowid, "status": "Open"}

def tool_request_due_date_change(student_id: str, new_due_date: str, reason: str, actor_id: str) -> dict:
    return request_due_date_change(actor_id, student_id, new_due_date, reason)

def tool_exam_schedule(semester: str) -> dict:
    with db() as con:
        rows = con.execute("SELECT subject,date,time,venue FROM exams WHERE lower(semester)=lower(?) ORDER BY date",
                           (semester.strip(),)).fetchall()
    return {"semester": semester, "exams": [dict(r) for r in rows]}

def tool_timetable(semester: str, day: str) -> dict:
    with db() as con:
        rows = con.execute("""SELECT period,subject FROM timetable
                            WHERE lower(semester)=lower(?) AND lower(day)=lower(?) ORDER BY period""",
                           (semester.strip(), day.strip())).fetchall()
    return {"semester": semester, "day": day, "classes": [dict(r) for r in rows]}

def tool_calendar(start_date: str = "", end_date: str = "", category: str = "") -> dict:
    sql = "SELECT title,category,start_date,end_date,start_time,venue,description,is_official FROM calendar_events WHERE 1=1"
    args = []
    if start_date: sql += " AND coalesce(end_date,start_date)>=?"; args.append(start_date)
    if end_date: sql += " AND start_date<=?"; args.append(end_date)
    if category: sql += " AND lower(category)=lower(?)"; args.append(category)
    sql += " ORDER BY start_date"
    with db() as con:
        rows = con.execute(sql, args).fetchall()
    return {"events": [dict(r) for r in rows]}

TOOLS = {
    "get_fee_status": (tool_fee_status, {"type":"object","properties":{"student_id":{"type":"string"}},"required":["student_id"]}),
    "get_scholarship_status": (tool_scholarship_status, {"type":"object","properties":{"student_id":{"type":"string"}},"required":["student_id"]}),
    "raise_support_ticket": (tool_raise_ticket, {"type":"object","properties":{"student_id":{"type":"string"},"issue":{"type":"string"}},"required":["student_id","issue"]}),
    "request_fee_due_date_change": (tool_request_due_date_change, {"type":"object","properties":{"student_id":{"type":"string"},"new_due_date":{"type":"string"},"reason":{"type":"string"}},"required":["student_id","new_due_date","reason"]}),
    "get_exam_schedule": (tool_exam_schedule, {"type":"object","properties":{"semester":{"type":"string"}},"required":["semester"]}),
    "get_semester_timetable": (tool_timetable, {"type":"object","properties":{"semester":{"type":"string"},"day":{"type":"string"}},"required":["semester","day"]}),
    "get_academic_calendar": (tool_calendar, {"type":"object","properties":{"start_date":{"type":"string"},"end_date":{"type":"string"},"category":{"type":"string"}}}),
}

def _append_trace(trace):
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")

def answer(query: str, student_id: str, history: list | None = None) -> tuple[str, dict]:
    started = time.perf_counter()
    trace = {"timestamp": datetime.now().isoformat(timespec="seconds"), "query": "[message omitted; trace stores no raw chat text]",
             "tools_used": [], "retrieved_evidence": [], "latency_seconds": None,
             "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "status": "ok"}
    student_id = (student_id or "").strip().upper()
    if not student_id:
        return "Please sign in before accessing student support records.", {"status":"unauthenticated","tools_used":[],"latency_seconds":0,"total_tokens":0}
    memory = load_memory(student_id)
    # Never save a turn containing credentials, OTPs or other high-risk secrets.
    contains_secret = bool(re.search(r"\b(otp|one.time.password|password|passcode|pin)\b", query, re.I))
    if not contains_secret:
        name_match = re.search(r"\bmy name is ([A-Za-z][A-Za-z .'-]{0,50})", query, re.I)
        if name_match: save_memory(student_id, "preferred_name", name_match.group(1).strip())
        prog_match = re.search(r"\bmy programme is ([A-Za-z0-9 &+-]{3,80})", query, re.I)
        if prog_match: save_memory(student_id, "programme", prog_match.group(1).strip())
    # Catch an explicitly named different sample student before model/tool execution.
    mentioned_ids = {x.upper() for x in re.findall(r"\bS10\d{2}\b", query, re.I)}
    if mentioned_ids and mentioned_ids != {student_id}:
        audit(student_id, "student", "private_record_access", next(iter(mentioned_ids)), False, "NotRequired", "Blocked before agent/tool execution", {"reason":"cross-student record request"})
        trace.update({"status":"authorization_denied","latency_seconds":round(time.perf_counter()-started,3),"authorization":"denied"})
        _append_trace(trace)
        return "Access denied. You can view private fee and scholarship information only for your own signed-in student account.", trace

    policy = retrieve_policy(query)
    trace["retrieved_evidence"] = [{"score": x["score"], "heading": next((ln[3:] for ln in x["text"].splitlines() if ln.startswith("## ")), "Handbook excerpt")} for x in policy]
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Deterministic offline mode keeps the original app demonstrable without an API key.
        q = query.lower()
        try:
            if any(w in q for w in ("due date change", "change my due date", "extend my fee")):
                match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
                result = tool_request_due_date_change(student_id, match.group(1) if match else "", "Student-requested change", student_id)
                trace["tools_used"].append("request_fee_due_date_change")
            elif "scholarship" in q:
                result = tool_scholarship_status(student_id, student_id); trace["tools_used"].append("get_scholarship_status")
            elif any(w in q for w in ("fee", "payment", "paid", "balance", "due")):
                result = tool_fee_status(student_id, student_id); trace["tools_used"].append("get_fee_status")
            elif "exam" in q:
                sem = "semester 2" if ("semester ii" in q or "semester 2" in q or "semester two" in q) else "semester 1"
                result = tool_exam_schedule(sem); trace["tools_used"].append("get_exam_schedule")
            elif "timetable" in q:
                sem = "semester 2" if ("semester ii" in q or "semester 2" in q) else "semester 1"
                day = next((d for d in ("monday","tuesday","wednesday","thursday","friday") if d in q), "monday")
                result = tool_timetable(sem, day); trace["tools_used"].append("get_semester_timetable")
            elif any(w in q for w in ("calendar", "fest", "concert", "holiday", "event")):
                result = tool_calendar(); trace["tools_used"].append("get_academic_calendar")
            else:
                result = retrieve_policy(query); trace["retrieved_evidence"] = [{"heading": next((ln[3:] for ln in x["text"].splitlines() if ln.startswith("## ")), "Handbook excerpt"), "score":x["score"]} for x in result]
            reply = json.dumps(result, ensure_ascii=False, indent=2)
            trace["status"] = "offline_deterministic"
        except Exception as exc:
            reply = "The local support tool could not complete this request. Please contact the support desk."
            trace["status"] = "tool_error"; trace["error_type"] = type(exc).__name__
        trace["latency_seconds"] = round(time.perf_counter()-started, 3)
        trace["authenticated_student"] = student_id
        _append_trace(trace)
        return reply, trace
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    messages = [
        {"role":"system","content":(
            "You are AI Student Support Agent for a college. Use tools for all student-record, scholarship, exam, timetable, calendar and ticket facts. "
            "Never invent facts. Student records are private: ask for the student's own ID before exposing fee/scholarship information; do not disclose another student's data. "
            "Use only relevant retrieved handbook excerpts for policy answers. If evidence is absent or insufficient, say the handbook does not specify. "
            "Calendar records are demo data and not official unless is_official=1. "
            "Persistent profile memory is limited to low-risk preferred name/programme/semester. Do not store temporary or sensitive statements. "
            "The authenticated student ID is " + student_id + ". For private tools, use only this ID. Sensitive due-date changes must be submitted as approval requests and must never be described as completed until an administrator approves. "
            f"Known profile memory for this session: {json.dumps(memory)}\n"
            f"Relevant handbook excerpts only:\n{json.dumps(policy, ensure_ascii=False)}"
        )}
    ]
    for m in (history or [])[-8:]:
        if m.get("role") in ("user","assistant"):
            messages.append({"role":m["role"],"content":m["content"][:1500]})
    messages.append({"role":"user","content":query})
    try:
        for _ in range(5):  # bounded agent/tool loop
            response = client.chat.completions.create(
                model=model, messages=messages,
                tools=[{"type":"function","function":{"name":n,"description":f"College data tool: {n}","parameters":schema}} for n,(_,schema) in TOOLS.items()],
                tool_choice="auto", temperature=0.2
            )
            usage = getattr(response, "usage", None)
            if usage:
                trace["prompt_tokens"] += getattr(usage,"prompt_tokens",0) or 0
                trace["completion_tokens"] += getattr(usage,"completion_tokens",0) or 0
                trace["total_tokens"] += getattr(usage,"total_tokens",0) or 0
            msg = response.choices[0].message
            if not msg.tool_calls:
                reply = msg.content or "I could not produce an answer from the available information."
                break
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                name = call.function.name
                if name not in TOOLS:
                    result = {"error": f"Tool {name} is not available."}
                else:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        result = TOOLS[name][0](actor_id=student_id, **args) if name in {"get_fee_status","get_scholarship_status","raise_support_ticket","request_fee_due_date_change"} else TOOLS[name][0](**args)
                        trace["tools_used"].append(name)
                    except Exception as exc:
                        result = {"error": f"Tool failed: {type(exc).__name__}: {exc}"}
                        trace["status"] = "tool_error"
                messages.append({"role":"tool","tool_call_id":call.id,"content":json.dumps(result,ensure_ascii=False)})
        else:
            reply = "I reached the tool-call limit before completing the request. Please try a narrower question."
            trace["status"] = "tool_loop_limit"
    except Exception as exc:
        reply = f"I couldn't complete that request because the support service returned an error ({type(exc).__name__}). Please try again later."
        trace["status"] = "llm_error"
        trace["error_type"] = type(exc).__name__
    trace["latency_seconds"] = round(time.perf_counter()-started, 3)
    trace["authenticated_student"] = student_id
    _append_trace(trace)
    print("[TRACE] " + json.dumps(trace, ensure_ascii=False))
    return reply, trace
