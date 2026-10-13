"""Record only this project's installed dependency closure, including active extras."""
from importlib.metadata import distribution
from pathlib import Path
import platform
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent


def lock():
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
    header = f'# Installed project dependency closure: {platform.system()} {platform.machine()}, Python {platform.python_version()}\n# Version pins, not artifact hashes; regenerate only after validation.\n'
    return header + ''.join(f'{name}=={version}\n' for name, version in sorted(versions.items()))


if __name__ == '__main__':
    import sys
    result = lock()
    if '--check' in sys.argv:
        print('Project dependency constraints: PASS')
    else:
        print(result, end='')
