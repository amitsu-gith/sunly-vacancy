/* サンリー 空室状況 埋め込みウィジェット
 * 使い方（あきばれ フリーHTML部品に貼る）:
 *   <div class="sunly-vacancy" data-store="onna" data-mode="summary"></div>
 *   <div class="sunly-vacancy" data-store="onna" data-mode="table"></div>
 *   <script src="https://<公開先>/sunly-vacancy.js" defer></script>
 * data-store は store_master.csv の key。data-mode は summary | table。
 * data-note     … 空室があるときだけ出す文言（省略時は店舗マスタの campaign 列）。空文字で非表示
 * data-repeat   … table で N 行ごとに項目名の行を挟む（既定: 室番号別=10、タイプ別=0）
 * data-size     … summary の文字サイズ（px）。既定は一覧ページと同じ 20。店舗ページは元のページの大きさ（店舗マスタの detail_px）を入れる
 * 幅・奥・高はすべて cm で出す。
 * 室番号別の表（mode=room の店舗）だけ:
 *   data-filter … 室番号の頭文字で絞る（例 "PT"、"PL,PT"）
 *   data-cols   … 出す列と順番。no,tatami,w,d,h,area,price,status（既定 no,tatami,w,d,h,price,status）
 *                 幅・奥・高はどれか1つを書けば3つそろえて出す
 *   data-link   … 室番号のリンク先。{room} を室番号に置き換える（例 "#{room}画像"）。ページ内リンクは同じ id があるときだけ張る
 * 取得に失敗した場合は data-fallback の文言を表示（無ければ何も表示しない）。
 */
