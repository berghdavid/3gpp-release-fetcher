"""
3GPP specification fetcher.
"""

import argparse
from ftp import fetch_specs, unzip_dirs, convert_doc

def get_parser() -> argparse.ArgumentParser:
    """Parse command line arguments into Args object."""
    desc = "Fetch, unzip and convert 3GPP specifications to PDF files using Gotenberg"
    parser = argparse.ArgumentParser(prog="3GPP-fetcher", description=desc, add_help=False)
    parser.add_argument("-g", "--gotenberg", dest="gotenberg", type=str, required=True,
                        metavar='\b', help="Gotenberg endpoint.")
    parser.add_argument("-v", "--version", dest="version", type=int, required=True,
                        metavar='\b', help="3GPP release version.")
    return parser


def main():
    """5G Analyzer entrypoint"""
    args = get_parser().parse_args()
    fetch_specs(args.version)
    unzip_dirs(args.version)
    convert_doc(args.version, args.gotenberg)

if __name__ == "__main__":
    main()
