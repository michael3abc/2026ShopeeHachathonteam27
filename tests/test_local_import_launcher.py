from pathlib import Path
import runpy

import pytest

LAUNCHER = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/local_import.py"))


def test_dotenv_is_literal_and_does_not_execute(tmp_path):
    path = tmp_path / "settings"
    marker = tmp_path / "must-not-exist"
    path.write_text(f"VALUE='$(touch {marker})'\nOTHER='hello world' # comment\n")
    assert LAUNCHER["read_env"](path) == {"VALUE": f"$(touch {marker})", "OTHER": "hello world"}
    assert not marker.exists()


@pytest.mark.parametrize("line", ["not an assignment", "1KEY=x", "KEY=unquoted space"])
def test_dotenv_rejects_invalid_assignment(tmp_path, line):
    path = tmp_path / "settings"
    path.write_text(line)
    with pytest.raises(ValueError):
        LAUNCHER["read_env"](path)
