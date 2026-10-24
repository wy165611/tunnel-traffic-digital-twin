#!/bin/bash
set -euo pipefail
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "x86_64" ]; then
  if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = "1" ]; then
    echo '检测到 Apple Silicon Mac 正通过 Rosetta 运行 x86_64 环境。请执行 arch -arm64 zsh 打开原生 arm64 终端，并使用 /opt/homebrew 下的 arm64 Homebrew 后重试。' >&2
  else
    echo 'Intel 芯片 Mac 暂不支持。安装说明：docs/install-macos.md' >&2
  fi
  exit 1
fi
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
pip_args=()
if [ -n "${TWIN_PIP_INDEX:-}" ]; then
  pip_args=(--index-url "$TWIN_PIP_INDEX")
fi
npm_registry="${TWIN_NPM_REGISTRY:-https://registry.npmjs.org}"
profile="${TWIN_DEPENDENCY_PROFILE:-auto}"
if [ "$profile" = auto ]; then
  profile=$(.venv/bin/python -c 'import platform,sys; print("locked" if platform.system()=="Darwin" and platform.machine()=="arm64" and sys.version_info[:2]==(3,13) else "compatible")')
fi
case "$profile" in
  locked)
    .venv/bin/python -c 'import platform,sys; assert platform.system()=="Darwin" and platform.machine()=="arm64" and sys.version_info[:2]==(3,13), "锁定配置仅适用 macOS arm64 / Python 3.13；其他平台请设置 TWIN_DEPENDENCY_PROFILE=compatible"'
    .venv/bin/python -m pip install -r requirements-locked-macos-py313.txt ${pip_args[@]+"${pip_args[@]}"}
    ;;
  compatible)
    echo '兼容依赖配置：跨平台解析结果需要重新运行测试；此安装不等同于本机验证的锁定版本。'
    echo 'Installing official CPU-only PyTorch packages...'
    .venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
    .venv/bin/python -m pip install -r requirements.txt ${pip_args[@]+"${pip_args[@]}"}
    ;;
  *) echo 'TWIN_DEPENDENCY_PROFILE 仅接受 auto、locked、compatible' >&2; exit 2 ;;
esac
.venv/bin/python scripts/lock_dependencies.py --check
.venv/bin/python scripts/download_models.py
.venv/bin/python scripts/prepare_demo.py --video examples/tunnel-demo.mp4
cd frontend
npm ci --registry="$npm_registry"
npm run build
