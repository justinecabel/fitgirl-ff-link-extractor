"""Ubuntu-inspired Tkinter presentation, shared by source and packaged builds."""

from pathlib import Path
import tkinter as tk
from tkinter import font, ttk
from installed_browser import BROWSERS
from extraction import DEFAULT_TABS, MIN_TABS, MAX_TABS


class UbuntuUI:
    def setup_theme(self):
        self.colors = {
            'background': '#f3f1ee', 'surface': '#ffffff',
            'text': '#292420', 'muted': '#59514b', 'border': '#c9c0b8',
            'orange': '#b9380c', 'orange_hover': '#a33009', 'orange_pressed': '#862506',
            'aubergine': '#2c001e', 'step_active': '#5e2750', 'soft_orange': '#fcebe3',
            'success': '#175b35', 'success_bg': '#e2f2e8',
            'danger': '#a12618', 'danger_hover': '#851c11',
            'disabled_bg': '#e5e0da', 'disabled_fg': '#696059',
            'step_pending_bg': '#e5e0da', 'step_pending_fg': '#504740',
        }
        families = set(font.families(self.root))
        self.ui_font = next((name for name in (
            'Ubuntu Sans', 'Ubuntu', 'Noto Sans', 'Segoe UI', 'DejaVu Sans'
        ) if name in families), 'TkDefaultFont')
        font.nametofont('TkDefaultFont').configure(family=self.ui_font, size=10)
        self.root.configure(background=self.colors['background'])
        self.root.option_add('*TCombobox*Listbox.font', (self.ui_font, 10))
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.colors['step_active'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')

        c = self.colors
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.style.configure('TFrame', background=c['background'])
        self.style.configure('Card.TFrame', background=c['surface'])
        self.style.configure('TLabel', background=c['background'], foreground=c['text'])
        self.style.configure('Card.TLabel', background=c['surface'])
        self.style.configure('Title.TLabel', background=c['surface'], font=(self.ui_font, 12, 'bold'))
        self.style.configure('Hint.TLabel', background=c['surface'], foreground=c['muted'], font=(self.ui_font, 9))
        self.style.configure('Count.TLabel', background=c['soft_orange'], foreground=c['orange'], padding=(8, 4), font=(self.ui_font, 9, 'bold'))
        self.style.configure('TButton', font=(self.ui_font, 10), padding=(10, 8),
            background='white', foreground=c['text'], borderwidth=1, bordercolor='#91857b', focuscolor=c['step_active'])
        self.style.map('TButton',
            background=[('disabled', c['disabled_bg']), ('pressed', '#d8d0c8'), ('active', '#f0eae4')],
            foreground=[('disabled', c['disabled_fg'])],
            bordercolor=[('disabled', c['border']), ('focus', c['step_active'])])
        self.style.configure('Compact.TButton', padding=(7, 4), font=(self.ui_font, 9))
        for style, normal, hover, pressed in (
            ('Primary.TButton', c['orange'], c['orange_hover'], c['orange_pressed']),
            ('Stop.TButton', c['danger'], c['danger_hover'], '#68140b'),
        ):
            self.style.configure(style, background=normal, foreground='white', bordercolor=normal,
                font=(self.ui_font, 10, 'bold'), focuscolor='white')
            self.style.map(style,
                background=[('disabled', c['disabled_bg']), ('pressed', pressed), ('active', hover)],
                foreground=[('disabled', c['disabled_fg']), ('!disabled', 'white')],
                bordercolor=[('disabled', c['border']), ('pressed', pressed), ('active', hover)])
        self.style.configure('TEntry', padding=(10, 9), fieldbackground='white', foreground=c['text'],
            bordercolor='#91857b', lightcolor='#91857b', darkcolor='#91857b', insertcolor=c['text'])
        self.style.map('TEntry', fieldbackground=[('disabled', c['disabled_bg'])],
            foreground=[('disabled', c['disabled_fg'])], bordercolor=[('focus', c['step_active'])])
        self.style.configure('TCombobox', padding=(7, 6), foreground=c['text'], arrowsize=12,
            background='white', fieldbackground='white', bordercolor='#91857b')
        self.style.map('TCombobox', fieldbackground=[('disabled', c['disabled_bg']), ('readonly', 'white')],
            foreground=[('disabled', c['disabled_fg']), ('readonly', c['text'])],
            selectbackground=[('readonly', 'white')], selectforeground=[('readonly', c['text'])],
            bordercolor=[('focus', c['step_active'])])
        self.style.configure('TSpinbox', padding=(7, 6), arrowsize=12, fieldbackground='white', foreground=c['text'])
        self.style.map('TSpinbox', fieldbackground=[('disabled', c['disabled_bg'])],
            foreground=[('disabled', c['disabled_fg'])], bordercolor=[('focus', c['step_active'])])
        self.style.configure('Ubuntu.Horizontal.TProgressbar', background=c['orange'], troughcolor='#ded6ce', borderwidth=0, thickness=6)
        for direction in ('Vertical', 'Horizontal'):
            self.style.configure(direction + '.TScrollbar', background='#b5aaa0', troughcolor='white', borderwidth=0, arrowsize=12)
        self.style.configure('Treeview', font=(self.ui_font, 9), rowheight=30,
            background='white', fieldbackground='white', foreground=c['text'], borderwidth=0)
        self.style.configure('Treeview.Heading', font=(self.ui_font, 9, 'bold'),
            background='#e9e3dd', foreground=c['text'], padding=(6, 8), relief='flat')
        self.style.map('Treeview', background=[('selected', c['step_active'])], foreground=[('selected', 'white')])

    def _card(self, parent):
        return tk.Frame(parent, background=self.colors['surface'], highlightbackground=self.colors['border'],
            highlightcolor=self.colors['border'], highlightthickness=1, bd=0)

    def setup_ui(self):
        c = self.colors
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        header = tk.Frame(self.root, background=c['aubergine'], padx=22, pady=12)
        header.grid(row=0, column=0, sticky='ew')
        icon_path = Path(__file__).resolve().parent / 'assets' / 'fitgirl-ff-link-extractor.png'
        if icon_path.is_file():
            self.window_icon = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self.window_icon)
            self.header_icon = self.window_icon.subsample(4, 4)
            tk.Label(header, image=self.header_icon, background=c['aubergine']).pack(side='left', padx=(0, 12))
        titles = tk.Frame(header, background=c['aubergine'])
        titles.pack(side='left')
        tk.Label(titles, text='FitGirl Link Extractor', background=c['aubergine'], foreground='white', font=(self.ui_font, 17, 'bold')).pack(anchor='w')
        tk.Label(titles, text='Load a page, extract selected files, then copy your links.', background=c['aubergine'], foreground='#eadde7', font=(self.ui_font, 9)).pack(anchor='w', pady=(2, 0))

        steps = ttk.Frame(self.root, padding=(22, 12, 22, 0))
        steps.grid(row=1, column=0, sticky='ew')
        self.step_labels = []
        for column in range(3):
            label = tk.Label(steps, font=(self.ui_font, 10, 'bold'), padx=12, pady=8, anchor='w')
            label.grid(row=0, column=column, sticky='ew', padx=(0, 8 if column < 2 else 0))
            steps.columnconfigure(column, weight=1, uniform='steps')
            self.step_labels.append(label)
        self.set_phase(1)

        content = ttk.Frame(self.root, padding=(22, 12, 22, 12))
        content.grid(row=2, column=0, sticky='nsew')
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        self.source_panel = source = self._card(content)
        source.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        source.columnconfigure(0, weight=1)
        ttk.Label(source, text='1. Load a game page', style='Title.TLabel').grid(row=0, column=0, sticky='w', padx=14, pady=(10, 7))
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(source, textvariable=self.url_var, font=(self.ui_font, 10))
        self.url_entry.grid(row=1, column=0, sticky='ew', padx=(14, 10))
        self.url_entry.bind('<Return>', self._fetch_from_entry)
        self.fetch_btn = ttk.Button(source, text='Load files', width=12, style='Primary.TButton', command=self.start_fetch_thread)
        self.fetch_btn.grid(row=1, column=1, padx=(0, 14))
        self.source_hint_var = tk.StringVar(value='Paste a full page URL to find its files.')
        ttk.Label(source, textvariable=self.source_hint_var, style='Hint.TLabel').grid(row=2, column=0, columnspan=2, sticky='w', padx=14, pady=(6, 9))

        panels = ttk.Frame(content)
        panels.grid(row=1, column=0, sticky='nsew')
        panels.columnconfigure(0, weight=2, minsize=330)
        panels.columnconfigure(1, weight=3, minsize=430)
        panels.rowconfigure(0, weight=1)
        self.files_panel = files = self._card(panels)
        files.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(2, weight=1)
        heading = ttk.Frame(files, style='Card.TFrame', padding=(12, 11, 12, 7))
        heading.grid(row=0, column=0, sticky='ew')
        ttk.Label(heading, text='2. Select files', style='Title.TLabel').pack(side='left')
        self.selection_var = tk.StringVar(value='0 selected')
        ttk.Label(heading, textvariable=self.selection_var, style='Count.TLabel').pack(side='right')
        file_actions = ttk.Frame(files, style='Card.TFrame', padding=(12, 0, 12, 7))
        file_actions.grid(row=1, column=0, sticky='ew')
        ttk.Label(file_actions, text='Select:', style='Hint.TLabel').pack(side='left', padx=(0, 7))
        self.select_all_btn = ttk.Button(file_actions, text='All', width=5, style='Compact.TButton', command=self.select_all)
        self.select_all_btn.pack(side='left')
        self.deselect_all_btn = ttk.Button(file_actions, text='None', width=5, style='Compact.TButton', command=self.deselect_all)
        self.deselect_all_btn.pack(side='left', padx=5)
        self.unfinished_btn = ttk.Button(file_actions, text='Unfinished', style='Compact.TButton', command=self.select_unfinished)
        self.unfinished_btn.pack(side='left')
        list_area = ttk.Frame(files, style='Card.TFrame')
        list_area.grid(row=2, column=0, sticky='nsew', padx=7)
        list_area.columnconfigure(0, weight=1)
        list_area.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(list_area, background='white', highlightthickness=0, width=260, height=100)
        self.scrollbar_list = ttk.Scrollbar(list_area, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style='Card.TFrame')
        self.scrollable_frame.bind('<Configure>', lambda event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.bind('<Configure>', self._resize_file_list)
        self.canvas.configure(yscrollcommand=self.scrollbar_list.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.scrollbar_list.grid(row=0, column=1, sticky='ns')
        self.files_empty = tk.Label(self.canvas, text='No files loaded\nLoad a game page in step 1.', background='white', foreground=c['muted'], font=(self.ui_font, 10), justify='center', wraplength=250)
        self.files_empty.place(relx=0.5, rely=0.45, anchor='center')

        settings = ttk.Frame(files, style='Card.TFrame', padding=(12, 9, 12, 0))
        settings.grid(row=3, column=0, sticky='ew')
        settings.columnconfigure(0, weight=1)
        ttk.Label(settings, text='Browser', style='Hint.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 4))
        ttk.Label(settings, text='Tabs at once', style='Hint.TLabel').grid(row=0, column=1, sticky='w', padx=(12, 0), pady=(0, 4))
        self.browser_var = tk.StringVar(value=BROWSERS[0])
        self.browser_combo = ttk.Combobox(settings, textvariable=self.browser_var, values=BROWSERS, state='disabled', width=18)
        self.browser_combo.grid(row=1, column=0, sticky='ew')
        self.tabs_var = tk.StringVar(value=str(DEFAULT_TABS))
        self.tabs_spin = ttk.Spinbox(settings, textvariable=self.tabs_var, from_=MIN_TABS, to=MAX_TABS, width=5, state='disabled')
        self.tabs_spin.grid(row=1, column=1, sticky='ew', padx=(12, 0))
        self.selection_hint_var = tk.StringVar(value='Load a page to enable extraction.')
        self.selection_hint = tk.Label(files, textvariable=self.selection_hint_var, background='white', foreground=c['muted'],
            font=(self.ui_font, 9), anchor='w', justify='left', height=2, wraplength=290)
        self.selection_hint.grid(row=4, column=0, sticky='ew', padx=12, pady=(4, 0))
        files.bind('<Configure>', lambda event: self.selection_hint.configure(wraplength=max(220, event.width - 26)))
        extraction_actions = ttk.Frame(files, style='Card.TFrame', padding=(12, 5, 12, 12))
        extraction_actions.grid(row=5, column=0, sticky='ew')
        extraction_actions.columnconfigure(0, weight=1)
        self.extract_btn = ttk.Button(extraction_actions, text='Extract selected', width=18, style='Primary.TButton', command=self.start_extraction_thread, state='disabled')
        self.extract_btn.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.stop_btn = ttk.Button(extraction_actions, text='Stop', width=9, style='Stop.TButton', command=self.stop_extraction, state='disabled')
        self.stop_btn.grid(row=0, column=1, sticky='e')

        self.results_panel = results = self._card(panels)
        results.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(2, weight=1)
        heading = ttk.Frame(results, style='Card.TFrame', padding=(12, 11, 12, 7))
        heading.grid(row=0, column=0, sticky='ew')
        ttk.Label(heading, text='3. Results & links', style='Title.TLabel').pack(side='left')
        self.result_var = tk.StringVar(value='0 links')
        ttk.Label(heading, textvariable=self.result_var, style='Count.TLabel').pack(side='right')
        ttk.Label(results, text='Next extraction replaces this queue. Copy links first.', style='Hint.TLabel').grid(row=1, column=0, sticky='w', padx=12, pady=(0, 8))
        output = ttk.Frame(results, style='Card.TFrame', padding=(7, 0, 7, 0))
        output.grid(row=2, column=0, sticky='nsew')
        output.columnconfigure(0, weight=1)
        output.rowconfigure(0, weight=1)
        self.result_tree = ttk.Treeview(output, columns=('file', 'state', 'url'), show='headings', selectmode='extended', height=5)
        for name, title, width in (('file', 'File', 130), ('state', 'Status', 100), ('url', 'Direct link / detail', 220)):
            self.result_tree.heading(name, text=title, anchor='w')
            self.result_tree.column(name, width=width, minwidth=80, stretch=name == 'url')
        self.result_tree.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(output, orient='vertical', command=self.result_tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(output, orient='horizontal', command=self.result_tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.result_tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.result_tree.tag_configure('Complete', foreground=c['success'])
        for state in ('Failed', 'Timed out'):
            self.result_tree.tag_configure(state, foreground=c['danger'])
        self.result_tree.tag_configure('Cancelled', foreground=c['muted'])
        self.result_tree.bind('<Control-c>', self._copy_selection)
        self.result_tree.bind('<<TreeviewSelect>>', lambda event: self.refresh_actions())
        self.output_empty = tk.Label(self.result_tree, text='No extraction started\nChoose files and use Extract selected.', background='white', foreground=c['muted'], font=(self.ui_font, 10), justify='center', wraplength=280)
        self.output_empty.place(relx=0.5, rely=0.45, anchor='center')
        output_actions = ttk.Frame(results, style='Card.TFrame', padding=(12, 12))
        output_actions.grid(row=3, column=0, sticky='ew')
        self.clear_btn = ttk.Button(output_actions, text='Clear', command=self.clear_output, state='disabled')
        self.clear_btn.pack(side='left')
        self.copy_btn = ttk.Button(output_actions, text='Copy all (0)', width=13, command=self.copy_to_clipboard, state='disabled')
        self.copy_btn.pack(side='right')
        self.copy_selected_btn = ttk.Button(output_actions, text='Copy selected', command=lambda: self.copy_to_clipboard(selected_only=True), state='disabled')
        self.copy_selected_btn.pack(side='right', padx=7)

        footer = ttk.Frame(self.root, padding=(22, 0, 22, 14))
        footer.grid(row=3, column=0, sticky='ew')
        footer.columnconfigure(1, weight=1)
        footer.rowconfigure(0, minsize=44)
        self.status_badge = tk.Label(footer, text='Ready', width=9, padx=6, pady=5, background=c['step_pending_bg'], foreground=c['step_pending_fg'], font=(self.ui_font, 9, 'bold'))
        self.status_badge.grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.status_var = tk.StringVar(value='Load a game page to begin. Chrome, Edge, Brave, or Firefox is required.')
        self.status_label = ttk.Label(footer, textvariable=self.status_var, foreground=c['text'], font=(self.ui_font, 9), wraplength=850, anchor='w')
        self.status_label.grid(row=0, column=1, sticky='ew')
        footer.bind('<Configure>', lambda event: self.status_label.configure(wraplength=max(250, event.width - 160)))
        self.progress = ttk.Progressbar(footer, orient='horizontal', mode='determinate', style='Ubuntu.Horizontal.TProgressbar')
        self.progress.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(7, 0))
        self.url_entry.focus_set()

    def set_phase(self, phase):
        self.phase = phase
        titles = ('Load page', 'Select & extract', 'Copy links')
        for index, (label, title) in enumerate(zip(self.step_labels, titles), 1):
            if index < phase:
                text, background, foreground = f'{index}  {title}  ✓', self.colors['success_bg'], self.colors['success']
            elif index == phase:
                text = f'{index}  {title}  • Current'
                background, foreground = self.colors['step_active'], 'white'
            else:
                text, background, foreground = f'{index}  {title}', self.colors['step_pending_bg'], self.colors['step_pending_fg']
            label.configure(text=text, background=background, foreground=foreground)

    def _fetch_from_entry(self, event):
        self.start_fetch_thread()
        return 'break'

    def _copy_selection(self, event):
        self.copy_to_clipboard(selected_only=True)
        return 'break'

    def _resize_file_list(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)
        for checkbox in self.file_widgets:
            checkbox.configure(wraplength=max(130, event.width - 45))
