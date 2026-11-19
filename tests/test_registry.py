# tests/test_registry.py
import unittest
import core.composers.mapping  # noqa: F401
import languages.vi  # noqa: F401
from core.composers.mapping import MappingComposer
from core.registry import get_composer_class, list_composers
from languages.vi.vi_telex.composer import ViTelexComposer
from languages.vi.vi_vni.composer import ViVniComposer


class TestComposerRegistry(unittest.TestCase):
    def test_all_composers_registered(self):
        registered = list_composers()
        self.assertIn("mapping", registered)
        self.assertIn("vi_vni", registered)
        self.assertIn("vi_telex", registered)
        self.assertIs(get_composer_class("mapping"), MappingComposer)
        self.assertIs(get_composer_class("vi_vni"), ViVniComposer)
        self.assertIs(get_composer_class("vi_telex"), ViTelexComposer)

    def test_unknown_composer_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_composer_class("non_existent_composer")


if __name__ == "__main__":
    unittest.main()