import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


TEMPLATES = Path(__file__).resolve().parent.parent / 'replace_files'


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class ConversionResult:
    package_name: str
    output_dir: Path
    urdf_path: Path
    sdf_path: Optional[Path] = None


def find_urdf_files(source):
    folder = _input_path(source) / 'urdf'
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == '.urdf') if folder.is_dir() else []


def _input_path(value):
    return Path(str(value).strip().strip('"')).expanduser().resolve()


def _asset_path(uri, source, urdf_dir):
    normalized = uri.replace('\\', '/')
    parsed = urlsplit(normalized)
    if parsed.scheme == 'package':
        path = source / unquote(parsed.path).lstrip('/')
    elif parsed.scheme == 'file':
        path = Path(url2pathname(parsed.path))
    elif Path(uri).is_absolute():
        path = Path(uri)
    elif not parsed.scheme:
        path = urdf_dir / unquote(normalized)
    else:
        raise ConversionError('Unsupported asset path: ' + uri)
    path = path.resolve()
    if not path.is_file():
        raise ConversionError('Asset file not found: ' + str(path))
    return path


def _copy_asset(source, relative, stage, copied):
    if relative in copied and copied[relative] != source:
        raise ConversionError('Conflicting asset filenames: ' + relative.as_posix())
    copied[relative] = source
    target = stage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))


def _copy_collada_images(asset, relative, stage, source, copied):
    try:
        tree = ET.parse(str(asset))
    except ET.ParseError as error:
        raise ConversionError('Invalid COLLADA mesh: ' + str(asset)) from error
    for index, image in enumerate(tree.findall('.//{*}image/{*}init_from')):
        reference = image.find('{*}ref')
        value = reference if reference is not None else image
        if not value.text or not value.text.strip():
            continue
        texture = _asset_path(value.text.strip(), source, asset.parent)
        destination = relative.parent / (relative.stem + '_textures') / str(index) / texture.name
        _copy_asset(texture, destination, stage, copied)
        value.text = destination.relative_to(relative.parent).as_posix()
    tree.write(str(stage / relative), encoding='utf-8', xml_declaration=True)


def _prepare_assets(robot, source, source_urdf, stage, package_name):
    meshes = source / 'meshes'
    if meshes.is_dir():
        for kind in ('visual', 'collision'):
            shutil.copytree(str(meshes), str(stage / 'meshes' / kind), dirs_exist_ok=True)
    copied = {}
    for kind in ('visual', 'collision'):
        for mesh in robot.findall('.//' + kind + '/geometry/mesh'):
            filename = mesh.get('filename')
            if not filename:
                raise ConversionError('Mesh filename is missing.')
            asset = _asset_path(filename, source, source_urdf.parent)
            try:
                relative = asset.relative_to(meshes)
            except ValueError:
                try:
                    relative = asset.relative_to(source)
                except ValueError:
                    relative = Path(asset.name)
            destination = Path('meshes') / kind / relative
            _copy_asset(asset, destination, stage, copied)
            if asset.suffix.lower() == '.dae':
                _copy_collada_images(asset, destination, stage, source, copied)
            mesh.set('filename', 'package://' + package_name + '/' + destination.as_posix())
    for texture in robot.findall('.//material/texture'):
        filename = texture.get('filename')
        if not filename:
            raise ConversionError('Texture filename is missing.')
        asset = _asset_path(filename, source, source_urdf.parent)
        try:
            relative = asset.relative_to(source / 'textures')
        except ValueError:
            relative = Path(asset.name)
        destination = Path('textures') / relative
        _copy_asset(asset, destination, stage, copied)
        texture.set('filename', 'package://' + package_name + '/' + destination.as_posix())


