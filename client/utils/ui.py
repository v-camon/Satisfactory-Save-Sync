import ctypes
from typing import Optional

MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
MB_ICONWARNING = 0x30
MB_ICONINFORMATION = 0x40
IDYES = 6

user32 = ctypes.windll.user32


def show_error(title: str, message: str) -> None:
    user32.MessageBoxW(0, message, title, MB_ICONERROR | MB_OK)


def show_info(title: str, message: str) -> None:
    user32.MessageBoxW(0, message, title, MB_ICONINFORMATION | MB_OK)


def show_timed_info(title: str, message: str, timeout_ms: int = 4000) -> None:
    try:
        user32.MessageBoxTimeoutW(0, message, title, MB_ICONINFORMATION | MB_OK, 0, timeout_ms)
    except Exception:
        import time
        time.sleep(timeout_ms / 1000)


def ask_yes_no(title: str, message: str) -> bool:
    res = user32.MessageBoxW(0, message, title, MB_ICONQUESTION | MB_YESNO)
    return res == IDYES