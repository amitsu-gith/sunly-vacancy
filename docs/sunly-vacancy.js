/* サンリー 空室状況 埋め込みウィジェット
 * 使い方（あきばれ フリーHTML部品に貼る）:
 *   <div class="sunly-vacancy" data-store="onna" data-mode="summary"></div>
 *   <div class="sunly-vacancy" data-store="onna" data-mode="table"></div>
 *   <script src="https://<公開先>/sunly-vacancy.js" defer></script>
 * data-store は store_master.csv の key。data-mode は summary | table。
 * data-note     … 空室があるときだけ出す文言（省略時は店舗マスタの campaign 列）。空文字で非表示
 * data-repeat   … table で N 行ごとに項目名の行を挟む（既定: 室番号別=10、タイプ別=0）
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
  function toM(cmv) {
    if (cmv == null) return '';
    var v = Number(cmv) / 100;
    return (Math.round(v * 100) % 10 === 0) ? v.toFixed(1) : v.toFixed(2);
  }
  function toCm(v) { return v == null ? '' : String(v); }
  function updLine(data) { return '<div class="sv-upd">空室情報 更新：' + esc(data.source_time.slice(0, 10)) + '</div>'; }

  /* 空室があるときだけ出すキャンペーン文言。data-note 属性があれば優先、無ければ店舗マスタの campaign */
  function campaignLine(el, e) {
    if (!(e.vacant > 0)) return '';
    var note = el.getAttribute('data-note');
    if (note == null) note = e.campaign || '';
    return note ? '<br>' + esc(note) : '';
  }

  function renderSummary(el, e, data) {
    el.innerHTML = '<div class="sv-summary">' + esc(e.summary) + campaignLine(el, e) + '</div>' + updLine(data);
  }

  function renderTable(el, e, data) {
    var h = '<div class="sv-wrap"><table class="sv-table">';
    var useM = e.kind === 'outdoor';
    var unit = useM ? 'ｍ' : '㎝';
    var f = useM ? toM : toCm;
    /* 長い表は N 行ごとに項目名の行を挟む（data-repeat で変更可。既定は室番号別=10、タイプ別=なし） */
    var rep = parseInt(el.getAttribute('data-repeat'), 10);
    if (isNaN(rep)) rep = e.mode === 'room' ? 10 : 0;
    var head;
    if (e.mode === 'type') {
      head = '<tr><th>タイプ</th><th>幅<br>' + unit + '</th><th>奥<br>' + unit + '</th><th>高<br>' + unit + '</th><th>月額<br>賃料</th><th>NO,</th><th>空室<br>状況</th></tr>';
      h += head;
      e.rows.forEach(function (r, i) {
        if (rep && i && i % rep === 0) h += head;
        var ok = r.vacant > 0;
        h += '<tr><td>' + esc(r.type) + '</td><td>' + f(r.w) + '</td><td>' + f(r.d) + '</td><td>' + f(r.h) + '</td>' +
          '<td>' + yen(r.price) + '</td><td class="sv-rooms">' + esc(r.rooms.join(' ')) + '</td>' +
          '<td class="' + (ok ? 'sv-ok' : 'sv-ng') + '">' + (ok ? '〇' : '×') + '</td></tr>';
      });
    } else {
      head = '<tr><th>NO,</th><th>帖</th><th>幅<br>' + unit + '</th><th>奥<br>' + unit + '</th><th>高<br>' + unit + '</th><th>月額<br>賃料</th><th>空室<br>状況</th></tr>';
      h += head;
      e.rows.forEach(function (r, i) {
        if (rep && i && i % rep === 0) h += head;
        h += '<tr><td>' + esc(r.room) + '</td><td>' + (r.tatami == null ? esc(r.type) : r.tatami) + '</td>' +
          '<td>' + f(r.w) + '</td><td>' + f(r.d) + '</td><td>' + f(r.h) + '</td><td>' + yen(r.price) + '</td>' +
          '<td class="' + (r.vacant ? 'sv-ok' : 'sv-ng') + '">' + (r.vacant ? '〇' : '×') + '</td></tr>';
      });
    }
    h += '</table></div>' + updLine(data);
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
