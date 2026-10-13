#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
profile="${TWIN_DEPENDENCY_PROFILE:-auto}"
if [ "$profile" = auto ]; then
  profile=$(.venv/bin/python -c 'import platform,sys; print("locked" if platform.system()=="Darwin" and platform.machine()=="arm64" and sys.version_info[:2]==(3,13) else "compatible")')
fi
case "$profile" in
  locked)
    .venv/bin/python -c 'import platform,sys; assert platform.system()=="Darwin" and platform.machine()=="arm64" and sys.version_info[:2]==(3,13), "锁定配置仅适用 macOS arm64 / Python 3.13；其他平台请设置 TWIN_DEPENDENCY_PROFILE=compatible"'
    .venv/bin/python -m pip install -r requirements-locked-macos-py313.txt
    ;;
  compatible)
    echo '兼容依赖配置：跨平台解析结果需要重新运行测试；此安装不等同于本机验证的锁定版本。'
    .venv/bin/python -m pip install -r requirements.txt
    ;;
  *) echo 'TWIN_DEPENDENCY_PROFILE 仅接受 auto、locked、compatible' >&2; exit 2 ;;
esac
.venv/bin/python scripts/lock_dependencies.py --check
.venv/bin/python scripts/download_models.py
.venv/bin/python scripts/prepare_demo.py
cd frontend
npm ci --registry=https://registry.npmjs.org
npm run build
