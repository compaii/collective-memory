"""Explicit text publication must never discover or load an embedding model."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IndexModeTests(unittest.TestCase):
    def run_case(self, mode, program):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'mapa').mkdir()
            (root / 'mapa/index.md').write_text('# Archive\n\nRetained source oraclemarker.\n')
            env = {**os.environ, 'MAPA_ROOT': tmp, 'MAPA_DATA': str(root / '.mapa'),
                   'MAPA_INDEX_MODE': mode, 'PYTHONPATH': str(ROOT / 'mapa')}
            subprocess.run([sys.executable, '-c', program], env=env, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_explicit_fts_publishes_searchable_text_without_model_discovery(self):
        self.run_case('fts-only', '''
import tier1, sqlite3
from unittest.mock import patch
with patch.object(tier1, 'vector_available', side_effect=AssertionError('model discovery forbidden')):
    tier1.do_index('curated')
    assert tier1.health_dict()['runtime_vector']=='not_probed'
con=sqlite3.connect(tier1.DB)
assert con.execute("select v from meta where k='mode'").fetchone()[0]=='fts-only'
assert con.execute("select count(*) from chunks_fts where chunks_fts match 'oraclemarker'").fetchone()[0]>0
''')

    def test_unknown_mode_fails_before_publication(self):
        self.run_case('mistyped', '''
import tier1
from unittest.mock import patch
with patch.object(tier1, 'vector_available', side_effect=AssertionError('model discovery forbidden')):
    try: tier1.do_index('curated')
    except ValueError as error: assert 'MAPA_INDEX_MODE' in str(error)
    else: raise AssertionError('Invalid mode accepted')
''')


if __name__ == '__main__':
    unittest.main()
