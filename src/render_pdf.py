#!/usr/bin/env python3
"""JSONデータからPDFを生成するモジュール"""

import json
import os
import re
import requests
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    HRFlowable, Flowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group

# 日本語フォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

BASE_URL = "https://www.shippai.org/fkd"


def create_styles():
    """PDF用スタイル定義"""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='JP_Title',
        fontName='HeiseiKakuGo-W5',
        fontSize=18,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=HexColor('#1a1a1a'),
    ))
    styles.add(ParagraphStyle(
        name='JP_H2',
        fontName='HeiseiKakuGo-W5',
        fontSize=13,
        leading=20,
        spaceBefore=16,
        spaceAfter=6,
        textColor=HexColor('#2c3e50'),
        borderWidth=0,
        borderPadding=4,
        backColor=HexColor('#ecf0f1'),
    ))
    styles.add(ParagraphStyle(
        name='JP_Body',
        fontName='HeiseiMin-W3',
        fontSize=10,
        leading=18,
        spaceAfter=6,
        textColor=HexColor('#333333'),
    ))
    styles.add(ParagraphStyle(
        name='JP_Label',
        fontName='HeiseiKakuGo-W5',
        fontSize=10,
        leading=16,
        spaceAfter=2,
        textColor=HexColor('#555555'),
    ))
    styles.add(ParagraphStyle(
        name='JP_Small',
        fontName='HeiseiMin-W3',
        fontSize=9,
        leading=14,
        spaceAfter=4,
        textColor=HexColor('#666666'),
    ))
    styles.add(ParagraphStyle(
        name='JP_Caption',
        fontName='HeiseiKakuGo-W5',
        fontSize=9,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=HexColor('#555555'),
    ))
    return styles


def download_image(url):
    """画像をダウンロードしてBytesIOオブジェクトを返す"""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return BytesIO(resp.content)
    except Exception as e:
        print(f"画像ダウンロード失敗: {url} - {e}")
        return None


def add_image(elements, img_url, caption, styles, max_width=160*mm, max_height=120*mm):
    """画像をelementsに追加"""
    img_data = download_image(img_url)
    if img_data:
        try:
            img = Image(img_data)
            iw, ih = img.drawWidth, img.drawHeight
            ratio = min(max_width / iw, max_height / ih)
            img.drawWidth = iw * ratio
            img.drawHeight = ih * ratio
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Paragraph(caption, styles['JP_Caption']))
        except Exception as e:
            print(f"画像埋め込み失敗: {caption} - {e}")
            elements.append(Paragraph(f"[画像読み込みエラー: {caption}]", styles['JP_Small']))
    else:
        elements.append(Paragraph(f"[画像取得失敗: {caption}]", styles['JP_Small']))


def add_section(elements, title, content, styles):
    """セクション見出し＋本文を追加"""
    elements.append(Paragraph(title, styles['JP_H2']))
    if isinstance(content, list):
        for line in content:
            elements.append(Paragraph(line, styles['JP_Body']))
    else:
        for para in content.split('\n'):
            if para.strip():
                elements.append(Paragraph(para.strip(), styles['JP_Body']))


def add_labeled_field(elements, label, value, styles):
    """ラベル: 値 の形式で追加"""
    elements.append(Paragraph(
        f'<b>{label}：</b>{value}',
        styles['JP_Body']
    ))


