/* SamskritaDhvani — shared frontend logic (Phase 4 wiring).
 *
 * Layered onto the static Stitch exports. Ground Rule 1 in the UI:
 * every number or result shown comes from a live API response or a
 * user action; any backend failure renders as an explicit error state.
 * No placeholder score is ever displayed as if it were real.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------- helpers

  function el(id) {
    return document.getElementById(id);
  }

  function setText(node, text) {
    if (node) node.textContent = text;
  }

  function setHTML(node, html) {
    if (node) node.innerHTML = html;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmtPct(x, digits) {
    return Number(x).toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function fmtClock(sec) {
    // 00:18.4 — the clock format the GVR screen already styles for
    var m = Math.floor(sec / 60);
    var s = sec - m * 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s.toFixed(1);
  }

  function isoDate(s) {
    try {
      return new Date(s).toISOString().slice(0, 10);
    } catch (e) {
      return String(s);
    }
  }

  // ---------------------------------------------------- API access

  /* fetch JSON; non-2xx and network failures become Error objects with
   * .kind ('network' | error-code from the body | 'http_error'),
   * .status, and the API's structured detail message. The UI renders
   * .kind/.message explicitly — it never falls back to fake data. */
  async function fetchJSON(url, opts) {
    var res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      var net = new Error(
        'Network error: could not reach ' + url + ' — is the API server running?'
      );
      net.kind = 'network';
      throw net;
    }
    var body = null;
    try {
      body = await res.json();
    } catch (e) {
      /* non-JSON response body */
    }
    if (!res.ok) {
      var d = (body && body.detail) || {};
      var err = new Error(d.detail || (body && body.detail) || res.statusText || 'HTTP ' + res.status);
      err.kind = d.error || 'http_error';
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  async function getWords() {
    return fetchJSON('/api/words');
  }

  async function getStatus() {
    return fetchJSON('/api/status');
  }

  async function submitSPD(wavBlob, wordId) {
    var fd = new FormData();
    fd.append('word_id', wordId);
    fd.append('audio', wavBlob, 'attempt.wav');
    return fetchJSON('/api/spd/score', { method: 'POST', body: fd });
  }

  async function submitGVR(wavBlob) {
    var fd = new FormData();
    fd.append('audio', wavBlob, 'recitation.wav');
    return fetchJSON('/api/gvr/recognize', { method: 'POST', body: fd });
  }

  // ------------------------------------------------------- recorder

  /* MediaRecorder wrapper. Browsers record webm/opus (or mp4/aac); the
   * backend's soundfile decoder cannot read those containers, so stop()
   * hands the raw blob to toWav16k() before upload. */
  function Recorder() {
    this.stream = null;
    this.rec = null;
    this.chunks = [];
    this.blob = null;
    this.mime = '';
    this._timer = null;
    this._t0 = 0;
    this._raf = 0;
    this.onLevel = null; // optional callback(peak 0..1) for live meters
  }

  Recorder.prototype.start = async function (maxSeconds) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      var e = new Error(
        'This browser does not support microphone capture (getUserMedia). ' +
          'Use desktop Chrome or Firefox, or the upload fallback.'
      );
      e.kind = 'mic';
      throw e;
    }
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.chunks = [];
    var mimes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
    this.mime = '';
    if (window.MediaRecorder && MediaRecorder.isTypeSupported) {
      for (var i = 0; i < mimes.length; i++) {
        if (MediaRecorder.isTypeSupported(mimes[i])) {
          this.mime = mimes[i];
          break;
        }
      }
    }
    if (!window.MediaRecorder) {
      var e2 = new Error('This browser does not support MediaRecorder. Use the upload fallback.');
      e2.kind = 'mic';
      throw e2;
    }
    this.rec = new MediaRecorder(this.stream, this.mime ? { mimeType: this.mime } : undefined);
    var self = this;
    this.rec.ondataavailable = function (ev) {
      if (ev.data && ev.data.size) self.chunks.push(ev.data);
    };
    this.rec.start(250);
    this._t0 = performance.now();

    // Optional live level meter (drives the GVR waveform bar).
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      var ac = new AC();
      var an = ac.createAnalyser();
      an.fftSize = 1024;
      ac.createMediaStreamSource(this.stream).connect(an);
      var buf = new Float32Array(an.fftSize);
      var tick = function () {
        if (!self.rec || self.rec.state !== 'recording') {
          ac.close();
          return;
        }
        an.getFloatTimeDomainData(buf);
        var peak = 0;
        for (var j = 0; j < buf.length; j++) peak = Math.max(peak, Math.abs(buf[j]));
        if (self.onLevel) self.onLevel(peak);
        self._raf = requestAnimationFrame(tick);
      };
      tick();
    } catch (e3) {
      /* level meter is optional; recording continues without it */
    }

    clearTimeout(this._timer);
    this._timer = setTimeout(function () {
      if (self.rec && self.rec.state === 'recording') self.stop();
    }, (maxSeconds || 60) * 1000);
  };

  Recorder.prototype.stop = async function () {
    clearTimeout(this._timer);
    cancelAnimationFrame(this._raf);
    if (!this.rec) return null;
    var self = this;
    if (this.rec.state !== 'inactive') {
      await new Promise(function (r) {
        self.rec.onstop = r;
        self.rec.stop();
      });
    }
    for (var i = 0; i < this.stream.getTracks().length; i++) {
      this.stream.getTracks()[i].stop();
    }
    this.blob = new Blob(this.chunks, { type: this.mime || 'audio/webm' });
    this.rec = null;
    return this.blob;
  };

  Object.defineProperty(Recorder.prototype, 'recording', {
    get: function () {
      return !!(this.rec && this.rec.state === 'recording');
    },
  });

  Object.defineProperty(Recorder.prototype, 'elapsed', {
    get: function () {
      return this._t0 ? (performance.now() - this._t0) / 1000 : 0;
    },
  });

  // ---------------------------------------------- 16 kHz WAV encode

  /* Decode any browser-playable audio blob, then render it through an
   * OfflineAudioContext at 16 kHz mono and emit a 16-bit PCM WAV blob
   * the backend's soundfile decoder accepts. */
  async function toWav16k(blob) {
    var AC = window.AudioContext || window.webkitAudioContext;
    var ac = new AC();
    var buf;
    try {
      buf = await ac.decodeAudioData(await blob.arrayBuffer());
    } catch (e) {
      await ac.close();
      var d = new Error(
        'Could not decode this audio in the browser. If you uploaded a file, try .wav or .flac.'
      );
      d.kind = 'decode';
      throw d;
    }
    var target = Math.max(1, Math.ceil(buf.duration * 16000));
    var off = new OfflineAudioContext(1, target, 16000);
    var src = off.createBufferSource();
    src.buffer = buf;
    src.connect(off.destination);
    src.start();
    var rendered = await off.startRendering();
    await ac.close();

    var ch = rendered.getChannelData(0);
    var n = ch.length;
    var out = new ArrayBuffer(44 + n * 2);
    var v = new DataView(out);
    function wstr(o, s) {
      for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
    }
    wstr(0, 'RIFF');
    v.setUint32(4, 36 + n * 2, true);
    wstr(8, 'WAVE');
    wstr(12, 'fmt ');
    v.setUint32(16, 16, true); // PCM
    v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); // mono
    v.setUint32(24, 16000, true);
    v.setUint32(28, 32000, true); // byte rate
    v.setUint16(32, 2, true);
    v.setUint16(34, 16, true);
    wstr(36, 'data');
    v.setUint32(40, n * 2, true);
    var o2 = 44;
    for (var k = 0; k < n; k++, o2 += 2) {
      var s2 = Math.max(-1, Math.min(1, ch[k]));
      v.setInt16(o2, s2 < 0 ? s2 * 0x8000 : s2 * 0x7fff, true);
    }
    return new Blob([out], { type: 'audio/wav' });
  }

  // ------------------------------------------------------ navigation

  /* Stitch's exports carry placeholder nav items (corpus-reader,
   * spectrogram-workbench, ...) that have no corresponding screens.
   * Replace them with the four real routes and mark the active page. */
  function wireNav() {
    var nav = document.querySelector('header nav');
    if (!nav) return;
    var pages = [
      ['/', 'Home'],
      ['/spd.html', 'SPD Practice'],
      ['/gvr.html', 'Verse Recognition'],
      ['/status.html', 'Corpus & Model Status'],
    ];
    var here = location.pathname.replace(/\/+$/, '') || '/';
    nav.innerHTML = pages
      .map(function (p) {
        var href = p[0],
          label = p[1];
        var active = here === href;
        var cls = active
          ? 'px-space-md py-space-sm transition-colors bg-primary-container text-on-primary font-medium rounded'
          : 'px-space-md py-space-sm text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors rounded';
        return (
          '<a class="' + cls + '" ' + (active ? 'aria-current="page" ' : '') + 'href="' + href + '">' +
          label +
          '</a>'
        );
      })
      .join('');
  }

  window.SD = {
    el: el,
    setText: setText,
    setHTML: setHTML,
    esc: esc,
    fmtPct: fmtPct,
    fmtClock: fmtClock,
    isoDate: isoDate,
    fetchJSON: fetchJSON,
    getWords: getWords,
    getStatus: getStatus,
    submitSPD: submitSPD,
    submitGVR: submitGVR,
    Recorder: Recorder,
    toWav16k: toWav16k,
    wireNav: wireNav,
  };
})();
