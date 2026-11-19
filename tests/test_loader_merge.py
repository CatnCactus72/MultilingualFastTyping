# tests/test_loader_merge.py
import unittest
from core.loader import build_pack_from_dict


class TestLoaderMergeLayers(unittest.TestCase):
    def test_three_layer_merge_script_pack_override(self):
        script_data = {
            "script": "latn",
            "normalization": "NFC",
            "word_boundaries": [" ", "."],
            "upper": {"ß": "ẞ"},
        }
        manifest_data = {
            "id": "de",
            "name": "Deutsch",
            "script": "latn",
            "composer": "mapping",
            "badge": {"label": "DE", "color": "#ef6c00"},
        }
        pack_data = {
            "rules": {"ä": ["a3"], "ß": ["sz"]},
        }
        override_data = {
            "rules": {"ä": ["ae"]},
            "disable": ["ß"],
        }

        pack, issues = build_pack_from_dict(
            pack_data,
            override_data=override_data,
            script_data=script_data,
            manifest_data=manifest_data,
        )
        errors = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(errors, [])
        self.assertEqual(pack.id, "de")
        self.assertEqual(pack.badge["label"], "DE")
        self.assertEqual(pack.trigger_map.get("ae"), "ä")
        self.assertNotIn("a3", pack.trigger_map)
        self.assertNotIn("sz", pack.trigger_map)
        self.assertEqual(pack.upper_map.get("ß"), "ẞ")


if __name__ == "__main__":
    unittest.main()