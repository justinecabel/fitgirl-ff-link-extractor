"""A bounded queue of background browser tabs, driven by one worker thread."""

from collections import deque
from dataclasses import dataclass, replace
import json
import time
from urllib.parse import unquote, urlparse

from websocket import create_connection


MIN_TABS = 1
MAX_TABS = 12
DEFAULT_TABS = 3


def filename_for(url):
    parsed = urlparse(url)
    return unquote(parsed.fragment or parsed.path.rsplit("/", 1)[-1] or url)


def is_direct_url(url):
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.hostname == "dl.fuckingfast.co"


class ProtocolError(RuntimeError):
    def __init__(self, message, *, code=None, method=None):
        super().__init__(message)
        self.code = code
        self.method = method


class TabClosed(ProtocolError):
    pass


INSTALL_SCRIPT = r"""() => {
    if (window.__ffInstalled) return;
    window.__ffInstalled = true;
    const capture = value => {
        try {
            const url = new URL(value, location.href);
            if (url.hostname === 'dl.fuckingfast.co' && /^https?:$/.test(url.protocol)) {
                window.__ffDirect = url.href;
                return true;
            }
        } catch (_) {}
        return false;
    };
    window.open = value => { capture(value); return null; };
    const send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...args) {
        this.addEventListener('load', () => {
            capture(this.getResponseHeader('HX-Redirect') || this.getResponseHeader('Location'));
        });
        return send.apply(this, args);
    };
    const fetch = window.fetch;
    window.fetch = async function(...args) {
        const response = await fetch.apply(this, args);
        capture(response.headers.get('HX-Redirect') || response.headers.get('Location'));
        capture(response.url);
        return response;
    };
    document.addEventListener('click', event => {
        const anchor = event.target.closest && event.target.closest('a');
        if (anchor && (capture(anchor.href) || anchor.target === '_blank')) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
}"""

POLL_SCRIPT = "(" + INSTALL_SCRIPT + r""")(); (() => {
    if (!document.body) return JSON.stringify({});
    const button = document.querySelector('a[hx-post], button[hx-post]');
    if (button && !button.hasAttribute('disabled') && button.getAttribute('aria-busy') !== 'true'
        && getComputedStyle(button).opacity !== '0.5') button.click();
    let url = window.__ffDirect;
    if (!url && location.hostname === 'dl.fuckingfast.co') url = location.href;
    if (!url) {
        const old = document.documentElement.innerHTML.match(/window\.open\(["'](https?:\/\/dl\.fuckingfast\.co\/[^"']+)["']/);
        if (old) url = old[1];
    }
    const verification = /just a moment|verify you are human|security verification/i.test(document.title)
        || !!document.querySelector('#challenge-running, #challenge-stage');
    return JSON.stringify({url, verification});
})()"""


class BackgroundTabs:
    """Use WebDriver BiDi so polling never activates or switches visible tabs."""
    def __init__(self, driver, *, on_diagnostic=lambda message: None):
        endpoint = driver.capabilities.get("webSocketUrl")
        if not endpoint:
            raise ProtocolError("This browser cannot control background tabs. Update the browser and retry.")
        self.socket = create_connection(endpoint, timeout=8, suppress_origin=True)
        self.counter = 0
        self.contexts = {}
        self.direct_urls = {}
        self.navigating = set()
        self.on_diagnostic = on_diagnostic
        self.reference = None
        try:
            self.reference = self.command("browsingContext.getTree", {})["contexts"][0]["context"]
            self.command("session.subscribe", {"events": ["network.beforeRequestSent"]})
            self.intercept = self.command("network.addIntercept", {
                "phases": ["beforeRequestSent"],
                "urlPatterns": [{"type": "pattern", "hostname": "dl.fuckingfast.co"}],
            })["intercept"]
        except Exception:
            self.socket.close()
            raise

    def _send(self, method, params):
        self.counter += 1
        self.socket.send(json.dumps({"id": self.counter, "method": method, "params": params}))
        return self.counter

    def command(self, method, params):
        wanted = self._send(method, params)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            message = json.loads(self.socket.recv())
            if message.get("method") == "network.beforeRequestSent":
                event = message["params"]
                request = event["request"]
                if event.get("isBlocked"):
                    if is_direct_url(request.get("url")):
                        self.direct_urls[event.get("context")] = request["url"]
                    # Prevent actual file downloads and browser download prompts.
                    self._send("network.failRequest", {"request": request["request"]})
            if message.get("id") == wanted:
                if message.get("type") == "error":
                    code = message.get("error")
                    error_class = TabClosed if code in ("no such frame", "no such window") else ProtocolError
                    raise error_class(message.get("message", "Browser command failed."), code=code, method=method)
                return message.get("result", {})
        raise ProtocolError("The browser is not responding.")

    def is_alive(self):
        try:
            return bool(self.command("browsingContext.getTree", {"root": self.reference, "maxDepth": 0})["contexts"])
        except Exception:
            return False

    def open(self, url):
        context = self.command("browsingContext.create", {
            "type": "tab", "background": True, "referenceContext": self.reference,
        })["context"]
        self.contexts[context] = None
        try:
            self.contexts[context] = self.command("script.addPreloadScript", {
                "functionDeclaration": INSTALL_SCRIPT, "contexts": [context],
            })["script"]
            self.command("browsingContext.navigate", {"context": context, "url": url, "wait": "none"})
            return context
        except Exception:
            self.close_tab(context)
            raise

    def poll(self, context):
        if context in self.direct_urls:
            return {"url": self.direct_urls[context]}
        try:
            result = self.command("script.evaluate", {
                "expression": POLL_SCRIPT, "target": {"context": context}, "awaitPromise": False,
            })
        except ProtocolError as error:
            # Chrome can replace a script context during a redirect or verification.
            # The top-level tab can still exist, so wait for its next document.
            transitions = ("cannot find context with specified id", "execution context was destroyed",
                           "cannot find default execution context", "no such execution context")
            if error.code not in ("no such frame", "no such window") and not any(
                    text in str(error).lower() for text in transitions):
                raise
            tree = self.command("browsingContext.getTree", {"root": context, "maxDepth": 0})
            if not tree.get("contexts"):
                raise TabClosed("The browser tab was closed.") from error
            if context not in self.navigating:
                self.on_diagnostic(f"TAB NAVIGATION: {error.method} [{error.code}]: {error}")
                self.navigating.add(context)
            return {}
        if context in self.direct_urls:
            return {"url": self.direct_urls[context]}
        value = result.get("result", {})
        if result.get("type") == "success" and value.get("type") == "string":
            self.navigating.discard(context)
            return json.loads(value["value"])
        return {}  # A navigation can briefly replace the document being inspected.

    def close_tab(self, context):
        script = self.contexts.pop(context, None)
        try:
            self.command("browsingContext.close", {"context": context})
        except Exception:
            pass
        if script:
            try:
                self.command("script.removePreloadScript", {"script": script})
            except Exception:
                pass
        self.direct_urls.pop(context, None)
        self.navigating.discard(context)

    def close(self):
        for context in list(self.contexts):
            self.close_tab(context)
        try:
            self.command("network.removeIntercept", {"intercept": self.intercept})
        except Exception:
            pass
        self.socket.close()


