import json
import unittest
from pathlib import Path
from ffw.archive import rebuild_catalog
from tests.workspace import workspace_temp

class LegacySourceTests(unittest.TestCase):
    def test_legacy_feed_identity_is_projected_to_episodes(self):
        root = workspace_temp(self)
        target = root / 'episodes' / 'legacy'
        target.mkdir(parents=True)
        original = json.loads(Path('archive/episodes/0529-much-more-marvel/metadata.json').read_text(encoding='utf-8'))
        for field in ('source_id', 'source_name', 'source_url'):
            original['episode'].pop(field, None)
        (target / 'metadata.json').write_text(json.dumps(original), encoding='utf-8')
        index, _ = rebuild_catalog(root, production=True)
        self.assertEqual('mtg-fast-finance', index['episodes'][0]['source_id'])
        self.assertEqual('MTG Fast Finance', index['episodes'][0]['source_name'])
