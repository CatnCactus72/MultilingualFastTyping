# tests/test_m1_packs.py
from pathlib import Path
import tempfile
import unittest

from core.engine import FastTypeEngine
from core.pack_manager import DEFAULT_LANGUAGES_DIR, PackManager
from tests.test_core import simulate_typing

REQUIRED_CHARS = {
    "fr": "é è ê ë à â î ï ô ù û ü ÿ ç œ æ".split(),
    "de": "ä ö ü ß".split(),
    "es": "á é í ó ú ü ñ ¿ ¡".split(),
    "it": "à è é ì í î ò ó ù ú".split(),
}

EXPECTED_UPPER = {
    "ß": "ẞ",
    "¿": "¿",
    "¡": "¡",
}

EXPECTED_BADGES = {
    "fr": "FRA",
    "de": "DEU",
    "es": "ESP",
    "it": "ITA",
    "vi_vni": "VNI",
    "vi_telex": "TLX",
}


class TestM1LanguagePacks(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.manager = PackManager(
            packs_dir=DEFAULT_LANGUAGES_DIR, config_dir=self.config_dir
        )
        self.manager.load_enabled_packs()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_all_6_packs_loaded_with_3_letter_badges(self):
        self.assertEqual(
            set(self.manager.packs.keys()),
            {"fr", "de", "es", "it", "vi_vni", "vi_telex"},
        )
        for pack_id, pack in self.manager.packs.items():
            errors = [i for i in self.manager.issues[pack_id] if i.level == "ERROR"]
            self.assertEqual(errors, [], f"Gói {pack_id} có lỗi: {errors}")
            self.assertEqual(pack.symbol, EXPECTED_BADGES[pack_id])

    def test_fr07_all_required_lowercase_and_uppercase_characters(self):
        for pack_id, chars in REQUIRED_CHARS.items():
            pack = self.manager.packs[pack_id]
            engine = FastTypeEngine(pack)

            output_to_trigger = {}
            for trig, out in pack.trigger_map.items():
                output_to_trigger.setdefault(out, trig)

            for ch in chars:
                self.assertIn(ch, output_to_trigger, f"Gói {pack_id} thiếu ký tự '{ch}'")
                trig = output_to_trigger[ch]

                engine.reset()
                res_lower = simulate_typing(engine, list(trig))
                self.assertEqual(res_lower, ch, f"[{pack_id}] Gõ '{trig}' phải ra '{ch}'")

                engine.reset()
                upper_trig = list(trig)
                for idx, c in enumerate(upper_trig):
                    if c.isalpha():
                        upper_trig[idx] = c.upper()
                        break
                expected_up = EXPECTED_UPPER.get(ch, ch.upper())
                res_upper = simulate_typing(engine, upper_trig)
                self.assertEqual(
                    res_upper,
                    expected_up,
                    f"[{pack_id}] Gõ '{''.join(upper_trig)}' phải ra '{expected_up}'",
                )

    def test_fr18_user_override_and_disable(self):
        pack, _ = self.manager.save_user_override(
            pack_id="de",
            rules={"ä": ["ae"]},
            disable=["ß"],
        )
        engine = FastTypeEngine(pack)

        self.assertEqual(simulate_typing(engine, ["a", "3"]), "a3")
        engine.reset()
        self.assertEqual(simulate_typing(engine, ["a", "e"]), "ä")
        engine.reset()
        self.assertEqual(simulate_typing(engine, ["s", "z"]), "sz")


if __name__ == "__main__":
    unittest.main(verbosity=2)