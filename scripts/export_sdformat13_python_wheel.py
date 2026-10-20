"""Build the Windows SDFormat 13 Python wheel directly from pinned source packages."""
import argparse
import calendar
import hashlib
import json
import os
from pathlib import Path
import tarfile
import zipfile

import pefile
from wheel.wheelfile import WheelFile
import zstandard


HELPER = 'sdformat13_python'
BOOTSTRAP = '''import os as _os
from pathlib import Path as _Path
_native = _Path(__file__).resolve().parent / 'native'
_dll_directory = _os.add_dll_directory(str(_native))
SCHEMA_DIRECTORY = _Path(__file__).resolve().parent / 'share' / 'sdformat13'
_paths = _os.environ.get('SDF_PATH', '').split(_os.pathsep)
if str(SCHEMA_DIRECTORY) not in _paths:
    _os.environ['SDF_PATH'] = _os.pathsep.join([str(SCHEMA_DIRECTORY)] + [p for p in _paths if p])
'''


def read_package(path):
    if path.name.endswith('.tar.bz2'):
        with tarfile.open(str(path), 'r:bz2') as archive:
            return {item.name: archive.extractfile(item).read() for item in archive if item.isfile()}
    files = {}
    with zipfile.ZipFile(str(path)) as archive:
        for name in archive.namelist():
            if name.endswith('.tar.zst'):
                with archive.open(name) as packed, zstandard.ZstdDecompressor().stream_reader(packed) as stream:
                    with tarfile.open(fileobj=stream, mode='r|') as tar:
                        files.update({item.name: tar.extractfile(item).read() for item in tar if item.isfile()})
    return files


def prepare(sources):
    recipe = json.loads((sources / 'build.json').read_text(encoding='utf-8'))
    recipe.update(distribution='sdformat13-python', version='13.6.0.post4')
    contents, licenses = {}, {}
    for record in recipe['packages']:
        package = sources / record['url'].rsplit('/', 1)[-1]
        if hashlib.sha256(package.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Source package differs from build.json: ' + package.name)
        for name, data in read_package(package).items():
            if name.startswith('Library/bin/') and name.endswith('.dll'):
                if recipe['included_dlls'].get(Path(name).name.lower()) == record['name']:
                    contents[HELPER + '/native/' + Path(name).name] = data
            elif name.startswith('Library/share/sdformat13/'):
                contents[HELPER + '/share/sdformat13/' + name[len('Library/share/sdformat13/'):]] = data
            elif name == 'Lib/site-packages/sdformat13.cp38-win_amd64.pyd':
                contents['sdformat13/sdformat13.cp38-win_amd64.pyd'] = data
            elif name == 'Lib/site-packages/gz/math7.cp38-win_amd64.pyd':
                contents['gz/math7/math7.cp38-win_amd64.pyd'] = data
            elif name.startswith('info/licenses/'):
                licenses['licenses/' + record['name'] + '/' + name[len('info/licenses/'):]] = data
    if set(contents) != set(recipe['runtime_order']):
        raise ValueError('Source packages do not contain the expected runtime files.')
    payload = {name: contents[name] for name in recipe['runtime_order']}
    runtime_files = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    payload[HELPER + '/__init__.py'] = BOOTSTRAP.encode('utf-8')
    payload['gz/math7/__init__.py'] = ('import ' + HELPER + '\nfrom .math7 import *\n').encode('utf-8')
    payload['sdformat13/__init__.py'] = ('import ' + HELPER + '\nimport gz.math7\nfrom .sdformat13 import *\n').encode('utf-8')
    name, version = recipe['distribution'], recipe['version']
    info = name.replace('-', '_') + '-' + version + '.dist-info'
    metadata = ['Metadata-Version: 2.1', 'Name: ' + name, 'Version: ' + version,
                'Summary: Bundled SDFormat 13 Python bindings for Windows 10 and later',
                'Requires-Python: >=3.8,<3.9', 'Platform: Windows 10 or later (x64)']
    for license_path in recipe['license_order']:
        payload[info + '/' + license_path] = licenses[license_path]
        metadata.append('License-File: ' + license_path)
    external = set()
    for filename, data in payload.items():
        if filename.endswith(('.dll', '.pyd')):
            binary = pefile.PE(data=data)
            imports = list(getattr(binary, 'DIRECTORY_ENTRY_IMPORT', [])) + list(getattr(binary, 'DIRECTORY_ENTRY_DELAY_IMPORT', []))
            for entry in imports:
                dll = entry.dll.decode('ascii').lower()
                if dll not in recipe['included_dlls']:
                    external.add(dll)
            binary.close()
    provenance = {'packages': recipe['packages'], 'included_dlls': recipe['included_dlls'],
                  'external_dlls': sorted(external), 'ucrt_provider': 'Windows 10 or later',
                  'runtime_files': runtime_files}
    payload[info + '/conda-provenance.json'] = json.dumps(provenance, indent=2).encode('utf-8')
    payload[info + '/METADATA'] = ('\n'.join(metadata) + '\n\n').encode('utf-8')
    payload[info + '/WHEEL'] = b'Wheel-Version: 1.0\nGenerator: sdformat13-python bundled export\nRoot-Is-Purelib: false\nTag: cp38-cp38-win_amd64\n'
    payload[info + '/top_level.txt'] = b'sdformat13\ngz\nsdformat13_python\n'
    return recipe, payload


def export(sources, output):
    recipe, payload = prepare(sources)
    output.mkdir(parents=True, exist_ok=True)
    filename = recipe['distribution'].replace('-', '_') + '-' + recipe['version'] + '-cp38-cp38-win_amd64.whl'
    wheel = output / filename
    if wheel.exists():
        raise ValueError('Output wheel already exists: ' + str(wheel))
    previous_epoch = os.environ.get('SOURCE_DATE_EPOCH')
    os.environ['SOURCE_DATE_EPOCH'] = str(calendar.timegm(tuple(recipe['zip_timestamp']) + (0, 0, -1)))
    try:
        with WheelFile(str(wheel), 'w') as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
    finally:
        if previous_epoch is None:
            os.environ.pop('SOURCE_DATE_EPOCH', None)
        else:
            os.environ['SOURCE_DATE_EPOCH'] = previous_epoch
    print(wheel)
    return wheel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path, help='Folder containing build.json and the pinned Conda archives')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export(args.sources.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
