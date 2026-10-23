"""Real installed-browser test using only local fixture pages."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

from extraction import BackgroundTabs, TabQueue
from installed_browser import create_driver


def run_smoke_test():
    counters = {'active': 0, 'peak': 0}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            number = self.path.rsplit('/', 1)[-1]
            if self.path.startswith('/part/') and number in ('1', '2'):
                self.send_response(302)
                self.send_header('Location', f'http://localhost:{self.server.server_port}/transition/{number}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if self.path.startswith('/transition/'):
                page = f'''<title>Just a moment...</title><div id="challenge-stage">Loading fixture</div>
                    <script>setTimeout(()=>location.replace('/ready/{number}'),250)</script>'''.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            if self.path.startswith('/resolve/'):
                with lock:
                    counters['active'] += 1
                    counters['peak'] = max(counters['peak'], counters['active'])
                time.sleep(1)
                self.send_response(200)
                self.send_header('HX-Redirect', 'https://dl.fuckingfast.co/fixture/' + number)
                self.send_header('Content-Length', '0')
                self.end_headers()
                with lock:
                    counters['active'] -= 1
                return
            action = f"let x=new XMLHttpRequest();x.open('GET','/resolve/{number}');x.send();"
            if number == '4':
                action = "setTimeout(()=>location.href='https://dl.fuckingfast.co/fixture/4',50);"
            page = f'''<title>Fixture {number}</title><a href="#" hx-post="/resolve/{number}"
                onclick="this.setAttribute('disabled','');{action}return false">Download</a>'''.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    driver = None
    tabs = None
    try:
        driver = create_driver()
        driver.get('data:text/html,<title>Extraction browser test</title><h1>Control tab</h1>')
        tabs = BackgroundTabs(driver)
        urls = [f'http://127.0.0.1:{server.server_port}/part/{number}' for number in range(1, 5)]
        observed = []
        jobs = TabQueue(tabs, timeout=20, interval=0.2).run(urls, 2, threading.Event(),
            on_job=lambda job: observed.append(len(tabs.contexts)))
        assert all(job.state == 'Complete' for job in jobs), [(job.filename, job.state, job.detail) for job in jobs]
        assert [job.direct_url for job in jobs] == [f'https://dl.fuckingfast.co/fixture/{number}' for number in range(1, 5)]
        assert max(observed) == 2, observed
        assert counters['peak'] >= 2, 'The fixture requests did not overlap'
        assert not tabs.contexts, 'Finished extraction tabs were left open'
        visibility = tabs.command('script.evaluate', {'expression': 'document.visibilityState',
            'target': {'context': tabs.reference}, 'awaitPromise': False})
        assert visibility['result']['value'] == 'visible', 'The control tab lost focus'
        # Exercise the same cleanup used after success, Stop, and app shutdown.
        from ff_grabber import FitgirlExtractorApp
        browser_pid = getattr(driver, 'browser_pid', None)
        service_process = driver.service.process
        owner = SimpleNamespace(driver=driver, tabs=tabs)
        FitgirlExtractorApp.close_session(owner)
        assert owner.driver is None and owner.tabs is None
        driver = tabs = None
        service_process.wait(timeout=5)
        if browser_pid and sys.platform.startswith('linux'):
            def browser_running():
                try:
                    state = (Path('/proc') / str(browser_pid) / 'stat').read_text().rsplit(')', 1)[1].split()[0]
                    return state != 'Z'
                except FileNotFoundError:
                    return False
            deadline = time.monotonic() + 5
            while browser_running() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not browser_running(), 'The browser and its control tab were left open'
        print('Installed-browser smoke test passed: concurrent tabs, redirects, stable focus, blocked download, all browser tabs closed.', flush=True)
    finally:
        if tabs:
            tabs.close()
        if driver:
            driver.quit()
        server.shutdown()
        server.server_close()
