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


def match_unit(row, unit_filter):
    u = row['トランクルームUNIT']
    if u == '駐車場':
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
            if r['vacant'] and r['type'] not in types:
                types.append(r['type'])
        return '・'.join(types) + ' 空き室有り'
    return f'空室有（{e["vacant"]}室）'


def build_store(m, src):
    entry = {
        'name': m['hp_name'], 'kind': m['kind'], 'mode': m['mode'],
        'page': m['page_path'], 'list_page': m['list_page'],
        'campaign': (m.get('campaign') or '').strip(),   # 空室があるときだけ表示する文言
        'total': len(src), 'vacant': 0, 'rows': [],
    }
    if m['mode'] == 'room':
        items = []
        for r in src:
            no = room_no(r['トランクルームNo'], r['店舗'])
            v = r['ステータス'] == '貸出待ち'
            items.append({
                'room': no,
                'type': nfkc(r['トランクルーム種別']),
                'tatami': num(r['面積（畳）']) or tatami_of(r['トランクルーム種別']),
                'w': num(r['幅cm']), 'd': num(r['奥行cm']), 'h': num(r['高さcm']),
                'area': num(r['面積（平米）']),
                'price': num(r['金額（税込）']),
                'vacant': v,
            })
            entry['vacant'] += v
        entry['rows'] = sorted(items, key=lambda x: room_sort_key(x['room']))
    else:
        groups = collections.OrderedDict()
        for r in src:
            key = (nfkc(r['トランクルーム種別']), num(r['金額（税込）']))
            g = groups.setdefault(key, {'type': key[0], 'tatami': tatami_of(key[0]), 'price': key[1],
                                        'total': 0, 'vacant': 0, 'rooms': [], 'dims': collections.Counter()})
            g['total'] += 1
            g['dims'][(num(r['幅cm']), num(r['奥行cm']), num(r['高さcm']), num(r['面積（平米）']))] += 1
            if r['ステータス'] == '貸出待ち':
                g['vacant'] += 1
                g['rooms'].append(room_no(r['トランクルームNo'], r['店舗']))
        for g in sorted(groups.values(), key=lambda g: (g['tatami'] or 999, g['price'] or 0, g['type'])):
            w, d, h, a = g['dims'].most_common(1)[0][0]
            entry['rows'].append({'type': g['type'], 'tatami': g['tatami'], 'w': w, 'd': d, 'h': h, 'area': a,
                                  'price': g['price'], 'total': g['total'], 'vacant': g['vacant'],
                                  'rooms': sorted(g['rooms'], key=room_sort_key)})
            entry['vacant'] += g['vacant']
    entry['summary'] = summary_text(entry)
    return entry


def build(csv_dir, out_dir, master_path):
    tr_path = os.path.join(csv_dir, 'trunkroom.csv')
    os_path = os.path.join(csv_dir, 'operatingstatus.csv')
    if not os.path.exists(tr_path):
        sys.exit(f'ERROR: {tr_path} がありません')
    rows = [r for r in load_csv(tr_path) if r.get('有効') == 't']
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
        src = [r for r in by_store.get(m['faboc_store'], []) if match_unit(r, m['unit_filter'])]
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
