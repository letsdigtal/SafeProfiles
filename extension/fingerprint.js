/* SafeProfiles Fingerprint Consistency (open source).
 * Runs in the page's MAIN world before page scripts. Goal: make every signal
 * of THIS profile stable + mutually consistent (same canvas seed, same GPU,
 * same timezone as the proxy geo). It does NOT promise invisibility - no
 * software can. Everything is wrapped in try/catch so pages never break.
 *
 * v1.3: timezone spoofing hardened - covers Intl.DateTimeFormat (default tz
 * + resolvedOptions), Date.getTimezoneOffset (correct sign + DST), and
 * Date.toString/toLocaleString family, so checker sites no longer see the
 * real timezone behind the proxy.
 */
(function () {
  'use strict';
  const CFG = (typeof window !== 'undefined' && window.__SP_CONFIG__) || {};
  const SEED_STR = String(CFG.seed || 'default');

  function hashSeed(s) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(hashSeed(SEED_STR));
  // Stable per-profile jitter values (same on every page load of this profile)
  const J = Array.from({ length: 64 }, () => rand());
  let ji = 0;
  const jr = () => J[(ji++) % J.length];

  function native(fn, name) {
    try {
      const n = name || fn.name || '';
      const s = 'function ' + n + '() { [native code] }';
      fn.toString = function toString() { return s; };
    } catch (e) { /* ignore */ }
    return fn;
  }
  function def(obj, prop, getter, name) {
    try {
      const g = native(function () { return getter(); }, name || ('get ' + prop));
      Object.defineProperty(obj, prop, { get: g, configurable: true });
    } catch (e) { /* ignore */ }
  }

  try {
    // ---- navigator: cores / memory / platform ----
    if (CFG.cores) {
      const c = CFG.cores;
      def(Navigator.prototype, 'hardwareConcurrency', () => c, 'get hardwareConcurrency');
    }
    if (CFG.memory !== undefined && CFG.memory !== null) {
      const m = CFG.memory;
      try { def(Navigator.prototype, 'deviceMemory', () => m, 'get deviceMemory'); } catch (e) {}
    }
    if (CFG.platform) {
      const p = CFG.platform;
      def(Navigator.prototype, 'platform', () => p, 'get platform');
    }

    // ---- screen consistency ----
    if (CFG.screen && CFG.screen.width) {
      const sc = CFG.screen;
      try {
        def(Screen.prototype, 'width', () => sc.width, 'get width');
        def(Screen.prototype, 'height', () => sc.height, 'get height');
        def(Screen.prototype, 'availWidth', () => sc.width, 'get availWidth');
        def(Screen.prototype, 'availHeight', () => sc.availHeight || sc.height, 'get availHeight');
      } catch (e) { /* some browsers lock Screen */ }
    }

    // ---- canvas: subtle stable noise ----
    try {
      const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
      CanvasRenderingContext2D.prototype.getImageData = native(function (sx, sy, w, h) {
        const img = origGetImageData.apply(this, arguments);
        try {
          const d = img.data;
          for (let i = 0; i < d.length; i += 4) {
            const n = (jr() - 0.5) * 2; // -1..1
            d[i] = Math.max(0, Math.min(255, d[i] + n));
          }
        } catch (e) {}
        return img;
      }, 'getImageData');
      const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = native(function () {
        try {
          const ctx = this.getContext('2d');
          if (ctx) { ctx.getImageData(0, 0, 1, 1); }
        } catch (e) {}
        return origToDataURL.apply(this, arguments);
      }, 'toDataURL');
    } catch (e) {}

    // ---- audio: subtle stable noise ----
    try {
      if (window.AudioBuffer && AudioBuffer.prototype.getChannelData) {
        const origGCD = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = native(function () {
          const data = origGCD.apply(this, arguments);
          try {
            for (let i = 0; i < data.length; i += 97) {
              data[i] = data[i] + (jr() - 0.5) * 0.0000002;
            }
          } catch (e) {}
          return data;
        }, 'getChannelData');
      }
    } catch (e) {}

    // ---- WebGL vendor/renderer spoof ----
    try {
      const VENDOR = 0x9245, RENDERER = 0x9246;
      const origGetParam = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = native(function (p) {
        if (p === VENDOR && CFG.gpuVendor) return CFG.gpuVendor;
        if (p === RENDERER && CFG.gpuRenderer) return CFG.gpuRenderer;
        return origGetParam.apply(this, arguments);
      }, 'getParameter');
      if (window.WebGL2RenderingContext) {
        const orig2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = native(function (p) {
          if (p === VENDOR && CFG.gpuVendor) return CFG.gpuVendor;
          if (p === RENDERER && CFG.gpuRenderer) return CFG.gpuRenderer;
          return orig2.apply(this, arguments);
        }, 'getParameter');
      }
    } catch (e) {}

    // ---- timezone spoofing (match your proxy country!) ----
    if (CFG.timezone) {
      const TZ = CFG.timezone;
      try {
        const OrigDTF = Intl.DateTimeFormat;

        // wall-clock time of a Date inside TZ (handles DST automatically)
        const partsFmt = new OrigDTF('en-US', { timeZone: TZ, hour12: false,
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit' });
        function wall(date) {
          const p = {};
          partsFmt.formatToParts(date).forEach(x => { p[x.type] = x.value; });
          return { y: +p.year, mo: (+p.month) - 1, d: +p.day,
                   h: (+p.hour) % 24, mi: +p.minute, s: +p.second };
        }
        // Real JS semantics: minutes between UTC and local (UTC - local).
        // Karachi (UTC+5) -> -300, New York winter (UTC-5) -> +300.
        function tzOffsetMinutes(date) {
          try {
            const w = wall(date);
            const asUTC = Date.UTC(w.y, w.mo, w.d, w.h, w.mi, w.s);
            return Math.round((date.getTime() - asUTC) / 60000);
          } catch (e) { return 0; }
        }

        // 1) Date.prototype.getTimezoneOffset
        Date.prototype.getTimezoneOffset = native(
          function () { return tzOffsetMinutes(this); }, 'getTimezoneOffset');

        // 2) Intl.DateTimeFormat: default to TZ when the page didn't ask
        function PatchedDTF(locales, options) {
          let o = options;
          try {
            o = Object.assign({}, options);
            if (!o.timeZone) o.timeZone = TZ;
          } catch (e) { /* keep original */ }
          return new OrigDTF(locales, o);
        }
        try { PatchedDTF.prototype = OrigDTF.prototype; } catch (e) {}
        try { PatchedDTF.supportedLocalesOf = function () {
          return OrigDTF.supportedLocalesOf.apply(OrigDTF, arguments); }; } catch (e) {}
        Intl.DateTimeFormat = PatchedDTF;

        // 3) resolvedOptions().timeZone
        const origRO = OrigDTF.prototype.resolvedOptions;
        OrigDTF.prototype.resolvedOptions = native(function () {
          const o = origRO.apply(this, arguments);
          try { if (o.timeZone) o.timeZone = TZ; } catch (e) {}
          return o;
        }, 'resolvedOptions');

        // 4) Date string methods (what checker sites display)
        const abbrFmt = new OrigDTF('en-US', { timeZone: TZ, timeZoneName: 'short' });
        function tzAbbr(date) {
          try {
            const part = abbrFmt.formatToParts(date)
              .find(p => p.type === 'timeZoneName');
            return part ? part.value : '';
          } catch (e) { return ''; }
        }
        function fmt(date) {
          try {
            const w = wall(date);
            const p2 = n => String(n).padStart(2, '0');
            const wd = new OrigDTF('en-US', { timeZone: TZ, weekday: 'short' }).format(date);
            const mon = new OrigDTF('en-US', { timeZone: TZ, month: 'short' }).format(date);
            return { w, p2, wd, mon };
          } catch (e) { return null; }
        }
        const origToString = Date.prototype.toString;
        Date.prototype.toString = native(function () {
          const f = fmt(this);
          if (!f) return origToString.call(this);
          return f.wd + ' ' + f.mon + ' ' + f.p2(f.w.d) + ' ' + f.p2(f.w.h) + ':' +
                 f.p2(f.w.mi) + ':' + f.p2(f.w.s) + ' ' + tzAbbr(this) + ' ' + f.w.y;
        }, 'toString');
        const origTTS = Date.prototype.toTimeString;
        Date.prototype.toTimeString = native(function () {
          const f = fmt(this);
          if (!f) return origTTS.call(this);
          return f.p2(f.w.h) + ':' + f.p2(f.w.mi) + ':' + f.p2(f.w.s) + ' ' + tzAbbr(this);
        }, 'toTimeString');
        Date.prototype.toLocaleString = native(function (l, o) {
          try { o = Object.assign({}, o); if (!o.timeZone) o.timeZone = TZ; } catch (e) {}
          return new OrigDTF(l, o).format(this);
        }, 'toLocaleString');
        Date.prototype.toLocaleDateString = native(function (l, o) {
          try { o = Object.assign({}, o); if (!o.timeZone) o.timeZone = TZ; } catch (e) {}
          return new OrigDTF(l, o).format(this);
        }, 'toLocaleDateString');
        Date.prototype.toLocaleTimeString = native(function (l, o) {
          try { o = Object.assign({}, o); if (!o.timeZone) o.timeZone = TZ; } catch (e) {}
          return new OrigDTF(l, o).format(this);
        }, 'toLocaleTimeString');
      } catch (e) {}
    }

    // ---- webdriver flag: hidden (we launch a normal, user-driven browser) ----
    try {
      def(Navigator.prototype, 'webdriver', () => false, 'get webdriver');
    } catch (e) {}
  } catch (e) { /* never break the page */ }
})();
