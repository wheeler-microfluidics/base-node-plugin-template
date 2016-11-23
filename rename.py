import sys

import rename_package_files as rp

def parse_args(args=None):
    """Parses arguments, returns (options, args)."""
    from argparse import ArgumentParser

    if args is None:
        args = sys.argv

    parser = ArgumentParser(description='Rename template project with'
                            'hyphen-separated <new name> (path names and in '
                            'files).')
    parser.add_argument('new_name', help='New project name (e.g., '
                        ' `my-new-project`)')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    rp.rename_package_files('.', 'microdrop-plugin-template', args.new_name)
