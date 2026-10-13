# -*- coding: utf-8 -*-
"""
ファボック trunkroom.csv → 公開用 vacancy.json / index.html を生成する。

使い方:
  python build_vacancy.py --csv-dir <CSVフォルダ> --out docs
  （省略時: --csv-dir input, --out docs）

判定ルール（2026-09-04 決定）
  空室   = 有効 == 't' かつ ステータス == '貸出待ち'
  満室   = それ以外（'貸出準備中' も満室扱い = ×）
個人情報は出力しない（室番号は英数字部分のみ抽出、メモ・備考は使わない）。
"""
import argparse, csv, io, json, os, re, sys, unicodedata, collections, datetime, html

BIKE_PAT = re.compile(r'KCS|バイク|BOX|ﾎﾟｰﾀﾌﾞﾙ|ｵｰﾌﾟﾝ|ﾌﾟﾚｰﾄ|ポータブル|オープン|プレート', re.I)
KIND_JA = {'outdoor': '屋外型', 'indoor': '屋内型', 'bike': 'バイク'}


def nfkc(s):
    return unicodedata.normalize('NFKC', s or '').strip()


def load_csv(path):
    with io.open(path, encoding='cp932', errors='replace', newline='') as f:
        return list(csv.DictReader(f))


def is_bike(row):
    return row['トランクルームUNIT'] == 'バイク' or bool(BIKE_PAT.search(row['トランクルーム種別']))


EXCLUDE_TYPE_PAT = re.compile(r'\bJR\b|ＪＲ')   # 種別に「JR」が付く部屋は無いものとして扱う（2026-09-04 指示）


def match_unit(row, unit_filter):
    u = row['トランクルームUNIT']
    if u == '駐車場':
        return False
    if EXCLUDE_TYPE_PAT.search(nfkc(row['トランクルーム種別'])):
        return False
    if unit_filter == 'バイク':
        return is_bike(row)
    if unit_filter == 'コンテナ':
        return u == 'コンテナ' and not is_bike(row)
    if unit_filter == 'トランクルーム':
        return u == 'トランクルーム' and not is_bike(row)
    return not is_bike(row)


def room_no(no, store):
    """'恩名-DT44' → 'DT44'、'上今泉-T1806審査○○' → 'T1806'、'桜森１丁目S17' → 'S17'"""
    s = nfkc(no)
    st = nfkc(store)
    if '-' in s:
        s = s.split('-', 1)[1]
    elif s.startswith(st):
        s = s[len(st):]
    s = s.strip()
    m = re.match(r'^([A-Za-z]*\s?\d+(?:-\d+)?)', s)
    return m.group(1).replace(' ', '') if m else re.sub(r'[^A-Za-z0-9]', '', s)[:8]


def room_sort_key(r):
    m = re.match(r'^([A-Za-z]*)(\d+)(?:-(\d+))?$', r)
    if not m:
        return ('~', 0, 0, r)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0), r)


def tatami_of(kind_label):
    m = re.search(r'(\d+(?:\.\d+)?)\s*帖', nfkc(kind_label))
    return float(m.group(1)) if m else None


def sqm_of(kind_label):
    """種別ラベルの括弧内の平米（例 0.69帖(1.14平米) → 1.14）。範囲（1.84~2.88平米）は拾わない"""
    m = re.search(r'\(\s*(\d+(?:\.\d+)?)\s*(?:平米|m2)', nfkc(kind_label))
    return float(m.group(1)) if m else None


IGNORE_IN_TYPE = ('中通路', '変形')   # 種別ラベルから除く語（2026-09-04 指示。中通路は同じタイプに統合、変形は別フラグで扱う）


def area_of(w, d):
    """ファボックに面積が無いときの面積（㎡）。幅×奥で計算する（2026-10-13 指示）"""
    return round(w * d / 10000, 2) if w and d else None


def type_label(s):
    s = nfkc(s)
    for w in IGNORE_IN_TYPE:
        s = s.replace(w, '')
    return re.sub(r'\s+', ' ', s).strip()


