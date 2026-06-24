from pathlib import Path

import pytest

from app.analysis.pipeline import analyze_track


def test_missing_audio_file_error():
    with pytest.raises(FileNotFoundError):
        analyze_track("missing", Path("does-not-exist.mp3"))
