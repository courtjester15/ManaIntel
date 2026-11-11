from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = attrs.get("src") if tag == "script" else attrs.get("href") if tag == "link" else None
        if value and not value.startswith("http"):
            self.paths.append(value.split("?")[0])


class WebAssetTests(unittest.TestCase):
    def test_every_entrypoint_asset_exists_and_is_in_both_deployment_paths(self):
        root = Path(__file__).resolve().parents[1]
        for entry in (root / "web").glob("*.html"):
            parser = Assets()
            parser.feed(entry.read_text(encoding="utf-8"))
            self.assertEqual(len(parser.paths), len(set(parser.paths)), entry.name)
            for asset in parser.paths:
                self.assertTrue((root / "web" / asset).is_file(), asset)
                for workflow in ("ffw.yml", "review.yml"):
                    text = (root / ".github/workflows" / workflow).read_text(encoding="utf-8")
                    self.assertRegex(text, rf"cp [^\n]*web/{re.escape(asset)}(?: |\n)", f"{workflow}: {asset}")
