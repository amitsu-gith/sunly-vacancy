# sunly-vacancy ｜ サンリーHP 空室状況 自動更新

ファボック（トランクルームクラウド）の `trunkroom.csv` から、HP に埋め込む空室データを生成し GitHub Pages で公開する。

## 構成
| ファイル | 役割 |
|---|---|
| `store_master.csv` | ファボック店舗名 ↔ HPページ の対応表。`publish=0` で非公開 |
| `build_vacancy.py` | CSV → `docs/vacancy.json` `docs/index.html` を生成 |
| `docs/sunly-vacancy.js` | あきばれのフリーHTML部品に貼る埋め込みスクリプト |
| `docs/test.html` | 店舗ごとの表示プレビューと貼り付け用HTML（`?store=onna`） |
| `update.ps1` | 毎朝の一括実行（取込 → 生成 → push） |
| `input/` | CSVの取込先。個人情報を含むため git 管理外 |

## 毎朝の運用
1. ファボックから `trunkroom.csv`（と `operatingstatus.csv`）をエクスポートし、`update.ps1` の `$CsvDir` に保存
2. タスクスケジューラが `update.ps1` を実行（手動でも可）
3. 数十秒〜1分で GitHub Pages に反映。`docs/index.html` で全店の状態と警告を確認できる

## 判定ルール
- 空室 = `有効 = t` かつ `ステータス = 貸出待ち`
- `貸出準備中` は満室扱い（×）
- `駐車場` UNIT は対象外
- バイクは `UNIT = バイク` または種別に KCS / バイク / BOX / ﾎﾟｰﾀﾌﾞﾙ / ｵｰﾌﾟﾝ / ﾌﾟﾚｰﾄ を含むもの
- 室番号は「店舗名-」以降の英数字部分だけを使う（メモ・氏名などは出力しない）

## あきばれ側の設定（初回のみ）
`docs/test.html?store=<key>` に表示されるHTMLをフリーHTML部品に貼る。
- 一覧ページ：`data-mode="summary"`（赤字の一言）
- 店舗詳細ページ：`data-mode="table"`（タイプ別または室番号別の ○× 表）

## 店舗マスタの列
`key`（埋め込みで使うID）/ `faboc_store`（ファボック店舗名そのまま）/ `unit_filter`（コンテナ・トランクルーム・バイク）/
`hp_name` / `kind`（outdoor・indoor・bike）/ `mode`（type=タイプ別表・room=室番号別表）/ `page_path` / `list_page` / `publish` / `note`
