"""Application-layer authentication, authorization, approvals and audit logging.

Classroom demonstration only: replace demo credentials with institutional SSO/MFA in production.
"""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "college.db"
ITERATIONS = 240_000


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def _verify(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS).hex()
        return hmac.compare_digest(actual, digest_hex)
    except Exception:
        return False


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_security():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS student_auth (
            student_id TEXT PRIMARY KEY REFERENCES students(student_id),
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approval_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(student_id),
            action_type TEXT NOT NULL,
            requested_value TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected')),
            requested_at TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            result TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            action TEXT NOT NULL,
            target_id TEXT,
            allowed INTEGER NOT NULL,
            approval_status TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_approval_student ON approval_requests(student_id,status);
        """)
        # Seed demo-only credentials if missing; unique per student.
        ids = [r[0] for r in con.execute("SELECT student_id FROM students")]
        for sid in ids:
            if not con.execute("SELECT 1 FROM student_auth WHERE student_id=?", (sid,)).fetchone():
                con.execute("INSERT INTO student_auth VALUES (?,?)", (sid, _hash_password(f"Demo@{sid}")))


def authenticate_student(student_id: str, password: str) -> bool:
    init_security()
    sid = (student_id or "").strip().upper()
    with connect() as con:
        row = con.execute("SELECT password_hash FROM student_auth WHERE student_id=?", (sid,)).fetchone()
    return bool(row and _verify(password or "", row["password_hash"]))


def authenticate_admin(password: str) -> bool:
    expected = os.getenv("ADMIN_DEMO_PASSWORD", "AdminDemo!2026")
    return hmac.compare_digest(password or "", expected)


def audit(actor_id: str, actor_role: str, action: str, target_id: str | None,
          allowed: bool, approval_status: str, result: str, details: dict | None = None):
    with connect() as con:
        con.execute("""INSERT INTO audit_log(timestamp,actor_id,actor_role,action,target_id,allowed,approval_status,result,details)
                      VALUES (?,?,?,?,?,?,?,?,?)""",
                    (datetime.now(timezone.utc).isoformat(), actor_id, actor_role, action,
                     target_id, int(allowed), approval_status, result,
                     json.dumps(details or {}, ensure_ascii=False)[:1500]))


def authorize_student_record(actor_id: str, target_id: str, action: str) -> bool:
    actor = (actor_id or "").strip().upper()
    target = (target_id or "").strip().upper()
    allowed = bool(actor and target and actor == target)
    if not allowed:
        audit(actor or "ANONYMOUS", "student", action, target, False, "NotRequired",
              "Blocked: student may access only their own private record", {"reason":"cross-student access"})
    return allowed


def request_due_date_change(actor_id: str, target_id: str, new_due_date: str, reason: str) -> dict:
    if not authorize_student_record(actor_id, target_id, "request_fee_due_date_change"):
        return {"ok":False,"status":"Blocked","message":"You can request changes only to your own record."}
    import re
    from datetime import date
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", new_due_date): raise ValueError
        date.fromisoformat(new_due_date)
    except Exception:
        audit(actor_id,"student","request_fee_due_date_change",target_id,False,"NotRequired","Rejected: invalid date")
        return {"ok":False,"status":"Rejected","message":"Use a valid date in YYYY-MM-DD format."}
    safe_reason = re.sub(r"(?i)\b(otp|password|passcode|pin)\b\s*(?:is|:|=)?\s*\S+", "[REDACTED]", reason or "")[:500]
    with connect() as con:
        exists = con.execute("SELECT 1 FROM students WHERE student_id=?",(target_id.upper(),)).fetchone()
        if not exists: return {"ok":False,"status":"Rejected","message":"Student record not found."}
        cur = con.execute("""INSERT INTO approval_requests(student_id,action_type,requested_value,reason,requested_at)
                              VALUES (?,?,?,?,?)""",(target_id.upper(),"fee_due_date_change",new_due_date,safe_reason,datetime.now(timezone.utc).isoformat()))
        rid = cur.lastrowid
    audit(actor_id,"student","request_fee_due_date_change",target_id,True,"Pending","Queued for human approval",{"request_id":rid,"new_due_date":new_due_date})
    return {"ok":True,"status":"Pending approval","request_id":rid,"message":f"Request #{rid} submitted. The fee due date has NOT been changed; an authorized administrator must review it."}


def review_approval(request_id: int, admin_id: str, decision: str) -> dict:
    decision = decision.strip().title()
    if decision not in {"Approved","Rejected"}:
        return {"ok":False,"message":"Decision must be Approved or Rejected."}
    with connect() as con:
        req = con.execute("SELECT * FROM approval_requests WHERE request_id=?",(int(request_id),)).fetchone()
        if not req:
            audit(admin_id,"admin","review_approval",None,False,"NotApproved","Request not found",{"request_id":request_id})
            return {"ok":False,"message":"Approval request not found."}
        if req["status"] != "Pending":
            audit(admin_id,"admin","review_approval",req["student_id"],False,req["status"],"Request already reviewed",{"request_id":request_id})
            return {"ok":False,"message":f"Request already {req['status'].lower()}."}
        result = "No change executed; request rejected by administrator."
        if decision == "Approved":
            if req["action_type"] == "fee_due_date_change":
                con.execute("UPDATE students SET due_date=? WHERE student_id=?",(req["requested_value"],req["student_id"]))
                result = "Fee due date updated after administrator approval."
            else:
                return {"ok":False,"message":"Unsupported approval action; no change executed."}
        con.execute("UPDATE approval_requests SET status=?,reviewed_by=?,reviewed_at=?,result=? WHERE request_id=?",
                    (decision,admin_id,datetime.now(timezone.utc).isoformat(),result,int(request_id)))
    audit(admin_id,"admin","review_approval",req["student_id"],True,decision,result,{"request_id":request_id,"action_type":req["action_type"]})
    return {"ok":True,"status":decision,"message":result}


def pending_approvals() -> list[dict]:
    with connect() as con:
        rows=con.execute("SELECT request_id,student_id,action_type,requested_value,reason,requested_at FROM approval_requests WHERE status='Pending' ORDER BY request_id").fetchall()
    return [dict(r) for r in rows]


def audit_rows(limit: int = 100) -> list[dict]:
    with connect() as con:
        rows=con.execute("SELECT * FROM audit_log ORDER BY audit_id DESC LIMIT ?",(int(limit),)).fetchall()
    return [dict(r) for r in rows]
