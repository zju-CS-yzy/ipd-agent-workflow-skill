from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKED = Path('docs/worked-projects/room-booking')


@unittest.skipUnless(shutil.which('git'), 'Git is required for checkout qualification')
class WorkedProjectCheckoutTests(unittest.TestCase):
    def test_worked_sources_keep_evidence_bytes_under_git_checkout_modes(self):
        expected = json.loads((ROOT / WORKED / 'evidence/verification.json').read_text(encoding='utf-8'))['source_sha256']
        with tempfile.TemporaryDirectory(prefix='ipd-worked-checkout-') as temporary:
            work = Path(temporary)
            seed = work / 'seed'
            seed.mkdir()

            def git(directory, *arguments):
                result = subprocess.run(['git', *arguments], cwd=directory, capture_output=True,
                                        text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                return result

            git(seed, 'init')
            files = [WORKED / 'implementation' / name for name in expected]
            files.append(WORKED / 'evidence/verification.json')
            if (ROOT / '.gitattributes').is_file():
                files.append(Path('.gitattributes'))
            for relative in files:
                target = seed / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            git(seed, '-c', 'core.autocrlf=false', 'add', '.')
            git(seed, '-c', 'user.name=Synthetic checkout fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-m', 'Seed exact worked-project evidence')
            for mode in ('true', 'false'):
                with self.subTest(autocrlf=mode):
                    checkout = work / ('checkout-' + mode)
                    git(seed, 'worktree', 'add', '--detach', '--no-checkout', str(checkout), 'HEAD')
                    git(checkout, '-c', 'core.autocrlf=' + mode, 'checkout', '--quiet', 'HEAD', '--', '.')
                    for name, expected_hash in expected.items():
                        content = (checkout / WORKED / 'implementation' / name).read_bytes()
                        self.assertEqual(hashlib.sha256(content).hexdigest(), expected_hash,
                                         'Saved byte evidence must survive Git checkout: ' + name)


if __name__ == '__main__':
    unittest.main()
