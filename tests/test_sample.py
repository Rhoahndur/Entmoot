"""
Sample tests to verify the test framework is working correctly.
"""

import pytest

from entmoot.utils.version import format_version_info, get_version


def test_get_version() -> None:
    """Test that get_version returns the correct version."""
    version = get_version()
    assert version == "0.1.0"
    assert isinstance(version, str)


def test_format_version_info() -> None:
    """Test that format_version_info returns expected structure."""
    info = format_version_info()
    assert isinstance(info, dict)
    assert "version" in info
    assert "project" in info
    assert "description" in info
    assert info["version"] == "0.1.0"
    assert info["project"] == "Entmoot"


def test_sample_math() -> None:
    """Simple test to verify pytest is working."""
    assert 1 + 1 == 2
    assert 2 * 2 == 4


@pytest.mark.unit
def test_marked_test() -> None:
    """Test with unit marker."""
    assert True


class TestSampleClass:
    """Sample test class to verify class-based tests work."""

    def test_in_class(self) -> None:
        """Test method in class."""
        assert "hello".upper() == "HELLO"

    def test_list_operations(self) -> None:
        """Test basic list operations."""
        test_list = [1, 2, 3]
        test_list.append(4)
        assert len(test_list) == 4
        assert test_list[-1] == 4
