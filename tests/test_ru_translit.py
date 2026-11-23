# tests/test_ru_translit.py
import unittest
from core.composers.base import KeyEvent, Passthrough, Replace
from core.engine import FastTypeEngine
from core.pack_manager import PackManager


def simulate_typing(engine: FastTypeEngine, text: str) -> str:
    out = ""
    for ch in text:
        if ch == "\b":
            act = engine.backspace()
            if isinstance(act, Passthrough):
                out = out[:-1]
            elif isinstance(act, Replace):
                out = (out[:-act.delete_n] if act.delete_n else out) + act.text
            continue
        act = engine.process_event(KeyEvent(char=ch, is_upper=ch.isupper()))
        if isinstance(act, Passthrough):
            out += ch
        elif isinstance(act, Replace):
            out = (out[:-act.delete_n] if act.delete_n else out) + act.text
    return out


class TestRussianTranslit(unittest.TestCase):
    def setUp(self):
        pm = PackManager()
        pm.discover_modes()
        pack, issues = pm.load_pack("ru")
        self.assertEqual([i for i in issues if i.level == "ERROR"], [])
        self.engine = FastTypeEngine(pack)

    def test_vesnushchatyy_and_shh(self):
        # веснушчатый với 'yy' -> 'ый' và cụm 'шч' không bị gộp nhầm thành 'щ'
        self.assertEqual(simulate_typing(self.engine, "vecnushchatyy"), "веснушчатый")
        self.engine.reset()
        # 'sh' -> 'ш', thêm 'h' thành 'shh' -> 'щ'
        self.assertEqual(simulate_typing(self.engine, "shhuka"), "щука")

    def test_yo_and_case(self):
        self.assertEqual(simulate_typing(self.engine, "yozh"), "ёж")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "Yozh"), "Ёж")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "Privet, mir!"), "Привет, мир!")

    def test_stress_mark_and_revert(self):
        # Gắn dấu trọng âm NFC và hoàn tác khi gõ lặp
        self.assertEqual(simulate_typing(self.engine, "molo'ko"), "моло\u0301ко")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "mo''"), "мо'")

    def test_backspace(self):
        # 'shh' -> 'щ', backspace lùi về 'sh' -> 'ш'
        self.assertEqual(simulate_typing(self.engine, "shh\ba"), "а")


if __name__ == "__main__":
    unittest.main()