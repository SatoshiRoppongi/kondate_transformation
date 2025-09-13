#!/usr/bin/env python3
"""
PDFの内容をデバッグするスクリプト
"""

import sys
import PyPDF2

def debug_pdf(pdf_path: str):
    """PDFの内容を詳細表示"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        print(f"ページ数: {len(reader.pages)}")
        
        for i, page in enumerate(reader.pages):
            print(f"\n=== ページ {i+1} ===")
            text = page.extract_text()
            print(f"文字数: {len(text)}")
            print("内容:")
            print(text)
            print("=" * 50)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python debug_pdf.py <pdf_path>")
        sys.exit(1)
    
    debug_pdf(sys.argv[1])