def type_name(kind_label):
    """タイプ別の表に出すタイプ名。帖の数字だけにする（例 W1.0帖 室内分割 半高 → 1.0帖。2026-10-13 指示）"""
    m = re.search(r'(\d+(?:\.\d+)?)\s*帖', nfkc(kind_label))
    return m.group(1) + '帖' if m else type_label(kind_label)


BIKE_ROW_NAME = 'バイクガレージ'   # bike_rows=1 の店舗で、コンテナの表に足すバイクの行の名前
DIM_TOLERANCE = 10                 # タイプ別の表で、同じ行とみなす寸法の差（cm。2026-10-13 指示）


def is_irregular(row):
    """変形部屋か。室番号・種別・備考・メモのいずれかに「変形」があれば True（文言そのものは出力しない）"""
    return any('変形' in nfkc(row.get(c, '')) for c in ('トランクルームNo', 'トランクルーム種別', '備考', 'メモ'))


def top_price(counter):
    """部屋数が一番多い金額（同数なら高い方）。無ければ None"""
    return max(counter.items(), key=lambda x: (x[1], x[0]))[0] if counter else None


def is_vacant(r):
    """空室か。店舗マスタの keep_rooms で残した部屋（無効・JR）は常に満室（×）"""
    return r['ステータス'] == '貸出待ち' and not r.get('_keep')


def num(s):
    s = nfkc(s).replace(',', '')
    if not s:
        return None
    try:
        return float(s) if '.' in s else int(s)
    except ValueError:
        return None


def summary_text(e):
    if e['vacant'] == 0:
        return '満室御礼'
    if e['kind'] == 'bike':
        return f'空室有（{e["vacant"]}台）'
    if e['mode'] == 'type':
        types = []
        for r in e['rows']:
            if r['vacant'] and r['type'] not in types and r['type'] != BIKE_ROW_NAME:
                types.append(r['type'])
        return '・'.join(types) + ' 空き室有り'
    return f'空室有（{e["vacant"]}室）'


