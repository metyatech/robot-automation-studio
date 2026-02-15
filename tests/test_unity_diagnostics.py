from robot_automation_studio.unity_diagnostics import extract_recent_unity_compile_errors


def test_extract_recent_unity_compile_errors_returns_last_matches() -> None:
    sample = """
Some line
Library/PackageCache/foo.cs(1,1): error CS0103: Name does not exist
Other line
Library/PackageCache/bar.cs(2,2): error CS0619: Obsolete API
Library/PackageCache/baz.cs(3,3): error CS1002: ; expected
"""
    errors = extract_recent_unity_compile_errors(sample, limit=2)
    assert len(errors) == 2
    assert "error CS0619" in errors[0]
    assert "error CS1002" in errors[1]


def test_extract_recent_unity_compile_errors_returns_empty_when_none() -> None:
    errors = extract_recent_unity_compile_errors("No compiler failures here", limit=3)
    assert errors == []
