from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-release.yml"
BUILD_SCRIPT = ROOT / "scripts" / "build_windows_release.ps1"
LAUNCHER = ROOT / "start-windows.bat"
RELEASES = "https://github.com/wy165611/tunnel-traffic-digital-twin/releases/latest"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_workflow() -> dict:
    document = yaml.safe_load(read(WORKFLOW))
    assert isinstance(document, dict)
    return document


def test_workflow_yaml_and_required_jobs_are_valid():
    workflow = load_workflow()
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"pull_request", "workflow_dispatch", "push"}
    assert triggers["pull_request"]["paths"] == [
        "scripts/**",
        "start-windows.bat",
        "一键启动.bat",
        ".github/**",
        "requirements*.txt",
        "frontend/**",
    ]
    assert workflow["jobs"]["windows-release"]["runs-on"] == "windows-latest"
    assert workflow["jobs"]["windows-release"]["needs"] == [
        "ubuntu-tests",
        "windows-install-test",
        "macos-install-test",
    ]
    assert workflow["jobs"]["ubuntu-tests"]["runs-on"] == "ubuntu-latest"
    assert workflow["jobs"]["windows-install-test"]["runs-on"] == "windows-latest"
    macos_job = workflow["jobs"]["macos-install-test"]
    assert macos_job["runs-on"] == "${{ matrix.os }}"
    assert macos_job["strategy"]["matrix"]["os"] == ["macos-14"]
    assert "macos-13" not in read(WORKFLOW)
    assert "macos-15-intel" not in read(WORKFLOW)


def test_workflow_builds_smoke_tests_uploads_and_publishes_assets():
    text = read(WORKFLOW)
    assert "TunnelTwin 中文 路径 Smoke" in text
    assert "便携版 Package" in text
    assert "pwsh -NoProfile -File .\\scripts\\setup-windows.ps1" in text
    assert "run: bash scripts/setup.sh" in text
    assert "./start.sh > backend/data/logs/install-smoke.log" in text
    assert "/api/health" in text
    assert "$FrontPage" in text
    assert "$Home" not in text
    assert "$($_.Exception.Message)" in text
    assert text.count("[System.IO.FileShare]::ReadWrite") == 2
    assert "ReadAllText" not in text
    assert "Get-Content $Stdout" not in text
    assert "Log read is temporarily unavailable" in text
    assert "scripts\\smoke_video.py" in text
    assert "actions/upload-artifact@v4" in text
    assert "softprops/action-gh-release@v2" in text
    assert "startsWith(github.ref, 'refs/tags/v')" in text
    assert "TunnelTwin-Windows-x64-portable.zip" in text
    assert "TunnelTwin-Windows-x64-lite.zip" in text
    assert "SHA256SUMS.txt" in text