(function () {
  var script = document.currentScript;
  var base = script ? script.src.replace(/[^\/]*$/, '') : '';
  var url = base + 'vacancy.json?v=' + Math.floor(Date.now() / 3600000);

  var css = '' +
    '.sv-summary{color:#FF0000;font-weight:bold;font-size:20px;line-height:1.4}' +
    '.sv-upd{font-size:12px;color:#666;margin:2px 0 6px}' +
    '.sv-wrap{overflow-x:auto}' +
    '.sv-table{border-collapse:collapse;width:100%;max-width:640px;font-size:15px;margin:6px 0}' +
    '.sv-table th,.sv-table td{border:1px solid #999;padding:4px 6px;text-align:center;white-space:nowrap}' +
    '.sv-table th{background:#f2f2f2;font-weight:bold}' +
    '.sv-table td.sv-ok{color:#FF0000;font-weight:bold;font-size:18px}' +
    '.sv-table td.sv-ng{color:#333}' +
    '.sv-table td.sv-rooms{font-size:13px;white-space:normal}';
  if (!document.getElementById('sv-style')) {
    var st = document.createElement('style');
    st.id = 'sv-style';
    st.textContent = css;
    document.head.appendChild(st);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function yen(n) { return n == null ? '' : '￥' + Number(n).toLocaleString('ja-JP'); }
  function toCm(v) { return v == null ? '' : String(v); }

  /* 空室があるときだけ出すキャンペーン文言。data-note 属性があれば優先、無ければ店舗マスタの campaign */
  function campaignLine(el, e) {
    if (!(e.vacant > 0)) return '';
    var note = el.getAttribute('data-note');
    if (note == null) note = e.campaign || '';
    return note ? '<br>' + esc(note) : '';
  }

  /* data-size があればその大きさ（px）にする。無ければ CSS の既定（20px） */
  function sizeAttr(el) {
    var px = parseInt(el.getAttribute('data-size'), 10);
    return px > 0 ? ' style="font-size:' + px + 'px"' : '';
  }

  function renderSummary(el, e, data) {
    el.innerHTML = '<div class="sv-summary"' + sizeAttr(el) + '>' + esc(e.summary) + campaignLine(el, e) + '</div>';
  }

  function renderTable(el, e, data) {
    var h = '<div class="sv-wrap"><table class="sv-table">';
    var unit = 'cm';
    var f = toCm;
    /* 長い表は N 行ごとに項目名の行を挟む（data-repeat で変更可。既定は室番号別=10、タイプ別=なし） */
    var rep = parseInt(el.getAttribute('data-repeat'), 10);
    if (isNaN(rep)) rep = e.mode === 'room' ? 10 : 0;
    var head;
    if (e.mode === 'type') {
      head = '<tr><th>タイプ</th><th>幅<br>' + unit + '</th><th>奥<br>' + unit + '</th><th>高<br>' + unit + '</th><th>月額賃料</th><th>NO</th><th>空室<br>状況</th></tr>';
      h += head;
      e.rows.forEach(function (r, i) {
        if (rep && i && i % rep === 0) h += head;
        var ok = r.vacant > 0;
        h += '<tr><td>' + esc(r.type) + '</td><td>' + f(r.w) + '</td><td>' + f(r.d) + '</td><td>' + f(r.h) + '</td>' +
          '<td>' + yen(r.price) + '</td><td class="sv-rooms">' + esc(r.rooms.join(' ')) + '</td>' +
          '<td class="' + (ok ? 'sv-ok' : 'sv-ng') + '">' + (ok ? '〇' : '×') + '</td></tr>';
      });
    } else {
      /* data-filter … 室番号の頭文字で絞る（例 "PT"。カンマ区切りで複数可）
       * data-cols   … 出す列と順番（no,tatami,w,d,h,area,price,status）
       * data-link   … 室番号のリンク先。{room} を室番号に置き換え、ページ内に同じ id があるときだけ張る（例 "#{room}画像"） */
      var filters = (el.getAttribute('data-filter') || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      var rows = filters.length ? e.rows.filter(function (r) {
        return filters.some(function (p) { return String(r.room).indexOf(p) === 0; });
      }) : e.rows;
      var cols = (el.getAttribute('data-cols') || 'no,tatami,w,d,h,price,status').split(',').map(function (s) { return s.trim(); });
      var link = el.getAttribute('data-link');
      var COLS = {
        no: ['NO', function (r) {
          var t = esc(r.room) + (r.irregular ? '<br>変形' : '');
          if (link) {
            var href = link.replace('{room}', r.room);
            if (href.charAt(0) !== '#' || document.getElementById(href.slice(1))) t = '<a href="' + esc(href) + '">' + t + '</a>';
          }
          return '<td>' + t + '</td>';
        }],
        tatami: ['帖', function (r) { return '<td>' + (r.tatami == null ? esc(r.type) : r.tatami) + '</td>'; }],
        w: ['幅<br>' + unit, function (r) { return '<td>' + f(r.w) + '</td>'; }],
        d: ['奥<br>' + unit, function (r) { return '<td>' + f(r.d) + '</td>'; }],
        h: ['高<br>' + unit, function (r) { return '<td>' + f(r.h) + '</td>'; }],
        area: ['面積<br>㎡', function (r) { return '<td>' + (r.area == null ? '' : r.area) + '</td>'; }],
        price: ['月額賃料', function (r) { return '<td>' + yen(r.price) + '</td>'; }],
        status: ['空室<br>状況', function (r) { return '<td class="' + (r.vacant ? 'sv-ok' : 'sv-ng') + '">' + (r.vacant ? '〇' : '×') + '</td>'; }]
      };
      /* 幅・奥・高はそろえて出す（どれかが指定されていれば、最初の位置に w,d,h の順で入れる） */
      var dimAt = -1;
      cols = cols.filter(function (c, i) {
        if (c === 'w' || c === 'd' || c === 'h') { if (dimAt < 0) dimAt = i; return false; }
        return true;
      });
      if (dimAt >= 0) cols.splice(Math.min(dimAt, cols.length), 0, 'w', 'd', 'h');
      cols = cols.filter(function (c) { return COLS[c]; });
      head = '<tr>' + cols.map(function (c) { return '<th>' + COLS[c][0] + '</th>'; }).join('') + '</tr>';
      h += head;
      rows.forEach(function (r, i) {
        if (rep && i && i % rep === 0) h += head;
        h += '<tr>' + cols.map(function (c) { return COLS[c][1](r); }).join('') + '</tr>';
      });
    }
    h += '</table></div>';
    el.innerHTML = h;
  }

  function run(data) {
    var els = document.querySelectorAll('.sunly-vacancy[data-store]');
    Array.prototype.forEach.call(els, function (el) {
      var e = data.stores[el.getAttribute('data-store')];
      if (!e) {
        el.innerHTML = '<span class="sv-upd">（店舗キー未登録: ' + esc(el.getAttribute('data-store')) + '）</span>';
        return;
      }
      if ((el.getAttribute('data-mode') || 'summary') === 'table') renderTable(el, e, data);
      else renderSummary(el, e, data);
    });
  }

  function fail() {
    var els = document.querySelectorAll('.sunly-vacancy[data-fallback]');
    Array.prototype.forEach.call(els, function (el) {
      el.innerHTML = '<div class="sv-summary">' + esc(el.getAttribute('data-fallback')) + '</div>';
    });
  }

  var x = new XMLHttpRequest();
  x.open('GET', url, true);
  x.onload = function () {
    if (x.status === 200) {
      try { run(JSON.parse(x.responseText)); } catch (err) { fail(); }
    } else {
      fail();
    }
  };
  x.onerror = fail;
  x.send();
})();
