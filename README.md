# AI Student Support Agent — Assignment 2 (Security Upgrade)

This is an **upgrade of the same Assignment 1 Streamlit chat application**. It retains the existing SQLite data, fee/scholarship tools, exams, semester timetables, academic calendar, policy retrieval, profile memory, Groq tool-calling loop and query tracing. It adds application-layer identity checks, approval workflow and audit evidence.

> **Classroom prototype only.** The included student records, credentials, fee balances, scholarship statuses, policies and calendar are synthetic. This is not production-ready identity management. Before real institutional use, integrate institutional SSO/MFA, role-based admin provisioning, secrets management, encryption at rest/in transit, secure session handling, rate limiting, retention controls, privacy review and approved official data sources.

## What changed

- `security.py` — password hashing/verification, student authentication, server-side authorization, approval requests, human review and append-only style audit entries.
- `agent.py` — private record tools now receive the authenticated identity from application code and reject a target ID that does not match it. The model cannot override this check. Fee due-date changes are queued, never directly executed by the student tool. Trace records omit raw chat text.
- `app.py` — same chat-style application, now with sign-in, separate administrator view, approval queue, explicit review confirmation and audit table.
- `demo_tests.py` — offline regression tests for original features plus authentication, cross-student access denial, approval/rejection, secret handling and audit evidence.
- `reports/assignment2_evaluation.md` and `.json` — generated test measurements.

## Demo sign-in

- Mahi sample student: ID `S1004`, password `Demo@S1004`.
- Other sample students: password is `Demo@` followed by their ID, e.g. `S1001` / `Demo@S1001`.
- Administrator: `AdminDemo!2026` by default. Set environment variable `ADMIN_DEMO_PASSWORD` to override it before launching.

Passwords are stored as PBKDF2-HMAC-SHA256 hashes in `student_auth`, not as plaintext. Demo passwords are predictable by design and must never be reused in a real system.

## Run on Windows PowerShell

Open the project folder (the folder containing this README) in VS Code. Activate your existing virtual environment, then:

```powershell
pip install -r requirements.txt
python setup_db.py
python demo_tests.py
streamlit run app.py
```

`python setup_db.py` recreates the sample database and resets the security tables, approvals and audit history. Do not run it against real data.

To enable Groq tool calling, copy `.env.example` to `.env`, add your API key, and restart Streamlit. Without a key, deterministic offline routing keeps the sample application testable. Offline mode reports zero model tokens because it makes no LLM call. With Groq, prompt/completion/total token counts are captured when the API response supplies usage metadata.

## Security design

1. The user signs in; Streamlit session state holds the authenticated student ID and role.
2. The application passes the authenticated student ID to `answer()`; it is not accepted from the user's chat as the authority.
3. Student fee, scholarship and ticket tools require both the requested target ID and the authenticated actor ID. The authorization function checks equality in ordinary Python tool code and logs denied attempts.
4. The UI does not offer student-to-student lookup. The agent also blocks explicit cross-student ID requests before calling the model. Tool-level checks remain the final enforcement boundary.
5. A fee due-date change creates a `Pending` approval request. The student's request does not change the student row. An authenticated administrator must explicitly confirm and approve it; rejection leaves the record unchanged.
6. Audit entries record timestamp, actor, role, action, target, allow/deny, approval state, result and limited structured details. Raw chat text is omitted from query traces. Password/OTP-like messages are blocked by the UI and not written to profile memory or traces.

## Evaluation

Run `python demo_tests.py`. It writes JSON and Markdown results under `reports/`. The tests are deterministic component/security tests, not live LLM answer-accuracy measurements. Assignment 1's earlier baseline was 9/9 component checks (100%). Assignment 2 expands the suite; percentages should not be treated as a controlled model-quality comparison because the test sets differ. Latency below is local component-test latency, not end-to-end network/model latency.

## Important limitations

- The demo administrator password and per-student demo passwords are classroom credentials, not a secure institutional login system.
- Admin identity is a single configured shared demo credential; production requires named administrator accounts, least privilege and MFA.
- Local SQLite is suitable for this demonstration only. Production needs institutional database controls, backups, monitoring and access policies.
- This is not legal/compliance certification. Have the institution's security, privacy and legal teams review deployment before real student data is used.
