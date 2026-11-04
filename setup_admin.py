# setup_admin.py
import sys
sys.path.insert(0, ".")
from core.database import Database
from security.audit_logger import AuditLogger
from security.admin_auth import AdminAuth

db = Database()
db.initialize()
audit = AuditLogger(db)
auth = AdminAuth(db, audit)

username = input("Admin username: ")
password = input("Admin password: ")
ok = auth.create_admin(username, password)
print("Admin created successfully." if ok else "Admin already exists.")
db.close()