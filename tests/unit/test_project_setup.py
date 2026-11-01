"""Tests for the initial Python project setup."""

import food_delivery_lakehouse


def test_package_is_importable() -> None:
    """Verify that the package is available through the src layout."""
    assert food_delivery_lakehouse.__name__ == "food_delivery_lakehouse"
