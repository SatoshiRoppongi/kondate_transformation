#!/usr/bin/env python3
"""
汎用的な献立表から献立チェックリストを生成するスクリプト（高度版）
PDFの構造解析とテーブル抽出を使用
"""

import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import red, orange, green, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MenuItem:
    """献立項目"""
    name: str
    category: str

@dataclass
class NutritionInfo:
    """栄養素情報"""
    red: List[str]
    yellow: List[str]
    green: List[str]

@dataclass
class DailyMenu:
    """1日分の献立"""
    date: str
    day_of_week: str
    menu_items: List[MenuItem]
    nutrition: NutritionInfo

class AdvancedKondateConverter:
    """高度な献立表コンバーター"""
    
    def __init__(self):
        # フォント設定
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
        
        # 料理カテゴリ判定用のパターン
        self.main_food_patterns = [
            r'.*ご飯', r'.*パン', r'.*そば', r'.*うどん', r'.*ラーメン', 
            r'.*焼きそば', r'.*麺', r'.*ライス'
        ]
        
        self.soup_patterns = [
            r'.*汁', r'.*スープ', r'.*みそ汁', r'.*味噌汁'
        ]
        
        self.drink_patterns = [
            r'.*茶', r'.*牛乳', r'.*ジュース', r'.*水'
        ]
        
        # 栄養素キーワード
        self.nutrition_keywords = {
            'red': ['肉', '魚', '卵', '豆', '乳', 'チーズ', '味噌', '鶏', '豚', '牛', '鮭', 'えび', 'いわし', 'さば'],
            'yellow': ['米', '麦', 'パン', '麺', '芋', '油', '砂糖', '小麦', 'バター'],
            'green': ['野菜', 'キャベツ', '人参', '玉ねぎ', '大根', '小松菜', '昆布', 'わかめ', 'しいたけ', 'ねぎ']
        }
    
    def analyze_pdf_structure(self, pdf_path: str) -> Dict[str, Any]:
        """PDFの構造を詳細分析"""
        logger.info(f"PDFの構造解析を開始: {pdf_path}")
        
        structure = {
            'pages': [],
            'tables': [],
            'text_blocks': [],
            'date_positions': [],
            'menu_sections': []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                logger.info(f"ページ {page_num + 1} を解析中...")
                
                page_info = {
                    'page_number': page_num + 1,
                    'text': page.extract_text(),
                    'tables': page.extract_tables(),
                    'chars': page.chars,
                    'words': page.extract_words()
                }
                
                structure['pages'].append(page_info)
                
                # テーブルを抽出
                if page_info['tables']:
                    for table in page_info['tables']:
                        structure['tables'].append({
                            'page': page_num + 1,
                            'table': table
                        })
                
                # 日付の位置を特定
                date_positions = self._find_date_positions(page_info['words'])
                structure['date_positions'].extend(date_positions)
        
        logger.info(f"構造解析完了: {len(structure['pages'])}ページ, {len(structure['tables'])}テーブル")
        return structure
    
    def _find_date_positions(self, words: List[Dict]) -> List[Dict]:
        """日付の位置を特定"""
        date_positions = []
        date_pattern = r'^(\d{1,2})([月火水木金土日])$'
        
        for word in words:
            try:
                text = word['text'].strip()
                match = re.match(date_pattern, text)
                if match:
                    date_positions.append({
                        'date': int(match.group(1)),
                        'day': match.group(2),
                        'x0': word.get('x0', 0),
                        'y0': word.get('y0', 0),
                        'x1': word.get('x1', 0),
                        'y1': word.get('y1', 0)
                    })
            except (KeyError, AttributeError):
                continue
        
        return date_positions
    
    def extract_menu_data_from_structure(self, structure: Dict[str, Any]) -> List[DailyMenu]:
        """構造化データから献立情報を抽出"""
        logger.info("献立データの抽出を開始...")
        
        daily_menus = []
        
        # 月を抽出
        month = self._extract_month_from_structure(structure)
        logger.info(f"検出された月: {month}")
        
        # テーブルベースの解析を試行
        if structure['tables']:
            daily_menus = self._extract_from_tables(structure, month)
        
        # テーブルが見つからない場合は位置ベースの解析
        if not daily_menus:
            daily_menus = self._extract_from_positions(structure, month)
        
        # それでも見つからない場合はテキストベースの解析
        if not daily_menus:
            daily_menus = self._extract_from_text_analysis(structure, month)
        
        logger.info(f"抽出完了: {len(daily_menus)}日分の献立")
        return daily_menus
    
    def _extract_month_from_structure(self, structure: Dict[str, Any]) -> str:
        """構造から月を抽出"""
        for page in structure['pages']:
            text = page['text']
            month_pattern = r'(\d+)月.*献.*立.*表'
            match = re.search(month_pattern, text)
            if match:
                return f"{int(match.group(1)):02d}"
        return "00"
    
    def _extract_from_tables(self, structure: Dict[str, Any], month: str) -> List[DailyMenu]:
        """テーブル構造から献立を抽出"""
        logger.info("テーブル構造からの抽出を試行...")
        
        daily_menus = []
        
        for table_info in structure['tables']:
            table = table_info['table']
            if not table or len(table) < 2:
                continue
            
            # テーブルのヘッダーを分析
            headers = [cell.strip() if cell else '' for cell in table[0]]
            logger.info(f"テーブルヘッダー: {headers}")
            
            # 献立表のメインテーブルを特定（日、曜、献立名を含む）
            if '日' in headers and '曜' in headers and '献立名' in headers:
                date_col = headers.index('日')
                day_col = headers.index('曜') 
                menu_col = headers.index('献立名')
                
                logger.info(f"献立テーブル発見: 日付列={date_col}, 曜日列={day_col}, メニュー列={menu_col}")
                
                # 各行から献立データを抽出
                for i, row in enumerate(table[1:], 1):
                    if len(row) <= max(date_col, day_col, menu_col):
                        continue
                        
                    date_cell = row[date_col].strip() if row[date_col] else ''
                    day_cell = row[day_col].strip() if row[day_col] else ''
                    menu_cell = row[menu_col].strip() if row[menu_col] else ''
                    
                    logger.info(f"行{i}: 日付={date_cell}, 曜日={day_cell}, メニュー={menu_cell[:50]}...")
                    
                    # 日付を解析
                    if date_cell and day_cell and menu_cell:
                        try:
                            date = int(date_cell)
                            day_of_week = day_cell
                            
                            # メニューを解析
                            menu_items = self._parse_menu_text_advanced(menu_cell)
                            
                            # 栄養素情報を抽出（テーブルの列から）
                            nutrition = self._extract_nutrition_from_table_row(row, headers)
                            
                            if menu_items:
                                daily_menu = DailyMenu(
                                    date=f"{month}/{date:02d}({day_of_week})",
                                    day_of_week=day_of_week,
                                    menu_items=menu_items,
                                    nutrition=nutrition
                                )
                                daily_menus.append(daily_menu)
                                logger.info(f"献立追加: {date}/{month}({day_of_week}) - {len(menu_items)}項目")
                        except ValueError:
                            logger.warning(f"日付の解析に失敗: {date_cell}")
                            continue
        
        return daily_menus
    
    def _find_date_column(self, headers: List[str]) -> Optional[int]:
        """日付列を特定"""
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in ['日', '曜', 'date']):
                return i
        return None
    
    def _find_menu_column(self, headers: List[str]) -> Optional[int]:
        """献立列を特定"""
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in ['献立', 'メニュー', '昼食', 'menu']):
                return i
        return None
    
    def _extract_from_positions(self, structure: Dict[str, Any], month: str) -> List[DailyMenu]:
        """位置情報を使った高度な抽出"""
        logger.info("位置ベースの抽出を試行...")
        
        daily_menus = []
        
        # 日付の位置から対応するメニューテキストを推定
        for page in structure['pages']:
            words = page['words']
            date_positions = structure['date_positions']
            
            for date_pos in date_positions:
                if date_pos['date'] <= 31:  # 有効な日付のみ
                    # この日付の近くにあるテキストを収集
                    nearby_text = self._get_nearby_text(words, date_pos)
                    
                    if nearby_text:
                        menu_items = self._parse_menu_text_advanced(nearby_text)
                        nutrition = self._extract_nutrition_advanced(nearby_text)
                        
                        if menu_items:
                            daily_menu = DailyMenu(
                                date=f"{month}/{date_pos['date']:02d}({date_pos['day']})",
                                day_of_week=date_pos['day'],
                                menu_items=menu_items,
                                nutrition=nutrition
                            )
                            daily_menus.append(daily_menu)
        
        return daily_menus
    
    def _get_nearby_text(self, words: List[Dict], date_pos: Dict, radius: float = 100) -> str:
        """日付位置の近くのテキストを取得"""
        nearby_words = []
        
        for word in words:
            try:
                # 日付位置から一定距離内の単語を収集
                word_x = word.get('x0', 0)
                word_y = word.get('y0', 0)
                if (abs(word_x - date_pos['x0']) < radius and 
                    abs(word_y - date_pos['y0']) < radius):
                    nearby_words.append(word['text'])
            except (KeyError, TypeError):
                continue
        
        return ' '.join(nearby_words)
    
    def _extract_from_text_analysis(self, structure: Dict[str, Any], month: str) -> List[DailyMenu]:
        """高度なテキスト解析による抽出"""
        logger.info("高度なテキスト解析による抽出を試行...")
        
        daily_menus = []
        
        # 全ページのテキストを結合
        full_text = '\n'.join([page['text'] for page in structure['pages']])
        
        # 日付パターンを検索
        date_pattern = r'(\d{1,2})\s*([月火水木金土日])'
        dates = []
        
        for match in re.finditer(date_pattern, full_text):
            date = int(match.group(1))
            day = match.group(2)
            if 1 <= date <= 31:  # 有効な日付
                dates.append((date, day, match.start(), match.end()))
        
        logger.info(f"検出された日付: {len(dates)}個")
        
        # 各日付に対してメニューテキストを抽出
        for i, (date, day, _, end) in enumerate(dates):
            # 次の日付までのテキストを取得
            next_start = dates[i + 1][2] if i + 1 < len(dates) else len(full_text)
            menu_text = full_text[end:next_start]
            
            # メニューを解析
            menu_items = self._parse_menu_text_advanced(menu_text)
            nutrition = self._extract_nutrition_advanced(menu_text)
            
            if menu_items:
                daily_menu = DailyMenu(
                    date=f"{month}/{date:02d}({day})",
                    day_of_week=day,
                    menu_items=menu_items,
                    nutrition=nutrition
                )
                daily_menus.append(daily_menu)
        
        return daily_menus
    
    def _parse_menu_text_advanced(self, text: str) -> List[MenuItem]:
        """高度なメニューテキスト解析"""
        menu_items = []
        
        # テキストをクリーンアップし、改行や空白で区切って個別の料理を抽出
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 改行区切りでメニューを分割
        menu_lines = text.split('\n')
        found_dishes = set()
        
        for line in menu_lines:
            line = line.strip()
            if not line:
                continue
                
            # 各行から個別の料理を抽出
            dishes_in_line = self._extract_individual_dishes(line)
            
            for dish in dishes_in_line:
                clean_dish = dish.strip()
                if len(clean_dish) > 1 and clean_dish not in found_dishes:
                    category = self._categorize_dish_advanced(clean_dish)
                    menu_items.append(MenuItem(clean_dish, category))
                    found_dishes.add(clean_dish)
        
        return menu_items
    
    def _extract_individual_dishes(self, line: str) -> List[str]:
        """一行から個別の料理を抽出"""
        dishes = []
        
        # よくある料理名のパターンを詳細に定義
        dish_patterns = [
            # 複合的な料理名
            r'えびと野菜の玉子焼き', r'ひじきとねぎの玉子焼き', r'野菜と炒り玉子の和え物',
            r'豚肉と野菜の炒め物', r'鶏肉と根菜の煮物', r'ひじきとさつま揚げの煮物',
            r'きゅうりともやしのゆかり和え', r'ポテトの和風バター和え',
            
            # 単一料理名
            r'ふりかけご飯', r'きのこご飯', r'麦ご飯', r'夕焼けご飯',
            r'あんかけ焼きそば', r'ロールパン',
            
            # 汁物・スープ
            r'味噌汁', r'コーンスープ', r'わかめスープ', r'すまし汁', 
            r'コンソメスープ', r'マカロニスープ', r'中華スープ',
            
            # おかず
            r'ツナカレー', r'ぎせい豆腐', r'鮭の竜田揚げ', r'鶏肉のみりん焼き',
            r'いわしの煮つけ', r'チキンナゲット', r'マーボー春雨', r'さばの塩焼き',
            r'ミートローフハヤシソース', r'鶏肉のカレー風味炒め', r'ちくわの青のりフライ',
            
            # 和え物・サラダ
            r'納豆和え', r'なめたけ和え', r'キャベツの梅和え', r'小松菜のお浸し',
            r'野菜の塩炒め', r'茄子の味噌炒め', r'人参ドレッシング和え',
            r'中華ドレッシングサラダ', r'白菜のマリネサラダ', r'トマトドレッシングサラダ',
            r'わかめサラダ', r'ブロッコリーサラダ',
            
            # 飲み物・その他
            r'麦茶', r'牛乳', r'シュークリーム', r'パイナップル', 
            r'グレープフルーツ', r'梨', r'チーズ'
        ]
        
        # 基本食材（単語）
        basic_items = ['ご飯', '味噌汁', '麦茶', '牛乳', 'チーズ']
        
        # パターンマッチング
        for pattern in dish_patterns:
            if re.search(pattern, line):
                dishes.append(pattern)
        
        # 基本食材の検索
        for item in basic_items:
            if item in line and item not in dishes:
                dishes.append(item)
        
        return dishes
    
    def _categorize_dish_advanced(self, dish_name: str) -> str:
        """高度な料理カテゴリ分類"""
        
        # 主食パターン
        for pattern in self.main_food_patterns:
            if re.search(pattern, dish_name):
                return "主食"
        
        # 汁物パターン
        for pattern in self.soup_patterns:
            if re.search(pattern, dish_name):
                return "汁物"
        
        # 飲み物パターン
        for pattern in self.drink_patterns:
            if re.search(pattern, dish_name):
                return "飲み物"
        
        return "おかず"
    
    def _extract_nutrition_advanced(self, text: str) -> NutritionInfo:
        """高度な栄養素情報抽出"""
        red_items = []
        yellow_items = []
        green_items = []
        
        # 各カテゴリのキーワードを検索
        for keyword in self.nutrition_keywords['red']:
            if keyword in text and keyword not in red_items:
                red_items.append(keyword)
        
        for keyword in self.nutrition_keywords['yellow']:
            if keyword in text and keyword not in yellow_items:
                yellow_items.append(keyword)
        
        for keyword in self.nutrition_keywords['green']:
            if keyword in text and keyword not in green_items:
                green_items.append(keyword)
        
        # デフォルト値
        if not red_items:
            red_items = ['タンパク質食品']
        if not yellow_items:
            yellow_items = ['炭水化物']
        if not green_items:
            green_items = ['野菜類']
        
        return NutritionInfo(red=red_items[:4], yellow=yellow_items[:2], green=green_items[:6])
    
    def _extract_nutrition_from_table_row(self, row: List[str], headers: List[str]) -> NutritionInfo:
        """テーブルの行から栄養素情報を抽出"""
        red_items = []
        yellow_items = []
        green_items = []
        
        # あか、きいろ、みどりの列を特定
        red_col = None
        yellow_col = None
        green_col = None
        
        for i, header in enumerate(headers):
            if 'あか' in header:
                red_col = i
            elif 'きいろ' in header:
                yellow_col = i
            elif 'みどり' in header:
                green_col = i
        
        # 各列から栄養素を抽出
        if red_col is not None and red_col < len(row) and row[red_col]:
            red_text = row[red_col].strip()
            red_items = self._parse_nutrition_text(red_text)
        
        if yellow_col is not None and yellow_col < len(row) and row[yellow_col]:
            yellow_text = row[yellow_col].strip()
            yellow_items = self._parse_nutrition_text(yellow_text)
        
        if green_col is not None and green_col < len(row) and row[green_col]:
            green_text = row[green_col].strip()
            green_items = self._parse_nutrition_text(green_text)
        
        # デバッグ情報を出力
        logger.info(f"栄養素抽出結果: あか={red_items}, きいろ={yellow_items}, みどり={green_items}")
        
        # 空の場合のみデフォルト値を設定
        if not red_items and not yellow_items and not green_items:
            red_items = ['肉・魚・卵']
            yellow_items = ['ご飯・パン']
            green_items = ['野菜・果物']
        
        return NutritionInfo(red=red_items, yellow=yellow_items, green=green_items)
    
    def _parse_nutrition_text(self, text: str) -> List[str]:
        """栄養素テキストをパース"""
        if not text:
            return []
        
        # より詳細な分割パターンを使用
        # カンマ、改行、スペース、全角スペースで分割
        items = re.split(r'[,、\s\n　]+', text.strip())
        # 空文字列を除去し、有効な食材名のみを抽出
        valid_items = []
        for item in items:
            item = item.strip()
            if item and len(item) >= 1:  # 1文字以上で有効とする
                valid_items.append(item)
        
        logger.info(f"栄養素パース結果: '{text}' -> {valid_items}")
        return valid_items
    
    def create_checklist_pdf(self, daily_menus: List[DailyMenu], output_path: str):
        """チェックリストPDFを生成"""
        logger.info(f"チェックリストPDF生成開始: {output_path}")
        
        c = canvas.Canvas(output_path, pagesize=A4)
        page_width, page_height = A4
        
        # ページごとに2日分を処理
        for i in range(0, len(daily_menus), 2):
            if i > 0:
                c.showPage()
            
            # 1日目（上半分）
            if i < len(daily_menus):
                self._draw_daily_checklist(c, daily_menus[i], page_width, page_height, True)
            
            # 切り取り線
            self._draw_cut_line(c, page_width, page_height / 2)
            
            # 2日目（下半分）
            if i + 1 < len(daily_menus):
                self._draw_daily_checklist(c, daily_menus[i + 1], page_width, page_height, False)
        
        c.save()
        logger.info("チェックリストPDF生成完了")
    
    def _draw_daily_checklist(self, c: canvas.Canvas, daily_menu: DailyMenu, 
                             page_width: float, page_height: float, is_top: bool):
        """1日分のチェックリストを描画"""
        # 上半分の場合はより上に、下半分の場合はより下に配置（余白を削減）
        if is_top:
            y_start = page_height - 30  # 上端から30ポイント下（20ポイント削減）
        else:
            y_start = page_height / 2 - 30  # 中央から30ポイント下（20ポイント削減）
        
        y_pos = y_start
        
        # タイトル（日付）- より大きなフォント
        c.setFont('HeiseiKakuGo-W5', 22)  # 20→22に増加
        title = f"{daily_menu.date} ☆献立表チェックリスト☆"
        text_width = c.stringWidth(title, 'HeiseiKakuGo-W5', 22)
        c.drawString((page_width - text_width) / 2, y_pos, title)
        
        y_pos -= 35  # 28→35に増加（見出しとチェックリストの間を広げる）
        
        # メニュー項目を主食優先で並び替え
        sorted_items = self._sort_menu_items_by_priority(daily_menu.menu_items)
        
        # メニュー項目 - プロフェッショナルなデザイン（フォントサイズ増加）
        c.setFont('HeiseiKakuGo-W5', 18)  # 16→18に増加
        
        for i, item in enumerate(sorted_items):
            # スタイリッシュなチェックボックスデザイン
            checkbox = "□"  # より見やすいチェックボックス
            
            # カテゴリに応じた絵文字を追加
            emoji = self._get_category_emoji(item.category)
            
            menu_text = f"{checkbox} {emoji} {item.name}"
            c.drawString(50, y_pos, menu_text)
            
            # メニュー項目の右側に自由記入欄（縦位置を揃える）
            menu_text_width = c.stringWidth(menu_text, 'HeiseiKakuGo-W5', 18)  # フォントサイズ更新
            
            # 括弧の位置を固定位置に設定（縦に揃えるため、間隔を半分に）
            bracket_left_x = 380  # 固定位置を右に移動（320→380）
            bracket_right_x = page_width - 35  # 右括弧の固定位置は維持
            
            # 丸括弧を描画（固定位置で縦に揃える）
            c.drawString(bracket_left_x, y_pos, "(")
            c.drawString(bracket_right_x, y_pos, ")")
            
            # 項目間に薄いライン（区切り）を追加
            if i < len(sorted_items) - 1:
                c.setStrokeColor(black)
                c.setLineWidth(0.3)
                c.line(50, y_pos - 3, page_width - 35, y_pos - 3)  # ライン位置調整
            
            y_pos -= 27  # 25→27に増加（行間を少し広める）
        
        y_pos -= 25  # 10→25に増加（チェックリストと栄養バランスの間を広げる）
        
        # 栄養バランス表示 - プロフェッショナルなデザイン
        self._draw_nutrition_section(c, daily_menu.nutrition, y_pos, page_width)
    
    def _draw_nutrition_section(self, c: canvas.Canvas, nutrition: NutritionInfo, 
                              start_y: float, page_width: float):
        """栄養素セクションをデザイン性高く描画"""
        y_pos = start_y
        
        # セクションタイトル（フォントサイズ増加）
        c.setFillColor(black)
        c.setFont('HeiseiKakuGo-W5', 17)  # 15→17に増加
        title = "🌈 今日の栄養バランス"
        title_width = c.stringWidth(title, 'HeiseiKakuGo-W5', 17)
        c.drawString((page_width - title_width) / 2, y_pos, title)
        
        y_pos -= 22  # 20→22に増加
        
        # 3つの栄養カテゴリを横並びで配置
        col_width = page_width / 3
        
        # 赤グループ - パワフルなイメージ（フォントサイズ増加）
        c.setFillColor(red)
        c.setFont('HeiseiKakuGo-W5', 14)  # 12→14に増加
        red_title = "🔴 つよいからだ"
        c.drawString(35, y_pos, red_title)
        
        # 黄グループ - エネルギッシュなイメージ  
        c.setFillColor(orange)
        yellow_title = "🟡 げんきのもと"
        c.drawString(35 + col_width, y_pos, yellow_title)
        
        # 緑グループ - 健康的なイメージ
        c.setFillColor(green)
        green_title = "🟢 けんこうサポート"
        c.drawString(35 + col_width * 2, y_pos, green_title)
        
        y_pos -= 17  # 15→17に増加
        
        # 各カテゴリの詳細説明（フォントサイズ増加）
        c.setFont('HeiseiKakuGo-W5', 10)  # 9→10に増加
        
        c.setFillColor(red)
        red_desc = "体をつくる 血や肉になる"
        c.drawString(35, y_pos, red_desc)
        
        c.setFillColor(orange) 
        yellow_desc = "力や体温のもとになる"
        c.drawString(35 + col_width, y_pos, yellow_desc)
        
        c.setFillColor(green)
        green_desc = "体の調子を整える"
        c.drawString(35 + col_width * 2, y_pos, green_desc)
        
        y_pos -= 14  # 12→14に増加
        
        # 実際の食材を見やすく表示（フォントサイズ増加）
        c.setFont('HeiseiKakuGo-W5', 12)  # 11→12に増加
        
        # 赤の食材 - より多く表示（行間を広げる）
        c.setFillColor(red)
        red_items = nutrition.red[:6]  # 6個まで増加
        for i, item in enumerate(red_items):
            item_y = y_pos - (i * 13)  # 11→13に増加（行間を広げる）
            c.drawString(35, item_y, f"• {item}")
        
        # 黄の食材 - より多く表示（行間を広げる）
        c.setFillColor(orange)
        yellow_items = nutrition.yellow[:6]  # 6個まで増加
        for i, item in enumerate(yellow_items):
            item_y = y_pos - (i * 13)  # 11→13に増加（行間を広げる）
            c.drawString(35 + col_width, item_y, f"• {item}")
        
        # 緑の食材 - より多く表示（行間を広げる）
        c.setFillColor(green)
        green_items = nutrition.green[:7]  # 7個まで増加
        for i, item in enumerate(green_items):
            item_y = y_pos - (i * 13)  # 11→13に増加（行間を広げる）
            c.drawString(35 + col_width * 2, item_y, f"• {item}")
        
        # 背景に薄い枠線を追加（オプション）
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        
        # 3つのカラムの境界線
        line_y_top = start_y + 5
        line_y_bottom = y_pos - 30
        
        c.line(col_width + 10, line_y_top, col_width + 10, line_y_bottom)
        c.line(col_width * 2 + 10, line_y_top, col_width * 2 + 10, line_y_bottom)
        
        # 色をリセット
        c.setFillColor(black)
    
    def _get_category_emoji(self, category: str) -> str:
        """カテゴリに応じた絵文字を返す"""
        emoji_map = {
            "主食": "🍚",      # ご飯
            "汁物": "🍜",      # 汁物・スープ
            "おかず": "🍳",    # おかず
            "飲み物": "🥛"     # 飲み物
        }
        return emoji_map.get(category, "🍽️")  # デフォルト
    
    def _sort_menu_items_by_priority(self, menu_items: List[MenuItem]) -> List[MenuItem]:
        """メニュー項目を主食優先で並び替え（元の順序を可能な限り維持）"""
        # 主食のキーワード
        main_dish_keywords = ['ご飯', 'パン', '麦ご飯', 'ふりかけご飯', 'きのこご飯', '夕焼けご飯', 'ロールパン']
        
        # 主食とその他に分ける
        main_dishes = []
        other_dishes = []
        
        for item in menu_items:
            is_main_dish = any(keyword in item.name for keyword in main_dish_keywords)
            if is_main_dish:
                main_dishes.append(item)
            else:
                other_dishes.append(item)
        
        # 主食を最初に、その後にその他の料理を元の順番で並べる
        return main_dishes + other_dishes
    
    def _draw_cut_line(self, c: canvas.Canvas, page_width: float, y_pos: float):
        """切り取り線を描画"""
        c.setDash([3, 3])
        c.line(30, y_pos, page_width - 30, y_pos)
        c.setDash([])
        
        c.setFont('HeiseiKakuGo-W5', 8)
        c.drawString(15, y_pos - 3, "✂")
    
    def convert(self, input_pdf_path: str, output_dir: str = ".") -> str:
        """メイン変換処理"""
        logger.info(f"高度な献立表変換を開始: {input_pdf_path}")
        
        # PDFの構造を解析
        structure = self.analyze_pdf_structure(input_pdf_path)
        
        # 献立データを抽出
        daily_menus = self.extract_menu_data_from_structure(structure)
        
        if not daily_menus:
            logger.error("献立データが見つかりませんでした")
            return ""
        
        # 月を抽出
        month = self._extract_month_from_structure(structure)
        
        # 出力ファイル名を生成
        output_filename = f"kondate_check_{month}.pdf"
        output_path = Path(output_dir) / output_filename
        
        # チェックリストPDFを生成
        self.create_checklist_pdf(daily_menus, str(output_path))
        
        logger.info(f"変換完了: {output_path}")
        return str(output_path)

def main():
    """メイン関数"""
    if len(sys.argv) != 2:
        print("使用方法: python advanced_kondate_converter.py <input_pdf_path>")
        sys.exit(1)
    
    input_pdf_path = sys.argv[1]
    
    if not Path(input_pdf_path).exists():
        print(f"ファイルが見つかりません: {input_pdf_path}")
        sys.exit(1)
    
    converter = AdvancedKondateConverter()
    output_path = converter.convert(input_pdf_path)
    
    if output_path:
        print(f"✓ 高度な変換成功: {output_path}")
    else:
        print("✗ 変換失敗")
        sys.exit(1)

if __name__ == "__main__":
    main()