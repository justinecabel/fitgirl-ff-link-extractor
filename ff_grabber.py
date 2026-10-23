import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()

if '--smoke-test' in sys.argv:
    import faulthandler
    faulthandler.dump_traceback_later(15, exit=True)

import datetime
import json
import os
from pathlib import Path
import queue
import threading
import traceback
from urllib.parse import quote, urljoin, urlparse
import tkinter as tk

import requests
from bs4 import BeautifulSoup

from extraction import BackgroundTabs, Job, MAX_TABS, MIN_TABS, TabQueue, filename_for
from installed_browser import BROWSERS, create_driver
from ubuntu_ui import UbuntuUI

STATE_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home()) if sys.platform == 'win32'
                 else os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'fitgirl-ff-link-extractor'
DIAG_LOG = STATE_DIR / 'diagnostics.log'


def diag(message):
    line = f'[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {message}'
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with DIAG_LOG.open('a', encoding='utf-8') as output:
            output.write(line + '\n')
    except OSError:
        pass


BROWSER_HELP = '''<!doctype html><meta charset="utf-8"><title>Extraction browser</title>
<body style="background:#f5f4f2;color:#292724;font:18px sans-serif;padding:50px;max-width:750px">
<h1 style="color:#5e2750">FitGirl Link Extractor</h1>
<p>Extraction tabs open in this window in the background.</p>
<p>If a file needs verification, select its tab and complete the check.
The app keeps your chosen tab in focus.</p>
<p>Return to the desktop app to follow progress, stop extraction, or copy your links.</p>
<p>This window and all its tabs close automatically when extraction finishes or is stopped.</p></body>'''


