# tests/test_ja_hiragana.py
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


class TestJaHiragana(unittest.TestCase):
    def setUp(self):
        pm = PackManager()
        pm.discover_modes()
        pack, issues = pm.load_pack("ja_hiragana")
        self.assertEqual([i for i in issues if i.level == "ERROR"], [])
        self.engine = FastTypeEngine(pack)

    def test_basic_and_digraphs(self):
        self.assertEqual(simulate_typing(self.engine, "konnnichiha"), "こんにちは")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "shashin"), "しゃしn")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "shashinn"), "しゃしん")

    def test_sokuon_and_hatsuon(self):
        self.assertEqual(simulate_typing(self.engine, "gakkou"), "がっこう")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "senpai"), "せんぱい")
        self.engine.reset()
        self.assertEqual(simulate_typing(self.engine, "shin'ai"), "しんあい")

    def test_backspace(self):
        self.assertEqual(simulate_typing(self.engine, "sh\ba"), "さ")


if __name__ == "__main__":
    unittest.main()