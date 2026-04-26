from __future__ import annotations

import subprocess


def test_readme_quickstart_mapping_is_valid() -> None:
    result = subprocess.run(
        ["bash", "ops/scripts/verify_readme_quickstart.sh", "--readme-only"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
