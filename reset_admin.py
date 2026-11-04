"""Reset an administrator username and password using the local DB key."""

import sys
from getpass import getpass
from pathlib import Path

import bcrypt

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.environment import load_env_file
from core.database import Database
from security.audit_logger import AuditLogger, AuditEvent
from security.admin_auth import AdminAuth, BCRYPT_COST


def main() -> int:
    load_env_file(PROJECT_ROOT / ".env")
    db = Database()
    try:
        db.initialize()
        audit = AuditLogger(db)
        accounts = db.fetchall("SELECT id, username FROM admins ORDER BY id")

        if accounts:
            if len(accounts) == 1:
                account = accounts[0]
            else:
                print("Administrator accounts:")
                for index, row in enumerate(accounts, 1):
                    print(f"{index}. {row['username']}")
                choice = input("Choose account number to reset: ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(accounts):
                    print("Invalid account selection.")
                    return 1
                account = accounts[int(choice) - 1]

            print(f"Resetting credentials for administrator: {account['username']}")
            username = input("New administrator username: ").strip()
            print("Password input is hidden: type it normally and press Enter.")
            password = getpass("New administrator password (12–72 UTF-8 bytes): ")
            confirmation = getpass("Confirm new password (hidden): ")
            if not username:
                print("Username cannot be empty.")
                return 1
            if password != confirmation:
                print("Passwords did not match.")
                return 1
            encoded_password = password.encode("utf-8")
            if not 12 <= len(encoded_password) <= 72:
                print("Password must be between 12 and 72 UTF-8 bytes.")
                return 1
            duplicate = db.fetchone(
                "SELECT id FROM admins WHERE username=? AND id<>?",
                (username, account["id"]),
            )
            if duplicate:
                print("That username is already assigned to another administrator.")
                return 1

            password_hash = bcrypt.hashpw(
                encoded_password, bcrypt.gensalt(rounds=BCRYPT_COST)
            ).decode("utf-8")
            db.execute(
                "UPDATE admins SET username=?, password_hash=? WHERE id=?",
                (username, password_hash, account["id"]),
            )
            db.commit()
            audit.log(
                AuditEvent.ADMIN_CREDENTIAL_RESET,
                f"admin_id={account['id']}; username_changed={username != account['username']}",
            )
            print("Administrator credentials updated.")
        else:
            print("No administrator account exists. Create the first account.")
            username = input("Administrator username: ").strip()
            print("Password input is hidden: type it normally and press Enter.")
            password = getpass("Administrator password (12–72 UTF-8 bytes): ")
            confirmation = getpass("Confirm password (hidden): ")
            if not username or password != confirmation:
                print("A username is required and passwords must match.")
                return 1
            encoded_password = password.encode("utf-8")
            if not 12 <= len(encoded_password) <= 72:
                print("Password must be between 12 and 72 UTF-8 bytes.")
                return 1
            auth = AdminAuth(db, audit)
            if not auth.create_admin(username, password):
                print("Could not create administrator account.")
                return 1
            print("Administrator account created.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
