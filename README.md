# 失敗知識データベース ETL

失敗知識データベース（https://www.shippai.org/fkd/）から事例データを抽出し、PDFレポートとJSONファイルを生成するETLパイプライン。

## セットアップ

```bash
# venv作成
python3 -m venv venv

# 依存パッケージインストール
venv/bin/pip install reportlab requests pillow beautifulsoup4
```

## 使い方

### 単一事例の処理

```bash
venv/bin/python src/run.py https://www.shippai.org/fkd/cf/CZ0200703.html
```

### 一覧ページから上位N件を処理

```bash
venv/bin/python src/run.py https://www.shippai.org/fkd/lis/cat001.html --limit 3
```

### 複数URLを指定

```bash
venv/bin/python src/run.py URL1 URL2 URL3
```

### オプション

| オプション | 説明 |
|-----------|------|
| `--limit N` | 一覧ページから処理する件数の上限 |
| `--output-dir DIR` | 出力ディレクトリ（デフォルト: `data/`） |

## 出力

各事例につき2ファイルが `data/` ディレクトリに生成される:

- `{事例ID}_{事例名称}.pdf` - 構造化されたPDFレポート（対角線図・画像埋め込み付き）
- `{事例ID}_{事例名称}.json` - 構造化されたJSONデータ
- `results_NNN.json` - 全事例の処理結果（成功・除外・エラー）。実行ごとに連番で自動生成

必須フィールド（概要・経過・原因・対策・シナリオ）が欠損している事例は処理をスキップし、results ファイルに除外理由が記録される。

## ディレクトリ構成

```
.
├── README.md           # このファイル
├── requirements.md   # ETL仕様書
├── src/
│   ├── extract.py      # URL → JSON抽出（HTMLパース、シナリオページ解析）
│   ├── render_pdf.py   # JSON → PDF描画（対角線図、画像埋め込み）
│   └── run.py          # CLIエントリポイント
├── data/               # 出力ディレクトリ（自動作成）
└── venv/               # Python仮想環境（自動作成）
```

## 仕様

詳細な仕様は [requirements.md](requirements.md) を参照。
