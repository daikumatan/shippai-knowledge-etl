#!/usr/bin/env python3
"""失敗知識データベースからデータを抽出してJSONを生成するモジュール"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.shippai.org/fkd/"

# 必須フィールド（HTMLラベル名 → JSONキー名）
REQUIRED_FIELDS = {
    "事例概要": "summary",
    "経過": "process",
    "原因": "cause",
    "対策": "countermeasure",
    "シナリオ": "scenario",
}


class MissingFieldsError(Exception):
    """必須フィールドが不足している場合の例外"""
    def __init__(self, case_id, case_name, url, missing_labels):
        self.case_id = case_id
        self.case_name = case_name
        self.url = url
        self.missing_labels = missing_labels
        fields_str = ", ".join(missing_labels)
        super().__init__(f"必須フィールド不足: {fields_str}")


def fetch_html(url):
    """URLからHTMLを取得してBeautifulSoupオブジェクトを返す"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def extract_case_id(url):
    """URLから事例IDを抽出する（例: CZ0200703）"""
    m = re.search(r"/cf/(\w+)\.html", url)
    if m:
        return m.group(1)
    raise ValueError(f"事例IDを抽出できません: {url}")


def parse_main_page(soup, case_url):
    """メインの事例ページからデータを抽出する"""
    data = {}
    case_id = extract_case_id(case_url)
    data["case_id"] = case_id
    data["url"] = case_url

    # メインテーブルの行を解析（ラベル→値のペア）
    rows = soup.select("table tr")
    field_map = {}
    multimedia_rows = []

    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        label_td = tds[0]
        value_td = tds[-1]
        label = label_td.get_text(strip=True)
        # bgcolorが#DFE9F2のtdがラベルセル
        bg = label_td.get("bgcolor", "")
        if bg.upper() != "#DFE9F2":
            continue

        if label == "マルチメディアファイル":
            # マルチメディアは複数行にまたがる（rowspan）
            link = value_td.find("a")
            if link:
                href = link.get("href", "")
                caption = link.get_text(strip=True)
                multimedia_rows.append((href, caption))
            continue

        field_map[label] = (label_td, value_td)

    # マルチメディアの残りの行（rowspanで最初のtdが省略されている行）
    # rowspanを持つtrの後続trはtdが1つだけになる
    # また、bgcolorが#DFE9F2でないtdだけの行もある
    for row in rows:
        tds = row.find_all("td")
        for td in tds:
            link = td.find("a")
            if link:
                href = link.get("href", "")
                if "/mf/" in href:
                    caption = link.get_text(strip=True)
                    entry = (href, caption)
                    if entry not in multimedia_rows:
                        multimedia_rows.append(entry)

    # 基本情報の抽出
    def get_text(label):
        if label in field_map:
            _, td = field_map[label]
            # <br>を\nに変換してテキスト取得
            for br in td.find_all("br"):
                br.replace_with("\n")
            return td.get_text(strip=True)
        return ""

    def get_html_text(label):
        """<br>を改行として保持したテキストを取得（段落間は空行）"""
        if label in field_map:
            _, td = field_map[label]
            for br in td.find_all("br"):
                br.replace_with("\n")
            text = td.get_text()
            lines = [line.strip() for line in text.split("\n")]
            # 空行でない行だけ取得し、段落間に空行を挿入
            paragraphs = []
            current = []
            for line in lines:
                if line:
                    current.append(line)
                else:
                    if current:
                        paragraphs.append("\n".join(current))
                        current = []
            if current:
                paragraphs.append("\n".join(current))
            return "\n\n".join(paragraphs)
        return ""

    data["case_name"] = get_text("事例名称")
    data["date"] = _parse_date(get_text("事例発生日付"))
    data["location"] = get_text("事例発生地")
    data["facility"] = get_text("事例発生場所")
    data["summary"] = get_text("事例概要")
    data["phenomenon"] = get_text("事象")
    data["process"] = get_html_text("経過")
    data["cause"] = get_html_text("原因")
    data["response"] = get_html_text("対処")
    data["countermeasure"] = get_html_text("対策")

    # 知識化（複数の書式に対応）
    if "知識化" in field_map:
        _, td = field_map["知識化"]
        for br in td.find_all("br"):
            br.replace_with("\n")
        knowledge_text = td.get_text().strip()
        items = []
        if "・" in knowledge_text:
            # 行頭「・」区切り
            for line in knowledge_text.split("\n"):
                line = line.strip()
                if line.startswith("・"):
                    items.append(line[1:].strip())
                elif line and items:
                    items[-1] += line
        elif re.search(r"^[0-9０-９]+[．.]\s*", knowledge_text, re.MULTILINE):
            # 番号付きリスト（1．2．...や1.2....）
            current = []
            for line in knowledge_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if re.match(r"^[0-9０-９]+[．.]\s*", line):
                    if current:
                        items.append("".join(current))
                    # 番号部分を除去
                    text = re.sub(r"^[0-9０-９]+[．.]\s*", "", line)
                    current = [text]
                elif current:
                    current.append(line)
            if current:
                items.append("".join(current))
        elif knowledge_text:
            # その他（テキスト全体を1項目として扱う）
            items = [knowledge_text]
        data["knowledge"] = items
    else:
        data["knowledge"] = []

    data["background"] = get_html_text("背景")

    # 代表図
    if "代表図" in field_map:
        _, td = field_map["代表図"]
        img = td.find("img")
        if img:
            src = img.get("src", "")
            # ../df/DZ0200703.jpg -> DZ0200703.jpg
            data["representative_image"] = os.path.basename(src)
        else:
            data["representative_image"] = ""
    else:
        data["representative_image"] = ""

    # シナリオ（リンク先のページから取得）
    scenario_link = None
    if "シナリオ" in field_map:
        _, td = field_map["シナリオ"]
        link = td.find("a")
        if link:
            scenario_link = urljoin(case_url, link.get("href", ""))
    # ページ上部のシナリオリンクも探す
    if not scenario_link:
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "/sf/" in href:
                scenario_link = urljoin(case_url, href)
                break

    if scenario_link:
        data["scenario"] = parse_scenario_page(scenario_link)
    else:
        data["scenario"] = {"cause": [], "action": [], "result": []}

    # マルチメディア
    data["images"] = {
        "representative": data.pop("representative_image"),
        "multimedia": []
    }
    for href, caption in multimedia_rows:
        file_id = os.path.splitext(os.path.basename(href))[0]
        data["images"]["multimedia"].append({
            "id": file_id,
            "caption": caption
        })

    # 情報源
    if "情報源" in field_map:
        _, td = field_map["情報源"]
        for br in td.find_all("br"):
            br.replace_with("\n")
        sources_text = td.get_text()
        data["sources"] = [s.strip() for s in sources_text.split("\n") if s.strip()]
    else:
        data["sources"] = []

    # 被害情報
    deaths_text = get_text("死者数")
    injuries_text = get_text("負傷者数")
    data["casualties"] = {
        "deaths": _parse_int(deaths_text),
        "injuries": _parse_int(injuries_text)
    }
    data["financial_damage"] = get_text("被害金額")
    data["social_impact"] = get_text("社会への影響")

    # 備考・分野・作成者
    data["notes"] = get_text("備考")
    data["field"] = get_text("分野")

    # データ作成者
    authors_text = get_html_text("データ作成者")
    if authors_text:
        # &nbsp;をスペースに変換（BeautifulSoupが処理済みの場合も）
        authors_text = authors_text.replace("\xa0", " ")
        data["authors"] = [a.strip() for a in authors_text.split("\n") if a.strip()]
    else:
        data["authors"] = []

    # 必須フィールド検証
    missing = []
    for html_label, json_key in REQUIRED_FIELDS.items():
        if html_label == "シナリオ":
            # シナリオはcause/action/resultのいずれかにデータがあればOK
            s = data.get("scenario", {})
            if not any(s.get(k) for k in ["cause", "action", "result"]):
                missing.append(html_label)
        elif html_label == "知識化":
            if not data.get("knowledge"):
                missing.append(html_label)
        else:
            if not data.get(json_key):
                missing.append(html_label)
    if missing:
        raise MissingFieldsError(
            data["case_id"], data["case_name"], case_url, missing
        )

    return data


