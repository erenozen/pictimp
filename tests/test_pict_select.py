"""Tests for platform mapping and vendor selection."""
import pytest
from unittest.mock import patch
from pairwise_cli.pict import get_vendor_target, UnsupportedPlatformError

def test_vendor_target_windows():
    with patch('platform.system', return_value='Windows'):
        with patch('platform.machine', return_value='AMD64'):
            assert get_vendor_target() == 'win-x64'

def test_vendor_target_linux():
    with patch('platform.system', return_value='Linux'):
        with patch('platform.machine', return_value='x86_64'):
            assert get_vendor_target() == 'linux-x64'

def test_vendor_target_macos_is_unsupported():
    with patch('platform.system', return_value='Darwin'):
        with patch('platform.machine', return_value='x86_64'):
            with pytest.raises(UnsupportedPlatformError):
                get_vendor_target()
            
def test_vendor_target_unsupported():
    with patch('platform.system', return_value='FreeBSD'):
        with patch('platform.machine', return_value='x86_64'):
            with pytest.raises(RuntimeError):
                get_vendor_target()
