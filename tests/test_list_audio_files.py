from bb_audio import list_audio_files
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_list_audio_files_finds_only_audio(tmp_path):
    # Create files
    (tmp_path / "test.wav").write_bytes(b"fake")
    (tmp_path / "test.flac").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "image.png").write_bytes(b"fake")

    files = list_audio_files(tmp_path)

    names = {Path(f).name for f in files}

    assert "test.wav" in names
    assert "test.flac" in names
    assert "notes.txt" not in names
    assert "image.png" not in names


def test_list_audio_files_ignores_directories(tmp_path):
    (tmp_path / "audio.wav").write_bytes(b"fake")
    (tmp_path / "subfolder").mkdir()
    (tmp_path / "subfolder" / "nested.wav").write_bytes(b"fake")

    files = list_audio_files(tmp_path)

    names = {Path(f).name for f in files}

    assert "audio.wav" in names
    assert "nested.wav" not in names


def test_list_audio_files_returns_full_paths(tmp_path):
    (tmp_path / "sound.wav").write_bytes(b"fake")

    files = list_audio_files(tmp_path)

    assert len(files) == 1
    assert str(tmp_path) in files[0]


def test_list_audio_files_empty_folder(tmp_path):
    files = list_audio_files(tmp_path)
    assert files == []
