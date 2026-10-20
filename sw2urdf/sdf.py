import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit


class SdfError(ValueError):
    pass


class BackendUnavailable(SdfError):
    pass


def rename_warning(changes):
    return ('SDF requires unique link and joint names. Rename these joints?\n\n' +
            '\n'.join(old + ' -> ' + new for old, new in changes.items()))


def convert_with_bindings(source, target):
    dll_handles = []
    directory = Path(sys.executable).parent / 'Library/bin'
    if os.name == 'nt' and hasattr(os, 'add_dll_directory') and directory.is_dir():
        dll_handles.append(os.add_dll_directory(str(directory)))
    for name in ('sdformat', 'sdformat16', 'sdformat15', 'sdformat14', 'sdformat13'):
        try:
            sdf = importlib.import_module(name)
            break
        except ImportError:
            continue
    else:
        raise BackendUnavailable('Install SDFormat Python bindings or select an SDF Python executable.')
    config = sdf.ParserConfig()
    preserve = getattr(config, 'urdf_set_preserve_fixed_joint', None)
    if preserve:
        preserve(True)
    root = sdf.Root()
    root.load_sdf_string(Path(source).read_text(encoding='utf-8'), config)
    Path(target).write_text(root.to_string(), encoding='utf-8')


class SdfConverter:
    def __init__(self, backend='auto', python_executable=None, confirm_rename=None):
        if backend not in ('auto', 'python', 'gz', 'ign'):
            raise SdfError('Unknown SDF backend: ' + backend)
        self.backend = backend
        self.python_executable = str(Path(str(python_executable).strip().strip('"')).expanduser()) if python_executable else None
        self.selected_backend = None
        self.confirm_rename = confirm_rename

    def prepare_urdf(self, robot):
        links = {link.get('name') for link in robot.findall('link')}
        used = links | {joint.get('name') for joint in robot.findall('joint')}
        changes = {}
        for joint in robot.findall('joint'):
            name = joint.get('name')
            if name not in links:
                continue
            renamed, index = name + '_joint', 2
            while renamed in used:
                renamed = name + '_joint_' + str(index)
                index += 1
            changes[name] = renamed
            used.add(renamed)
        if not changes:
            return
        if self.confirm_rename is None or not self.confirm_rename(dict(changes)):
            raise SdfError('Conversion cancelled: SDF link and joint name conflicts: ' + ', '.join(changes))
        for joint in robot.findall('joint') + robot.findall('transmission/joint'):
            if joint.get('name') in changes:
                joint.set('name', changes[joint.get('name')])
        for mimic in robot.findall('joint/mimic'):
            if mimic.get('joint') in changes:
                mimic.set('joint', changes[mimic.get('joint')])
        joint_options = {'preserveFixedJoint', 'provideFeedback', 'implicitSpringDamper',
                         'stopCfm', 'stopErp', 'fudgeFactor', 'springReference', 'springStiffness'}
        for gazebo in robot.findall('gazebo'):
            if gazebo.get('reference') in changes and any(child.tag in joint_options for child in gazebo):
                gazebo.set('reference', changes[gazebo.get('reference')])
        for element in robot.iter():
            if element.tag in ('joint_name', 'jointName') and (element.text or '').strip() in changes:
                element.text = changes[element.text.strip()]

    def _run(self, command, cwd):
        try:
            return subprocess.run(command, cwd=str(cwd), capture_output=True,
                                  encoding='utf-8', errors='replace', timeout=60,
                                  env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SdfError('SDF conversion failed: ' + str(error)) from error

    def _convert(self, source, target):
        backends = ('python', 'gz', 'ign') if self.backend == 'auto' else (self.backend,)
        for backend in backends:
            if backend == 'python':
                if getattr(sys, 'frozen', False) and not self.python_executable:
                    command = [sys.executable, '--sdf-worker', str(source), str(target)]
                else:
                    command = [self.python_executable or sys.executable, str(Path(__file__).resolve()),
                               '--worker', str(source), str(target)]
                result = self._run(command, source.parent)
                if result.returncode == 3 and self.backend == 'auto' and not self.python_executable:
                    continue
            else:
                executable = shutil.which(backend)
                if not executable:
                    if self.backend == 'auto':
                        continue
                    raise BackendUnavailable('SDF executable not found: ' + backend)
                result = self._run([executable, 'sdf', '-p', str(source)], source.parent)
                if result.returncode == 0:
                    target.write_text(result.stdout, encoding='utf-8')
            if result.returncode:
                detail = result.stderr.strip() or result.stdout.strip()
                raise SdfError(detail or 'SDF conversion failed.')
            self.selected_backend = backend
            return
        raise BackendUnavailable('Install SDFormat Python bindings or select an SDF Python executable.')

    def convert(self, source, target):
        source, target = Path(source).resolve(), Path(target).resolve()
        original = ET.parse(str(source)).getroot()
        self.prepare_urdf(original)
        fixed = {joint.get('name') for joint in original.findall('joint') if joint.get('type') == 'fixed'}
        resources = {}
        for element in original.iter():
            uri = element.get('filename', '')
            parsed = urlsplit(uri)
            if parsed.scheme == 'package':
                relative = '..' + parsed.path
                resources[uri] = relative
                resources['model://' + parsed.netloc + parsed.path] = relative
        for name in fixed:
            gazebo = next((g for g in original.findall('gazebo') if g.get('reference') == name), None)
            if gazebo is None:
                gazebo = ET.SubElement(original, 'gazebo', reference=name)
            preserve = gazebo.find('preserveFixedJoint')
            if preserve is None:
                preserve = ET.SubElement(gazebo, 'preserveFixedJoint')
            preserve.text = 'true'
        with tempfile.TemporaryDirectory(prefix='sdf-', dir=str(source.parent)) as temporary:
            prepared, converted = Path(temporary) / 'input.urdf', Path(temporary) / 'output.sdf'
            ET.ElementTree(original).write(str(prepared), encoding='utf-8', xml_declaration=True)
            self._convert(prepared, converted)
            try:
                sdf = ET.parse(str(converted)).getroot()
            except (OSError, ET.ParseError) as error:
                raise SdfError('Invalid SDF output: ' + str(error)) from error
        if sdf.tag != 'sdf' or sdf.find('model') is None:
            raise SdfError('SDF output must contain a model.')
        preserved = {joint.get('name') for joint in sdf.findall('model/joint') if joint.get('type') == 'fixed'}
        if fixed - preserved:
            raise SdfError('SDF converter omitted fixed joints: ' + ', '.join(sorted(fixed - preserved)))
        for element in sdf.iter():
            if element.text and element.text.strip() in resources:
                element.text = resources[element.text.strip()]
        ET.ElementTree(sdf).write(str(target), encoding='utf-8', xml_declaration=True)


def worker_main(arguments):
    try:
        convert_with_bindings(arguments[0], arguments[1])
        return 0
    except BackendUnavailable as error:
        print(str(error), file=sys.stderr)
        return 3
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        sys.exit(worker_main(sys.argv[2:]))
    sys.exit('Use the conversion tool to generate SDF.')
