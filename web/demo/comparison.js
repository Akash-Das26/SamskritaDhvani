/* SamskritaDhvani — DEMO overlay (branch `demo`).
 *
 * Adds two things to the existing SPD screen, without changing the
 * Stitch layout it is layered onto:
 *
 *   1. the reference-vs-attempt comparison strip deferred in
 *      Frontend.md §6.1 — one canvas, two waveform lanes, a play
 *      button per lane;
 *   2. a persistent DEMO banner, because every score shown here is
 *      scored against synthetic, non-ear-verified references and a
 *      provisional calibration. The banner is not dismissible.
 *
 * Everything is drawn from live data: the reference clip is fetched
 * from /api/reference-audio/<word>.wav, the attempt is the exact
 * 16 kHz WAV blob the page is about to submit. No placeholder
 * waveform, no invented duration.
 */
(function () {
  'use strict';

  var BANNER_TEXT =
    'DEMO — references not ear-verified, calibration provisional; not a result.';

  var words = [];
  var wordByDeva = {};
  var currentWord = null;

  var refBuffer = null;
  var refUrl = null;
  var refAudio = null;
  var refToken = 0;          // bumped per load; stale responses are dropped

  var attemptBlob = null;
  var attemptUrl = null;
  var attemptBuffer = null;
  var attemptAudio = null;

  var active = null;          // 'ref' | 'attempt' | null
  var progress = 0;           // 0..1 of the active lane
  var raf = 0;

  var canvas, ctx, els = {};
  var LANE = { ref: null, att: null };

  var AC = window.AudioContext || window.webkitAudioContext;

  // -------------------------------------------------------------- helpers

  function el(id) { return document.getElementById(id); }

  function fmt(s) {
    if (!isFinite(s) || s <= 0) return '—';
    return s.toFixed(2) + ' s';
  }

  // --------------------------------------------------------------- banner

  function injectBanner() {
    if (el('demoBanner')) return;
    var bar = document.createElement('div');
    bar.id = 'demoBanner';
    bar.setAttribute('role', 'status');
    bar.className =
      'fixed bottom-0 left-0 right-0 z-50 bg-tertiary-container text-on-tertiary ' +
      'font-code text-code px-gutter py-space-xs text-center';
    bar.textContent = BANNER_TEXT;
    document.body.appendChild(bar);
    document.body.style.paddingBottom = '32px';
  }

  // ---------------------------------------------------------------- strip

  function injectStrip() {
    if (el('demoComparison')) return;
    var anchor = document.getElementById('waveformContainer');
    var section = anchor ? anchor.closest('section') : null;
    if (!section) return;

    /* Inside the recording card, directly under the capture controls, so
     * the graph is in view with the microphone. Appending to the card's
     * inner surface keeps the Stitch layout and only adds the strip. */
    var host = section.querySelector('.bg-surface-container-lowest') || section;

    var wrap = document.createElement('div');
    wrap.id = 'demoComparison';
    wrap.className =
      'flex flex-col gap-space-sm pt-space-md border-t border-outline-variant/50';
    wrap.innerHTML =
      '<div class="flex flex-col sm:flex-row sm:items-center justify-between ' +
      'gap-space-xs">' +
        '<div class="flex items-center gap-space-sm">' +
          '<span class="font-label-lg text-label-lg uppercase tracking-wider ' +
          'text-on-surface font-semibold">Reference vs attempt</span>' +
          '<span class="px-2 py-0.5 bg-surface-container rounded font-code ' +
          'text-code text-on-surface-variant">demo graph</span>' +
        '</div>' +
        '<span class="font-code text-[10px] text-on-surface-variant">' +
          'shaded band = active span (browser estimate)</span>' +
      '</div>' +
      '<div class="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">' +
        '<div class="flex items-center justify-between bg-surface-container-low ' +
        'rounded px-space-sm py-space-xs">' +
          '<div class="flex flex-col">' +
            '<span class="font-label-sm text-label-sm uppercase tracking-wider ' +
            'text-on-surface-variant">Reference recitation</span>' +
            '<span class="font-code text-code text-on-surface" id="demoRefMeta">' +
            'select a word</span>' +
          '</div>' +
          '<button id="demoPlayRef" class="flex items-center gap-1 px-space-sm py-1 ' +
          'rounded bg-surface-container text-on-surface-variant whitespace-nowrap ' +
          'font-label-sm text-label-sm transition-colors" disabled>' +
            '<span class="material-symbols-outlined text-[16px]">play_arrow</span>' +
            '<span id="demoPlayRefLabel">Play reference</span></button>' +
        '</div>' +
        '<div class="flex items-center justify-between bg-surface-container-low ' +
        'rounded px-space-sm py-space-xs">' +
          '<div class="flex flex-col">' +
            '<span class="font-label-sm text-label-sm uppercase tracking-wider ' +
            'text-on-surface-variant">Your attempt</span>' +
            '<span class="font-code text-code text-on-surface" id="demoAttMeta">' +
            'no attempt yet</span>' +
          '</div>' +
          '<button id="demoPlayAtt" class="flex items-center gap-1 px-space-sm py-1 ' +
          'rounded bg-surface-container text-on-surface-variant whitespace-nowrap ' +
          'font-label-sm text-label-sm transition-colors" disabled>' +
            '<span class="material-symbols-outlined text-[16px]">play_arrow</span>' +
            '<span id="demoPlayAttLabel">Play attempt</span></button>' +
        '</div>' +
      '</div>' +
      '<div class="bg-surface-container-low rounded p-space-sm">' +
        '<canvas id="demoCompareCanvas" class="w-full block" height="132" ' +
        'aria-label="Reference and attempt waveforms"></canvas>' +
        '<div class="flex justify-between font-code text-[10px] ' +
        'text-on-surface-variant/70 pt-1">' +
          '<span>reference lane · top</span><span>attempt lane · bottom</span>' +
        '</div>' +
      '</div>';

    host.appendChild(wrap);

    canvas = el('demoCompareCanvas');
    ctx = canvas.getContext('2d');
    els.refMeta = el('demoRefMeta');
    els.attMeta = el('demoAttMeta');
    els.playRef = el('demoPlayRef');
    els.playAtt = el('demoPlayAtt');
    els.playRefLabel = el('demoPlayRefLabel');
    els.playAttLabel = el('demoPlayAttLabel');

    els.playRef.addEventListener('click', function () { toggle('ref'); });
    els.playAtt.addEventListener('click', function () { toggle('attempt'); });
    window.addEventListener('resize', draw);
    draw();
  }

  // --------------------------------------------------------------- canvas

  function peaks(buffer, n) {
    var ch = buffer.getChannelData(0);
    var step = Math.max(1, Math.floor(ch.length / n));
    var out = [];
    for (var i = 0; i < n; i++) {
      var lo = 1, hi = -1;
      var end = Math.min(ch.length, (i + 1) * step);
      for (var j = i * step; j < end; j++) {
        var v = ch[j];
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
      out.push(lo > hi ? [0, 0] : [lo, hi]);
    }
    return out;
  }

  /* The span of each clip that actually carries sound, found from the
   * envelope at 8 % of the clip's own peak. This is a browser-side visual
   * aid only — the server's VAD gate is what decides what is scored. */
  function activeSpan(buffer) {
    var ch = buffer.getChannelData(0);
    var bins = 300;
    var step = Math.max(1, Math.floor(ch.length / bins));
    var env = [];
    var max = 0;
    for (var i = 0; i < bins; i++) {
      var peak = 0;
      for (var j = i * step; j < Math.min(ch.length, (i + 1) * step); j++) {
        var v = Math.abs(ch[j]);
        if (v > peak) peak = v;
      }
      env.push(peak);
      if (peak > max) max = peak;
    }
    if (!(max > 0)) return null;
    var threshold = 0.08 * max;
    var first = -1, last = -1;
    for (var k = 0; k < env.length; k++) {
      if (env[k] > threshold) {
        if (first < 0) first = k;
        last = k;
      }
    }
    if (first < 0) return null;
    return [first / bins, (last + 1) / bins];
  }

  function drawLane(buffer, rect, color, emptyLabel) {
    var mid = rect.y + rect.h / 2;
    ctx.strokeStyle = 'rgba(138,114,108,0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(rect.x, mid + 0.5);
    ctx.lineTo(rect.x + rect.w, mid + 0.5);
    ctx.stroke();

    if (!buffer) {
      ctx.fillStyle = '#8a726c';
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.fillText(emptyLabel, rect.x + 6, mid + 4);
      return;
    }

    var span = activeSpan(buffer);
    if (span) {
      ctx.fillStyle = 'rgba(93,63,0,0.12)';
      ctx.fillRect(rect.x + 6 + span[0] * (rect.w - 12), rect.y + 2,
                   Math.max(1, (span[1] - span[0]) * (rect.w - 12)),
                   rect.h - 4);
    }

    var n = Math.max(24, Math.floor(rect.w - 12));
    var p = peaks(buffer, n);
    var bw = (rect.w - 12) / p.length;
    var half = (rect.h - 10) / 2;
    ctx.fillStyle = color;
    for (var i = 0; i < p.length; i++) {
      var lo = Math.max(-1, p[i][0]);
      var hi = Math.min(1, p[i][1]);
      var y0 = mid - hi * half;
      var y1 = mid - lo * half;
      ctx.fillRect(rect.x + 6 + i * bw, y0, Math.max(1, bw * 0.75),
                   Math.max(1, y1 - y0));
    }
  }

  function draw() {
    if (!canvas) return;
    var cssW = canvas.clientWidth || 600;
    var cssH = 132;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    var gap = 14;
    var laneH = (cssH - gap) / 2;
    LANE.ref = { x: 0, y: 0, w: cssW, h: laneH };
    LANE.att = { x: 0, y: laneH + gap, w: cssW, h: laneH };

    drawLane(refBuffer, LANE.ref, 'rgba(126,38,15,0.75)',
             currentWord && currentWord.reference_audio_url
               ? 'loading reference…'
               : 'no demo reference for this word');
    drawLane(attemptBuffer, LANE.att, 'rgba(161,63,42,0.75)',
             'record or upload an attempt');

    if (active && LANE[active === 'ref' ? 'ref' : 'att']) {
      var r = LANE[active === 'ref' ? 'ref' : 'att'];
      var x = r.x + progress * r.w;
      ctx.strokeStyle = '#5d3f00';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, r.y + 2);
      ctx.lineTo(x, r.y + r.h - 2);
      ctx.stroke();
    }
  }

  // ------------------------------------------------------------ playback

  function stopActive() {
    if (active === 'ref' && refAudio) refAudio.pause();
    if (active === 'attempt' && attemptAudio) attemptAudio.pause();
    active = null;
    progress = 0;
    cancelAnimationFrame(raf);
    updatePlayLabels();
    draw();
  }

  function tick() {
    var a = active === 'ref' ? refAudio : attemptAudio;
    if (!a || a.paused) { active = null; progress = 0; updatePlayLabels(); draw(); return; }
    progress = a.duration ? Math.min(1, a.currentTime / a.duration) : 0;
    draw();
    raf = requestAnimationFrame(tick);
  }

  function toggle(which) {
    var isSame = active === which;
    stopActive();
    if (isSame) return;
    var a = which === 'ref' ? refAudio : attemptAudio;
    if (!a) return;
    try { a.currentTime = 0; } catch (e) { /* not seekable yet */ }
    a.play().then(function () {
      active = which;
      progress = 0;
      updatePlayLabels();
      tick();
    }).catch(function () {
      active = null;
      updatePlayLabels();
    });
  }

  function updatePlayLabels() {
    if (!els.playRef) return;
    var refReady = !!refAudio;
    var attReady = !!attemptAudio;
    els.playRef.disabled = !refReady;
    els.playAtt.disabled = !attReady;
    els.playRef.classList.toggle('opacity-50', !refReady);
    els.playAtt.classList.toggle('opacity-50', !attReady);
    els.playRefLabel.textContent = active === 'ref' ? 'Stop' : 'Play reference';
    els.playAttLabel.textContent = active === 'attempt' ? 'Stop' : 'Play attempt';
  }

  function makeAudio(url, which, duration) {
    var a = new Audio(url);
    a.preload = 'auto';
    a.addEventListener('ended', function () {
      if (active === which) { active = null; progress = 0; updatePlayLabels(); draw(); }
    });
    if (duration) a._expected = duration;
    return a;
  }

  // ------------------------------------------------------- reference clip

  function showRefMeta(text, available) {
    if (!els.refMeta) return;
    els.refMeta.textContent = text;
    els.refMeta.classList.toggle('text-on-surface-variant', !available);
  }

  function loadReference(word) {
    var token = ++refToken;          // any in-flight load is now stale
    if (refUrl) URL.revokeObjectURL(refUrl);
    refBuffer = null;
    refUrl = null;
    refAudio = null;
    if (active === 'ref') stopActive();
    updatePlayLabels();

    if (!word || !word.reference_audio_url) {
      showRefMeta(word ? 'no demo reference (covers kRSNa, yoga, zAnti)' : 'select a word',
                  false);
      draw();
      return;
    }

    showRefMeta('loading…', false);
    draw();

    fetch(word.reference_audio_url)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.arrayBuffer();
      })
      .then(function (ab) {
        if (token !== refToken) return null;     // word changed mid-flight
        var ac = new AC();
        return ac.decodeAudioData(ab.slice(0)).then(function (buf) {
          ac.close();
          return { buf: buf, ab: ab };
        });
      })
      .then(function (res) {
        if (!res || token !== refToken) return;
        refBuffer = res.buf;
        refUrl = URL.createObjectURL(new Blob([res.ab], { type: 'audio/wav' }));
        refAudio = makeAudio(refUrl, 'ref', res.buf.duration);
        showRefMeta(fmt(res.buf.duration) + ' · synthetic TTS (demo)', true);
        updatePlayLabels();
        draw();
      })
      .catch(function (e) {
        if (token !== refToken) return;
        showRefMeta('reference unavailable (' + e.message + ')', false);
        draw();
      });
  }

  // --------------------------------------------------------------- attempt

  function setAttempt(blob) {
    if (!blob || !blob.size) return;
    attemptBlob = blob;
    if (attemptUrl) URL.revokeObjectURL(attemptUrl);
    attemptUrl = URL.createObjectURL(blob);
    if (attemptAudio) { attemptAudio.pause(); attemptAudio = null; }
    if (active === 'attempt') stopActive();

    var ac = new AC();
    blob.arrayBuffer().then(function (ab) {
      return ac.decodeAudioData(ab);
    }).then(function (buf) {
      ac.close();
      attemptBuffer = buf;
      attemptAudio = makeAudio(attemptUrl, 'attempt', buf.duration);
      els.attMeta.textContent = fmt(buf.duration) + ' · 16 kHz mono';
      updatePlayLabels();
      draw();
    }).catch(function () {
      ac.close();
      attemptBuffer = null;
      els.attMeta.textContent = 'audio could not be decoded in the browser';
      updatePlayLabels();
      draw();
    });
  }

  // ---------------------------------------------------------------- wiring

  function findWordByDeva(text) {
    return wordByDeva[text] || null;
  }

  function watchWord() {
    var node = document.getElementById('wordDeva');
    if (!node) return;
    var last = null;
    var obs = new MutationObserver(function () {
      var t = (node.textContent || '').trim();
      if (t === last || !t || t === '—') return;
      last = t;
      var w = findWordByDeva(t);
      currentWord = w;
      loadReference(w);
    });
    obs.observe(node, { childList: true, characterData: true, subtree: true });
  }

  function watchAttempt() {
    var orig = window.SD && window.SD.toWav16k;
    if (typeof orig !== 'function') return;
    window.SD.toWav16k = function (blob) {
      return orig.apply(this, arguments).then(function (wav) {
        setAttempt(wav);
        return wav;
      });
    };
  }

  function boot() {
    injectBanner();
    injectStrip();
    watchAttempt();
    watchWord();
    if (!window.SD || typeof SD.getWords !== 'function') return;
    SD.getWords().then(function (data) {
      words = data.words || [];
      wordByDeva = {};
      words.forEach(function (w) { wordByDeva[w.devanagari] = w; });
      var node = document.getElementById('wordDeva');
      var t = node ? (node.textContent || '').trim() : '';
      if (t && t !== '—') {
        currentWord = findWordByDeva(t);
        loadReference(currentWord);
      }
    }).catch(function () { /* the page shows the word-list error itself */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
