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
- 種別に「JR」が付く部屋（例: `5.0帖 JR`）は無いものとして扱う（表・件数・検算のすべてから除外）
- 種別の「中通路」は無視し、同じ帖数のタイプに統合する（例: `1.5帖 中通路` → `1.5帖`）
- 「変形」は室番号・種別・備考・メモのいずれかに含まれていれば変形部屋として NO 欄に表示する。
  ファボックの備考欄に「変形」と入れれば HP にも反映される
- バイクは `UNIT = バイク` または種別に KCS / バイク / BOX / ﾎﾟｰﾀﾌﾞﾙ / ｵｰﾌﾟﾝ / ﾌﾟﾚｰﾄ を含むもの
- 室番号は「店舗名-」以降の英数字部分だけを使う（メモ・氏名などは出力しない）

## あきばれ側の設定（初回のみ）
`docs/test.html?store=<key>` に表示されるHTMLをフリーHTML部品に貼る。
- 一覧ページ：`data-mode="summary"`（赤字の一言）
- 店舗詳細ページ：`data-mode="table"`（タイプ別または室番号別の ○× 表）

### 埋め込み要素の属性
- `data-note` … 空室があるときだけ赤字の下に出す文言。省略時は店舗マスタの `campaign` 列。`data-note=""` で非表示
- `data-repeat` … table で N 行ごとに項目名の行を挟む。既定は室番号別の表が 10 行ごと、タイプ別は挟まない
- `data-fallback` … データ取得に失敗したときに出す文言
- `data-size` … summary の文字サイズ（px）。省略時は 20（一覧ページの大きさ）。店舗ページは元のページの大きさ（店舗マスタの `detail_px`）を入れる。`test.html` の貼り付けHTMLには自動で入る
- 表の見出しは「NO」「月額賃料」、幅・奥・高はすべて cm
- タイプ別の表は、タイプと幅・奥・高が同じで金額だけ違う行を、一番高い金額の1行にまとめる（空室数・室番号は合算）
- 室番号別の表（`mode=room` の店舗）だけ：
  - `data-filter` … 室番号の頭文字で絞る（例 `PT`、`PL,PT`）。バイクのポータブル・プレートを別の表にするとき
  - `data-cols` … 出す列。`no,tatami,area,w,d,h,price,status`（既定は `no,tatami,w,d,h,price,status`）。順番は全店共通で NO・帖・面積・幅・奥・高・月額賃料・空室状況（書いた順は関係ない）。幅・奥・高はどれか1つを書けば3つそろえて出す
  - `data-link` … 室番号のリンク先。`{room}` を室番号に置き換える（例 `#{room}画像`）。ページ内リンクはその id がページにあるときだけ張る

## 店舗マスタの列
`key`（埋め込みで使うID）/ `faboc_store`（ファボック店舗名そのまま）/ `unit_filter`（コンテナ・トランクルーム・バイク）/
`hp_name` / `kind`（outdoor・indoor・bike）/ `mode`（type=タイプ別表・room=室番号別表）/ `page_path` / `list_page` / `publish` /
`campaign`（空室があるときだけ表示する文言。全店「６か月以上利用で初月賃料無料」を初期値にした）/ `note` /
`detail_px`（店舗ページの一言の文字サイズ。2026-10-13 に公開中のページから測った値。一言が無いページは空欄）
