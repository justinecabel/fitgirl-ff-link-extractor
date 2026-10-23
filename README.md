# FitGirl FuckingFast Link Extractor

A Python desktop app that finds FuckingFast files on FitGirl pages and extracts
their direct download URLs for a download manager.

## One screen, three steps

1. **Load a game page.** Paste the page URL and choose **Load files**.
2. **Select and extract files.** Choose the parts you need. The browser selector,
   **Tabs at once** (1–12, default **3**), **Extract**, and **Stop** are all in the
   file-selection panel. **All**, **None**, and **Unfinished** adjust the selection.
3. **Copy links.** Use **Copy all** for every completed link, or select completed
   rows and choose **Copy selected** (Ctrl+C also works).

The current step has a dark aubergine background and an explicit Current label;
finished steps have a check mark. Action buttons use darker orange with readable
white text. Loading, extraction, stopping, and completion have explicit text
states. Controls are enabled only when their action is available.

Results stay in file order even when tabs finish in a different order. **Stop**
cancels unfinished files, closes the extraction browser, and keeps completed
links available for copying. **Unfinished** selects only failed, timed-out, or
cancelled files from the current page so they can be retried.

Editing the page URL requires **Load files** before extraction can start with
that new page. Loading a page keeps completed results available. Starting a new
extraction replaces the queue, so copy any links you need first. **Clear** clears
only the results and keeps the file selection.

## Browser behavior

Install **Chrome/Chromium, Edge, Brave, or Firefox** first. Auto-detect checks
those browsers in that order; the selector also lets you choose one explicitly.
Each batch opens one separate automation window with up to your chosen number
of extraction tabs in the background. Polling
and opening tabs do not select them or switch the focused tab. Completed tabs
close and the next queued file takes the available slot.

If verification is needed, select that browser tab and complete the check.
The app does not switch tabs for you. Each file has a two-minute limit; a
closed or unsuccessful tab does not stop the other files. The app intercepts
direct downloads to collect the URLs, rather than downloading the files.
When a batch finishes, fails, or is stopped, the app closes its entire automation
window, including the extractor information tab. Closing the app also closes
that window. The next batch opens a fresh automation window.

Redirects and verification pages can briefly replace a tab's script context.
The app waits for the new document while the tab remains open, instead of
failing the file immediately. Persistent browser errors retain their cause
in the queue and `diagnostics.log`.

**No lightweight browser is bundled or downloaded.** Browser automation may
still download a small matching **driver** on first use. Your installed
browser supplies the browser engine. Use an up-to-date browser with WebDriver
BiDi support. This version was tested with Chrome on Ubuntu; other listed
browsers and Linux distributions have not been runtime-tested here. Snap or
Flatpak browser packaging can also affect driver compatibility.

Browser and tab-limit choices are saved in
`~/.local/state/fitgirl-ff-link-extractor/settings.json` on Linux (or under
`$XDG_STATE_HOME`). Startup and extraction errors are logged to `diagnostics.log`
in the same directory.

## Releases

