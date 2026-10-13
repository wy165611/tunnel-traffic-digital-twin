"""Record only this project's installed dependency closure, including active extras."""
from importlib.metadata import distribution
from pathlib import Path
import platform
import sys
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
LOCKED_FILE = ROOT / 'requirements-locked-macos-py313.txt'


def installed_closure():
    pending = [Requirement(line.strip()) for line in (ROOT / 'requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
    extras, versions = {}, {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        active = set(requirement.extras) | {''}
        previous = extras.get(name, set())
        installed = distribution(name)
        if not requirement.specifier.contains(installed.version, prereleases=True):
            raise ValueError(f'{name} installed {installed.version} does not satisfy {requirement.specifier}')
        if name in versions and active <= previous:
            continue
        extras[name] = active | previous
        versions[name] = installed.version
        for raw in installed.requires or []:
            dependency = Requirement(raw)
            if dependency.marker is None or any(dependency.marker.evaluate({'extra': extra}) for extra in extras[name]):
                pending.append(dependency)
    return versions


def lock():
    header = f'# Installed project dependency closure: {platform.system()} {platform.machine()}, Python {platform.python_version()}\n# Version pins, not artifact hashes; regenerate only after validation.\n'
    versions = installed_closure()
    return header + ''.join(f'{name}=={version}\n' for name, version in sorted(versions.items()))


def locked_platform():
    return platform.system() == 'Darwin' and platform.machine() == 'arm64' and sys.version_info[:2] == (3, 13)


def parse_locked():
    expected = {}
    for line in LOCKED_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '==' not in line:
            continue
        name, version = line.split('==', 1)
        expected[canonicalize_name(name)] = version.strip()
    return expected


def check():
    versions = installed_closure()
    if locked_platform():
        expected = parse_locked()
        missing = [name for name in expected if name not in versions]
        if missing:
            raise ValueError('锁定文件中的依赖未安装：' + ', '.join(sorted(missing)))
        mismatched = [f'{name} (锁定 {expected[name]}，当前 {versions[name]})' for name in expected if versions.get(name) != expected[name]]
        if mismatched:
            raise ValueError('锁定依赖版本不一致：' + '; '.join(mismatched))
        print('Locked dependency closure: PASS')
        return
    print('Project dependency constraints: PASS (未对照 requirements-locked-macos-py313.txt；当前平台非 macOS arm64 / Python 3.13)')


if __name__ == '__main__':
    import sys
    if '--check' in sys.argv:
        check()
    else:
        print(lock(), end='')
