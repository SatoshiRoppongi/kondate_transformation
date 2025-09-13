#!/usr/bin/env python3
"""
献立表の解析をデバッグするスクリプト
"""

import sys
import re
import PyPDF2

def debug_parsing(pdf_path: str):
    """パース処理をデバッグ"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    
    # テキストを行に分割してクリーンアップ
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    print("=== 全ての行 ===")
    for i, line in enumerate(lines[:30]):  # 最初の30行のみ表示
        print(f"{i:2d}: {line}")
    
    print("\n=== 日付パターンマッチング ===")
    date_pattern = r'(\d+)([月火水木金土日])'
    
    current_menu_block = []
    menu_blocks = []
    
    for line in lines:
        # 日付行を検出
        match = re.match(date_pattern, line)
        if match and len(line) <= 5:  # 短い行で日付のみ
            print(f"日付検出: {line} (length: {len(line)})")
            if current_menu_block:
                menu_blocks.append(current_menu_block)
            current_menu_block = [line]
        elif current_menu_block:
            current_menu_block.append(line)
    
    # 最後のブロックを追加
    if current_menu_block:
        menu_blocks.append(current_menu_block)
    
    print(f"\n=== メニューブロック数: {len(menu_blocks)} ===")
    for i, block in enumerate(menu_blocks[:5]):  # 最初の5ブロックのみ表示
        print(f"ブロック {i+1}:")
        for line in block:
            print(f"  {line}")
        print()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python debug_parsing.py <pdf_path>")
        sys.exit(1)
    
    debug_parsing(sys.argv[1])