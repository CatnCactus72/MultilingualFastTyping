# tests/test_zh_pinyin.py
import unittest
from core.composers.base import KeyEvent, Passthrough, Replace
from core.engine import FastTypeEngine
from core.pack_manager import DEFAULT_LANGUAGES_DIR, PackManager


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


class TestZhPinyin(unittest.TestCase):
    def setUp(self):
        self.manager = PackManager(packs_dir=DEFAULT_LANGUAGES_DIR)
        self.manager.discover_modes()
        self.pack, self.issues = self.manager.load_pack("zh_pinyin")
        self.engine = FastTypeEngine(self.pack)

    def _type(self, keys: str) -> str:
        self.engine.reset()
        return simulate_typing(self.engine, keys)

    def test_01_manifest_and_pack_loaded_cleanly(self):
        errors = [i for i in self.issues if i.level == "ERROR"]
        self.assertEqual(errors, [])
        self.assertEqual(self.pack.composer, "zh_pinyin")
        self.assertEqual(self.pack.badge["label"], "PIN")

    def test_02_tone_placement_priority_a_o_e_and_iu_ui(self):
        # Ưu tiên a > o > e
        self.assertEqual(self._type("lian3"), "liǎn")
        self.assertEqual(self._type("hao3"), "hǎo")
        self.assertEqual(self._type("guo2"), "guó")
        self.assertEqual(self._type("xie4"), "xiè")
        # Quy tắc iu -> u, ui -> i
        self.assertEqual(self._type("liu2"), "liú")
        self.assertEqual(self._type("gui4"), "guì")

    def test_03_umlaut_u_two_layer_marks(self):
        # Gõ qua phím 'v' (v_as_umlaut = true)
        self.assertEqual(self._type("nv3"), "nǚ")
        self.assertEqual(self._type("lv2"), "lǘ")
        self.assertEqual(self._type("nv4"), "nǜ")
        self.assertEqual(self._type("nv1"), "nǖ")
        # Gõ qua 'u' + '6' (bất kể thứ tự thanh điệu và phím umlaut)
        self.assertEqual(self._type("nu63"), "nǚ")
        self.assertEqual(self._type("nu36"), "nǚ")

    def test_04_continuous_multi_syllable_and_apostrophe(self):
        # Tự động chốt âm tiết khi gặp phụ âm đầu âm tiết mới
        self.assertEqual(self._type("cong1ming2"), "cōngmíng")
        self.assertEqual(self._type("ni3hao3"), "nǐhǎo")
        self.assertEqual(self._type("zhong1guo2"), "zhōngguó")
        # Tách âm tiết bằng dấu nháy đơn '
        self.assertEqual(self._type("xi1'an1"), "xī'ān")
        self.assertEqual(self._type("nv3'er2"), "nǚ'ér")

    def test_05_tone_clear_revert_and_case(self):
        # Xóa thanh bằng phím '0'
        self.assertEqual(self._type("ma10"), "ma")
        # Gõ lặp phím thanh điệu -> hoàn tác và chuyển sang raw_mode
        self.assertEqual(self._type("ma11"), "ma1")
        # Giữ nguyên chữ hoa đầu âm tiết
        self.assertEqual(self._type("Bei3jing1"), "Běijīng")

    def test_06_backspace_and_restore_invalid_on_boundary(self):
        # Backspace xóa ký tự cuối và tự tính lại vị trí dấu thanh
        self.assertEqual(self._type("lian3\b"), "liǎ")
        self.assertEqual(self._type("cong1ming2\b"), "cōngmín")
        # Khôi phục từ sai chính tả khi gặp khoảng trắng (restore_invalid = true)
        self.assertEqual(self._type("test1 "), "test1 ")


if __name__ == "__main__":
    unittest.main(verbosity=2)