from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from scripts.release_info import check_development_base, debian_version, development_info, release_info


class ReleaseTests(unittest.TestCase):
    def test_alpha_is_a_prerelease_with_a_distinct_package_version(self):
        info = release_info('v0.4.0-alpha.1')
        self.assertEqual(info['version'], '0.4.0-alpha.1')
        self.assertEqual(info['package_version'], '0.4.0~alpha.1')
        self.assertEqual(info['deb_asset'], 'fitgirl-ff-link-extractor_0.4.0-alpha.1_amd64.deb')
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


class DevelopmentTests(unittest.TestCase):
    def test_each_run_advances_the_development_component(self):
        first = development_info('0.4.0-alpha.1', 1)
        second = development_info('0.4.0-alpha.1', 2)
        self.assertEqual(first['tag'], 'v0.4.0-dev.1')
        self.assertEqual(second['tag'], 'v0.4.0-dev.2')
        self.assertEqual(first['package_version'], '0.4.0~dev.1')
        self.assertEqual(first['prerelease'], 'true')
        self.assertEqual(first['title'], 'v0.4.0 Development 1')
        self.assertEqual(first['deb_asset'], 'fitgirl-ff-link-extractor_0.4.0-dev.1_amd64.deb')

    def test_development_cli_validates_the_source_base(self):
        base = release_info('v' + Path('VERSION').read_text().strip())['base_version']
        result = subprocess.run([sys.executable, 'scripts/release_info.py', f'v{base}-dev.7',
            '--check-development-base', 'VERSION'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'version={base}-dev.7', result.stdout)
        self.assertIn('prerelease=true', result.stdout)

    def test_a_new_base_changes_the_version_without_resetting_the_counter(self):
        self.assertEqual(development_info('0.5.0-beta.2', 12)['version'], '0.5.0-dev.12')

    def test_invalid_counters_cannot_produce_tags(self):
        for value in (0, -1, 1.5, True, '2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                development_info('0.4.0-alpha.1', value)

    def test_automatic_builds_cannot_publish_a_different_base_or_release_channel(self):
        check_development_base(release_info('v0.4.0-dev.3'), '0.4.0-alpha.1')
        for tag in ('v0.5.0-dev.3', 'v0.4.0-alpha.3', 'v0.4.0'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                check_development_base(release_info(tag), '0.4.0-alpha.1')

    @unittest.skipUnless(shutil.which('dpkg'), 'Debian version comparison requires dpkg')
    def test_development_numbers_sort_numerically_and_before_stable(self):
        versions = ['0.4.0-dev.1', '0.4.0-dev.2', '0.4.0-dev.10', '0.4.0']
        for before, after in zip(versions, versions[1:]):
            subprocess.run(['dpkg', '--compare-versions', debian_version(before), 'lt', debian_version(after)], check=True)
