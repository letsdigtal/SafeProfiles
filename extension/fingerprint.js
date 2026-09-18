/* SafeProfiles Fingerprint Consistency (open source).
 * Runs in the page's MAIN world before page scripts. Goal: make every signal
 * of THIS profile stable + mutually consistent (same canvas seed, same GPU,
 * same timezone as the proxy geo). It does NOT promise invisibility - no
 * software can. Everything is wrapped in try/catch so pages never break.
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

    // ---- timezone consistency (match your proxy country!) ----
    if (CFG.timezone) {
      const TZ = CFG.timezone;
      try {
        const OrigDTF = Intl.DateTimeFormat;
        const fmtForOffset = new OrigDTF('en-US', { timeZone: TZ, hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const utcFmt = new OrigDTF('en-US', { timeZone: 'UTC', hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
        function tzOffsetMinutes(date) {
          try {
            const tz = new Date(fmtForOffset.format(date));
            const utc = new Date(utcFmt.format(date));
            return Math.round((utc - tz) / 60000);
          } catch (e) { return date.getTimezoneOffset(); }
        }
        const origRO = OrigDTF.prototype.resolvedOptions;
        OrigDTF.prototype.resolvedOptions = native(function () {
          const o = origRO.apply(this, arguments);
          try { o.timeZone = TZ; } catch (e) {}
          return o;
        }, 'resolvedOptions');
        const origGTO = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = native(function () { return tzOffsetMinutes(this); }, 'getTimezoneOffset');
      } catch (e) {}
    }

    // ---- webdriver flag: hidden (we launch a normal, user-driven browser) ----
    try {
      def(Navigator.prototype, 'webdriver', () => false, 'get webdriver');
    } catch (e) {}
  } catch (e) { /* never break the page */ }
})();
