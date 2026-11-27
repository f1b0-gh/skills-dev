"""Repository checks should catch broken packages without parsing code as links."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from test_examples import REPO, SCRATCH
sys.path.insert(0, str(REPO / 'scripts'))
from validate import validate


class RepositoryValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='structure-', dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'skills/demo/SKILL.md'
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text('---\nname: demo\ndescription: Use when demonstrating a skill.\n---\n# Demo\n')
        (self.root / 'provenance').mkdir()
        (self.root / 'provenance/imports.json').write_text(json.dumps({'files': [], 'modified': [], 'omitted': []}))

    def append(self, text):
        with self.skill.open('a') as f:
            f.write(text)

    def test_minimal_valid_bundle(self):
        self.assertEqual(validate(self.root), [])

    def test_missing_reference_rejected(self):
        self.append('[Guide](references/missing.md)\n')
        self.assertTrue(any('missing.md' in e for e in validate(self.root)))

    def test_code_examples_are_not_file_links(self):
        self.append('```rust\n/// [Self](Self::new)\n```\n`[text](path)`\n')
        self.assertEqual(validate(self.root), [])

    def test_escaping_link_rejected(self):
        self.append('[Outside](../../../outside.md)\n')
        self.assertTrue(any('escaping' in e for e in validate(self.root)))

    def test_name_must_match_install_directory(self):
        self.skill.write_text(self.skill.read_text().replace('name: demo', 'name: different'))
        self.assertTrue(any('invalid name' in e for e in validate(self.root)))

    def test_import_edits_must_be_declared(self):
        (self.root / 'provenance/imports.json').write_text(json.dumps({'files': [{'path': 'skills/demo/SKILL.md', 'source_sha256': '0' * 64}], 'modified': [], 'omitted': []}))
        self.assertTrue(any('modification inventory' in e for e in validate(self.root)))

if __name__ == '__main__':
    unittest.main()
