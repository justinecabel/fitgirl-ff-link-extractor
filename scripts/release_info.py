"""Validate release tags and translate prereleases into Debian's version order."""
import argparse
from pathlib import Path
import re

NUMBER = r'(?:0|[1-9][0-9]*)'
TAG = re.compile(rf'v(?P<base>{NUMBER}\.{NUMBER}\.{NUMBER})(?:-(?P<stage>dev|alpha|beta|rc)\.(?P<number>{NUMBER}))?')


def debian_version(version):
    return re.sub(r'-(dev|alpha|beta|rc)(?=\.|$)', r'~\1', version, count=1)


def release_info(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError('Use vX.Y.Z or vX.Y.Z-dev.N, -alpha.N, -beta.N, or -rc.N.')
    version = tag[1:]
    stage = match['stage']
    title = f"v{match['base']}"
    if stage:
        label = {'dev': 'Development', 'rc': 'RC'}.get(stage, stage.title())
        title += f" {label} {match['number']}"
    return {'tag': tag, 'version': version, 'package_version': debian_version(version),
            'base_version': match['base'], 'stage': stage or 'stable',
            'deb_asset': f'fitgirl-ff-link-extractor_{version}_amd64.deb',
            'prerelease': str(bool(stage)).lower(), 'title': title}


def development_info(version, build_number):
    if type(build_number) is not int or build_number < 1:
        raise ValueError('The development build number must be a positive integer.')
    base = release_info('v' + version)['base_version']
    return release_info(f'v{base}-dev.{build_number}')


def check_development_base(info, reference_version):
    base = release_info('v' + reference_version)['base_version']
    if info['stage'] != 'dev' or info['base_version'] != base:
        raise ValueError('Development tags must use -dev.N and the base version from VERSION.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Release tag, or source/package version for a build mode')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--debian', action='store_true')
    mode.add_argument('--check-version', type=Path)
    mode.add_argument('--development-build', type=int)
    mode.add_argument('--check-development-base', type=Path)
    args = parser.parse_args()
    if args.debian:
        print(debian_version(args.version))
        return
    try:
        info = (development_info(args.version, args.development_build)
                if args.development_build is not None else release_info(args.version))
        if args.check_version and args.check_version.read_text().strip() != info['version']:
            raise ValueError('The release tag must match VERSION.')
        if args.check_development_base:
            check_development_base(info, args.check_development_base.read_text().strip())
    except (ValueError, OSError) as error:
        parser.error(str(error))
    for name, value in info.items():
        print(f'{name}={value}')


if __name__ == '__main__':
    main()
