import argparse
import sys

from .core import ConversionError, convert_package
from .sdf import SdfConverter, SdfError, rename_warning, worker_main


def confirm_rename(changes):
    print('Warning: ' + rename_warning(changes), file=sys.stderr)
    try:
        return input('Rename and continue? [YES/NO]: ').strip().lower() in ('y', 'yes')
    except (EOFError, OSError):
        return False


def main(arguments=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) == 3 and arguments[0] == '--sdf-worker':
        return worker_main(arguments[1:])
    parser = argparse.ArgumentParser(description='Convert exported URDF models into ROS 2 packages.')
    parser.add_argument('source', nargs='?', help='Export folder containing urdf and meshes')
    parser.add_argument('target', nargs='?', help='Output package folder')
    parser.add_argument('--package-name', help='ROS 2 package name (default: output folder name)')
    parser.add_argument('--urdf', help='URDF filename in the source urdf folder')
    parser.add_argument('--urdf-only', action='store_true', help='Generate the ROS 2 package and URDF')
    parser.add_argument('--sdf-backend', choices=('auto', 'python', 'gz', 'ign'), default='auto')
    parser.add_argument('--sdf-python', help='Python executable with SDFormat bindings installed')
    args = parser.parse_args(arguments)
    if not args.source and not args.target:
        from .gui import launch_gui
        return launch_gui(args)
    if not args.source or not args.target:
        parser.error('provide both source and target folders')
    try:
        backend = SdfConverter(args.sdf_backend, args.sdf_python, confirm_rename)
        result = convert_package(args.source, args.target, args.package_name, args.urdf,
                                 generate_sdf=not args.urdf_only, sdf_converter=backend)
    except (ConversionError, SdfError, OSError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1
    print('Package: ' + str(result.output_dir))
    print('URDF: ' + str(result.urdf_path))
    if result.sdf_path:
        print('SDF: ' + str(result.sdf_path))
    return 0
