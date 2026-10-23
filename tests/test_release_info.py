from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from scripts.release_info import debian_version, release_info


class ReleaseTests(unittest.TestCase):
    def test_alpha_is_a_prerelease_with_a_distinct_package_version(self):
        info = release_info('v0.4.0-alpha.1')
        self.assertEqual(info['version'], '0.4.0-alpha.1')
        self.assertEqual(info['package_version'], '0.4.0~alpha.1')
        self.assertEqual(info['prerelease'], 'true')
        self.assertEqual(info['title'], 'v0.4.0 Alpha 1')

    def test_stable_releases_are_not_marked_as_prereleases(self):
        info = release_info('v0.4.0')
        self.assertEqual(info['prerelease'], 'false')
        self.assertEqual(info['package_version'], '0.4.0')

    def test_invalid_release_tags_cannot_enter_the_publish_workflow(self):
        for value in ('0.4.0', 'v0.4', 'v0.4.0-alpha', 'v0.4.0-alpha.01', 'v0.4.0-preview.1', 'v0.4.0\nlatest=true'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release_info(value)

    def test_normal_package_revisions_and_ci_suffixes_are_kept(self):
        self.assertEqual(debian_version('0.4.0-1'), '0.4.0-1')
        self.assertEqual(debian_version('0.4.0-alpha.1+git12'), '0.4.0~alpha.1+git12')

    @unittest.skipUnless(shutil.which('dpkg'), 'Debian version comparison requires dpkg')
    def test_alpha_beta_rc_and_stable_upgrade_in_order(self):
        versions = ['0.4.0-alpha.1', '0.4.0-alpha.2', '0.4.0-beta.1', '0.4.0-rc.1', '0.4.0']
        for before, after in zip(versions, versions[1:]):
            subprocess.run(['dpkg', '--compare-versions', debian_version(before), 'lt', debian_version(after)], check=True)

    def test_a_tag_must_match_the_checked_out_version(self):
        result = subprocess.run([sys.executable, 'scripts/release_info.py', 'v9.9.9', '--check-version', 'VERSION'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must match VERSION', result.stderr)