def parse_scenario_page(url):
    """シナリオページからアイテムを抽出し、カテゴリ別にグループ化する"""
    soup = fetch_html(url)

    items = []
    separators = []  # (index_after, type) type: "single" or "double"

    # シナリオの左半分のtd（valign="top", width="60%"）を探す
    main_td = None
    for td in soup.find_all("td", {"valign": "top"}):
        width = td.get("width", "")
        if "60%" in width:
            main_td = td
            break

    if not main_td:
        # フォールバック: ページ全体から探す
        main_td = soup

    # 番号付きアイテムを抽出
    for b_tag in main_td.find_all("b"):
        text = b_tag.get_text(strip=True)
        m = re.match(r"(\d+)\.", text)
        if m:
            num = int(m.group(1))
            # 隣のtdからアイテム名を取得
            parent_tr = b_tag.find_parent("tr")
            if parent_tr:
                tds = parent_tr.find_all("td")
                if len(tds) >= 3:
                    item_text = tds[2].get_text(strip=True)
                    items.append((num, item_text))

    # 区切り線を検出
    for img in main_td.find_all("img"):
        src = img.get("src", "")
        if "sinario_line_1" in src:
            # 単線 - この画像の前にあるアイテムの番号を特定
            # space.gifのwidthから位置を推定
            parent_tr = img.find_parent("tr")
            if parent_tr:
                space_img = parent_tr.find("img", src=re.compile(r"space\.gif"))
                if space_img:
                    w = int(space_img.get("width", 0))
                    # width = 5 * (item_number) + 10 くらい (0-indexed)
                    # 最初の3項目の後: width=15, 次: 35, ...
                    idx = (w - 15) // 20  # 0-indexed group number
                    item_after = (idx + 1) * 3  # 最後のアイテム番号(1-based)
                    separators.append((item_after, "single"))
        elif "sinario_line_2" in src:
            parent_tr = img.find_parent("tr")
            if parent_tr:
                space_img = parent_tr.find("img", src=re.compile(r"space\.gif"))
                if space_img:
                    w = int(space_img.get("width", 0))
                    idx = (w - 15) // 20
                    item_after = (idx + 1) * 3
                    separators.append((item_after, "double"))

    # 二重線の位置からカテゴリ境界を特定
    double_boundaries = sorted([s[0] for s in separators if s[1] == "double"])

    # アイテムを番号順にソート
    items.sort(key=lambda x: x[0])
    item_texts = [text for _, text in items]

    # カテゴリ分け（二重線の位置で分割）
    # 二重線が2つある場合: [0..b1) = 原因, [b1..b2) = 行動, [b2..] = 結果
    if len(double_boundaries) >= 2:
        b1 = double_boundaries[0]
        b2 = double_boundaries[1]
        cause_items = item_texts[:b1]
        action_items = item_texts[b1:b2]
        result_items = item_texts[b2:]
    elif len(double_boundaries) == 1:
        b1 = double_boundaries[0]
        cause_items = item_texts[:b1]
        action_items = []
        result_items = item_texts[b1:]
    else:
        # 境界が見つからない場合、全体をフラットに扱う
        cause_items = item_texts
        action_items = []
        result_items = []

    # 3項目ずつグループ化
    def group_by_three(lst):
        return [lst[i:i+3] for i in range(0, len(lst), 3)]

    return {
        "cause": group_by_three(cause_items),
        "action": group_by_three(action_items),
        "result": group_by_three(result_items),
    }


def _parse_date(text):
    """日付テキストをYYYY-MM-DD形式に変換"""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return text


def _parse_int(text):
    """テキストから整数を抽出"""
    m = re.search(r"\d+", text)
    if m:
        return int(m.group())
    return 0


def extract_case_urls_from_list(list_url, limit=None):
    """一覧ページから事例URLのリストを取得する"""
    soup = fetch_html(list_url)
    urls = []
    for a in soup.select("ul.list_all a"):
        href = a.get("href", "")
        if "/cf/" in href:
            full_url = urljoin(list_url, href)
            urls.append(full_url)
            if limit and len(urls) >= limit:
                break
    return urls


def extract(case_url, output_dir="data"):
    """事例URLからデータを抽出してJSONファイルに保存する"""
    print(f"抽出中: {case_url}")
    soup = fetch_html(case_url)
    data = parse_main_page(soup, case_url)

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{data['case_id']}_{data['case_name']}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"JSON保存完了: {filepath}")
    return filepath, data


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.shippai.org/fkd/cf/CZ0200703.html"
    extract(url)
