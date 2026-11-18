# tests/test_core.py
import sys
import time
from typing import List, Union
import unittest

from core.engine import FastTypeEngine, KeyEvent, Passthrough, Replace, ResetEvent
from core.loader import PackValidationError, build_pack_from_dict

SAMPLE_PACK_DATA = {
    "meta": {"id": "test", "name": "Test Pack", "version": 1, "symbol": "TS"},
    "rules": {"ä": "ae", "ë": "e:", "ñ": "nh", "ß": "sz"},
    "upper": {"ß": "ẞ"},
}


def simulate_typing(
    engine: FastTypeEngine, events: List[Union[KeyEvent, ResetEvent, str]]
) -> str:
  """Mô phỏng một ô nhập văn bản nhận chuỗi sự kiện phím."""
  screen: List[str] = []
  for ev in events:
    if isinstance(ev, str):
      if ev == " ":
        key_ev = KeyEvent(char=" ", is_break_key=True)
      else:
        key_ev = KeyEvent(char=ev, is_upper=ev.isupper())
    else:
      key_ev = ev

    action = engine.process_event(key_ev)
    if isinstance(action, Passthrough):
      if (
          isinstance(key_ev, KeyEvent)
          and not key_ev.has_modifier
          and key_ev.char
      ):
        screen.append(key_ev.char)
    elif isinstance(action, Replace):
      for _ in range(action.delete_count):
        if screen:
          screen.pop()
      for ch in action.text:
        screen.append(ch)
  return "".join(screen)


class TestM0Acceptance(unittest.TestCase):

  def setUp(self):
    self.pack, _ = build_pack_from_dict(SAMPLE_PACK_DATA)
    self.engine = FastTypeEngine(self.pack)

  def test_01_basic_match(self):
    self.assertEqual(simulate_typing(self.engine, ["a", "e"]), "ä")

  def test_02_revert(self):
    self.assertEqual(simulate_typing(self.engine, ["a", "e", "e"]), "ae")

  def test_03_locked_after_revert(self):
    self.assertEqual(simulate_typing(self.engine, ["a", "e", "e", "e"]), "aee")

  def test_04_upper_first_char(self):
    self.assertEqual(simulate_typing(self.engine, ["A", "e"]), "Ä")

  def test_05_upper_both_chars(self):
    self.assertEqual(simulate_typing(self.engine, ["A", "E"]), "Ä")

  def test_06_lower_first_upper_second(self):
    self.assertEqual(simulate_typing(self.engine, ["a", "E"]), "ä")

  def test_07_spanish_nh_cases(self):
    self.assertEqual(simulate_typing(self.engine, ["n", "h"]), "ñ")
    self.engine.reset()
    self.assertEqual(simulate_typing(self.engine, ["N", "h"]), "Ñ")
    self.engine.reset()
    self.assertEqual(simulate_typing(self.engine, ["N", "H"]), "Ñ")

  def test_08_caps_lock_nh(self):
    # Khi bật Caps Lock, hệ điều hành gửi ký tự hoa ('N', 'H') kèm is_upper=True
    events = [
        KeyEvent(char="N", is_upper=True),
        KeyEvent(char="H", is_upper=True),
    ]
    self.assertEqual(simulate_typing(self.engine, events), "Ñ")

  def test_09_custom_upper_exception_eszett(self):
    self.assertEqual(simulate_typing(self.engine, ["s", "z"]), "ß")
    self.engine.reset()
    self.assertEqual(simulate_typing(self.engine, ["S", "z"]), "ẞ")

  def test_10_space_breaks_buffer(self):
    self.assertEqual(simulate_typing(self.engine, ["a", " ", "e"]), "a e")

  def test_11_arrow_left_breaks_buffer(self):
    events = ["a", KeyEvent(char="", is_break_key=True), "e"]
    self.assertEqual(simulate_typing(self.engine, events), "ae")

  def test_12_13_14_name_colon_sequence(self):
    # #12: N, a, m, e, : -> Namë
    events = ["N", "a", "m", "e", ":"]
    self.assertEqual(simulate_typing(self.engine, events), "Namë")

    # #13: thêm : -> Name: (hoàn tác)
    self.engine.reset()
    events.append(":")
    self.assertEqual(simulate_typing(self.engine, events), "Name:")

    # #14: thêm : -> Name:: (quy tắc đã khóa)
    self.engine.reset()
    events.append(":")
    self.assertEqual(simulate_typing(self.engine, events), "Name::")

  def test_15_ctrl_c_modifier(self):
    events = ["a", KeyEvent(char="c", has_modifier=True), "e"]
    self.assertEqual(simulate_typing(self.engine, events), "ae")

  def test_16_no_active_pack(self):
    self.engine.set_pack(None)
    self.assertEqual(simulate_typing(self.engine, ["a", "e"]), "ae")

  def test_17_duplicate_trigger_error(self):
    bad_pack = {
        "meta": {"id": "bad"},
        "rules": {"ä": "ae", "æ": "AE"},  # Trùng trigger không phân biệt hoa/thường
    }
    with self.assertRaises(PackValidationError):
      build_pack_from_dict(bad_pack)

  def test_18_dead_rule_prefix_warning(self):
    warn_pack = {
        "meta": {"id": "warn"},
        "rules": {"ä": "a:", "ā": "a:b"},
    }
    _, issues = build_pack_from_dict(warn_pack)
    kinds = [i.kind for i in issues]
    self.assertIn("DEAD_RULE_PREFIX", kinds)

  def test_benchmark_under_1ms(self):
    iterations = 10_000
    seq = [KeyEvent(char="a"), KeyEvent(char="e"), KeyEvent(char="e"), KeyEvent(char=" ", is_break_key=True)]
    start = time.perf_counter()
    for _ in range(iterations):
      for ev in seq:
        self.engine.process_event(ev)
    elapsed_ms = (time.perf_counter() - start) * 1000
    avg_ms_per_key = elapsed_ms / (iterations * len(seq))
    print(f"\n[Benchmark M0] Trung bình mỗi phím: {avg_ms_per_key:.5f} ms (Ngưỡng yêu cầu: < 1.0 ms)")
    self.assertLess(avg_ms_per_key, 1.0)


def run_cli():
  pack, issues = build_pack_from_dict(SAMPLE_PACK_DATA)
  engine = FastTypeEngine(pack)
  print(f"=== MultilingualFastType M0 CLI ({pack.name}) ===")
  for issue in issues:
    print(f"[{issue.level}] {issue.message}")
  print("Nhập chuỗi phím bất kỳ để xem kết quả biến đổi (gõ 'quit' để thoát):")
  while True:
    try:
      line = input("> ")
    except EOFError:
      break
    if line.strip() == "quit":
      break
    engine.reset()
    result = simulate_typing(engine, list(line))
    print(f"  Kết quả: {result}")


if __name__ == "__main__":
  if "--cli" in sys.argv:
    run_cli()
  else:
    unittest.main(verbosity=2)