def _package_files(stage, package_name, urdf_name, robot, generate_sdf):
    (stage / package_name).mkdir()
    (stage / package_name / '__init__.py').touch()
    (stage / 'resource').mkdir()
    (stage / 'resource' / package_name).touch()
    for filename in ('setup.py', 'package.xml', 'launch.py', 'rviz/view.rviz'):
        relative = Path('launch/launch.py') if filename == 'launch.py' else Path(filename)
        content = (TEMPLATES / filename).read_text(encoding='utf-8')
        content = content.replace('lesson_urdf', package_name)
        content = content.replace("'urdf/planar_3dof.urdf'", repr('urdf/' + urdf_name))
        if filename == 'rviz/view.rviz':
            children = {child.get('link') for child in robot.findall('joint/child')}
            roots = [link.get('name') for link in robot.findall('link') if link.get('name') not in children]
            content = content.replace('ROOT_LINK', roots[0] if roots else 'base_link')
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    cfg = '[develop]\nscript_dir=$base/lib/{0}\n[install]\ninstall_scripts=$base/lib/{0}\n'
    (stage / 'setup.cfg').write_text(cfg.format(package_name), encoding='utf-8')
    if generate_sdf:
        manifest = ET.parse(str(stage / 'package.xml'))
        for dependency in ('ros_gz_sim', 'ros_gz_bridge'):
            ET.SubElement(manifest.getroot(), 'exec_depend').text = dependency
        manifest.write(str(stage / 'package.xml'), encoding='utf-8', xml_declaration=True)
        for name in ('world', 'config'):
            shutil.copytree(str(TEMPLATES / name), str(stage / name))
        content = (TEMPLATES / 'gz_simulator_launch.py').read_text(encoding='utf-8')
        content = content.replace('lesson_urdf', package_name)
        content = content.replace("'urdf/planar_3dof.urdf'", repr('urdf/' + urdf_name))
        (stage / 'launch/gz_simulator_launch.py').write_text(content, encoding='utf-8')


def convert_package(source, target, package_name=None, urdf_name=None,
                    generate_sdf=False, sdf_converter=None):
    source, target = _input_path(source), _input_path(target)
    if source == target or source in target.parents or target in source.parents:
        raise ConversionError('Choose separate source and output folders.')
    package_name = package_name or target.name
    if not re.fullmatch(r'[a-z][a-z0-9_]*', package_name):
        raise ConversionError('Package name must start with a lowercase letter and use lowercase letters, digits or underscores.')
    candidates = find_urdf_files(source)
    if urdf_name:
        selection = str(urdf_name).strip().strip('"')
        selected = _input_path(selection) if Path(selection).is_absolute() else (source / 'urdf' / selection).resolve()
        candidates = [p for p in candidates if p.resolve() == selected]
    if len(candidates) != 1:
        raise ConversionError('Select one URDF file from the source urdf folder.')
    source_urdf = candidates[0]
    try:
        robot = ET.parse(str(source_urdf)).getroot()
    except ET.ParseError as error:
        raise ConversionError('Invalid URDF: ' + str(error)) from error
    if robot.tag != 'robot':
        raise ConversionError('URDF must contain a robot element.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sw2urdf-', dir=str(target.parent)) as temporary:
        stage = Path(temporary)
        _prepare_assets(robot, source, source_urdf, stage, package_name)
        (stage / 'urdf').mkdir()
        output_urdf = stage / 'urdf' / source_urdf.name
        ET.ElementTree(robot).write(str(output_urdf), encoding='utf-8', xml_declaration=True)
        _package_files(stage, package_name, source_urdf.name, robot, generate_sdf)
        if generate_sdf:
            if sdf_converter is None:
                from .sdf import SdfConverter
                sdf_converter = SdfConverter()
            sdf_converter.convert(output_urdf, stage / 'urdf/robot.sdf')
            version = ET.parse(str(stage / 'urdf/robot.sdf')).getroot().get('version')
            model = ET.Element('model')
            ET.SubElement(model, 'name').text = package_name
            ET.SubElement(model, 'version').text = '1.0'
            ET.SubElement(model, 'sdf', version=version).text = 'urdf/robot.sdf'
            ET.ElementTree(model).write(str(stage / 'model.config'), encoding='utf-8', xml_declaration=True)
        shutil.copytree(str(stage), str(target), dirs_exist_ok=True)
    return ConversionResult(package_name, target, target / 'urdf' / source_urdf.name,
                            target / 'urdf/robot.sdf' if generate_sdf else None)