def build_diagonal_diagram(scenario_data, max_width=None, max_height=None):
    """失敗マンダラの対角線図をreportlab Drawingとして描画する

    scenario_data: {"cause": [[...], ...], "action": [[...], ...], "result": [[...], ...]}
    max_width: 最大描画幅（指定時はステップ幅を自動調整）
    max_height: 最大描画高さ（指定時はステップ高さを自動調整）
    """
    # シナリオアイテムをフラットなリストに展開
    cause_groups = scenario_data.get("cause", [])
    action_groups = scenario_data.get("action", [])
    result_groups = scenario_data.get("result", [])

    all_items = []
    num = 1
    for group in cause_groups:
        for item in group:
            all_items.append((num, item, "cause"))
            num += 1
    cause_count = num - 1

    for group in action_groups:
        for item in group:
            all_items.append((num, item, "action"))
            num += 1
    action_end = num - 1

    for group in result_groups:
        for item in group:
            all_items.append((num, item, "result"))
            num += 1

    total_items = len(all_items)
    if total_items == 0:
        return None

    # グループ区切り位置を計算（0-indexed）
    single_line_after = set()
    double_line_after = set()

    idx = 0
    for group in cause_groups:
        idx += len(group)
        single_line_after.add(idx - 1)
    if cause_count > 0:
        # 原因→行動の境界は二重線
        double_line_after.add(cause_count - 1)
        single_line_after.discard(cause_count - 1)

    for group in action_groups:
        idx += len(group)
        single_line_after.add(idx - 1)
    if action_end > cause_count:
        # 行動→結果の境界は二重線
        double_line_after.add(action_end - 1)
        single_line_after.discard(action_end - 1)

    for group in result_groups:
        idx += len(group)
        single_line_after.add(idx - 1)
    # 最後のアイテムには区切り線不要
    single_line_after.discard(total_items - 1)

    # 描画パラメータ
    bar_w = 42 * mm
    bar_h = 5.5 * mm
    step_x = 3.8 * mm
    step_y = 7.2 * mm

    sep_extra = 3 * mm
    dsep_extra = 5 * mm
    margin_left = 2 * mm
    margin_top = 8 * mm
    font_size = 7.5

    # Y位置を事前計算
    y_positions = []
    cur_y = margin_top
    for i in range(total_items):
        y_positions.append(cur_y)
        cur_y += step_y
        if i in double_line_after:
            cur_y += dsep_extra
        elif i in single_line_after:
            cur_y += sep_extra

    total_h = cur_y + 5 * mm
    total_w = margin_left + total_items * step_x + bar_w + 15 * mm

    d = Drawing(total_w, total_h)

    # 色設定
    colors = {
        "cause": HexColor('#dce6f1'),
        "action": HexColor('#e2efda'),
        "result": HexColor('#fce4d6'),
    }

    for i, (num, text, category) in enumerate(all_items):
        x = margin_left + i * step_x
        y = total_h - y_positions[i] - bar_h

        fill_color = colors[category]
        rect = Rect(x, y, bar_w, bar_h,
                     fillColor=fill_color,
                     strokeColor=HexColor('#666666'),
                     strokeWidth=0.5)
        d.add(rect)

        label = f"{num:02d}. {text}"
        s = String(x + 2 * mm, y + 1.5 * mm, label,
                   fontName='HeiseiMin-W3',
                   fontSize=font_size,
                   fillColor=HexColor('#1a1a1a'))
        d.add(s)

    # カテゴリラベル（右側に括弧線とラベル）
    category_ranges = {}
    if cause_count > 0:
        category_ranges["原因"] = (0, cause_count - 1)
    if action_end > cause_count:
        category_ranges["行動"] = (cause_count, action_end - 1)
    if total_items > action_end:
        category_ranges["結果"] = (action_end, total_items - 1)

    for label, (first_idx, last_idx) in category_ranges.items():
        mid_idx = (first_idx + last_idx) // 2
        y_top = total_h - y_positions[first_idx]
        y_bot = total_h - y_positions[last_idx] - bar_h
        brace_x = margin_left + last_idx * step_x + bar_w + 2 * mm

        d.add(Line(brace_x, y_top, brace_x, y_bot,
                    strokeColor=HexColor('#333333'), strokeWidth=0.8))
        d.add(Line(brace_x, y_top, brace_x - 2 * mm, y_top,
                    strokeColor=HexColor('#333333'), strokeWidth=0.8))
        d.add(Line(brace_x, y_bot, brace_x - 2 * mm, y_bot,
                    strokeColor=HexColor('#333333'), strokeWidth=0.8))
        d.add(String(brace_x + 2 * mm,
                      (y_top + y_bot) / 2 - 3,
                      label,
                      fontName='HeiseiKakuGo-W5',
                      fontSize=10,
                      fillColor=HexColor('#2c3e50')))

    # 区切り線
    for i in range(total_items - 1):
        if i in double_line_after:
            x_start = margin_left + (i + 1) * step_x - 1 * mm
            x_end = x_start + bar_w + 2 * mm
            y_line = total_h - (y_positions[i] + step_y + dsep_extra / 2) - bar_h / 2
            d.add(Line(x_start, y_line - 1, x_end, y_line - 1,
                        strokeColor=HexColor('#2c3e50'), strokeWidth=1.2))
            d.add(Line(x_start, y_line + 1, x_end, y_line + 1,
                        strokeColor=HexColor('#2c3e50'), strokeWidth=1.2))
        elif i in single_line_after:
            x_start = margin_left + (i + 1) * step_x
            x_end = x_start + bar_w
            y_line = total_h - (y_positions[i] + step_y + sep_extra / 2) - bar_h / 2
            d.add(Line(x_start, y_line, x_end, y_line,
                        strokeColor=HexColor('#999999'), strokeWidth=0.5))

    # 軸ラベル
    d.add(String(total_w / 2 - 15 * mm, total_h - 4 * mm,
                  "（時間の進行）→",
                  fontName='HeiseiKakuGo-W5', fontSize=7,
                  fillColor=HexColor('#666666')))

    # ページに収まらない場合、均等にスケーリング
    if max_width or max_height:
        scale_x = max_width / d.width if max_width and d.width > max_width else 1
        scale_y = max_height / d.height if max_height and d.height > max_height else 1
        scale = min(scale_x, scale_y)
        if scale < 1:
            g = Group()
            g.transform = (scale, 0, 0, scale, 0, 0)
            for item in list(d.contents):
                g.add(item)
            scaled = Drawing(d.width * scale, d.height * scale)
            scaled.add(g)
            return scaled

    return d


