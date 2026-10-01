'use strict';
// Guided tour: spotlight one element at a time. Never places a call or hits the API.
(function () {
  var KEY = 'voice.onboarded.v1';
  var STEPS = [
    { target: 'call', nl: ['De gespreksknop', 'Druk hier om een gesprek te starten. De microfoon gaat pas aan als u dat doet; deze rondleiding start niets.'], en: ['The call button', 'Press it to start a call. The microphone only turns on when you do; this tour starts nothing.'] },
    { target: 'transcript', nl: ['Het gespreksverslag', 'Wat u zegt en wat de assistent antwoordt, regel voor regel zoals in een gespreksoverzicht.'], en: ['The call log', 'What you say and what the assistant answers, line by line like a call record.'] },
    { target: 'insights', nl: ['Live inzicht', 'Het onderwerp, de stemming, het vertrouwen en het aantal beurten. Open het sentimentverloop voor de grafiek.'], en: ['Live insight', 'The issue, mood, confidence and turn count. Open the sentiment trend for the chart.'] },
    { target: 'personas', nl: ['Kies een medewerker', 'Sarah, Alex en Nina hebben elk een eigen stem en stijl. Kies er een voor het gesprek.'], en: ['Pick an agent', 'Sarah, Alex and Nina each have their own voice and style. Choose one for the call.'] },
    { target: 'handsfree', nl: ['Handsfree', 'Zodra het gesprek loopt luistert de assistent continu mee. U hoeft niet steeds te drukken; stoppen kan met dezelfde knop.'], en: ['Hands-free', 'Once the call is running the assistant keeps listening. You do not have to press each time; stop with the same button.'] }
  ];

  function lang() { try { return (typeof state !== 'undefined' && state.language === 'en') ? 'en' : 'nl'; } catch (e) { return 'nl'; } }
  function seen() { try { return localStorage.getItem(KEY) === 'yes'; } catch (e) { return false; } }
  function mark() { try { localStorage.setItem(KEY, 'yes'); } catch (e) { /* ignore */ } }
  function visible(el) { if (!el) return false; var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
  function find(t) { return t ? document.querySelector('[data-tour="' + t + '"]') : null; }

  var layer = null, steps = [], idx = 0, prevFocus = null;

  function close() {
    if (!layer) return;
    mark();
    layer.remove();
    layer = null;
    window.removeEventListener('resize', place);
    document.removeEventListener('scroll', place, true);
    document.removeEventListener('keydown', onKey, true);
    if (prevFocus && prevFocus.focus) { try { prevFocus.focus(); } catch (e) { /* ignore */ } }
  }

  function onKey(e) {
    if (!layer) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); go(1); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); return; }
    if (e.key === ' ') { e.stopPropagation(); return; }
    if (e.key === 'Tab') {
      var f = layer.querySelectorAll('button:not([hidden])');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  function go(d) {
    var n = idx + d;
    if (n < 0) return;
    if (n >= steps.length) { close(); return; }
    idx = n;
    render();
  }

  function render() {
    var s = steps[idx], el = find(s.target), l = lang(), txt = s[l];
    el.scrollIntoView({ block: 'center' });
    layer.querySelector('.tour-count').textContent = (idx + 1) + ' / ' + steps.length;
    layer.querySelector('.tour-title').textContent = txt[0];
    layer.querySelector('.tour-body').textContent = txt[1];
    layer.querySelector('.tour-back').hidden = idx === 0;
    layer.querySelector('.tour-skip').hidden = idx === steps.length - 1;
    layer.querySelector('.tour-next').textContent = idx === steps.length - 1 ? (l === 'en' ? 'Got it' : 'Begrepen') : (l === 'en' ? 'Next' : 'Volgende');
    layer.querySelector('.tour-back').textContent = l === 'en' ? 'Back' : 'Terug';
    layer.querySelector('.tour-skip').textContent = l === 'en' ? 'Skip the tour' : 'Overslaan';
    place();
    setTimeout(place, 120);
    layer.querySelector('.tour-next').focus();
  }

  function place() {
    if (!layer) return;
    var s = steps[idx], el = find(s.target);
    if (!el) return;
    var r = el.getBoundingClientRect(), pad = 6;
    var spot = layer.querySelector('.tour-spot'), card = layer.querySelector('.tour-card');
    spot.style.top = (r.top - pad) + 'px';
    spot.style.left = (r.left - pad) + 'px';
    spot.style.width = (r.width + pad * 2) + 'px';
    spot.style.height = (r.height + pad * 2) + 'px';
    var vw = window.innerWidth, vh = window.innerHeight;
    if (vw <= 520) {
      card.classList.add('sheet');
      card.style.top = '';
      card.style.left = '';
      return;
    }
    card.classList.remove('sheet');
    var cw = card.offsetWidth, ch = card.offsetHeight;
    var top = r.bottom + 14;
    if (top + ch > vh - 12) top = Math.max(12, r.top - ch - 14);
    var left = Math.min(Math.max(12, r.left + r.width / 2 - cw / 2), vw - cw - 12);
    card.style.top = top + 'px';
    card.style.left = left + 'px';
  }

  function start() {
    if (layer) return;
    steps = STEPS.filter(function (s) { return visible(find(s.target)); });
    if (!steps.length) return;
    idx = 0;
    prevFocus = document.activeElement;
    layer = document.createElement('div');
    layer.className = 'tour-layer';
    layer.setAttribute('role', 'dialog');
    layer.setAttribute('aria-modal', 'true');
    layer.innerHTML = '<div class="tour-spot"></div><div class="tour-card"><div class="tour-count"></div><h2 class="tour-title"></h2><p class="tour-body"></p><div class="tour-actions"><button type="button" class="tour-skip"></button><span class="tour-gap"></span><button type="button" class="tour-back"></button><button type="button" class="tour-next"></button></div></div>';
    document.body.appendChild(layer);
    layer.querySelector('.tour-skip').addEventListener('click', close);
    layer.querySelector('.tour-back').addEventListener('click', function () { go(-1); });
    layer.querySelector('.tour-next').addEventListener('click', function () { go(1); });
    window.addEventListener('resize', place);
    document.addEventListener('scroll', place, true);
    document.addEventListener('keydown', onKey, true);
    render();
  }

  window.startTour = start;
  document.addEventListener('DOMContentLoaded', function () {
    var b = document.getElementById('tourBtn');
    if (b) b.addEventListener('click', function () {
      var m = document.getElementById('menuPanel');
      if (m) m.hidden = true;
      start();
    });
    if (!seen()) {
      var tries = 0;
      var t = setInterval(function () {
        tries++;
        if (!document.getElementById('loadOverlay') && visible(find('call'))) { clearInterval(t); start(); }
        else if (tries > 60) clearInterval(t);
      }, 250);
    }
  });
})();
