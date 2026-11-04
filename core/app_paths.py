"""Writable application paths and per-install secrets."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def user_data_dir() -> Path:
    """Return VisioExam's writable per-user data directory."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "VisioExam"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    """Use a user-owned settings file in packaged builds."""
    return user_data_dir() / ".env" if is_frozen() else project_root() / ".env"


def bundled_root() -> Path:
    """Root of bundled read-only assets (or the source project)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return project_root()


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    """Protect/unprotect bytes for the current Windows user using DPAPI."""
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is only available on Windows.")

    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    blob_pointer = ctypes.POINTER(DataBlob)
    crypt32.CryptProtectData.argtypes = [
        blob_pointer, wintypes.LPCWSTR, blob_pointer, wintypes.LPVOID,
        wintypes.LPVOID, wintypes.DWORD, blob_pointer,
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        blob_pointer, ctypes.POINTER(wintypes.LPWSTR), blob_pointer,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, blob_pointer,
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    source_buffer = ctypes.create_string_buffer(data)
    source = DataBlob(
        len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    target = DataBlob()
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(source), "VisioExam database key", None, None, None,
            0x01, ctypes.byref(target),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 0x01,
            ctypes.byref(target),
        )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def get_or_create_database_key() -> str:
    """Return a stable random SQLCipher key protected for this Windows user."""
    key_file = user_data_dir() / "database-key.dpapi"
    try:
        return _dpapi(key_file.read_bytes(), protect=False).decode("ascii")
    except FileNotFoundError:
        key = secrets.token_hex(32)
        encrypted = _dpapi(key.encode("ascii"), protect=True)
        temporary = key_file.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        try:
            temporary.replace(key_file)
        except OSError:
            temporary.unlink(missing_ok=True)
            if key_file.exists():
                return _dpapi(key_file.read_bytes(), protect=False).decode("ascii")
            raise
        return key
