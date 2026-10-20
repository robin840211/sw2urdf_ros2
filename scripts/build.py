"""Build the GUI and CLI with the current host's native SDFormat runtime."""

import argparse
import importlib.metadata
import importlib.util
import os
import sys
from pathlib import Path


def license_data(root, conda_support):
    files = [(str(root / 'LICENSE'), 'licenses/sw2urdf_ros2')]
    distributions = conda_support.walk_dependency_tree('sdformat15-python')
    for name, distribution in sorted(distributions.items()):
        metadata = distribution.raw
        cached = metadata.get('extracted_package_dir') or metadata.get('link', {}).get('source')
        directory = Path(cached) / 'info/licenses' if cached else None
        if directory is None or not directory.is_dir():
            print('License texts unavailable in package cache: ' + name, file=sys.stderr)
            continue
        for filename in sorted(directory.rglob('*')):
            if filename.is_file():
                destination = Path('licenses') / name / filename.relative_to(directory).parent
                files.append((str(filename), destination.as_posix()))
    pyinstaller = importlib.metadata.distribution('pyinstaller')
    for filename in pyinstaller.files or ():
        if '/licenses/' in filename.as_posix():
            path = Path(pyinstaller.locate_file(filename))
            if path.is_file():
                files.append((str(path), 'licenses/pyinstaller'))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Distribution folder (default: dist)')
    parser.add_argument('--work', type=Path, help='Build folder (default: build/desktop)')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = (args.output or root / 'dist').resolve()
    work = (args.work or root / 'build/desktop').resolve()
    if (output / 'sw2urdf_ros2').exists():
        parser.error('Choose an output folder without an existing sw2urdf_ros2 build.')
    if not (Path(sys.prefix) / 'conda-meta').is_dir():
        parser.error('Run this script with Python from the environment.yml environment.')
    if importlib.util.find_spec('sdformat15') is None:
        parser.error('Install the environment.yml dependencies before building.')
    try:
        from PyInstaller import __main__ as pyinstaller
        from PyInstaller.utils.hooks import conda_support
    except ImportError:
        parser.error('Install PyInstaller in this environment: python -m pip install pyinstaller')

    prefix = Path(sys.prefix)
    schemas = prefix / ('Library/share/sdformat15' if os.name == 'nt' else 'share/sdformat15')
    if not schemas.is_dir():
        parser.error('SDFormat XML schemas were not found in the current environment.')
    work.mkdir(parents=True, exist_ok=True)
    options = [
        str(root / 'conversion_urdf_ros_2_ros2.py'),
        '--name', 'sw2urdf_ros2', '--onedir', '--console',
        '--distpath', str(output), '--workpath', str(work / 'objects'),
        '--specpath', str(work), '--paths', str(root),
        '--hidden-import', 'sdformat15',
        '--hidden-import', 'gz.math8',
        '--runtime-hook', str(root / 'scripts/pyi_runtime.py'),
        '--add-data', str(root / 'replace_files') + os.pathsep + 'replace_files',
        '--add-data', str(root / 'sw2urdf/sdf.py') + os.pathsep + 'sw2urdf',
        '--add-data', str(schemas) + os.pathsep + 'share/sdformat15',
    ]
    for source, destination in conda_support.collect_dynamic_libs('sdformat15-python'):
        options.extend(['--add-binary', source + os.pathsep + destination])
    for source, destination in license_data(root, conda_support):
        options.extend(['--add-data', source + os.pathsep + destination])
    pyinstaller.run(options)
    print('Application: ' + str(output / 'sw2urdf_ros2'))


if __name__ == '__main__':
    main()
