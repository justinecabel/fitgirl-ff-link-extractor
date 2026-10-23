"""Validate release tags and translate prereleases into Debian's version order."""
import argparse
from pathlib import Path
import re

NUMBER = r'(?:0|[1-9][0-9]*)'
TAG = re.compile(rf'v(?P<base>{NUMBER}\.{NUMBER}\.{NUMBER})(?:-(?P<stage>alpha|beta|rc)\.(?P<number>{NUMBER}))?')


def debian_version(version):
    return re.sub(r'-(alpha|beta|rc)(?=\.|$)', r'~\1', version, count=1)


def release_info(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError('Use vX.Y.Z or vX.Y.Z-alpha.N, -beta.N, or -rc.N.')
    version = tag[1:]
    stage = match['stage']
    title = f"v{match['base']}"
    if stage:
        title += f" {stage.upper() if stage == 'rc' else stage.title()} {match['number']}"
    return {'tag': tag, 'version': version, 'package_version': debian_version(version),
            'prerelease': str(bool(stage)).lower(), 'title': title}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Release tag, or package version with --debian')
    parser.add_argument('--debian', action='store_true')
    parser.add_argument('--check-version', type=Path)
    args = parser.parse_args()
    if args.debian:
        print(debian_version(args.version))
        return
    try:
        info = release_info(args.version)
        if args.check_version and args.check_version.read_text().strip() != info['version']:
            raise ValueError('The release tag must match VERSION.')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    for name, value in info.items():
        print(f'{name}={value}')


if __name__ == '__main__':
    main()