def build_store(m, src):
    entry = {
        'name': m['hp_name'], 'kind': m['kind'], 'mode': m['mode'],
        'page': m['page_path'], 'list_page': m['list_page'],
        'campaign': (m.get('campaign') or '').strip(),   # 空室があるときだけ表示する文言
        'show_area': m.get('show_area') == '1',              # 表に面積の列を出す（いまのHPに広さ㎡がある店舗）
        'detail_px': num(m.get('detail_px') or ''),          # 店舗ページの一言の文字サイズ（元のページに合わせる）
        'total': len(src), 'vacant': 0, 'rows': [],
    }
    irregular = set((m.get('irregular_rooms') or '').split())   # 店舗マスタで変形とする室（ファボックに記入が無いもの）
    if m['mode'] == 'room':
        items = []
        for r in src:
            no = room_no(r['トランクルームNo'], r['店舗'])
            v = is_vacant(r)
            items.append({
                'room': no,
                'irregular': is_irregular(r) or no in irregular,
                'type': type_label(r['トランクルーム種別']),
                'tatami': num(r['面積（畳）']) or tatami_of(r['トランクルーム種別']),
                'w': num(r['幅cm']), 'd': num(r['奥行cm']), 'h': num(r['高さcm']),
                'area': num(r['面積（平米）']) or sqm_of(r['トランクルーム種別']) or area_of(num(r['幅cm']), num(r['奥行cm'])),
                'price': num(r['金額（税込）']),
                'vacant': v,
            })
            entry['vacant'] += v
        entry['rows'] = sorted(items, key=lambda x: room_sort_key(x['room']))
    else:
        # タイプ（帖）と幅・奥・高が同じ部屋を1行にまとめる。空室数・室番号は合算（2026-10-13 指示）
        # 金額はファボックの部屋ごとの値がばらつくので、空室の部屋の金額（空室が無ければ部屋数が一番多い金額）にする（2026-10-13 指示）
        # 向きが違う部屋（580×220 と 220×580 など）は別の行。bike_rows=1 の店舗はバイクの部屋を「バイクガレージ」の行にする
        merged = collections.OrderedDict()
        for r in src:
            bike = is_bike(r)
            name = BIKE_ROW_NAME if bike else type_name(r['トランクルーム種別'])
            dims = (num(r['幅cm']), num(r['奥行cm']), num(r['高さcm']))
            row = merged.get((name,) + dims)
            if row is None:
                row = merged[(name,) + dims] = {'type': name, 'tatami': None if bike else tatami_of(name),
                                                'w': dims[0], 'd': dims[1], 'h': dims[2], 'areas': collections.Counter(),
                                                'prices': collections.Counter(), 'vprices': collections.Counter(),
                                                'total': 0, 'vacant': 0, 'rooms': [], 'bike': bike}
            p = num(r['金額（税込）'])
            if p is not None:
                row['prices'][p] += 1
                if is_vacant(r):
                    row['vprices'][p] += 1
            row['areas'][num(r['面積（平米）'])] += 1
            row['total'] += 1
            if is_vacant(r):
                no = room_no(r['トランクルームNo'], r['店舗'])
                row['vacant'] += 1
                row['rooms'].append(no + ('(変形)' if is_irregular(r) or no in irregular else ''))
        # 同じタイプで幅・奥・高の差がどれも DIM_TOLERANCE cm 以内の行は入力の揺れとみて1行にする（寸法は部屋数の多い方）
        clusters = []
        for row in sorted(merged.values(), key=lambda r: -r['total']):
            for c in clusters:
                if c['type'] == row['type'] and all(
                        a is not None and b is not None and abs(a - b) <= DIM_TOLERANCE
                        for a, b in zip((c['w'], c['d'], c['h']), (row['w'], row['d'], row['h']))):
                    c['prices'].update(row['prices'])
                    c['vprices'].update(row['vprices'])
                    c['areas'].update(row['areas'])
                    c['total'] += row['total']
                    c['vacant'] += row['vacant']
                    c['rooms'] += row['rooms']
                    break
            else:
                clusters.append(row)
        for row in clusters:
            v, a = row.pop('vprices'), row.pop('prices')
            row['price'] = top_price(v) or top_price(a)
        for row in sorted(clusters, key=lambda r: (r['bike'], r['tatami'] or 999, r['price'] or 0, r['w'] or 0)):
            row['area'] = row.pop('areas').most_common(1)[0][0] or area_of(row['w'], row['d'])
            row['rooms'] = sorted(row['rooms'], key=room_sort_key)
            if row.pop('bike'):
                entry['total'] -= row['total']     # バイクガレージの行は店舗の総数・空室数・一言に数えない（バイクのページで数える）
            else:
                entry['vacant'] += row['vacant']
            entry['rows'].append(row)
    entry['summary'] = summary_text(entry)
    return entry


