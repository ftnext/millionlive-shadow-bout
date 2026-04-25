# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "PyMuPDF",
# ]
# ///

import os
import sys

import fitz  # PyMuPDF


def pdf_to_images(pdf_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)

    print(f"Total pages: {len(doc)}")

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        # 解像度を高めにするための設定
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix=mat)

        output_filename = f"page_{page_num + 1:03d}.png"
        output_filepath = os.path.join(output_dir, output_filename)
        pix.save(output_filepath)

        print(f"Saved: {output_filepath}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    pdf_file = "million_Shadowbout52_cmyk.pdf"
    output_directory = "pdf_images"

    pdf_path = os.path.join(base_dir, pdf_file)
    out_path = os.path.join(base_dir, output_directory)

    if not os.path.exists(pdf_path):
        print(f"エラー: {pdf_path} が見つかりません。")
        sys.exit(1)

    print(f"Loading PDF: {pdf_path}")
    pdf_to_images(pdf_path, out_path)
