from bb_audio import should_write_file
import sys
from pathlib import Path

# Ensure the project root (Audio_Tools/) is on the import path when running tests
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_new_file_returns_new(tmp_path):
    output_path = tmp_path / "normalized_test.wav"  # does not exist yet
    should_write, reason = should_write_file(
        str(output_path), overwrite=False, dry_run=False)
    assert should_write is True
    assert reason == "new"


def test_existing_file_without_overwrite_returns_exists(tmp_path):
    output_path = tmp_path / "normalized_test.wav"
    output_path.write_bytes(b"fake")  # create the file

    should_write, reason = should_write_file(
        str(output_path), overwrite=False, dry_run=False)
    assert should_write is False
    assert reason == "exists"


def test_existing_file_with_overwrite_returns_overwrite(tmp_path):
    output_path = tmp_path / "normalized_test.wav"
    output_path.write_bytes(b"fake")  # create the file

    should_write, reason = should_write_file(
        str(output_path), overwrite=True, dry_run=False)
    assert should_write is True
    assert reason == "overwrite"


def test_existing_file_in_dry_run_without_overwrite_returns_dry_run_skip(tmp_path):
    output_path = tmp_path / "normalized_test.wav"
    output_path.write_bytes(b"fake")  # create the file

    should_write, reason = should_write_file(
        str(output_path), overwrite=False, dry_run=True)
    assert should_write is False
    assert reason == "dry_run_skip"