def test_ubuntu_job_runs_backend_and_frontend_validation():
    steps = load_workflow()["jobs"]["ubuntu-tests"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "python -m pytest" in commands
    assert "npm test" in commands
    assert "npm run build" in commands


def test_build_script_creates_frontend_models_demo_and_both_archives():
    text = read(BUILD_SCRIPT)
    assert "npm.cmd ci" in text
    assert "npm.cmd run build" in text
    assert "scripts\\download_models.py" in text
    assert "scripts\\prepare_demo.py" in text
    assert "Copy-Tree (Join-Path $Portable 'data') (Join-Path $Lite 'data') @('models')" in text
    assert "TunnelTwin-Windows-x64-portable.zip" in text
    assert "TunnelTwin-Windows-x64-lite.zip" in text
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "SHA256SUMS.txt" in text
    assert "$Size -ge 2GB" in text


def test_build_script_prepares_offline_embedded_python_correctly():
    text = read(BUILD_SCRIPT)
    assert "$env:PYTHONUTF8 = '1'" in text
    assert "$env:PYTHONIOENCODING = 'utf-8'" in text
    assert "python-$PythonVersion-embed-amd64.zip" in text
    assert "get-pip.py" in text
    assert "python*._pth" in text
    assert "'#import site'" in text
    assert "@('Lib\\site-packages', '..', 'import site')" in text
    assert "--target" not in text
    assert "'torch', 'torchvision', '-r'" in text
    assert "--extra-index-url', $PipIndex" in text
    assert "https://download.pytorch.org/whl/cpu" in text
    assert "scripts\\lock_dependencies.py --check" in text
    assert "$SitePackages = Join-Path $Runtime 'Lib\\site-packages'" in text
    assert "$env:TWIN_DATA_DIR = Join-Path $Portable 'data'" in text


def test_launcher_prefers_embedded_runtime_and_keeps_venv_fallback():
    text = read(LAUNCHER)
    assert 'set "RUNTIME_PY=%~dp0runtime\\python.exe"' in text
    assert 'set "VENV_PY=%~dp0.venv\\Scripts\\python.exe"' in text
    assert text.index('if exist "%RUNTIME_PY%" goto portable_env') < text.index('if exist "%VENV_PY%" goto check_env')
    assert 'set "TWIN_DATA_DIR=%~dp0data"' in text
    assert 'if not exist "data\\videos\\demo.mp4"' in text
    assert ':prepare_models' in text
    assert '"%APP_PY%" scripts\\download_models.py' in text
    assert 'if errorlevel 1 goto model_fail' in text
    assert '"%APP_PY%" -m uvicorn backend.main:app' in text


def test_launcher_builds_missing_frontend_or_points_to_releases():
    text = read(LAUNCHER)
    assert 'if not exist "frontend\\dist\\index.html" call :ensure_frontend' in text
    assert "call npm.cmd ci" in text
    assert "call npm.cmd run build" in text
    assert RELEASES in text
    assert "TWIN_NPM_REGISTRY" in text
    assert "TWIN_PIP_INDEX" in text


def test_launcher_switches_ports_and_opens_the_selected_address():
    text = read(LAUNCHER)
    assert 'set /a LAST_PORT=FIRST_PORT+10' in text
    assert 'netstat -ano | findstr /R /C:":%PORT% .*LISTENING"' in text
    assert 'set /a PORT+=1' in text
    assert "Start-Process 'http://127.0.0.1:%PORT%'" in text
    assert '--port %PORT%' in text
    assert 'TWIN_NO_BROWSER' in text


def test_windows_scripts_have_bom_and_crlf_line_endings():
    for name in ("build_windows_release.ps1", "setup-windows.ps1"):
        content = (ROOT / "scripts" / name).read_bytes()
        assert content.startswith(b"\xef\xbb\xbf"), name
        assert b"\n" not in content.replace(b"\r\n", b""), name
    for name in ("一键启动.bat", "停止.bat", "start-windows.bat"):
        content = (ROOT / name).read_bytes()
        assert b"\n" not in content.replace(b"\r\n", b""), name


def test_gitattributes_protects_windows_and_macos_line_endings():
    rules = set(read(ROOT / ".gitattributes").splitlines())
    assert "*.bat text eol=crlf" in rules
    assert "*.cmd text eol=crlf" in rules
    assert "*.ps1 text eol=crlf" in rules
    assert "*.sh text eol=lf" in rules
    assert "pwsh -NoProfile -File" in read(WORKFLOW)


def test_model_downloader_supports_optional_huggingface_mirror(monkeypatch):
    from scripts.download_models import model_download_url

    source = "https://huggingface.co/example/model/resolve/main/model.pt"
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    assert model_download_url(source) == source
    monkeypatch.setenv("HF_ENDPOINT", "https://hf-mirror.com/")
    assert model_download_url(source) == "https://hf-mirror.com/example/model/resolve/main/model.pt"
    other = "https://download.pytorch.org/models/model.pth"
    assert model_download_url(other) == other
