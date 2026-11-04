# import_exam.py
import getpass
import sys
sys.path.insert(0, ".")
from core.database import Database
from security.audit_logger import AuditLogger
from security.admin_auth import AdminAuth
from admin.admin_module import AdminModule

db = Database()
db.initialize()
audit = AuditLogger(db)
auth = AdminAuth(db, audit)
admin = AdminModule(db, auth, audit)
username = input("Admin username: ").strip()
password = getpass.getpass("Admin password: ")
if not auth.login(username, password):
    raise SystemExit("Administrator login failed.")

exam_id = admin.create_exam("Computer Science Paper 1", time_limit=3600)
print(f"Created exam ID: {exam_id}")

n = admin.import_questions_csv("questions.csv", exam_id)
print(f"Imported {n} questions")
db.close()
