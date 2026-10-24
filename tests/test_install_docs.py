from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_readme_has_concise_windows_and_macos_quickstarts():
    readme = read("README.md")
    install = readme.index("## 安装与使用")
    windows = readme.index("### Windows 10/11（64 位）", install)
    macos = readme.index("### macOS（Apple Silicon 与 Intel）", windows)
    assert install < windows < macos
    assert "TunnelTwin-Windows-x64-portable.zip" in readme[windows:macos]
    assert "docs/install-windows.md" in readme[windows:macos]
    assert "git clone https://github.com/wy165611/tunnel-traffic-digital-twin.git" in readme[macos:]
    assert "bash scripts/setup.sh" in readme[macos:]
    assert "./start.sh" in readme[macos:]
    assert "docs/install-macos.md" in readme[macos:]


def test_windows_guide_covers_all_installation_and_usage_paths():
    guide = read("docs/install-windows.md")
    assert "方式一：便携完整版" in guide
    assert "方式二：轻量在线版" in guide
    assert "方式三：源码部署" in guide
    assert "不包含 `runtime` Python 环境与模型权重" in guide
    assert "scripts\\setup-windows.ps1" in guide
    assert ".\\start-windows.bat" in guide
    assert "视频管理" in guide and "开始分析" in guide and "数据导出" in guide
    assert "停止.bat" in guide
    for topic in ("SmartScreen", "杀毒软件", "端口被占用", "中文路径", "首次启动很慢"):
        assert topic in guide
    assert "docs/install-windows.md" in read("README.md")
    assert "(install-windows.md)" in read("docs/Windows分发版启动说明.md")


def test_macos_guide_matches_actual_commands_and_platform_behavior():
    guide = read("docs/install-macos.md")
    for command in (
        "xcode-select --install",
        "brew install python@3.13 node",
        "bash scripts/setup.sh",
        "./start.sh",
        "TWIN_PORT=8001 ./start.sh",
        "bash scripts/dev.sh",
    ):
        assert command in guide
    for topic in (
        "Apple Silicon",
        "Intel",
        "device: mps",
        "requirements-locked-macos-py313.txt",
        "无法验证开发者",
        "终端没有权限访问文件夹",
        "OpenCV",
        "TWIN_PIP_INDEX",
        "TWIN_NPM_REGISTRY",
    ):
        assert topic in guide


def test_macos_setup_supports_documented_mirrors_and_demo():
    script = read("scripts/setup.sh")
    assert 'pip_args=(--index-url "$TWIN_PIP_INDEX")' in script
    assert 'npm_registry="${TWIN_NPM_REGISTRY:-https://registry.npmjs.org}"' in script
    assert 'npm ci --registry="$npm_registry"' in script
    assert "scripts/prepare_demo.py --video examples/tunnel-demo.mp4" in script
    assert (ROOT / "examples/tunnel-demo.mp4").is_file()
    assert (ROOT / "start.sh").is_file()
    assert (ROOT / "scripts/dev.sh").is_file()