@dataclass
class Job:
    index: int
    url: str
    filename: str
    state: str = "Queued"
    direct_url: str = ""
    detail: str = ""
    started: float = 0
    context: str | None = None


class TabQueue:
    def __init__(self, tabs, *, timeout=120, interval=0.5, clock=time.monotonic):
        self.tabs = tabs
        self.timeout = timeout
        self.interval = interval
        self.clock = clock

    def run(self, urls, limit, stop, on_job=lambda job: None, on_progress=lambda *args: None,
            on_error=lambda job, error: None):
        if not MIN_TABS <= limit <= MAX_TABS:
            raise ValueError(f"Choose between {MIN_TABS} and {MAX_TABS} concurrent tabs.")
        jobs = [Job(index, url, filename_for(url)) for index, url in enumerate(urls)]
        pending = deque(jobs)
        active = {}
        completed = 0
        for job in jobs:
            on_job(replace(job))

        def finish(job, state, detail=""):
            nonlocal completed
            job.state, job.detail = state, detail
            if job.context is not None:
                self.tabs.close_tab(job.context)
                active.pop(job.context, None)
            if state != "Cancelled":
                completed += 1
            on_job(replace(job))

        try:
            while pending or active:
                if stop.is_set():
                    break
                while pending and len(active) < limit and not stop.is_set():
                    job = pending.popleft()
                    job.state = "Opening"
                    on_job(replace(job))
                    try:
                        job.context = self.tabs.open(job.url)
                        job.started = self.clock()
                        job.state = "Waiting"
                        active[job.context] = job
                        on_job(replace(job))
                    except Exception as error:
                        on_error(replace(job), error)
                        finish(job, "Failed", "Could not open this tab. Retry the file.")
                for job in list(active.values()):
                    if stop.is_set():
                        break
                    try:
                        info = self.tabs.poll(job.context)
                        if is_direct_url(info.get("url")):
                            job.direct_url = info["url"]
                            finish(job, "Complete")
                        elif self.clock() - job.started >= self.timeout:
                            finish(job, "Timed out", "No link received. Complete verification and retry.")
                        else:
                            state = "Verification" if info.get("verification") else "Waiting"
                            if state != job.state:
                                job.state = state
                                on_job(replace(job))
                    except TabClosed as error:
                        on_error(replace(job), error)
                        finish(job, "Failed", "The browser tab was closed. Retry the file.")
                    except Exception as error:
                        on_error(replace(job), error)
                        detail = " ".join(str(error).split())[:180] or type(error).__name__
                        finish(job, "Failed", f"Browser error: {detail}. Retry the file; details are in diagnostics.log.")
                on_progress(completed, len(jobs), len(active))
                if pending or active:
                    stop.wait(self.interval)
        finally:
            for job in list(active.values()) + list(pending):
                finish(job, "Cancelled", "Stopped before a link was received.")
            on_progress(completed, len(jobs), 0)
        return jobs
