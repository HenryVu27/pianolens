/* PianoLens S-03 listening study: trial design (pure functions, no DOM).
 *
 * Works in the browser (window.S03Design) and in Node (module.exports) so the trial
 * builder can be tested headlessly: `node study/app/test_design.mjs`.
 *
 * Design (study/protocol-S03.md, section 4):
 *  Part A, detection: reference (original) then A and B; one of A/B is the original, the
 *    other is degraded; "Which one differs from the reference?". Constant stimuli: every
 *    level of every dimension, `detReps` times, excerpts rotated within each dimension.
 *  Part B, preference: original vs degraded, "Which do you prefer?", every level,
 *    `prefReps` times; plus `prefIdentical` original-vs-original pairs (position bias).
 *  Position of the degraded clip is balanced within each dimension (half first, half
 *  second) and randomised; trial order is shuffled per listener with a seeded PRNG;
 *  catch trials (gross wrong notes) are spread evenly through each part.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.S03Design = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const MODES = {
    // Henry as subject zero: all five pilot levels, 2 detection reps, 1 preference rep.
    pilot: { detReps: 2, prefReps: 1, prefIdentical: 4, detCatch: 4, prefCatch: 2 },
    // Main study (after the pilot fixes the ladders): 4 detection levels x 3 reps,
    // 3 preference levels x 2 reps (power analysis design A2).
    main: { detReps: 3, prefReps: 2, prefIdentical: 7, detCatch: 4, prefCatch: 2 },
  };

  // ---------------------------------------------------------------- PRNG
  function xmur3(str) {
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return function () {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      return (h ^= h >>> 16) >>> 0;
    };
  }
  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function rngFor(seed) {
    return mulberry32(xmur3(String(seed))());
  }
  function shuffle(arr, rnd) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rnd() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // ---------------------------------------------------------------- manifest helpers
  function index(manifest) {
    const by = {};
    for (const s of manifest.stimuli) {
      by[s.span] = by[s.span] || {};
      const key = s.dimension === "original" ? s.excerpt + "|orig"
        : s.dimension === "catch" ? s.excerpt + "|catch"
          : s.excerpt + "|" + s.dimension + "|" + s.level;
      by[s.span][key] = s;
    }
    return by;
  }
  function dimsAndLevels(manifest, span) {
    const out = {};
    for (const s of manifest.stimuli) {
      if (s.span !== span || s.dimension === "original" || s.dimension === "catch") continue;
      out[s.dimension] = out[s.dimension] || new Set();
      out[s.dimension].add(s.level);
    }
    const res = {};
    for (const d of Object.keys(out).sort()) res[d] = Array.from(out[d]).sort((a, b) => a - b);
    return res;
  }
  function excerptIds(manifest) {
    return manifest.excerpts.map((e) => e.id);
  }

  // balanced 0/1 vector of length n (half ones), shuffled
  function balanced(n, rnd) {
    const v = [];
    for (let i = 0; i < n; i++) v.push(i % 2);
    return shuffle(v, rnd);
  }

  // spread catch trials evenly and avoid the same excerpt twice in a row where possible
  function interleave(trials, catches) {
    const out = trials.slice();
    const n = catches.length;
    for (let k = 0; k < n; k++) {
      const pos = Math.round(((k + 1) * (out.length + 1)) / (n + 1)) - 1;
      out.splice(Math.max(1, Math.min(out.length, pos)), 0, catches[k]);
    }
    return out;
  }
  function separateExcerpts(trials) {
    const a = trials.slice();
    for (let i = 1; i < a.length; i++) {
      if (a[i].excerpt !== a[i - 1].excerpt) continue;
      for (let j = i + 1; j < a.length; j++) {
        const okHere = a[j].excerpt !== a[i - 1].excerpt;
        const okThere = a[i].excerpt !== a[j - 1].excerpt &&
          (j + 1 >= a.length || a[i].excerpt !== a[j + 1].excerpt);
        if (okHere && okThere) {
          [a[i], a[j]] = [a[j], a[i]];
          break;
        }
      }
    }
    return a;
  }

  function cellsForDim(levels, reps, excerpts, rnd, usable) {
    // every (level, rep) once; excerpts cycle through a per-dimension random permutation,
    // skipping excerpts whose stimulus at that level is missing or identical to the original
    // (e.g. no harmony change left to blur in a short clip)
    const cells = [];
    for (const lv of levels) for (let r = 0; r < reps; r++) cells.push({ level: lv, rep: r });
    const order = shuffle(cells, rnd);
    const perm = shuffle(excerpts, rnd);
    const flip = balanced(order.length, rnd);
    const out = [];
    let ptr = 0;
    order.forEach((c, j) => {
      for (let t = 0; t < perm.length; t++) {
        const e = perm[(ptr + t) % perm.length];
        if (!usable || usable(e, c.level)) {
          out.push({ ...c, excerpt: e, second: flip[j] === 1 });
          ptr = (ptr + t + 1) % perm.length;
          return;
        }
      }
    });
    return out;
  }

  // ---------------------------------------------------------------- session builder
  function buildSession(manifest, opts) {
    const mode = MODES[opts.mode || "main"];
    if (!mode) throw new Error("unknown mode " + opts.mode);
    const cfg = Object.assign({}, mode, opts.overrides || {});
    const rnd = rngFor("S03|" + opts.seed);
    const idx = index(manifest);
    const ex = excerptIds(manifest);
    const missing = [];
    const need = (span, key) => {
      const s = idx[span] && idx[span][key];
      if (!s) missing.push(span + ":" + key);
      return s ? s.id : null;
    };
    const mk = (part, o) => Object.assign({ part }, o);

    // Part A
    const detDims = dimsAndLevels(manifest, "det");
    let partA = [];
    for (const [dim, levels] of Object.entries(detDims)) {
      const okA = (e, lv) => {
        const st = idx.det[e + "|" + dim + "|" + lv];
        return Boolean(st) && st.changed !== false;
      };
      for (const c of cellsForDim(levels, cfg.detReps, ex, rnd, okA)) {
        const deg = need("det", c.excerpt + "|" + dim + "|" + c.level);
        const orig = need("det", c.excerpt + "|orig");
        const stim = idx.det[c.excerpt + "|" + dim + "|" + c.level];
        partA.push(mk("A", {
          kind: "test", excerpt: c.excerpt, dimension: dim, level: c.level,
          x: stim ? stim.x : null, rep: c.rep, degraded_position: c.second ? 2 : 1,
          ref: orig, a: c.second ? orig : deg, b: c.second ? deg : orig,
        }));
      }
    }
    partA = shuffle(partA, rnd);
    const catchEx = shuffle(ex, rnd);
    const catchFlipA = balanced(cfg.detCatch, rnd);
    const catchesA = [];
    for (let k = 0; k < cfg.detCatch; k++) {
      const e = catchEx[k % catchEx.length];
      const orig = need("det", e + "|orig");
      const deg = need("det", e + "|catch");
      const second = catchFlipA[k] === 1;
      catchesA.push(mk("A", {
        kind: "catch", excerpt: e, dimension: "catch", level: null, x: null, rep: k,
        degraded_position: second ? 2 : 1, ref: orig, a: second ? orig : deg, b: second ? deg : orig,
      }));
    }
    partA = separateExcerpts(interleave(partA, catchesA));

    // Part B
    const prefDims = dimsAndLevels(manifest, "pref");
    let partB = [];
    for (const [dim, levels] of Object.entries(prefDims)) {
      const okB = (e, lv) => {
        const st = idx.pref[e + "|" + dim + "|" + lv];
        return Boolean(st) && st.changed !== false;
      };
      for (const c of cellsForDim(levels, cfg.prefReps, ex, rnd, okB)) {
        const deg = need("pref", c.excerpt + "|" + dim + "|" + c.level);
        const orig = need("pref", c.excerpt + "|orig");
        const stim = idx.pref[c.excerpt + "|" + dim + "|" + c.level];
        partB.push(mk("B", {
          kind: "test", excerpt: c.excerpt, dimension: dim, level: c.level,
          x: stim ? stim.x : null, rep: c.rep, original_position: c.second ? 1 : 2,
          a: c.second ? orig : deg, b: c.second ? deg : orig,
        }));
      }
    }
    const identEx = shuffle(ex, rnd);
    for (let k = 0; k < cfg.prefIdentical; k++) {
      const e = identEx[k % identEx.length];
      const orig = need("pref", e + "|orig");
      partB.push(mk("B", {
        kind: "identical", excerpt: e, dimension: "none", level: 0, x: 0, rep: k,
        original_position: null, a: orig, b: orig,
      }));
    }
    partB = shuffle(partB, rnd);
    const catchFlipB = balanced(cfg.prefCatch, rnd);
    const catchesB = [];
    for (let k = 0; k < cfg.prefCatch; k++) {
      const e = catchEx[(k + cfg.detCatch) % catchEx.length];
      const orig = need("pref", e + "|orig");
      const deg = need("pref", e + "|catch");
      const second = catchFlipB[k] === 1;
      catchesB.push(mk("B", {
        kind: "catch", excerpt: e, dimension: "catch", level: null, x: null, rep: k,
        original_position: second ? 1 : 2, a: second ? orig : deg, b: second ? deg : orig,
      }));
    }
    partB = separateExcerpts(interleave(partB, catchesB));

    // practice: Part A = two catch-level trials + one strongest-level trial, with feedback
    const practiceA = [];
    const pe = shuffle(ex, rnd);
    for (let k = 0; k < 2; k++) {
      const e = pe[k];
      const second = k === 1;
      const orig = need("det", e + "|orig");
      const deg = need("det", e + "|catch");
      practiceA.push(mk("A", {
        kind: "practice", excerpt: e, dimension: "catch", level: null, x: null, rep: k,
        degraded_position: second ? 2 : 1, ref: orig, a: second ? orig : deg, b: second ? deg : orig,
      }));
    }
    const dimNames = Object.keys(detDims);
    if (dimNames.length) {
      const d = dimNames[Math.floor(rnd() * dimNames.length)];
      const lv = detDims[d][detDims[d].length - 1];
      const e = pe[2 % pe.length];
      const orig = need("det", e + "|orig");
      const deg = need("det", e + "|" + d + "|" + lv);
      practiceA.push(mk("A", {
        kind: "practice", excerpt: e, dimension: d, level: lv, x: null, rep: 2,
        degraded_position: 1, ref: orig, a: deg, b: orig,
      }));
    }
    const e = pe[3 % pe.length];
    const practiceB = [mk("B", {
      kind: "practice", excerpt: e, dimension: "catch", level: null, x: null, rep: 0,
      original_position: 2, a: need("pref", e + "|catch"), b: need("pref", e + "|orig"),
    })];

    [practiceA, partA, practiceB, partB].forEach((list) =>
      list.forEach((t, i) => { t.index = i; t.trial_id = t.part + (t.kind === "practice" ? "p" : "") + i; }));
    return { config: cfg, mode: opts.mode || "main", seed: String(opts.seed),
      practiceA, partA, practiceB, partB, missing };
  }

  // ---------------------------------------------------------------- misc
  function participantCode(rnd) {
    const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no 0/O/1/I
    let s = "P";
    for (let i = 0; i < 6; i++) s += alphabet[Math.floor(rnd() * alphabet.length)];
    return s;
  }

  return { MODES, buildSession, participantCode, rngFor, shuffle, index, dimsAndLevels };
});