def render_pdf(data, output_dir="data"):
    """JSONデータからPDFを生成する

    data: extract.pyで生成されたdict
    output_dir: 出力ディレクトリ
    """
    styles = create_styles()
    elements = []

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{data['case_id']}_{data['case_name']}.pdf"
    output_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    # タイトル
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("失敗事例", styles['JP_Label']))
    elements.append(Paragraph(data["case_name"], styles['JP_Title']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#2c3e50')))
    elements.append(Spacer(1, 5*mm))

    # 基本情報
    add_labeled_field(elements, "事例名称", data["case_name"], styles)
    add_labeled_field(elements, "事例発生日付", data.get("date", ""), styles)
    add_labeled_field(elements, "事例発生地", data.get("location", ""), styles)
    add_labeled_field(elements, "事例発生場所", data.get("facility", ""), styles)
    elements.append(Spacer(1, 3*mm))

    # 代表図
    rep_img = data.get("images", {}).get("representative", "")
    if rep_img:
        elements.append(Paragraph("代表図", styles['JP_H2']))
        img_url = f"{BASE_URL}/df/{rep_img}"
        add_image(elements, img_url, "代表図", styles)

    # テキストセクション
    text_sections = [
        ("事例概要", "summary"),
        ("事象", "phenomenon"),
        ("経過", "process"),
        ("原因", "cause"),
        ("対処", "response"),
        ("対策", "countermeasure"),
    ]
    for title, key in text_sections:
        value = data.get(key, "")
        if value:
            add_section(elements, title, value, styles)

    # 知識化
    knowledge = data.get("knowledge", [])
    if knowledge:
        add_section(elements, "知識化",
                    "\n".join(f"・{k}" for k in knowledge), styles)

    # 背景
    background = data.get("background", "")
    if background:
        add_section(elements, "背景", background, styles)

    # シナリオ（対角線図）
    scenario = data.get("scenario", {})
    has_scenario = any(scenario.get(k) for k in ["cause", "action", "result"])
    if has_scenario:
        elements.append(Paragraph("シナリオ", styles['JP_H2']))
        elements.append(Paragraph(
            "以下は「失敗マンダラ」の概念に従った対角線図です。"
            "左上（原因）から右下（結果）へ、時系列に沿って脈絡として展開しています。",
            styles['JP_Small']))
        elements.append(Spacer(1, 3*mm))

        max_diagram_w = A4[0] - 40 * mm - 12  # 左右マージン20mm×2 + フレーム内部パディング
        max_diagram_h = A4[1] - 40 * mm - 12  # 上下マージン20mm×2 + フレーム内部パディング
        diagram = build_diagonal_diagram(scenario, max_width=max_diagram_w, max_height=max_diagram_h)
        if diagram:
            elements.append(diagram)
            elements.append(Spacer(1, 5*mm))

    # マルチメディアファイル
    multimedia = data.get("images", {}).get("multimedia", [])
    if multimedia:
        elements.append(Paragraph("マルチメディアファイル", styles['JP_H2']))
        for item in multimedia:
            file_id = item["id"]
            caption = item.get("caption", file_id)
            # 拡張子を推測（jpgが一般的）
            img_url = f"{BASE_URL}/mf/{file_id}.jpg"
            add_image(elements, img_url, caption, styles)
            elements.append(Spacer(1, 3*mm))

    # 情報源
    sources = data.get("sources", [])
    if sources:
        elements.append(Paragraph("情報源", styles['JP_H2']))
        for src in sources:
            # URLを検出してハイパーリンクにする
            url_match = re.search(r'(https?://\S+)', src)
            if url_match:
                url = url_match.group(1)
                text_before = src[:url_match.start()].strip()
                display = f'{text_before} <link href="{url}" color="blue"><u>{url}</u></link>'
                elements.append(Paragraph(display, styles['JP_Body']))
            else:
                elements.append(Paragraph(src, styles['JP_Body']))

    # 被害情報
    casualties = data.get("casualties", {})
    if casualties:
        elements.append(Paragraph("被害情報", styles['JP_H2']))
        add_labeled_field(elements, "死者数", str(casualties.get("deaths", 0)), styles)
        add_labeled_field(elements, "負傷者数", str(casualties.get("injuries", 0)), styles)
    financial = data.get("financial_damage", "")
    if financial:
        add_labeled_field(elements, "被害金額", financial, styles)

    # 社会への影響
    social = data.get("social_impact", "")
    if social:
        add_section(elements, "社会への影響", social, styles)

    # 備考
    notes = data.get("notes", "")
    if notes:
        add_section(elements, "備考", notes, styles)

    # 分野
    field = data.get("field", "")
    if field:
        add_labeled_field(elements, "分野", field, styles)
        elements.append(Spacer(1, 2*mm))

    # データ作成者
    authors = data.get("authors", [])
    if authors:
        add_section(elements, "データ作成者", "\n".join(authors), styles)

    # PDF生成
    doc.build(elements)
    print(f"PDF生成完了: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    json_path = sys.argv[1] if len(sys.argv) > 1 else "data/CZ0200703_浜岡原発タービンの損傷.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    render_pdf(data)
