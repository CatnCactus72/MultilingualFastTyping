#!/usr/bin/env python3
# launcher.py
from pathlib import Path
import subprocess
import sys
import time

APP_DIR = Path(__file__).resolve().parent
TRAY_SCRIPT = APP_DIR / "gui" / "tray_icon.py"
SETTINGS_SCRIPT = APP_DIR / "gui" / "settings_window.py"


def is_process_running(script_name: str) -> bool:
  """Kiểm tra xem một script Python của ứng dụng đã chạy ngầm hay chưa."""
  try:
    res = subprocess.run(
        ["pgrep", "-f", script_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0
  except FileNotFoundError:
    return False


def ensure_ibus_engine_active() -> None:
  """Đảm bảo ibus-daemon đang chạy và kích hoạt engine multilingual-fasttype."""
  # Khởi động ibus-daemon nếu chưa chạy
  subprocess.run(
      ["ibus-daemon", "-drx"],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
  )
  time.sleep(0.3)
  # Chuyển engine hiện tại sang multilingual-fasttype
  subprocess.run(
      ["ibus", "engine", "multilingual-fasttype"],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
  )


def ensure_tray_running() -> None:
  """Khởi chạy biểu tượng khay hệ thống nếu chưa chạy."""
  if not is_process_running("gui/tray_icon.py"):
    subprocess.Popen(
        [sys.executable, str(TRAY_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_settings() -> None:
  """Mở cửa sổ cài đặt (nếu chưa mở)."""
  if not is_process_running("gui/settings_window.py"):
    subprocess.Popen(
        [sys.executable, str(SETTINGS_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def notify_started() -> None:
  try:
    subprocess.Popen(
        [
            "notify-send",
            "-a",
            "MultilingualFastType",
            "-t",
            "2000",
            "Multilingual FastType đã bật",
            "Bấm Ctrl+Shift+F1..F4 hoặc dùng icon khay hệ thống để chọn ngôn ngữ.",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
  except FileNotFoundError:
    pass


if __name__ == "__main__":
  ensure_ibus_engine_active()
  ensure_tray_running()

  if "--settings" in sys.argv:
    open_settings()
  elif "--silent" not in sys.argv:
    notify_started()