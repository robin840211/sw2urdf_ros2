import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sw2urdf.gui import ConversionApp


def main():
    with tempfile.TemporaryDirectory(prefix='sw2urdf-gui-smoke-') as temporary:
        folder = Path(temporary).resolve()
        source = folder / '貼上來源 with spaces'
        (source / 'urdf').mkdir(parents=True)
        urdf = source / 'urdf/assembly.urdf'
        urdf.write_text('<robot name="assembly"><link name="base"/></robot>', encoding='utf-8')
        target = folder / '貼上輸出/robot_description'
        root = tk.Tk()
        root.withdraw()
        try:
            app = ConversionApp(root)
            app.source.set('"' + str(source) + '"')
            app.target.set('"' + str(target) + '"')
            app.urdf_name.set('"' + str(urdf) + '"')
            app.generate_sdf.set(False)
            assert str(app.urdf_selection.cget('state')) == 'normal'
            with patch('sw2urdf.gui.filedialog.askdirectory') as browse, \
                    patch('sw2urdf.gui.messagebox.showerror') as error:
                app.convert_button.invoke()
                assert app.running
                deadline = time.monotonic() + 15
                while app.running and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                assert not app.running, 'GUI conversion did not finish'
                assert not error.called, error.call_args
                assert not browse.called
                assert app.status.get().startswith('Completed:')
                assert (target / 'urdf/assembly.urdf').is_file()
                assert not app.convert_button.instate(['disabled'])
            print('PASS: real Tkinter GUI conversion using pasted quoted source/output/URDF paths, editable URDF field and worker completion')
        finally:
            root.destroy()


if __name__ == '__main__':
    main()