class FitgirlExtractorApp(UbuntuUI):
    def __init__(self, root):
        self.root = root
        root.title('FitGirl Link Extractor')
        width = min(1180, max(920, root.winfo_screenwidth() - 80))
        height = min(860, max(720, root.winfo_screenheight() - 90))
        root.geometry(f'{width}x{height}')
        root.minsize(920, 720)
        self.checkbox_vars = {}
        self.file_widgets = []
        self.results = {}
        self.operation = None
        self.closing = False
        self.cleanup_started = False
        self.run_error = None
        self.loaded_url = None
        self.batch_url = None
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.driver = None
        self.tabs = None
        self.setup_theme()
        self.setup_ui()
        self.load_settings()
        self.url_var.trace_add('write', self.source_changed)
        self.tabs_var.trace_add('write', lambda *args: self.refresh_actions())
        self.refresh_actions()
        self.event_poller = root.after(50, self.drain_events)
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        root.bind_all('<MouseWheel>', self._on_mousewheel)
        root.bind_all('<Button-4>', self._on_mousewheel)
        root.bind_all('<Button-5>', self._on_mousewheel)

    def post(self, event, *args):
        self.events.put((event, args))

    def drain_events(self):
        for _ in range(200):
            try:
                event, args = self.events.get_nowait()
            except queue.Empty:
                break
            if event == 'closed':
                self.root.destroy()
                return
            if self.closing:
                if event == 'finished':
                    self.start_cleanup()
                continue
            if event == 'fetched':
                self.populate_checkboxes(*args)
            elif event == 'fetch_error':
                self.set_busy(None)
                self.set_status(args[0], error=True)
            elif event == 'status':
                self.set_status(args[0])
            elif event == 'browser_closing':
                self.set_busy('finishing')
                self.set_status('Closing all extraction browser tabs...')
            elif event == 'job':
                self.update_job(args[0])
            elif event == 'progress':
                self.update_progress(*args)
            elif event == 'error':
                self.run_error = args[0]
            elif event == 'finished':
                self.finish_extraction(args[0])
        self.event_poller = self.root.after(50, self.drain_events)

    def set_status(self, message, error=False, level=None):
        self.status_var.set(message)
        self.status_label.configure(foreground=self.colors['danger'] if error else self.colors['text'])
        label = 'Error' if error else level or ('Working' if self.operation else 'Ready')
        colors = {
            'Error': (self.colors['danger'], 'white'),
            'Working': (self.colors['step_active'], 'white'),
            'Done': (self.colors['success'], 'white'),
            'Copied': (self.colors['success'], 'white'),
        }
        background, foreground = colors.get(label, (self.colors['step_pending_bg'], self.colors['step_pending_fg']))
        self.status_badge.configure(text=label, background=background, foreground=foreground)

    def valid_page_url(self):
        try:
            parsed = urlparse(self.url_var.get().strip())
            return parsed.scheme in ('http', 'https') and bool(parsed.hostname)
        except ValueError:
            return False

    def source_is_changed(self):
        return self.loaded_url is not None and self.loaded_url != self.url_var.get().strip()

    def source_changed(self, *args):
        if not self.operation:
            self.set_phase(1 if self.source_is_changed() or not self.checkbox_vars else 2)
        self.refresh_actions()

    def unfinished_urls(self):
        if self.batch_url != self.loaded_url:
            return set()
        return {job.url for job in self.results.values()
                if job.state in ('Failed', 'Timed out', 'Cancelled') and job.url in self.checkbox_vars}

    def refresh_actions(self):
        busy = self.operation is not None
        has_files = bool(self.checkbox_vars)
        count = sum(variable.get() for variable in self.checkbox_vars.values())
        changed = self.source_is_changed()
        try:
            valid_tabs = MIN_TABS <= int(self.tabs_var.get()) <= MAX_TABS
        except ValueError:
            valid_tabs = False

        def enable(widget, enabled):
            widget.configure(state='normal' if enabled else 'disabled')

        enable(self.url_entry, not busy)
        enable(self.fetch_btn, not busy and self.valid_page_url())
        self.fetch_btn.configure(text='Loading...' if self.operation == 'fetch' else 'Reload files' if self.loaded_url is not None and not changed else 'Load files',
            style='Primary.TButton' if not has_files or changed else 'TButton')
        enable(self.select_all_btn, not busy and has_files and count < len(self.checkbox_vars))
        enable(self.deselect_all_btn, not busy and count > 0)
        enable(self.unfinished_btn, not busy and not changed and bool(self.unfinished_urls()))
        for widget in self.file_widgets:
            enable(widget, not busy and not changed)
        self.browser_combo.configure(state='readonly' if has_files and not busy and not changed else 'disabled')
        enable(self.tabs_spin, has_files and not busy and not changed)
        enable(self.extract_btn, not busy and count > 0 and not changed and valid_tabs)
        self.extract_btn.configure(text='Closing browser...' if self.operation == 'finishing' else 'Extracting...' if self.operation == 'extract' else f'Extract {count} file' + ('' if count == 1 else 's') if count else 'Extract selected',
            style='Primary.TButton' if self.phase == 2 else 'TButton')
        enable(self.stop_btn, self.operation == 'extract' and not self.stop_event.is_set())
        self.stop_btn.configure(text='Stopping...' if self.operation == 'extract' and self.stop_event.is_set() else 'Stop')
        links = self.successful_links()
        enable(self.clear_btn, not busy and bool(self.results))
        enable(self.copy_btn, self.operation != 'closing' and bool(links))
        self.copy_btn.configure(text=f'Copy all ({len(links)})', style='Primary.TButton' if self.phase == 3 and not busy else 'TButton')
        enable(self.copy_selected_btn, self.operation != 'closing' and bool(self.successful_links(selected_only=True)))
        self.source_hint_var.set('URL changed. Load files to update the selection.' if changed else
            'Enter a full URL starting with https://.' if self.url_var.get().strip() and not self.valid_page_url() else
            f'{len(self.checkbox_vars)} files loaded. Completed links are kept until the next extraction.' if self.loaded_url is not None else
            'Paste a full page URL to find its files.')
        hint = ('Load the updated page before extracting.' if changed else
                'Selection is locked until this operation finishes.' if busy else
                'Load a page to enable extraction.' if not has_files else
                f'Enter a whole tab limit from {MIN_TABS} to {MAX_TABS}.' if not valid_tabs else
                'Select at least one file to extract.' if not count else
                'Browser closes when finished or stopped.')
        self.selection_hint_var.set(hint)
        self.selection_hint.configure(foreground=self.colors['danger'] if has_files and not valid_tabs else self.colors['muted'])

    def set_busy(self, operation):
        self.operation = operation
        self.refresh_actions()
        if operation in ('fetch', 'extract'):
            self.progress.stop()
            self.progress.configure(mode='indeterminate', maximum=100, value=0)
            self.progress.start(12)
        else:
            value = self.progress['value'] if str(self.progress['mode']) == 'determinate' else 0
            self.progress.stop()
            self.progress.configure(mode='determinate', value=value)

    def successful_links(self, selected_only=False):
        indices = None
        if selected_only:
            indices = {int(item.removeprefix('job-')) for item in self.result_tree.selection()}
        return [job.direct_url for index, job in sorted(self.results.items())
                if job.direct_url and (indices is None or index in indices)]

    def copy_to_clipboard(self, selected_only=False):
        links = self.successful_links(selected_only)
        if not links:
            self.set_status('There are no completed links to copy yet.')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(links))
        self.set_status(f'Copied {len(links)} link(s) to the clipboard.', level='Copied')

    def clear_output(self, notify=True):
        if self.operation:
            return
        self.result_tree.delete(*self.result_tree.get_children())
        self.results.clear()
        self.batch_url = None
        self.result_var.set('0 links')
        self.output_empty.place(relx=0.5, rely=0.45, anchor='center')
        self.progress.configure(value=0)
        self.set_phase(2 if self.checkbox_vars and not self.source_is_changed() else 1)
        self.refresh_actions()
        if notify:
            self.set_status('Results cleared. Your file selection is kept.')

    def select_all(self):
        if not self.operation:
            for variable in self.checkbox_vars.values():
                variable.set(True)

    def deselect_all(self):
        if not self.operation:
            for variable in self.checkbox_vars.values():
                variable.set(False)

    def select_unfinished(self):
        if not self.operation and not self.source_is_changed():
            urls = self.unfinished_urls()
            for url, variable in self.checkbox_vars.items():
                variable.set(url in urls)
            self.set_status(f'Selected {len(urls)} unfinished file(s). Extract these to retry; copy completed links first.')

    def update_selection_count(self, *args):
        count = sum(variable.get() for variable in self.checkbox_vars.values())
        self.selection_var.set(f'{count} of {len(self.checkbox_vars)} selected')
        if not self.operation:
            self.set_phase(2 if self.checkbox_vars and not self.source_is_changed() else 1)
        self.refresh_actions()

    def start_fetch_thread(self):
        if self.operation:
            return
        url = self.url_var.get().strip()
        if not self.valid_page_url():
            self.set_status('Enter a full game-page URL starting with https://.', error=True)
            return
        self.set_busy('fetch')
        self.set_phase(1)
        self.set_status('Loading the page and finding its files...')
        threading.Thread(target=self.run_fetch, args=(url,), daemon=True).start()

    def run_fetch(self, url):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            response.raise_for_status()
            links = {}
            for anchor in BeautifulSoup(response.text, 'html.parser').find_all('a', href=True):
                link = urljoin(response.url, anchor['href'])
                host = urlparse(link).hostname or ''
                if host == 'fuckingfast.co' or host.endswith('.fuckingfast.co'):
                    links[link] = None
            self.post('fetched', list(links), url)
        except Exception:
            diag('FETCH ERROR\n' + traceback.format_exc())
            self.post('fetch_error', 'Could not load this page. Check the URL and connection, then retry.')

    def populate_checkboxes(self, links, url=None):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.checkbox_vars.clear()
        self.file_widgets.clear()
        self.loaded_url = self.url_var.get().strip() if url is None else url
        for link in links:
            variable = tk.BooleanVar(value=True)
            self.checkbox_vars[link] = variable
            variable.trace_add('write', self.update_selection_count)
            checkbox = tk.Checkbutton(self.scrollable_frame, text=filename_for(link), variable=variable,
                background='white', activebackground='white', foreground=self.colors['text'],
                selectcolor=self.colors['soft_orange'], disabledforeground=self.colors['disabled_fg'], font=(self.ui_font, 10),
                anchor='w', justify='left', wraplength=280, highlightthickness=0, bd=0,
                padx=8, pady=7)
            checkbox.pack(fill='x', anchor='w')
            self.file_widgets.append(checkbox)
        self.set_busy(None)
        self.update_selection_count()
        if links:
            self.files_empty.place_forget()
            self.set_phase(2)
            self.set_status(f'Found {len(links)} files. Choose your files and tab limit, then start extraction.')
        else:
            self.set_phase(1)
            self.files_empty.configure(text='No files found\nTry another FitGirl game page.')
            self.files_empty.place(relx=0.5, rely=0.45, anchor='center')
            self.set_status('This page contains no FuckingFast links.', error=True)

    def start_extraction_thread(self):
        if self.operation:
            return
        if self.source_is_changed():
            self.set_status('The page URL changed. Load files before starting extraction.', error=True)
            return
        links = [url for url, variable in self.checkbox_vars.items() if variable.get()]
        if not links:
            self.set_status('Choose at least one file first.', error=True)
            return
        try:
            limit = int(self.tabs_var.get())
            if not MIN_TABS <= limit <= MAX_TABS:
                raise ValueError
        except ValueError:
            self.set_status(f'Set Tabs at once to a whole number between {MIN_TABS} and {MAX_TABS}.', error=True)
            return
        self.clear_output(notify=False)
        self.batch_url = self.loaded_url
        for index, link in enumerate(links):
            self.update_job(Job(index, link, filename_for(link)))
        self.stop_event.clear()
        self.run_error = None
        browser = self.browser_var.get()
        self.save_settings(browser, limit)
        self.set_phase(2)
        self.set_busy('extract')
        self.set_status(f'Preparing {browser}. One browser window will be used for this batch.')
        threading.Thread(target=self.run_extraction, args=(links, browser, limit), daemon=True).start()

    def run_extraction(self, links, browser, limit):
        try:
            if self.stop_event.is_set():
                return
            self.driver = create_driver(browser)
            if self.stop_event.is_set():
                return
            self.driver.get('data:text/html;charset=utf-8,' + quote(BROWSER_HELP))
            self.tabs = BackgroundTabs(self.driver, on_diagnostic=diag)
            self.post('status', 'Extraction is running. Select a browser tab yourself if verification is needed.')
            TabQueue(self.tabs).run(links, limit, self.stop_event,
                on_job=lambda job: self.post('job', job),
                on_progress=lambda *args: self.post('progress', *args),
                on_error=lambda job, error: diag(f'TAB ERROR [{job.index + 1}] {job.filename}\n'
                    + ''.join(traceback.format_exception(error))))
        except Exception as error:
            diag('EXTRACTION ERROR\n' + traceback.format_exc())
            message = str(error) if isinstance(error, RuntimeError) else 'Could not start or contact the browser. Check it is installed, then retry.'
            self.post('error', message)
        finally:
            self.post('browser_closing')
            self.close_session()
            self.post('finished', self.stop_event.is_set())

    def update_job(self, job):
        self.results[job.index] = job
        item = f'job-{job.index}'
        values = (job.filename, job.state, job.direct_url or job.detail)
        if self.result_tree.exists(item):
            self.result_tree.item(item, values=values, tags=(job.state,))
        else:
            self.result_tree.insert('', 'end', iid=item, values=values, tags=(job.state,))
        self.output_empty.place_forget()
        count = len(self.successful_links())
        self.result_var.set(f'{count} links')
        self.refresh_actions()

    def update_progress(self, completed, total, active):
        self.progress.stop()
        self.progress.configure(mode='determinate', maximum=max(1, total), value=completed)
        if not self.stop_event.is_set():
            self.set_status(f'{completed} of {total} processed · {active} active tabs · {len(self.successful_links())} links ready. Complete any verification in the browser.')

    def finish_extraction(self, stopped):
        if self.closing:
            self.start_cleanup()
            return
        for job in list(self.results.values()):
            if job.state in ('Queued', 'Opening', 'Waiting', 'Verification'):
                job.state = 'Failed' if self.run_error else 'Cancelled'
                job.detail = 'Browser setup failed. Retry extraction.' if self.run_error else 'Stopped before a link was received.'
                self.update_job(job)
        ready = len(self.successful_links())
        failed = sum(job.state in ('Failed', 'Timed out') for job in self.results.values())
        self.set_phase(3 if ready else 2)
        self.set_busy(None)
        if self.run_error:
            self.set_status(self.run_error, error=True)
        elif stopped:
            self.set_status(f'Stopped. Browser closed. {ready} completed link(s) kept. Use Unfinished to select files to retry.', level='Stopped')
        else:
            self.set_status(f'Finished · Browser closed · {ready} links ready · {failed} unsuccessful. Copy links or select unfinished files to retry.',
                error=not ready and failed > 0, level='Done' if ready else 'Ready')

    def stop_extraction(self):
        if self.operation == 'extract':
            self.stop_event.set()
            self.refresh_actions()
            self.set_status('Stopping and closing all extraction browser tabs. Completed links will be kept.')

    def close_session(self):
        if self.tabs:
            try:
                self.tabs.close()
            except Exception:
                pass
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                diag('BROWSER CLOSE ERROR\n' + traceback.format_exc())
        self.driver = self.tabs = None

    def on_close(self):
        if self.closing:
            return
        extracting = self.operation in ('extract', 'finishing')
        self.closing = True
        self.stop_event.set()
        self.set_busy('closing')
        self.set_status('Closing the extraction browser...')
        if not extracting:
            self.start_cleanup()

    def start_cleanup(self):
        if self.cleanup_started:
            return
        self.cleanup_started = True
        def cleanup():
            self.close_session()
            self.post('closed')
        threading.Thread(target=cleanup, daemon=True).start()

    def load_settings(self):
        try:
            settings = json.loads((STATE_DIR / 'settings.json').read_text())
            if not isinstance(settings, dict):
                return
            if settings.get('browser') in BROWSERS:
                self.browser_var.set(settings['browser'])
            if type(settings.get('tabs')) is int and MIN_TABS <= settings['tabs'] <= MAX_TABS:
                self.tabs_var.set(str(settings['tabs']))
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self, browser, limit):
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            (STATE_DIR / 'settings.json').write_text(json.dumps({'browser': browser, 'tabs': limit}))
        except OSError:
            pass

    def _on_mousewheel(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget == self.canvas or (widget and str(widget).startswith(str(self.scrollable_frame))):
            direction = -1 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else 1
            self.canvas.yview_scroll(direction, 'units')


if __name__ == '__main__':
    if '--browser-smoke-test' in sys.argv:
        from smoke_browser import run_smoke_test
        run_smoke_test()
        sys.exit(0)
    root = tk.Tk(className='FitgirlFFExtractor')
    app = FitgirlExtractorApp(root)
    if '--smoke-test' in sys.argv:
        root.update()
        assert root.winfo_ismapped(), 'The application window did not open'
        print('GUI smoke test passed', flush=True)
        root.after(300, app.on_close)
    root.mainloop()
    if '--smoke-test' in sys.argv:
        faulthandler.cancel_dump_traceback_later()
