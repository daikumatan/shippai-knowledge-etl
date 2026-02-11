# 失敗知識データベース ETL 仕様書

## 1. 目的

失敗知識データベース（https://www.shippai.org/fkd/）から事例データを抽出し、PDF形式のレポートとJSON形式の構造化データを生成する。

## 2. データソース

- **事例ページ**: `https://www.shippai.org/fkd/cf/{事例ID}.html`
- **シナリオページ**: `https://www.shippai.org/fkd/sf/{シナリオID}.html`（事例ページからリンク）
- **マルチメディア**: `https://www.shippai.org/fkd/mf/{ファイルID}.jpg`（事例ページからリンク）
- **代表図**: `https://www.shippai.org/fkd/df/{図ID}.jpg`
- **一覧ページ**: `https://www.shippai.org/fkd/lis/{カテゴリ}.html`（事例URLのリスト）

## 3. 抽出ルール

1. 各事例に記載の日本語は一字一句そのまま抽出すること
2. 事例IDはURLパス（`/cf/CZ0200703.html` → `CZ0200703`）から抽出する
3. 日付は `YYYY-MM-DD` 形式に変換する（例: `2006年06月15日` → `2006-06-15`）
4. シナリオページを自動的にフェッチし、番号付きアイテムをカテゴリ別（原因・行動・結果）にグループ化する
   - カテゴリ境界は二重線（`sinario_line_2.gif`）、グループ境界は単線（`sinario_line_1.gif`）で判定する
5. マルチメディアリンクからファイルIDとキャプションを抽出する

### 3.1 必須フィールド

以下のフィールドをすべて含む事例のみ処理対象とする。いずれかが欠損している事例は除外する。

| HTMLラベル | JSONキー | 説明 |
|-----------|---------|------|
| 事例概要 | `summary` | 事例の概要 |
| 経過 | `process` | 時系列の経過 |
| 原因 | `cause` | 原因分析 |
| 対策 | `countermeasure` | 恒久対策 |
| シナリオ | `scenario` | 失敗マンダラのシナリオデータ |

以下のフィールドは任意（存在すれば抽出するが、欠損していても除外しない）:

| HTMLラベル | JSONキー | 説明 |
|-----------|---------|------|
| 対処 | `response` | 応急対処 |
| 知識化 | `knowledge` | 教訓・知見 |

### 3.2 処理結果ファイル

すべての事例の処理結果（成功・除外・エラー）を `data/results_NNN.json`（連番）に記録する。実行のたびに既存ファイルの最大番号+1で自動採番される（例: `results_001.json`, `results_002.json`, ...）。形式は以下の通り:

```json
{
  "processed_at": "2026-02-11T20:58:00",
  "summary": {"total": 10, "success": 8, "excluded": 1, "error": 1},
  "cases": [
    {
      "case_id": "CZ0200703",
      "case_name": "浜岡原発タービンの損傷",
      "url": "https://...",
      "status": "success",
      "outputs": ["CZ0200703_浜岡原発タービンの損傷.json", "...pdf"]
    },
    {
      "case_id": "CA0000095",
      "case_name": "ブラケットの変形で...",
      "url": "https://...",
      "status": "excluded",
      "missing_fields": ["対処"]
    },
    {
      "url": "https://...",
      "status": "error",
      "message": "エラーメッセージ"
    }
  ]
}
```

- `status` は `success`、`excluded`、`error` のいずれか
- `excluded` の場合、`missing_fields` に不足しているフィールドのHTMLラベル名を配列で記載する
- `error` の場合、`message` にエラーメッセージを記載する

## 4. 出力仕様

### 4.1 出力先

すべての出力ファイル（PDF, JSON）は `data/` ディレクトリに格納する。ディレクトリが存在しない場合は自動作成する。

### 4.2 ファイル命名規則

`{事例ID}_{事例名称}` の形式とする。

- 例: `data/CZ0200703_浜岡原発タービンの損傷.pdf`
- 例: `data/CZ0200703_浜岡原発タービンの損傷.json`

### 4.3 PDF出力形式

人が見て見やすい形式とする。以下のルールに従う:

1. セクション見出し（h1, h2等）で正しく構造化して表示する
2. 代表図をPDFに埋め込む
3. シナリオセクションは「対角線図」として描画する（詳細は「5. 対角線図の描画仕様」を参照）
4. マルチメディアファイルセクションのリンク先画像をすべてPDFに埋め込む
5. 情報源セクションのURLはクリック可能なハイパーリンクとする
6. 備考・分野・データ作成者などの付帯情報もすべて含める

### 4.4 JSON出力形式

以下のスキーマに従う:

```json
{
  "case_id": "事例ID",
  "case_name": "事例名称",
  "url": "元データのURL",
  "date": "YYYY-MM-DD形式の発生日付",
  "location": "事例発生地",
  "facility": "事例発生場所",
  "summary": "事例概要",
  "phenomenon": "事象",
  "process": "経過",
  "cause": "原因",
  "response": "対処",
  "countermeasure": "対策",
  "knowledge": ["知識化の各項目を配列で"],
  "background": "背景",
  "scenario": {
    "cause": [["グループ1項目1", "項目2", "項目3"], ["グループ2..."]],
    "action": [["..."]],
    "result": [["..."]]
  },
  "images": {
    "representative": "代表図のファイル名",
    "multimedia": [
      {"id": "ファイルID", "caption": "キャプション"}
    ]
  },
  "sources": ["情報源の各項目を配列で"],
  "casualties": {"deaths": 0, "injuries": 0},
  "financial_damage": "被害金額のテキスト",
  "social_impact": "社会への影響",
  "notes": "備考",
  "field": "分野",
  "authors": ["データ作成者を配列で"]
}
```

- `scenario` は失敗マンダラの対角線図データ。`cause`/`action`/`result` の各配列内の要素が1グループ（3項目）に対応する
- テキストフィールドは元データの日本語をそのまま格納する

## 5. 対角線図の描画仕様

失敗マンダラにおける「脈絡による具体的表現」（参考: https://www.shippai.org/fkd/inf/mandara.html#4 図12）を対角線図として描画する。reportlab の Drawing API を使用すること。

1. **レイアウト**: 横軸=時間の進行、縦軸=ステップの進行。各項目を矩形バーとして、左上から右下へ階段状に配置する
2. **番号**: 各項目は通し番号（01, 02, ...）付き。3項目ずつ1グループとなる
3. **カテゴリ**: 「原因」「行動」「結果」の3つ
4. **区切り線**: 同一カテゴリ内のグループ間は「単線」（細線）、カテゴリ間（原因→行動、行動→結果）は「二重線」（太線2本）で区切る
5. **色分け**: 原因=青系(`#dce6f1`)、行動=緑系(`#e2efda`)、結果=橙系(`#fce4d6`)
6. **カテゴリラベル**: 各カテゴリの右側に括弧線（`]`型）とラベルテキスト（「原因」「行動」「結果」）を配置する
7. **軸ラベル**: 上部に「（時間の進行）→」を表示する

## 6. ソースコード構成

ETLパイプラインは `src/` ディレクトリ内の3つのモジュールで構成される:

```
src/
├── extract.py      # URL → JSON抽出（HTMLパース、シナリオページ解析）
├── render_pdf.py   # JSON → PDF描画（対角線図、画像埋め込み）
└── run.py          # CLIエントリポイント
```

- **extract.py**: shippai.org のHTMLを BeautifulSoup でパースし、事例データをJSONスキーマに変換する。シナリオページ（`sf/`）も自動的にフェッチして解析する
- **render_pdf.py**: JSONデータから reportlab でPDFを生成する。対角線図の描画、画像のダウンロード・埋め込み、ハイパーリンクの設定を行う
- **run.py**: CLIインターフェース。事例URL（`cf/`）と一覧URL（`lis/`）の両方に対応。`--limit` オプションで処理件数を制御可能

## 7. 実行環境

- Python 3.x
- venv をプロジェクトルートに作成する（存在しない場合は自動作成）
- 依存パッケージ: `reportlab`, `requests`, `pillow`, `beautifulsoup4`
- 日本語フォント: reportlab CID フォント `HeiseiMin-W3`（明朝）, `HeiseiKakuGo-W5`（角ゴシック）
