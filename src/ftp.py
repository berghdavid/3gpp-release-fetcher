"""
Functions for fetching 3GPP specs over FTP.
"""

from ftplib import FTP, error_perm
import os
import zipfile
from os.path import join, relpath
from requests import post
from tqdm import tqdm


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
    ftp_host = "www.3gpp.org"
    download_path = join(DOWNLOADS_DIR, release_v)
    os.makedirs(download_path, exist_ok=True)

    ftp = FTP(ftp_host)
    ftp.login(ftp_user, ftp_password)
    ftp_recursive_download(ftp, f"/Specs/latest/Rel-{release_v}", download_path)
    ftp.quit()


def unzip_dirs(release_v: str):
    """Unzip all .zip files in the downloads directory."""
    root_dir = join(DOWNLOADS_DIR, release_v)
    for dirpath, _, filenames in os.walk(root_dir):
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
            if filename.lower().endswith(".doc"):
                doc_path = join(dirpath, filename)

                # Mirror directory structure inside pdf_root
                rel_path = relpath(dirpath, root_dir)
                pdf_dir = join(PDF_DIR, rel_path)
                os.makedirs(pdf_dir, exist_ok=True)

                pdf_path = join(pdf_dir, filename + ".pdf")

                with open(doc_path, "rb") as f:
                    files = {"files": (filename, f, "application/msword")}
                    response = post(gotenberg_url, files=files, timeout=10)

                if response.status_code == 200:
                    with open(pdf_path, "wb") as pdf_file:
                        pdf_file.write(response.content)
                    print(f"✅ Converted: {doc_path} → {pdf_path}")
                else:
                    print(f"❌ Failed ({response.status_code}): {doc_path}")
