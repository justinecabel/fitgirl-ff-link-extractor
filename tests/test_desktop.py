import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import ff_grabber
from extraction import Job
from installed_browser import BROWSERS, system_browser_environment


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state_patch = patch.object(ff_grabber, 'STATE_DIR', Path(self.temporary.name))
        self.state_patch.start()
        self.root = tk.Tk()
        self.app = ff_grabber.FitgirlExtractorApp(self.root)
        self.root.update()

    def tearDown(self):
        self.root.after_cancel(self.app.event_poller)
        self.root.destroy()
        self.state_patch.stop()
        self.temporary.cleanup()

    def test_default_is_installed_browser_with_three_tabs(self):
        self.assertEqual(self.app.browser_var.get(), BROWSERS[0])
        self.assertEqual(self.app.tabs_var.get(), '3')

    def test_tab_limit_is_saved_and_invalid_settings_do_not_break_startup(self):
        self.app.save_settings('Google Chrome', 7)
        self.app.load_settings()
        self.assertEqual(self.app.browser_var.get(), 'Google Chrome')
        self.assertEqual(self.app.tabs_var.get(), '7')
        (ff_grabber.STATE_DIR / 'settings.json').write_text('[]')
        self.app.load_settings()
        self.assertEqual(self.app.tabs_var.get(), '7')

    def test_file_selection_updates_the_start_button(self):
        self.app.populate_checkboxes(['https://fuckingfast.co/one#part-01.bin', 'https://fuckingfast.co/two#extra.bin'])
        self.assertEqual(self.app.selection_var.get(), '2 of 2 selected')
        self.app.deselect_all()
        self.assertTrue(self.app.extract_btn.instate(['disabled']))
        self.app.select_all()
        self.assertEqual(self.app.selection_var.get(), '2 of 2 selected')
        self.assertFalse(self.app.extract_btn.instate(['disabled']))

    def test_result_rows_and_clipboard_preserve_input_order(self):
        for index in range(3):
            self.app.update_job(Job(index, f'page/{index}', f'file-{index}'))
        self.app.update_job(Job(2, 'page/2', 'file-2', 'Complete', 'https://dl.fuckingfast.co/2'))
        self.app.update_job(Job(0, 'page/0', 'file-0', 'Complete', 'https://dl.fuckingfast.co/0'))
        self.app.update_job(Job(1, 'page/1', 'file-1', 'Failed', detail='Closed tab'))
        self.assertEqual(self.app.result_tree.get_children(), ('job-0', 'job-1', 'job-2'))
        self.app.copy_to_clipboard()
        self.assertEqual(self.root.clipboard_get(), 'https://dl.fuckingfast.co/0\nhttps://dl.fuckingfast.co/2')
        self.assertIn('Copied 2', self.app.status_var.get())

    def test_invalid_tab_limit_is_inline_and_does_not_start_a_worker(self):
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        for value in ('0', '13', 'many', '2.5'):
            self.app.tabs_var.set(value)
            with patch('ff_grabber.threading.Thread') as thread:
                self.app.start_extraction_thread()
                thread.assert_not_called()
            self.assertIsNone(self.app.operation)
            self.assertIn('between 1 and 12', self.app.status_var.get())

    def test_clear_restores_empty_queue(self):
        self.app.update_job(Job(0, 'page', 'file', 'Complete', 'https://dl.fuckingfast.co/file'))
        self.app.clear_output()
        self.root.update()
        self.assertFalse(self.app.result_tree.get_children())
        self.assertTrue(self.app.output_empty.winfo_ismapped())
        self.assertTrue(self.app.copy_btn.instate(['disabled']))

    def test_busy_state_locks_settings_and_stop_keeps_existing_links(self):
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        self.app.update_job(Job(0, 'page', 'file', 'Complete', 'https://dl.fuckingfast.co/file'))
        self.app.set_busy('extract')
        self.assertEqual(str(self.app.browser_combo['state']), 'disabled')
        self.assertEqual(str(self.app.tabs_spin['state']), 'disabled')
        self.app.stop_extraction()
        self.assertTrue(self.app.stop_event.is_set())
        self.app.finish_extraction(True)
        self.assertEqual(self.app.successful_links(), ['https://dl.fuckingfast.co/file'])
        self.assertEqual(str(self.app.browser_combo['state']), 'readonly')

    def test_controls_fit_the_minimum_window(self):
        self.root.geometry('920x720')
        self.root.update()
        for widget in (self.app.url_entry, self.app.fetch_btn, self.app.browser_combo,
                       self.app.tabs_spin, self.app.extract_btn, self.app.stop_btn,
                       self.app.copy_btn, self.app.copy_selected_btn, self.app.clear_btn,
                       self.app.select_all_btn, self.app.deselect_all_btn, self.app.unfinished_btn):
            with self.subTest(widget=widget):
                self.assertTrue(widget.winfo_ismapped())
                self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())


    def test_buttons_follow_selection_and_result_state(self):
        self.assertTrue(self.app.fetch_btn.instate(['disabled']))
        self.assertTrue(self.app.select_all_btn.instate(['disabled']))
        self.assertTrue(self.app.clear_btn.instate(['disabled']))
        self.assertEqual(str(self.app.browser_combo['state']), 'disabled')
        self.app.url_var.set('https://example.test/game')
        self.assertFalse(self.app.fetch_btn.instate(['disabled']))
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        self.assertTrue(self.app.select_all_btn.instate(['disabled']))
        self.assertFalse(self.app.deselect_all_btn.instate(['disabled']))
        self.assertEqual(self.app.extract_btn['text'], 'Extract 1 file')
        self.app.deselect_all()
        self.assertTrue(self.app.deselect_all_btn.instate(['disabled']))
        self.assertTrue(self.app.extract_btn.instate(['disabled']))
        self.app.select_all()
        self.app.tabs_var.set('0')
        self.assertTrue(self.app.extract_btn.instate(['disabled']))
        self.assertIn('1 to 12', self.app.selection_hint_var.get())

    def test_extraction_controls_belong_to_the_file_panel(self):
        for widget in (self.app.extract_btn, self.app.stop_btn, self.app.tabs_spin, self.app.browser_combo):
            self.assertTrue(str(widget).startswith(str(self.app.files_panel) + '.'))
            self.assertFalse(str(widget).startswith(str(self.app.source_panel) + '.'))

    def test_changing_the_page_requires_reload_and_keeps_completed_links(self):
        self.app.url_var.set('https://example.test/first')
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        self.app.update_job(Job(0, 'https://fuckingfast.co/one', 'one', 'Complete', 'https://dl.fuckingfast.co/one'))
        self.app.url_var.set('https://example.test/second')
        self.assertTrue(self.app.extract_btn.instate(['disabled']))
        with patch('ff_grabber.threading.Thread') as worker:
            self.app.start_extraction_thread()
            worker.assert_not_called()
        self.assertIn('URL changed', self.app.status_var.get())
        self.app.populate_checkboxes(['https://fuckingfast.co/two'])
        self.assertEqual(self.app.successful_links(), ['https://dl.fuckingfast.co/one'])
        self.assertFalse(self.app.copy_btn.instate(['disabled']))

    def test_copy_selected_excludes_failed_and_unselected_rows(self):
        for index, state in enumerate(('Complete', 'Failed', 'Complete')):
            self.app.update_job(Job(index, f'page/{index}', f'file-{index}', state,
                f'https://dl.fuckingfast.co/{index}' if state == 'Complete' else ''))
        self.app.result_tree.selection_set(('job-0', 'job-1'))
        self.root.update()
        self.assertFalse(self.app.copy_selected_btn.instate(['disabled']))
        self.app.copy_selected_btn.invoke()
        self.assertEqual(self.root.clipboard_get(), 'https://dl.fuckingfast.co/0')
        self.app.result_tree.selection_set(('job-1',))
        self.root.update()
        self.assertTrue(self.app.copy_selected_btn.instate(['disabled']))

    def test_unfinished_selects_only_retryable_files_from_this_page(self):
        urls = ['https://fuckingfast.co/' + str(index) for index in range(4)]
        self.app.populate_checkboxes(urls)
        self.app.batch_url = self.app.loaded_url
        for index, state in enumerate(('Complete', 'Failed', 'Timed out', 'Cancelled')):
            self.app.update_job(Job(index, urls[index], f'file-{index}', state,
                'https://dl.fuckingfast.co/0' if index == 0 else ''))
        self.assertFalse(self.app.unfinished_btn.instate(['disabled']))
        self.app.unfinished_btn.invoke()
        self.assertEqual([v.get() for v in self.app.checkbox_vars.values()], [False, True, True, True])
        self.assertEqual(self.app.successful_links(), ['https://dl.fuckingfast.co/0'])

    def test_finishing_disables_stop_until_browser_cleanup_completes(self):
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        self.app.set_busy('finishing')
        self.assertTrue(self.app.stop_btn.instate(['disabled']))
        self.assertTrue(self.app.extract_btn.instate(['disabled']))
        self.assertEqual(self.app.extract_btn['text'], 'Closing browser...')

    def test_completion_keeps_full_progress_and_promotes_copy(self):
        self.app.populate_checkboxes(['https://fuckingfast.co/one'])
        self.app.set_busy('extract')
        self.app.update_job(Job(0, 'https://fuckingfast.co/one', 'one', 'Complete', 'https://dl.fuckingfast.co/one'))
        self.app.update_progress(1, 1, 0)
        self.app.set_busy('finishing')
        self.app.finish_extraction(False)
        self.assertEqual(self.app.progress['value'], 1)
        self.assertEqual(self.app.progress['maximum'], 1)
        self.assertEqual(self.app.copy_btn['style'], 'Primary.TButton')
        self.assertEqual(self.app.extract_btn['style'], 'TButton')
        self.assertEqual(self.app.phase, 3)

    def test_browser_is_quit_after_success_stop_or_setup_error(self):
        for outcome in ('success', 'stop', 'setup-error'):
            with self.subTest(outcome=outcome):
                self.app.stop_event.clear()
                driver = Mock()
                tabs = Mock()
                def batch(*args, **kwargs):
                    if outcome == 'stop':
                        self.app.stop_event.set()
                with patch('ff_grabber.create_driver', return_value=driver), \
                        patch('ff_grabber.BackgroundTabs', return_value=tabs) as factory, \
                        patch('ff_grabber.TabQueue') as queue, patch('ff_grabber.diag'):
                    queue.return_value.run.side_effect = batch
                    if outcome == 'setup-error':
                        factory.side_effect = RuntimeError('Browser setup failed')
                    self.app.run_extraction(['https://fuckingfast.co/one'], 'Google Chrome', 2)
                driver.quit.assert_called_once()
                self.assertIsNone(self.app.driver)
                self.assertIsNone(self.app.tabs)
                if outcome != 'setup-error':
                    tabs.close.assert_called_once()

    def test_failed_batch_shows_an_error_and_keeps_retry_available(self):
        url = 'https://fuckingfast.co/one'
        self.app.populate_checkboxes([url])
        self.app.batch_url = self.app.loaded_url
        self.app.update_job(Job(0, url, 'one', 'Failed', detail='Tab closed'))
        self.app.finish_extraction(False)
        self.assertEqual(self.app.status_badge['text'], 'Error')
        self.assertTrue(self.app.copy_btn.instate(['disabled']))
        self.assertFalse(self.app.extract_btn.instate(['disabled']))
        self.assertFalse(self.app.unfinished_btn.instate(['disabled']))

    def test_active_and_flow_text_have_strong_contrast(self):
        def luminance(color):
            values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
            return sum(v * weight for v, weight in zip(values, (0.2126, 0.7152, 0.0722)))
        pairs = [(self.app.colors['step_active'], '#ffffff'),
                 (self.app.colors['success_bg'], self.app.colors['success']),
                 (self.app.colors['step_pending_bg'], self.app.colors['step_pending_fg']),
                 ('#ffffff', self.app.colors['muted'])]
        for style in ('Primary.TButton', 'Stop.TButton', 'TButton'):
            for state in ((), ('active',), ('pressed',), ('disabled',)):
                pairs.append((self.app.style.lookup(style, 'background', state),
                              self.app.style.lookup(style, 'foreground', state)))
        for background, foreground in pairs:
            if foreground == 'white':
                foreground = '#ffffff'
            if background == 'white':
                background = '#ffffff'
            high, low = sorted((luminance(background), luminance(foreground)), reverse=True)
            self.assertGreaterEqual((high + 0.05) / (low + 0.05), 4.5, (background, foreground))


class EnvironmentTests(unittest.TestCase):
    def test_snap_editor_settings_are_removed_only_for_the_browser(self):
        values = {'SNAP': '/snap/code/272', 'SNAP_USER_DATA': '/home/user/snap/code/272',
                  'GSETTINGS_SCHEMA_DIR': '/home/user/snap/code/272/schemas',
                  'GTK_PATH': '/snap/code/272/gtk', 'XDG_DATA_DIRS': '/snap/code/272/share:/usr/share'}
        with patch.dict(os.environ, values):
            with system_browser_environment():
                self.assertNotIn('GSETTINGS_SCHEMA_DIR', os.environ)
                self.assertNotIn('GTK_PATH', os.environ)
                self.assertEqual(os.environ['XDG_DATA_DIRS'], '/usr/share')
            self.assertEqual(os.environ['GTK_PATH'], values['GTK_PATH'])

    def test_frozen_library_path_is_restored_after_an_error(self):
        with patch.object(ff_grabber.sys, 'frozen', True, create=True), \
                patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundle', 'LD_LIBRARY_PATH_ORIG': '/system'}):
            with self.assertRaises(RuntimeError):
                with system_browser_environment():
                    self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/system')
                    raise RuntimeError('driver failure')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundle')
