"""Launch one installed browser. Only its matching automation driver is managed."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import sys

import setuptools  # Register distutils before the Chrome driver imports it.
import undetected_chromedriver as uc
from selenium import webdriver


BROWSERS = ("Auto-Detect Browser", "Google Chrome", "Microsoft Edge", "Brave", "Mozilla Firefox")


class BrowserError(RuntimeError):
    pass


@contextmanager
def system_browser_environment():
    """Keep frozen-app and Snap-editor GUI libraries out of an external browser."""
    saved = {}
    prefixes = [os.environ[name] for name in ("SNAP", "SNAP_USER_DATA", "SNAP_USER_COMMON") if os.environ.get(name)]
    if getattr(sys, "frozen", False):
        prefixes.append(getattr(sys, "_MEIPASS", ""))
    prefixes = [prefix.rstrip("/") + "/" for prefix in prefixes if prefix]

    def set_variable(name, value):
        saved[name] = os.environ.get(name)
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        set_variable("LD_LIBRARY_PATH", os.environ.get("LD_LIBRARY_PATH_ORIG"))
    for name in ("GSETTINGS_SCHEMA_DIR", "GTK_PATH", "GTK_EXE_PREFIX", "GTK_DATA_PREFIX",
                 "GIO_EXTRA_MODULES", "GIO_MODULE_DIR", "GDK_PIXBUF_MODULE_FILE",
                 "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        value = os.environ.get(name, "")
        if any(part.startswith(tuple(prefixes)) for part in value.split(os.pathsep)):
            set_variable(name, None)
    if prefixes and os.environ.get("XDG_DATA_DIRS"):
        paths = os.environ["XDG_DATA_DIRS"].split(os.pathsep)
        cleaned = [path for path in paths if not (path.rstrip("/") + "/").startswith(tuple(prefixes))]
        if cleaned != paths:
            set_variable("XDG_DATA_DIRS", os.pathsep.join(cleaned))
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def find_browser(selection="Auto-Detect Browser"):
    names = {
        "Google Chrome": ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"),
        "Microsoft Edge": ("microsoft-edge-stable", "microsoft-edge", "msedge"),
        "Brave": ("brave-browser", "brave"),
        "Mozilla Firefox": ("firefox",),
    }
    paths = {
        "Google Chrome": (r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe", r"%LocalAppData%\Google\Chrome\Application\chrome.exe", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "Microsoft Edge": (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        "Brave": (r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe", r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe", "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        "Mozilla Firefox": (r"%ProgramFiles%\Mozilla Firefox\firefox.exe", r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe", "/Applications/Firefox.app/Contents/MacOS/firefox"),
    }
    choices = BROWSERS[1:] if selection == BROWSERS[0] else (selection,)
    for choice in choices:
        for name in names.get(choice, ()):
            executable = shutil.which(name)
            if executable:
                return choice, executable
        for path in paths.get(choice, ()):
            executable = os.path.expandvars(path)
            if Path(executable).is_file() and os.access(executable, os.X_OK):
                return choice, executable
    raise BrowserError(f"{selection} was not found. Install Chrome, Edge, Brave, or Firefox, then retry.")


def create_driver(selection="Auto-Detect Browser", *, headless=False):
    kind, executable = find_browser(selection)

    def launch(version=None):
        if kind == "Mozilla Firefox":
            options = webdriver.FirefoxOptions()
            options.binary_location = executable
            if headless:
                options.add_argument("-headless")
            options.set_capability("webSocketUrl", True)
            return webdriver.Firefox(options=options)
        if kind == "Microsoft Edge":
            options = webdriver.EdgeOptions()
        else:
            options = uc.ChromeOptions()
        options.binary_location = executable
        options.set_capability("webSocketUrl", True)
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        if kind == "Microsoft Edge":
            if headless:
                options.add_argument("--headless=new")
            return webdriver.Edge(options=options)
        return uc.Chrome(options=options, browser_executable_path=executable,
                         version_main=version, headless=headless,
                         use_subprocess=True, no_sandbox=False)

    with system_browser_environment():
        try:
            driver = launch()
        except Exception as error:
            match = re.search(r"Current browser version is (\d+)", str(error))
            if kind in ("Google Chrome", "Brave") and match:
                driver = launch(int(match.group(1)))
            else:
                raise
    return driver
