import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import convert_package, find_urdf_files
from .sdf import SdfConverter, rename_warning


class ConversionApp:
    def __init__(self, root, options=None):
        self.root = root
        root.title('SolidWorks to ROS2 Conversion')
        self.source = tk.StringVar()
        self.target = tk.StringVar()
        self.package_name = tk.StringVar(value=getattr(options, 'package_name', None) or '')
        self.urdf_name = tk.StringVar(value=getattr(options, 'urdf', None) or '')
        self.generate_sdf = tk.BooleanVar(value=not getattr(options, 'urdf_only', False))
        self.backend = tk.StringVar(value=getattr(options, 'sdf_backend', 'auto'))
        self.sdf_python = tk.StringVar(value=getattr(options, 'sdf_python', None) or '')
        self.status = tk.StringVar()
        self.results = queue.Queue()
        self.closed = threading.Event()
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.running = False
        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky='nsew')
        root.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        for row, label, variable, browse in (
                (0, 'Source Folder', self.source, self.select_source),
                (1, 'Output Folder', self.target, self.select_target),
                (6, 'SDF Python', self.sdf_python, self.select_sdf_python)):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=5)
            entry = ttk.Entry(frame, textvariable=variable, width=58)
            entry.grid(row=row, column=1, sticky='ew', padx=8)
            if row == 0:
                entry.bind('<FocusOut>', lambda event: self.update_urdf_files())
            ttk.Button(frame, text='Browse', command=browse).grid(row=row, column=2)
        ttk.Label(frame, text='Package Name').grid(row=2, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.package_name).grid(row=2, column=1, sticky='ew', padx=8)
        ttk.Label(frame, text='URDF File').grid(row=3, column=0, sticky='w', pady=5)
        self.urdf_selection = ttk.Combobox(frame, textvariable=self.urdf_name)
        self.urdf_selection.grid(row=3, column=1, sticky='ew', padx=8)
        ttk.Button(frame, text='Browse', command=self.select_urdf).grid(row=3, column=2)
        ttk.Checkbutton(frame, text='Generate SDF', variable=self.generate_sdf).grid(row=4, column=1, sticky='w', pady=5)
        ttk.Label(frame, text='SDF Converter').grid(row=5, column=0, sticky='w', pady=5)
        ttk.Combobox(frame, textvariable=self.backend, values=('auto', 'python', 'gz', 'ign'),
                     state='readonly').grid(row=5, column=1, sticky='ew', padx=8)
        self.convert_button = ttk.Button(frame, text='Start Conversion', command=self.start_conversion)
        self.convert_button.grid(row=7, column=1, pady=14)
        ttk.Label(frame, textvariable=self.status, wraplength=550).grid(row=8, column=0, columnspan=3, sticky='w')
        root.after(100, self.check_result)

    def select_source(self):
        folder = filedialog.askdirectory(title='Select the SolidWorks export folder')
        if folder:
            self.source.set(folder)
            self.update_urdf_files()

    def update_urdf_files(self):
        if self.source.get().strip():
            files = [path.name for path in find_urdf_files(self.source.get())]
            self.urdf_selection['values'] = files
            current = self.urdf_name.get().strip().strip('"')
            if Path(current).name not in files:
                self.urdf_name.set(files[0] if files else '')

    def select_urdf(self):
        filename = filedialog.askopenfilename(title='Select URDF', filetypes=[('URDF', '*.urdf')])
        if filename:
            self.urdf_name.set(filename)
            if not self.source.get().strip():
                self.source.set(str(Path(filename).parent.parent))

    def select_target(self):
        folder = filedialog.askdirectory(title='Select the output package folder', mustexist=False)
        if folder:
            self.target.set(folder)
            if not self.package_name.get():
                self.package_name.set(Path(folder).name)

    def select_sdf_python(self):
        executable = filedialog.askopenfilename(title='Select Python with SDFormat')
        if executable:
            self.sdf_python.set(executable)

    def start_conversion(self):
        if self.running:
            return
        if not self.source.get() or not self.target.get():
            messagebox.showerror('Error', 'Select source and output folders.')
            return
        arguments = dict(source=self.source.get(), target=self.target.get(),
                         package_name=self.package_name.get() or None,
                         urdf_name=self.urdf_name.get() or None,
                         generate_sdf=self.generate_sdf.get(),
                         sdf_converter=SdfConverter(self.backend.get(), self.sdf_python.get() or None,
                                                    self.confirm_rename))
        self.running = True
        self.convert_button.state(['disabled'])
        self.status.set('Converting...')
        threading.Thread(target=self.convert, args=(arguments,)).start()

    def convert(self, arguments):
        try:
            self.results.put((True, convert_package(**arguments)))
        except Exception as error:
            self.results.put((False, str(error)))

    def close(self):
        self.closed.set()
        self.root.destroy()

    def confirm_rename(self, changes):
        response = queue.Queue()
        self.results.put(('confirm', (changes, response)))
        while not self.closed.is_set():
            try:
                return response.get(timeout=0.1)
            except queue.Empty:
                pass
        return False

    def check_result(self):
        try:
            success, result = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            if success == 'confirm':
                changes, response = result
                response.put(messagebox.askyesno('SDF name conflict', rename_warning(changes),
                                                icon='warning', default='no', parent=self.root))
            else:
                self.running = False
                self.convert_button.state(['!disabled'])
                if success:
                    self.status.set('Completed: ' + str(result.output_dir))
                else:
                    self.status.set('Conversion failed')
                    messagebox.showerror('Error', result)
        if not self.closed.is_set():
            self.root.after(100, self.check_result)


def launch_gui(options=None):
    root = tk.Tk()
    ConversionApp(root, options)
    root.mainloop()
    return 0
