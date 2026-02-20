"""Filesystem mocking and extraction fallback testing."""
import os
import stat
import pytest
from unittest.mock import patch
from pairwise_cli.pict import get_extracted_pict_path

def test_cache_extraction_fallbacks(tmp_path):
    # Mocking os.makedirs to raise OSError for the typical paths,
    # forcing it to fallback to tempdir.
    
    # We will let tmp_path be the fallback it finally reaches successfully
    
    orig_makedirs = os.makedirs
    def mock_makedirs(name, exist_ok=False, *args, **kwargs):
        if "pairwise-cli" in str(name) and "tmp" not in str(name).lower() and "temp" not in str(name).lower():
            raise OSError("Permission denied mocked")
        # else allow
        orig_makedirs(name, exist_ok=exist_ok)

    with patch('os.makedirs', side_effect=mock_makedirs):
        # Even with mocked failures, get_extracted_pict_path should find the tempdir
        # fallback and return a valid path instead of raising RuntimeError.
        try:
            path = get_extracted_pict_path()
            assert "pairwise-cli" in path
        except RuntimeError as e:
            pytest.fail(f"Extraction fallback failed to find temp directory override: {e}")

def test_extraction_complete_failure_raises():
    def mock_makedirs_fail_all(name, exist_ok=False):
        raise OSError("Permission denied on all")
        
    with patch('os.makedirs', side_effect=mock_makedirs_fail_all):
        with pytest.raises(RuntimeError, match="Could not find a writable cache directory"):
            get_extracted_pict_path()
