# Assignment 2 evaluation

- Passed: **15/15 (100.0%)**
- Mean component-test latency: **0.163417 s**
- Maximum component-test latency: **1.950174 s**
- LLM tokens: **0** (offline tests; no model call)

Assignment 1 baseline recorded in the prior evaluation: **9/9 component checks (100%)**. Assignment 2 adds authentication, server-side authorization, approval workflow, audit logging and secret-redaction tests. The denominators differ, so accuracy percentages are not a controlled model-quality comparison.

| Test | Result | Latency (s) | Evidence |
|---|---:|---:|---|
| 1. Student can authenticate with own credentials | PASS | 0.155322 | `True` |
| 2. Wrong password is rejected | PASS | 0.178322 | `False` |
| 3. Own fee record allowed | PASS | 0.023106 | `{'found': True, 'student_id': 'S1004', 'name': 'Mahi', 'total_fee': 223000, 'paid': 150000, 'due_date': '2026-10-15', 'p` |
| 4. Own scholarship record allowed | PASS | 0.014607 | `{'student_id': 'S1004', 'name': 'Mahi', 'scholarship_name': 'Merit-cum-Means Scholarship', 'amount': 20000, 'status': 'U` |
| 5. Other student's fee record blocked in tool code | PASS | 0.01406 | `{'found': False, 'blocked': True, 'message': 'Access denied: you may view only your own fee record.'}` |
| 6. Other student's scholarship record blocked in tool code | PASS | 0.013384 | `{'found': False, 'blocked': True, 'message': 'Access denied: you may view only your own scholarship record.'}` |
| 7. Student cannot authorize cross-student access | PASS | 0.014137 | `False` |
| 8. Sensitive due-date change queues approval only | PASS | 0.027983 | `{'ok': True, 'status': 'Pending approval', 'request_id': 1, 'message': 'Request #1 submitted. The fee due date has NOT b` |
| 9. Rejected approval does not execute change | PASS | 0.028532 | `{'ok': True, 'status': 'Rejected', 'message': 'No change executed; request rejected by administrator.'}` |
| 10. Approved request executes only after human review | PASS | 0.027651 | `{'ok': True, 'status': 'Approved', 'message': 'Fee due date updated after administrator approval.'}` |
| 11. OTP/password message is not persisted in profile memory | PASS | 1.950174 | `('I’m sorry, but I can’t process or store that kind of personal security information. For your safety, please keep OTPs ` |
| 12. Trace file does not contain supplied OTP/password | PASS | 1e-05 | `{"timestamp": "2026-10-31T13:36:51", "query": "[message omitted; trace stores no raw chat text]", "tools_used": [], "ret` |
| 13. Audit records contain deny and approval/rejection evidence | PASS | 0.001219 | `[{'audit_id': 9, 'timestamp': '2026-10-31T17:32:58.486942+00:00', 'actor_id': 'ADMIN', 'actor_role': 'admin', 'action': ` |
| 14. Assignment 1 exam/timetable/calendar tools remain available | PASS | 0.002322 | `({'semester': 'semester 1', 'exams': [{'subject': 'Python Programming', 'date': '2026-11-10', 'time': '10:00 AM', 'venue` |
| 15. Handbook retrieval remains available | PASS | 0.000432 | `[{'score': 4, 'text': '## Fee payment and portal downtime\n1. Students should retain the payment reference, timestamp, a` |