def build(csv_dir, out_dir, master_path):
    tr_path = os.path.join(csv_dir, 'trunkroom.csv')
    os_path = os.path.join(csv_dir, 'operatingstatus.csv')
    if not os.path.exists(tr_path):
        sys.exit(f'ERROR: {tr_path} がありません')
    all_rows = load_csv(tr_path)
    rows = [r for r in all_rows if r.get('有効') == 't']
    all_by_store = collections.defaultdict(list)
    for r in all_rows:
        all_by_store[r['店舗']].append(r)
    src_time = datetime.datetime.fromtimestamp(os.path.getmtime(tr_path))
    now = datetime.datetime.now()
    warnings = []
    if (now - src_time).days >= 2:
        warnings.append(f'CSVが古い可能性: trunkroom.csv 更新日時 {src_time:%Y-%m-%d %H:%M}')

    with io.open(master_path, encoding='utf-8-sig', newline='') as f:
        master = list(csv.DictReader(f))

    by_store = collections.defaultdict(list)
    for r in rows:
        by_store[r['店舗']].append(r)
    known = {m['faboc_store'] for m in master}
    for s in by_store:
        if s not in known:
            warnings.append(f'店舗マスタ未登録: {s}（{len(by_store[s])}室）')

    stores = {}
    for m in master:
        if m['publish'] != '1':
            continue
        src = [r for r in by_store.get(m['faboc_store'], []) if match_unit(r, m['unit_filter'])
               or (m.get('bike_rows') == '1' and m['mode'] == 'type' and is_bike(r) and r['トランクルームUNIT'] != '駐車場')]
        # keep_rooms … 無効・JR で外れるが、いまのHPに載っている部屋。表には出すが常に×（2026-10-13 指示）
        keep = set((m.get('keep_rooms') or '').split())
        if keep:
            have = {id(r) for r in src}
            for r in all_by_store.get(m['faboc_store'], []):
                if id(r) not in have and room_no(r['トランクルームNo'], r['店舗']) in keep:
                    src.append(dict(r, _keep=True))
        if not src:
            warnings.append(f'{m["key"]}: 該当ユニットなし（{m["faboc_store"]} / {m["unit_filter"]}）')
        stores[m['key']] = build_store(m, src)

    # 検算: operatingstatus.csv の店舗別（空室 − 準備中）と突合
    # ファボックの稼働率集計は「貸出準備中」を空室に含めるため差し引いて比較する
    if os.path.exists(os_path):
        agg = collections.defaultdict(int)
        for r in load_csv(os_path):
            agg[r['店舗名']] += int(r['空室'] or 0) - int(r['準備中'] or 0)
        mine = collections.defaultdict(int)
        for m in master:
            if m['publish'] == '1' and m['key'] in stores:
                mine[m['faboc_store']] += stores[m['key']]['vacant']
        for s, v in mine.items():
            if s in agg and agg[s] != v:
                warnings.append(f'検算差異 {s}: operatingstatus 空室={agg[s]} / 生成={v}')

    data = {
        'generated_at': now.strftime('%Y-%m-%d %H:%M'),
        'source_time': src_time.strftime('%Y-%m-%d %H:%M'),
        'stores': stores,
        'warnings': warnings,
    }
    os.makedirs(out_dir, exist_ok=True)
    with io.open(os.path.join(out_dir, 'vacancy.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    write_index(data, out_dir)
    return data


def write_index(data, out_dir):
    esc = html.escape
    rows = []
    order = {'outdoor': 0, 'indoor': 1, 'bike': 2}
    for key, e in sorted(data['stores'].items(), key=lambda kv: (order[kv[1]['kind']], kv[1]['page'])):
        cls = 'vac' if e['vacant'] else 'full'
        rows.append(
            f'<tr class="{cls}"><td>{esc(e["name"])}</td><td>{KIND_JA[e["kind"]]}</td>'
            f'<td>{e["vacant"]} / {e["total"]}</td><td>{esc(e["summary"])}</td>'
            f'<td><a href="https://www.trunk-sunly.jp{esc(e["page"])}" target="_blank">{esc(e["page"])}</a></td>'
            f'<td><a href="test.html?store={esc(key)}">プレビュー</a></td></tr>')
    warn = ''.join(f'<li>{esc(w)}</li>' for w in data['warnings'])
    warn_html = f'<div class="w"><b>警告</b><ul>{warn}</ul></div>' if warn else ''
    page = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>サンリー 空室状況（確認用）</title>
<style>body{{font-family:sans-serif;margin:16px;color:#222}}table{{border-collapse:collapse;font-size:14px}}
td,th{{border:1px solid #bbb;padding:4px 8px}}tr.vac td:nth-child(4){{color:#d00;font-weight:bold}}
tr.full td:nth-child(4){{color:#777}}.w{{background:#fff4e5;padding:8px;border:1px solid #f0c080;margin:8px 0}}</style></head><body>
<h1>サンリー 空室状況（確認用）</h1>
<p>データ更新：{esc(data["source_time"])}（CSV）／ 生成：{esc(data["generated_at"])}</p>
{warn_html}
<table><tr><th>店舗</th><th>種別</th><th>空室/管理</th><th>一覧表示文言</th><th>HPページ</th><th></th></tr>{''.join(rows)}</table>
</body></html>'''
    with io.open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument('--csv-dir', default=os.path.join(here, 'input'))
    ap.add_argument('--out', default=os.path.join(here, 'docs'))
    ap.add_argument('--master', default=os.path.join(here, 'store_master.csv'))
    a = ap.parse_args()
    d = build(a.csv_dir, a.out, a.master)
    print(f'生成完了: {len(d["stores"])}店舗  空室合計 {sum(e["vacant"] for e in d["stores"].values())}  '
          f'CSV日時 {d["source_time"]}')
    for w in d['warnings']:
        print('WARN:', w)
