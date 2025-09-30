"""
3GPP specification fetcher.
"""

import argparse
from ftplib import FTP, error_perm
import os
from typing import List
import zipfile
from queue import PriorityQueue
from threading import Thread, Lock
from os.path import join, relpath, getsize
from requests import post, Timeout
from tqdm import tqdm


FTP_3GPP_HOST = "www.3gpp.org"
DOWNLOADS_DIR = "downloads"
PDF_DIR = "pdfs"

cq = PriorityQueue()


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
    print(f"Fetching 3GPP v{release_v} specifications...")
    download_path = join(DOWNLOADS_DIR, release_v)
    os.makedirs(download_path, exist_ok=True)

    ftp = FTP(host=FTP_3GPP_HOST)
    ftp.login(ftp_user, ftp_password)
    ftp_recursive_download(ftp, f"/Specs/latest/Rel-{release_v}", download_path)
    ftp.quit()


def unzip_dirs(release_v: str):
    """Unzip all .zip files in the downloads directory."""
    print(f"Unzipping 3GPP v{release_v} specifications...")
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


def convert_docs(release_v: str, gotenberg_endpoint: str, timeout: float, threads: int):
    """Convert all unconverted .doc files to PDF in the extracted directory."""
    gotenberg_url = f"{gotenberg_endpoint}/forms/libreoffice/convert"
    root_dir = join(DOWNLOADS_DIR, release_v)
    print(f"Converting 3GPP v{release_v} specifications to PDF...")
    print(f"\tConversion url: {gotenberg_url}")
    print(f"\tTimeout:        {timeout:.2f}")

    lock = Lock()
    fails = []
    converted = []

    workers: List[Thread] = []
    for i in range(threads):
        t = Thread(target=converter_worker, args=(i, gotenberg_url, timeout, converted, lock))
        workers.append(t)

    pre_converted = []
    doc_files = []
    tot_files = 0
    for dirpath, _, filenames in os.walk(root_dir):
        tot_files += len(filenames)
        for filename in filenames:
            lower = filename.lower()
            if not (lower.endswith(".doc") or lower.endswith(".docx")):
                continue

            doc_path = join(dirpath, filename)
            doc_files.append(doc_path)

            # Mirror directory structure inside pdf_root
            pdf_dir = join(PDF_DIR, relpath(dirpath, root_dir))
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = join(pdf_dir, filename + ".pdf")
            if os.path.isfile(pdf_path):
                pre_converted.append(doc_path)
                continue

            # (priority, (filename, doc_path, pdf_path))
            cq.put((getsize(doc_path), (filename, doc_path, pdf_path)))

    convertibles = len(doc_files)-len(pre_converted)
    print(f"Found {tot_files} files in total")
    print(f"Found {len(doc_files)} convertible files")
    print(f"PDFs already existed for {len(pre_converted)} files")
    print(f"Starting conversion of {convertibles} files...")

    for t in workers:
        t.start()

    cq.join()
    for t in workers:
        t.join()

    failed = [x for x in doc_files if x not in converted and x not in pre_converted]
    print(f"PDFs were created for {len(converted)}/{convertibles} files")
    print(f"Conversion failed for {len(failed)}/{convertibles} files")
    if len(fails) > 0:
        print(f"The following file conversions failed:\n{failed}")


def converter_worker(id: int, gotenberg_url: str, timeout: float, converted: List[str], lock: Lock):
    while not cq.empty():
        _, item = cq.get()
        filename, doc_path, pdf_path = item
        with open(doc_path, "rb") as f:
            files = {"files": (filename, f, "application/msword")}
            try:
                response = post(gotenberg_url, files=files, timeout=timeout)
            except Timeout as e:
                print(f"Error: Timeout - {e.strerror}")
                continue

        if response.status_code == 200:
            with open(pdf_path, "wb") as pdf_file:
                pdf_file.write(response.content)
            print(f"✅ Converted by {id}: {doc_path} → {pdf_path}")
            with lock:
                converted.append(doc_path)
        else:
            print(f"❌ Failed by {id} ({response.status_code} - {response.text}): {doc_path}")
        cq.task_done()


def get_parser() -> argparse.ArgumentParser:
    """Parse command line arguments into Args object."""
    desc = "Fetch, unzip and convert 3GPP specifications to PDF files using Gotenberg"
    parser = argparse.ArgumentParser(prog="3GPP-fetcher", description=desc, add_help=False)
    parser.add_argument("-g", "--gotenberg", dest="gotenberg", type=str, required=True,
                        metavar='\b', help="Gotenberg endpoint.")
    parser.add_argument("-v", "--version", dest="version", type=str, required=True,
                        metavar='\b', help="3GPP release version.")
    parser.add_argument("-f", "--skip-fetch", dest="skip_fetch", type=bool, default=False,
                        required=False, metavar='\b', help="Skip the data fetching stage.")
    parser.add_argument("-u", "--skip-unzip", dest="skip_unzip", type=bool, default=False,
                        required=False, metavar='\b', help="Skip the unzipping stage.")
    parser.add_argument("-c", "--skip-convert", dest="skip_convert", type=bool, default=False,
                        required=False, metavar='\b', help="Skip the PDF conversion stage.")
    parser.add_argument("-t", "--timeout", dest="timeout", type=float, default=60.0,
                        required=False, metavar='\b', help="PDF conversion timeout.")
    parser.add_argument("-p", "--threads", dest="threads", type=int, default=1,
                        required=False, metavar='\b', help="Threads to run in parallel.")
    return parser


def main():
    """5G Analyzer entrypoint"""
    args = get_parser().parse_args()
    if not args.skip_fetch:
        fetch_specs(args.version)
    else:
        print("Skipping fetching as `--skip-fetch` was provided...")
    if not args.skip_unzip:
        unzip_dirs(args.version)
    else:
        print("Skipping unzipping as `--skip-unzip` was provided...")
    if not args.skip_convert:
        convert_docs(args.version, args.gotenberg, args.timeout, args.threads)
    else:
        print("Skipping pdf-conversion as `--skip-convert` was provided...")


if __name__ == "__main__":
    main()
