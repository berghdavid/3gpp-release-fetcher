"""
Functions for fetching 3GPP specs over FTP.
"""

import glob
from ftplib import FTP
import os
import zipfile
import requests


DOWNLOADS_DIR = "downloads"
EXTRACTED_DIR = "extracted"
PDF_DIR = "pdfs"


def fetch_specs(release_v: str, ftp_user="", ftp_password=""):
    """Fetch all 3GPP specifications for a certain release version."""
    ftp_host = f"https://www.3gpp.org/ftp/Specs/latest/Rel-{release_v}"
    download_path = f"{DOWNLOADS_DIR}/{release_v}"
    os.makedirs(download_path, exist_ok=True)

    ftp = FTP(host=ftp_host, user=ftp_user, passwd=ftp_password)
    for directory in ftp.nlst():
        ftp.cwd(directory)
        for filename in ftp.nlst():
            if filename.endswith(".zip"):
                local_path = os.path.join(download_path, f"{directory}_{filename}")
                with open(local_path, "wb") as f:
                    ftp.retrbinary(f"RETR {filename}", f.write)
        ftp.cwd("..")

    ftp.quit()


def unzip_dirs(release_v: str):
    """Unzip all .zip files in the downloads directory."""
    download_path = f"{DOWNLOADS_DIR}/{release_v}"
    extracted_path = f"{EXTRACTED_DIR}/{release_v}"
    os.makedirs(extracted_path, exist_ok=True)

    for zip_path in glob.glob(os.path.join(download_path, "*.zip")):
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extracted_path)


def convert_doc(release_v: str, gotenberg_endpoint: str):
    """Convert all .doc files to PDF in the extracted directory."""
    extracted_path = f"{EXTRACTED_DIR}/{release_v}"
    pdf_path = f"{PDF_DIR}/{release_v}"
    gotenberg_url = f"{gotenberg_endpoint}/forms/libreoffice/convert"
    os.makedirs(pdf_path, exist_ok=True)

    for doc_path in glob.glob(os.path.join(extracted_path, "*.doc")):
        with open(doc_path, "rb") as f:
            files = {"files": (os.path.basename(doc_path), f, "application/msword")}
            response = requests.post(gotenberg_url, files=files, timeout=10)
            if response.status_code == 200:
                file_path = os.path.join(pdf_path, os.path.basename(doc_path) + ".pdf")
                with open(file_path, "wb") as pdf_file:
                    pdf_file.write(response.content)
            else:
                print(f"Failed to convert {doc_path}, status {response.status_code}")
