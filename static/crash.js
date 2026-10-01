'use strict';
// Shows one friendly screen instead of a half-working page when the app throws.
(function () {
  var shown = false;
  var BENIGN = /ResizeObserver|NotAllowedError|Permission denied|AbortError|NetworkError|Failed to fetch|Load failed|Script error/i;

  function show(detail) {
    if (shown) return;
    shown = true;
    var nl = (document.documentElement.lang || 'nl') !== 'en';
    var wrap = document.createElement('div');
    wrap.className = 'crash';
    wrap.setAttribute('role', 'alert');
    var card = document.createElement('div');
    card.className = 'crash-card';
    var h = document.createElement('h1');
    h.textContent = nl ? 'Er ging iets mis' : 'Something went wrong';
    var p = document.createElement('p');
    p.textContent = nl
      ? 'De pagina is gestopt door een fout. Laad hem opnieuw om verder te gaan.'
      : 'The page hit an error and stopped. Reload it to carry on.';
    var d = document.createElement('p');
    d.className = 'crash-detail';
    d.textContent = String(detail || '').slice(0, 240);
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = nl ? 'Pagina herladen' : 'Reload the page';
    b.addEventListener('click', function () { location.reload(); });
    card.append(h, p, d, b);
    wrap.appendChild(card);
    document.body.appendChild(wrap);
  }

  window.addEventListener('error', function (e) {
    var msg = (e && e.message) || '';
    if (BENIGN.test(msg)) return;
    if (e && e.target && e.target !== window) return;
    show(msg);
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e && e.reason;
    var msg = (r && (r.message || r.name)) || String(r || '');
    if (BENIGN.test(msg) || (r && r.name === 'NotAllowedError')) return;
    show(msg);
  });
})();
