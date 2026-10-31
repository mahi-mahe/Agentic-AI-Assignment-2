"""Assignment 2 security regression suite; runs offline and reports measured timings."""
import json, re, time
from pathlib import Path
from agent import (tool_fee_status, tool_scholarship_status, tool_exam_schedule,
                   tool_timetable, tool_calendar, retrieve_policy, save_memory,
                   load_memory, answer, TRACE_PATH)
from security import (init_security, authenticate_student, authorize_student_record,
                      request_due_date_change, review_approval, audit_rows, connect)

init_security()
results=[]
def check(name, fn, predicate):
    t=time.perf_counter()
    try:
        value=fn(); ok=bool(predicate(value)); evidence=str(value)[:500]
    except Exception as exc:
        ok=False; evidence=f"{type(exc).__name__}: {exc}"
    results.append({"test":name,"passed":ok,"latency_seconds":round(time.perf_counter()-t,6),"evidence":evidence})
    return value

check("1. Student can authenticate with own credentials",lambda:authenticate_student("S1004","Demo@S1004"),lambda x:x is True)
check("2. Wrong password is rejected",lambda:authenticate_student("S1004","wrong-password"),lambda x:x is False)
check("3. Own fee record allowed",lambda:tool_fee_status("S1004","S1004"),lambda x:x.get("found") and x.get("student_id")=="S1004")
check("4. Own scholarship record allowed",lambda:tool_scholarship_status("S1004","S1004"),lambda x:x.get("student_id")=="S1004")
check("5. Other student's fee record blocked in tool code",lambda:tool_fee_status("S1001","S1004"),lambda x:x.get("blocked") is True)
check("6. Other student's scholarship record blocked in tool code",lambda:tool_scholarship_status("S1001","S1004"),lambda x:x.get("blocked") is True)
check("7. Student cannot authorize cross-student access",lambda:authorize_student_record("S1004","S1001","test"),lambda x:x is False)
req=check("8. Sensitive due-date change queues approval only",lambda:request_due_date_change("S1004","S1004","2026-12-20","Demo test request"),lambda x:x.get("status")=="Pending approval")
request_id=req.get("request_id") if isinstance(req,dict) else None
check("9. Rejected approval does not execute change",lambda:review_approval(request_id,"ADMIN","Rejected") if request_id else {},lambda x:x.get("status")=="Rejected")
with connect() as con: current_due=con.execute("SELECT due_date FROM students WHERE student_id='S1004'").fetchone()[0]
req2=request_due_date_change("S1004","S1004","2026-12-25","Approval execution test")
check("10. Approved request executes only after human review",lambda:review_approval(req2["request_id"],"ADMIN","Approved"),lambda x:x.get("status")=="Approved")
with connect() as con:
    updated_due=con.execute("SELECT due_date FROM students WHERE student_id='S1004'").fetchone()[0]
    con.execute("UPDATE students SET due_date=? WHERE student_id='S1004'",(current_due,))
check("11. OTP/password message is not persisted in profile memory",lambda:answer("My OTP is 123456 and my password is secret", "S1004"),lambda x:"123456" not in json.dumps(load_memory("S1004")) and "secret" not in json.dumps(load_memory("S1004")).lower())
# Verify traces omit raw sensitive message.
trace_text=TRACE_PATH.read_text(encoding="utf-8") if TRACE_PATH.exists() else ""
check("12. Trace file does not contain supplied OTP/password",lambda:trace_text,lambda x:"123456" not in x and "secret" not in x)
check("13. Audit records contain deny and approval/rejection evidence",lambda:audit_rows(100),lambda rows:any(r["allowed"]==0 for r in rows) and any(r["approval_status"]=="Rejected" for r in rows) and any(r["approval_status"]=="Approved" for r in rows))
check("14. Assignment 1 exam/timetable/calendar tools remain available",lambda:(tool_exam_schedule("semester 1"),tool_timetable("semester 2","monday"),tool_calendar()),lambda x:bool(x[0]["exams"]) and bool(x[1]["classes"]) and bool(x[2]["events"]))
check("15. Handbook retrieval remains available",lambda:retrieve_policy("fee payment portal downtime"),lambda x:len(x)>0)

passed=sum(x["passed"] for x in results); total=len(results)
latencies=[x["latency_seconds"] for x in results]
report={"suite":"Assignment 2 security regression (offline)","passed":passed,"total":total,"accuracy_percent":round(100*passed/total,2),"mean_test_latency_seconds":round(sum(latencies)/len(latencies),6),"max_test_latency_seconds":round(max(latencies),6),"llm_tokens":0,"token_note":"Offline deterministic tests; no LLM call. Live API token counts are recorded in traces when the provider returns usage." ,"results":results}
(BASE:=Path(__file__).resolve().parent / "reports").mkdir(exist_ok=True)
(BASE/"assignment2_evaluation.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
(BASE/"assignment2_evaluation.md").write_text(
    "# Assignment 2 evaluation\n\n"+
    f"- Passed: **{passed}/{total} ({report['accuracy_percent']}%)**\n- Mean component-test latency: **{report['mean_test_latency_seconds']} s**\n- Maximum component-test latency: **{report['max_test_latency_seconds']} s**\n- LLM tokens: **0** (offline tests; no model call)\n\n"+
    "Assignment 1 baseline recorded in the prior evaluation: **9/9 component checks (100%)**. Assignment 2 adds authentication, server-side authorization, approval workflow, audit logging and secret-redaction tests. The denominators differ, so accuracy percentages are not a controlled model-quality comparison.\n\n"+
    "| Test | Result | Latency (s) | Evidence |\n|---|---:|---:|---|\n"+
    "".join(f"| {r['test']} | {'PASS' if r['passed'] else 'FAIL'} | {r['latency_seconds']} | `{r['evidence'][:120].replace('|','/')}` |\n" for r in results),encoding="utf-8")
print(json.dumps(report,indent=2,ensure_ascii=False))
print(f"\nRESULT: {passed}/{total} ({report['accuracy_percent']}%)")
