"""
Script to pre-generate and cache high-quality WebP book covers (cover_s.webp and cover_l.webp)
for all books in data/books.json. Ensures zero latency and no lag when opening the WebApp books section.
"""
import sys
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
import time
import concurrent.futures
from services import book_service
BOOKS_FILE = BASE_DIR / "data" / "books.json"
BK_DIR = BASE_DIR / "data" / "bk"


def process_book(b: dict) -> int:
    bid = str(b.get("id") or b.get("i") or "")
    if not bid:
        return 0
    book_folder = BK_DIR / bid
    book_folder.mkdir(parents=True, exist_ok=True)

    cov_s = book_folder / "cover_s.webp"
    cov_l = book_folder / "cover_l.webp"

    written = 0
    if not cov_s.exists():
        bytes_s = book_service.generate_dynamic_book_cover(b, size="s", fmt="WEBP")
        cov_s.write_bytes(bytes_s)
        written += 1

    if not cov_l.exists():
        bytes_l = book_service.generate_dynamic_book_cover(b, size="l", fmt="WEBP")
        cov_l.write_bytes(bytes_l)
        written += 1

    return written


def main():
    if not BOOKS_FILE.exists():
        print("data/books.json not found!")
        return

    books = json.loads(BOOKS_FILE.read_text(encoding="utf-8"))
    total = len(books)
    print(f"Generating covers for {total} books...")

    t0 = time.time()
    count_generated = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        results = executor.map(process_book, books)
        for r in results:
            count_generated += r

    dt = time.time() - t0
    print(f"Done! Processed {total} books ({count_generated} files written) in {dt:.2f} seconds.")


if __name__ == "__main__":
    main()
