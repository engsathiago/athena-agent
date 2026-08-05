from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    assert "%LOCALAPPDATA%\\athena\\athena-agent\\venv\\Scripts" in doc
    assert "Get-Command athena        # should print C:\\Users\\<you>\\AppData\\Local\\athena\\athena-agent\\venv\\Scripts\\athena.exe" in doc
    assert '$athenaBin = "$InstallDir\\venv\\Scripts"' in install
