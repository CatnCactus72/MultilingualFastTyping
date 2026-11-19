# tests/test_core.py
import sys
import time
from typing import List, Union
import unittest

from core.composers.base import KeyEvent, Passthrough, Replace, ResetEvent
from core.engine import FastTypeEngine
from core.loader import build_pack_from_dict

SAMPLE_PACK_DATA = {
    "meta": {"id": "test", "name": "Test Pack", "version": 1, "symbol": "TS"},
    "rules": {"ä": "ae", "ë": "e3", "ñ": "nh", "ß": "sz"},
    "upper": {"ß": "ẞ"},
}


def simulate_typing(
    engine: FastTypeEngine, events: List[Union[KeyEvent, ResetEvent, str]]
) -> str:
    """Mô phỏng một ô nhập văn bản nhận chuỗi sự kiện phím."""
    screen: List[str] = []
    for ev in events:
        if isinstance(ev, str):
            key_ev: Union[KeyEvent, ResetEvent] = KeyEvent(
                char=ev, is_upper=ev.isupper(), is_printable=True
            )
        else:
            key_ev = ev

        action = engine.process_event(key_ev)
        if isinstance(action, Passthrough):
            if isinstance(key_ev, KeyEvent) and key_ev.is_printable and key_ev.char:
                screen.append(key_ev.char)
        elif isinstance(action, Replace):
            for _ in range(action.delete_n):
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
        events = ["a", ResetEvent(reason="navigation"), "e"]
        self.assertEqual(simulate_typing(self.engine, events), "ae")

    def test_12_13_14_name_vni_sequence(self):
        events = ["N", "e", "3"]
        self.assertEqual(simulate_typing(self.engine, events), "Në")

        self.engine.reset()
        events.append("3")
        self.assertEqual(simulate_typing(self.engine, events), "Ne3")

        self.engine.reset()
        events.append("3")
        self.assertEqual(simulate_typing(self.engine, events), "Ne33")
        
    def test_15_non_printable_resets_buffer(self):
        events = ["a", KeyEvent(char="", is_printable=False), "e"]
        self.assertEqual(simulate_typing(self.engine, events), "ae")

    def test_16_no_active_pack(self):
        self.engine.set_pack(None)
        self.assertEqual(simulate_typing(self.engine, ["a", "e"]), "ae")

    def test_17_duplicate_trigger_error_g01(self):
        bad_pack = {
            "meta": {"id": "bad"},
            "rules": {"ä": "ae", "æ": "AE"},
        }
        _, issues = build_pack_from_dict(bad_pack)
        error_codes = [i.code for i in issues if i.level == "ERROR"]
        self.assertIn("G-01", error_codes)

    def test_18_shadowed_prefix_rule_g02(self):
        warn_pack = {
            "meta": {"id": "warn"},
            "rules": {"ä": "a:", "ā": "a:b"},
        }
        _, issues = build_pack_from_dict(warn_pack)
        codes = [i.code for i in issues]
        self.assertIn("G-02", codes)

    def test_benchmark_under_1ms(self):
        iterations = 10_000
        seq = [
            KeyEvent(char="a"),
            KeyEvent(char="e"),
            KeyEvent(char="e"),
            KeyEvent(char=" "),
        ]
        start = time.perf_counter()
        for _ in range(iterations):
            for ev in seq:
                self.engine.process_event(ev)
        elapsed_ms = (time.perf_counter() - start) * 1000
        avg_ms_per_key = elapsed_ms / (iterations * len(seq))
        self.assertLess(avg_ms_per_key, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)