"""
3GPP specification fetcher.
"""

import argparse
from ftplib import FTP, error_perm
import os
import zipfile
from os.path import join, relpath
from requests import post
from tqdm import tqdm


FTP_3GPP_HOST = "www.3gpp.org"
DOWNLOADS_DIR = "downloads"
PDF_DIR = "pdfs"


def ftp_recursive_download(ftp: FTP, remote_dir: str, local_dir: str):
    """Recursively fetch a directory over FTP."""
    os.makedirs(local_dir, exist_ok=True)
    ftp.cwd(remote_dir)

    items = ftp.nlst()
    for i in tqdm(range(len(items))):
        item = items[i]
        try:
            ftp.cwd(item)
            ftp.cwd("..")
            ftp_recursive_download(ftp, join(remote_dir, item), join(local_dir, item))
        except error_perm:
            local_path = os.path.join(local_dir, item)
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {item}", f.write)
    ftp.cwd("..")


def fetch_specs(release_v: str, ftp_user="", ftp_password=""):
    """Fetch all 3GPP specifications for a certain release version."""
    download_path = join(DOWNLOADS_DIR, release_v)
    os.makedirs(download_path, exist_ok=True)

    ftp = FTP(host=FTP_3GPP_HOST)
    ftp.login(ftp_user, ftp_password)
    ftp_recursive_download(ftp, f"/Specs/latest/Rel-{release_v}", download_path)
    ftp.quit()


def unzip_dirs(release_v: str):
    """Unzip all .zip files in the downloads directory."""
    download_path = join(DOWNLOADS_DIR, release_v)
    for dirpath, _, filenames in os.walk(download_path):
        for filename in filenames:
            if filename.lower().endswith(".zip"):
                zip_path = join(dirpath, filename)
                extract_dir = join(dirpath, os.path.splitext(filename)[0])
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(zip_path, "r") as z:
                        z.extractall(extract_dir)
                    print(f"Extracted {zip_path} → {extract_dir}")
                except zipfile.BadZipFile:
                    print(f"Bad zip file: {zip_path}")


def convert_docs(release_v: str, gotenberg_endpoint: str):
    """Convert all .doc files to PDF in the extracted directory."""
    gotenberg_url = f"{gotenberg_endpoint}/forms/libreoffice/convert"
    root_dir = join(DOWNLOADS_DIR, release_v)

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            lower = filename.lower()
            if lower.endswith(".doc") or lower.endswith(".docx"):
                doc_path = join(dirpath, filename)

                # Mirror directory structure inside pdf_root
                pdf_dir = join(PDF_DIR, relpath(dirpath, root_dir))
                os.makedirs(pdf_dir, exist_ok=True)

                pdf_path = join(pdf_dir, filename + ".pdf")

                with open(doc_path, "rb") as f:
                    files = {"files": (filename, f, "application/msword")}
                    response = post(gotenberg_url, files=files, timeout=60)

                if response.status_code == 200:
                    with open(pdf_path, "wb") as pdf_file:
                        pdf_file.write(response.content)
                    print(f"✅ Converted: {doc_path} → {pdf_path}")
                else:
                    print(f"❌ Failed ({response.status_code}): {doc_path}")


def get_parser() -> argparse.ArgumentParser:
    """Parse command line arguments into Args object."""
    desc = "Fetch, unzip and convert 3GPP specifications to PDF files using Gotenberg"
    parser = argparse.ArgumentParser(prog="3GPP-fetcher", description=desc, add_help=False)
    parser.add_argument("-g", "--gotenberg", dest="gotenberg", type=str, required=True,
                        metavar='\b', help="Gotenberg endpoint.")
    parser.add_argument("-v", "--version", dest="version", type=str, required=True,
                        metavar='\b', help="3GPP release version.")
    return parser


def main():
    """5G Analyzer entrypoint"""
    args = get_parser().parse_args()
    fetch_specs(args.version)
    unzip_dirs(args.version)
    convert_docs(args.version, args.gotenberg)


if __name__ == "__main__":
    main()
