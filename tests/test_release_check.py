from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.release_check import _read_text


class ReleaseCheckTests(unittest.TestCase):
    def test_read_text_normalizes_platform_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "SKILL.md"
            path.write_bytes(b"---\r\nname: example\r\n---\rbody\r")

            self.assertEqual(
                _read_text(path),
                "---\nname: example\n---\nbody\n",
            )


if __name__ == "__main__":
    unittest.main()