The current named release is **0.4.0 Alpha 1** (`v0.4.0-alpha.1`), marked as a GitHub
prerelease. Installers are published on the
[Releases page](https://github.com/justinecabel/fitgirl-ff-link-extractor/releases).
The alpha is intended for testing and feedback.

The **Publish release** workflow builds both installers, runs the Linux checks,
attaches the `.deb`, Windows `.exe`, and `SHA256SUMS`, then publishes the release.
Alpha, beta, and release-candidate tags are marked **Pre-release** and do not
replace the latest stable release. Assets are uploaded to a draft before it
is published.

To publish another alpha, set `VERSION` to `0.4.0-alpha.2`, commit, and push to
`main`. A version-changing push starts the release workflow and creates its
matching tag. You can also run **Actions → Publish release → Run workflow**,
or push an explicit matching `v*` tag. Release tags must match `VERSION`.
Published tags and assets are left unchanged when a workflow is rerun.

### Automatic development versions

Every push to `main` starts **Publish development build**. The workflow takes
`0.4.0` from `VERSION` and allocates `0.4.0-dev.1`, `0.4.0-dev.2`, and so on.
After both installer builds and the Linux checks pass, it publishes a GitHub
prerelease with the `.deb`, `.exe`, and checksums. A push containing several
commits produces one build for its tip commit.

The development counter is GitHub's workflow run number. Retrying a run reuses
its version; starting a new manual run advances it. Different build versions
can run concurrently, so newer pushes do not cancel earlier development builds.
The counter continues when the base version changes.

`VERSION` remains the source for named alpha, beta, and stable releases. The
workflow creates no version-bump commits, and development releases do not become
the latest stable release. Update `VERSION` deliberately when starting a new
base version or publishing a named release.

Debian packages use `0.4.0~alpha.1` internally so an eventual stable `0.4.0`
upgrades correctly. The build script converts supported `-alpha`, `-beta`, and
`-rc`, and `-dev` version suffixes automatically.
Download filenames use `-alpha.1`; the package metadata keeps `~alpha.1`.

## Ubuntu installer (.deb)

The **Build Ubuntu DEB** GitHub Actions workflow builds an `amd64` / x86-64
installer on Ubuntu 22.04. It runs for pull requests, as part of named and
development releases, and manually through **Actions → Build Ubuntu DEB → Run workflow**.

After a successful run, download and unzip the
**FitGirl-FF-Link-Extractor-Ubuntu-amd64** artifact, then install its `.deb`:

```bash
sudo apt install ./fitgirl-ff-link-extractor_*.deb
```

Open **FitGirl Link Extractor** from the app menu or run
`fitgirl-ff-link-extractor`. The package includes Python, Tkinter, and Python
dependencies, so no virtual environment or pip setup is needed. An installed
browser is required separately.

CI packages target Ubuntu 22.04 and newer on x86-64. Other Debian-based systems
need compatible libraries and a graphical desktop. The package records the
build system's glibc version as its minimum requirement; locally built
packages can therefore require a newer Ubuntu version. There is no universal
installer for every Linux distribution or architecture.

Upgrading from 0.2.0 removes the obsolete AppArmor profile for its downloaded
browser. To reclaim the old browser cache after closing the old version:

```bash
rm -rf -- ~/.cache/fitgirl-ff-link-extractor/browser
```

Remove the app with:

```bash
sudo apt remove fitgirl-ff-link-extractor
```

### Build a .deb locally

```bash
sudo apt install python3-tk python3-venv binutils
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt
FF_BUILD_PYTHON=.venv/bin/python ./scripts/build_deb.sh
```

The installer is written to `dist/`. Pass a version as the first argument to
`build_deb.sh` or change `VERSION`. Tagged builds use the version after `v`;
other CI builds add a run number.

The workflow runs desktop and queue tests, validates the desktop entry, and
opens the packaged app under a virtual display. It also tests the packaged
app with an installed Chrome browser against local fixture pages: redirects, concurrent
requests, the tab limit, ordered results, focus preservation, interception of
direct downloads, and closing the entire browser including its information tab. Live download sites are not part of that test.

## Running from source

```bash
git clone https://github.com/justinecabel/fitgirl-ff-link-extractor.git
cd fitgirl-ff-link-extractor
```

### Ubuntu / Debian: setup and launch in one command

From a terminal in your desktop session:

```bash
./start.sh
```

The launcher installs missing Ubuntu packages (`python3`, `python3-tk`, and
`python3-venv` as needed), creates a local `.venv`, installs Python
dependencies, and opens the app. Ubuntu asks for an administrator password
only when system setup or removal of the old app browser profile is needed.
It does not install a browser. Rerun the same command to launch the app again
or retry interrupted setup.

On other Linux distributions, install Python, Tkinter, and venv support using
your distribution's package manager, then create the environment, install
`requirements.txt`, and run `ff_grabber.py` manually.

### Windows

The **Build Windows EXE** workflow generates the standalone executable. The
`.exe` is for Windows; Ubuntu users should use the `.deb` or `start.sh`.

With Python and Tkinter installed, source setup is:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python ff_grabber.py
```

### Run source checks

Use a graphical desktop (or prefix with `xvfb-run -a` on a Linux CI runner):

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python ff_grabber.py --smoke-test
.venv/bin/python ff_grabber.py --browser-smoke-test
```

The browser smoke test opens the installed browser and serves its test pages
locally. It does not need a FitGirl page or download a game file.
