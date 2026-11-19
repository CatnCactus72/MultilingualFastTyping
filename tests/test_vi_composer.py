# tests/test_vi_composer.py
import unittest
from core.engine import FastTypeEngine
from core.pack_manager import DEFAULT_LANGUAGES_DIR, PackManager
from core.testing.roundtrip import simulate_sequence
from languages.vi.vi_common.bindings import (
    PRESET_TELEX,
    PRESET_VNI,
    validate_vi_bindings_static,
)
from languages.vi.vi_common.roundtrip import validate_vi_roundtrip_c07
from languages.vi.vi_telex.composer import ViTelexComposer
from languages.vi.vi_vni.composer import ViVniComposer


class TestVietnameseStage2(unittest.TestCase):

    def setUp(self):
        self.manager = PackManager(packs_dir=DEFAULT_LANGUAGES_DIR)
        self.vni_pack, self.vni_issues = self.manager.load_pack("vi_vni")
        self.telex_pack, self.telex_issues = self.manager.load_pack("vi_telex")

    def _type_vni(self, keys: str, pack=None) -> str:
        comp = ViVniComposer(pack or self.vni_pack)
        return simulate_sequence(comp, keys)

    def _type_telex(self, keys: str, pack=None) -> str:
        comp = ViTelexComposer(pack or self.telex_pack)
        return simulate_sequence(comp, keys)

    def test_01_manifests_and_packs_loaded_cleanly(self):
        self.assertEqual([i for i in self.vni_issues if i.level == "ERROR"], [])
        self.assertEqual([i for i in self.telex_issues if i.level == "ERROR"], [])
        self.assertEqual(self.vni_pack.composer, "vi_vni")
        self.assertEqual(self.vni_pack.badge["label"], "VNI")
        self.assertEqual(self.telex_pack.composer, "vi_telex")
        self.assertEqual(self.telex_pack.badge["label"], "TLX")

    def test_02_vni_free_mark_and_tone_placement(self):
        self.assertEqual(self._type_vni("toan2"), "toàn")
        self.assertEqual(self._type_vni("toa2n"), "toàn")
        self.assertEqual(self._type_vni("tie6n1"), "tiến")
        self.assertEqual(self._type_vni("tie61n"), "tiến")
        self.assertEqual(self._type_vni("nguoi72"), "người")
        self.assertEqual(self._type_vni("nguoi27"), "người")
        self.assertEqual(self._type_vni("d9a8ng"), "đăng")
        self.assertEqual(self._type_vni("Viet65"), "Việt")

    def test_03_telex_free_mark_and_tone_placement(self):
        self.assertEqual(self._type_telex("toanf"), "toàn")
        self.assertEqual(self._type_telex("toafn"), "toàn")
        self.assertEqual(self._type_telex("tieens"), "tiến")
        self.assertEqual(self._type_telex("nguowif"), "người")
        self.assertEqual(self._type_telex("ddangw"), "đăng")
        self.assertEqual(self._type_telex("Vieetj"), "Việt")

    def test_04_tone_repositioning_hoa_to_hoan(self):
        self.assertEqual(self._type_vni("hoa2"), "hòa")
        self.assertEqual(self._type_vni("hoa2n"), "hoàn")
        self.assertEqual(self._type_telex("hoaf"), "hòa")
        self.assertEqual(self._type_telex("hoafn"), "hoàn")

    def test_05_modern_vs_classic_tone_style(self):
        classic_vni = {"options": {"tone_style": "classic", "validate": "strict"}}
        classic_telex = {"options": {"tone_style": "classic", "validate": "strict"}}

        self.assertEqual(self._type_vni("hoa2"), "hòa")
        self.assertEqual(self._type_vni("thuy3"), "thủy")
        self.assertEqual(self._type_vni("hoa2", classic_vni), "hoà")
        self.assertEqual(self._type_vni("thuy3", classic_vni), "thuỷ")
        self.assertEqual(self._type_vni("toan1", classic_vni), "toán")
        self.assertEqual(self._type_vni("huynh2", classic_vni), "huỳnh")

        self.assertEqual(self._type_telex("hoaf", classic_telex), "hoà")
        self.assertEqual(self._type_telex("thuyr", classic_telex), "thuỷ")

    def test_06_open_uo_exception_huo_thuo(self):
        self.assertEqual(self._type_vni("huo7"), "huơ")
        self.assertEqual(self._type_vni("thuo73"), "thuở")
        self.assertEqual(self._type_vni("thuo73ng"), "thưởng")
        self.assertEqual(self._type_telex("huow"), "huơ")
        self.assertEqual(self._type_telex("thuowr"), "thuở")
        self.assertEqual(self._type_telex("thuowrng"), "thưởng")

    def test_07_revert_and_raw_mode(self):
        # VNI
        self.assertEqual(self._type_vni("a6"), "â")
        self.assertEqual(self._type_vni("a66"), "a6")
        self.assertEqual(self._type_vni("d9"), "đ")
        self.assertEqual(self._type_vni("d99"), "d9")
        self.assertEqual(self._type_vni("a1"), "á")
        self.assertEqual(self._type_vni("a11"), "a1")
        # Telex
        self.assertEqual(self._type_telex("aa"), "â")
        self.assertEqual(self._type_telex("aaa"), "aa")
        self.assertEqual(self._type_telex("dd"), "đ")
        self.assertEqual(self._type_telex("ddd"), "dd")
        self.assertEqual(self._type_telex("xooong"), "xoong")
        self.assertEqual(self._type_telex("ooocs"), "óoc")

    def test_08_backspace_recalculates_tone(self):
        self.assertEqual(self._type_vni("toa2n\b"), "tòa")
        self.assertEqual(self._type_vni("tie6n1\b"), "tiế")
        self.assertEqual(self._type_telex("toafn\b"), "tòa")

    def test_09_restore_invalid_words(self):
        self.assertEqual(self._type_telex("windows "), "windows ")
        self.assertEqual(self._type_vni("mp3 "), "mp3 ")

    def test_10_h3_stop_coda_restriction(self):
        self.assertEqual(self._type_vni("hoac1"), "hoác")
        self.assertEqual(self._type_vni("hoac5"), "hoạc")
        self.assertEqual(self._type_vni("hoac2"), "hoac2")

    def test_11_c_vi_conflict_rules(self):
        bad_c01 = list(PRESET_TELEX) + [{"op": "MARK_CIRC", "triggers": [{"key": "w"}]}]
        self.assertIn("C-VI-01", [i.code for i in validate_vi_bindings_static(bad_c01)])

        bad_c02 = [{"op": "TONE_SAC", "triggers": [{"key": "n"}]}]
        self.assertIn("C-VI-02", [i.code for i in validate_vi_bindings_static(bad_c02)])

        bad_c03 = [
            b if b["op"] != "MARK_CIRC" else {"op": "MARK_CIRC", "triggers": [{"repeat": "a"}, {"repeat": "e"}]}
            for b in PRESET_TELEX
        ]
        self.assertIn("C-VI-03", [i.code for i in validate_vi_bindings_static(bad_c03)])

    def test_12_full_roundtrip_vni_and_telex(self):
        vni_cfg = {"options": {"tone_style": "modern"}, "bindings": PRESET_VNI}
        vni_errors = validate_vi_roundtrip_c07(
            vni_cfg, composer_factory=lambda: ViVniComposer(vni_cfg)
        )
        self.assertEqual(vni_errors, [])

        telex_cfg = {"options": {"tone_style": "modern"}, "bindings": PRESET_TELEX}
        telex_errors = validate_vi_roundtrip_c07(
            telex_cfg, composer_factory=lambda: ViTelexComposer(telex_cfg)
        )
        self.assertEqual(telex_errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)