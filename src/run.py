#!/usr/bin/env python3
"""失敗知識データベース ETL パイプライン CLI エントリポイント

使用例:
  # 単一事例のURL
  python src/run.py https://www.shippai.org/fkd/cf/CZ0200703.html

  # 一覧ページから上位N件を処理
  python src/run.py https://www.shippai.org/fkd/lis/cat001.html --limit 3

  # 複数URLを指定
  python src/run.py URL1 URL2 URL3
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract import extract, extract_case_urls_from_list, MissingFieldsError
from render_pdf import render_pdf


def process_case(case_url, output_dir):
    """1つの事例を処理する（抽出→PDF生成）"""
    json_path, data = extract(case_url, output_dir)
    pdf_path = render_pdf(data, output_dir)
    return json_path, pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="失敗知識データベースからデータを抽出し、PDF/JSONファイルを生成する"
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="事例URL（cf/）または一覧ページURL（lis/）"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="一覧ページから処理する件数の上限"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="出力ディレクトリ（デフォルト: プロジェクトルートの data/）"
    )
    args = parser.parse_args()

    # 出力ディレクトリの決定
    if args.output_dir:
        output_dir = args.output_dir
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, "data")

    # URLを展開（一覧ページの場合は個別URLに展開）
    case_urls = []
    for url in args.urls:
        if "/lis/" in url:
            print(f"一覧ページからURL取得中: {url}")
            urls = extract_case_urls_from_list(url, limit=args.limit)
            print(f"  {len(urls)}件の事例を検出")
            case_urls.extend(urls)
        elif "/cf/" in url:
            case_urls.append(url)
        else:
            print(f"警告: 不明なURL形式（スキップ）: {url}")

    if not case_urls:
        print("処理対象の事例がない。")
        sys.exit(1)

    print(f"\n合計 {len(case_urls)} 件の事例を処理\n")
    print("=" * 60)

    cases = []
    success_count = 0
    excluded_count = 0
    error_count = 0
    for i, url in enumerate(case_urls, 1):
        print(f"\n[{i}/{len(case_urls)}] {url}")
        print("-" * 60)
        try:
            json_path, pdf_path = process_case(url, output_dir)
            cases.append({
                "case_id": os.path.basename(json_path).split("_")[0],
                "case_name": os.path.basename(json_path).replace(".json", "").split("_", 1)[1],
                "url": url,
                "status": "success",
                "outputs": [os.path.basename(json_path), os.path.basename(pdf_path)],
            })
            success_count += 1
        except MissingFieldsError as e:
            print(f"除外: {e}")
            cases.append({
                "case_id": e.case_id,
                "case_name": e.case_name,
                "url": e.url,
                "status": "excluded",
                "missing_fields": e.missing_labels,
            })
            excluded_count += 1
        except Exception as e:
            print(f"エラー: {e}")
            cases.append({
                "url": url,
                "status": "error",
                "message": str(e),
            })
            error_count += 1

    # results.json出力
    os.makedirs(output_dir, exist_ok=True)
    results = {
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total": len(case_urls),
            "success": success_count,
            "excluded": excluded_count,
            "error": error_count,
        },
        "cases": cases,
    }
    # 連番ファイル名を決定（results_001.json, results_002.json, ...）
    existing = glob.glob(os.path.join(output_dir, "results_*.json"))
    max_num = 0
    for f in existing:
        m = re.search(r"results_(\d+)\.json$", f)
        if m:
            max_num = max(max_num, int(m.group(1)))
    next_num = max_num + 1
    results_filename = f"results_{next_num:03d}.json"
    results_path = os.path.join(output_dir, results_filename)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n処理結果出力: {results_path}")

    print("\n" + "=" * 60)
    print(f"完了: {success_count}/{len(case_urls)} 件成功")
    if excluded_count:
        print(f"除外: {excluded_count} 件（必須フィールド不足）")
    if error_count:
        print(f"エラー: {error_count} 件")
        for case in cases:
            if case["status"] == "error":
                print(f"  - {case['url']}: {case['message']}")


if __name__ == "__main__":
    main()
