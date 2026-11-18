# tests/test_m1_packs.py
from pathlib import Path
import tempfile
import unittest

from core.engine import FastTypeEngine
from core.pack_manager import DEFAULT_PACKS_DIR, PackManager
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


class TestM1LanguagePacks(unittest.TestCase):

  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    self.config_dir = Path(self.temp_dir.name)
    self.manager = PackManager(
        packs_dir=DEFAULT_PACKS_DIR, config_dir=self.config_dir
    )
    self.manager.load_enabled_packs()

  def tearDown(self):
    self.temp_dir.cleanup()

  def test_all_4_packs_loaded_without_errors(self):
    self.assertEqual(set(self.manager.packs.keys()), {"fr", "de", "es", "it"})
    for pack_id, issues in self.manager.issues.items():
      errors = [i for i in issues if i.level == "ERROR"]
      self.assertEqual(errors, [], f"Gói {pack_id} có lỗi: {errors}")

  def test_fr07_all_required_lowercase_and_uppercase_characters(self):
    for pack_id, chars in REQUIRED_CHARS.items():
      pack = self.manager.packs[pack_id]
      engine = FastTypeEngine(pack)

      # Đảo ngược trigger_map để lấy ít nhất 1 trigger cho mỗi ký tự đầu ra
      output_to_trigger = {}
      for trig, out in pack.trigger_map.items():
        output_to_trigger.setdefault(out, trig)

      for ch in chars:
        self.assertIn(
            ch, output_to_trigger, f"Gói {pack_id} thiếu ký tự '{ch}'"
        )
        trig = output_to_trigger[ch]

        # Kiểm tra gõ chữ thường
        engine.reset()
        res_lower = simulate_typing(engine, list(trig))
        self.assertEqual(
            res_lower, ch, f"[{pack_id}] Gõ '{trig}' phải ra '{ch}'"
        )

        # Kiểm tra gõ chữ hoa (viết hoa chữ cái đầu tiên trong trigger)
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
    # Người dùng đổi trigger của 'ä' thành 'a:' và tắt quy tắc 'ß' trong tiếng Đức
    pack, _ = self.manager.save_user_override(
        pack_id="de",
        rules={"ä": ["a:"]},
        disable=["ß"],
    )
    engine = FastTypeEngine(pack)

    # Trigger cũ 'ae' không còn biến đổi thành 'ä'
    self.assertEqual(simulate_typing(engine, ["a", "e"]), "ae")
    # Trigger mới 'a:' biến đổi thành 'ä'
    engine.reset()
    self.assertEqual(simulate_typing(engine, ["a", ":"]), "ä")
    # Quy tắc 'ß' đã bị disable nên gõ 'sz' giữ nguyên 'sz'
    engine.reset()
    self.assertEqual(simulate_typing(engine, ["s", "z"]), "sz")


if __name__ == "__main__":
  unittest.main(verbosity=2)