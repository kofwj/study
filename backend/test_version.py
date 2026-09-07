# -*- coding: utf-8 -*-
import pytest

import version


def test_next_version_patch_and_carry():
    assert version.next_version("0.1.0") == "0.1.1"
    assert version.next_version("V 0.1.9") == "0.1.10"
    assert version.next_version("0.1.99") == "0.2.0"
    assert version.next_version("0.99.99") == "1.0.0"
    assert version.next_version("1.0.0") == "1.0.1"


def test_next_version_rejects_bad_values():
    with pytest.raises(ValueError):
        version.next_version("1.2")
    with pytest.raises(ValueError):
        version.next_version("0.1.100")
    with pytest.raises(ValueError):
        version.next_version("99.99.99")


def test_bump_version_file(tmp_path):
    p = tmp_path / "VERSION"
    p.write_text("0.1.98\n", encoding="utf-8")
    assert version.bump_version_file(p) == "0.1.99"
    assert p.read_text(encoding="utf-8") == "0.1.99\n"
    assert version.bump_version_file(p) == "0.2.0"
