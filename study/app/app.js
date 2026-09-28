/* PianoLens S-03 listening study app. Plain JS, no external services.
 *
 * Query parameters:
 *   stim=<path>   folder with manifest.js and audio/ (default ../../data/interim/study_s03/)
 *   mode=pilot|main   design (see design.js MODES; default main)
 *   parts=AB|A|B  which parts to run in this session (default AB)
 *   autotest=1    no audio, simulated answers; writes the result JSON into #autotest-result
 *                 (used by study/app/smoke_test.py with headless Chrome)
 *
 * Data never leaves the browser: state is kept in localStorage (so a session can resume)
 * and exported as a JSON file by the participant.
 */
(function () {
  "use strict";

  const APP_VERSION = "0.1.0";
  const PROTOCOL_VERSION = "S-03 protocol 0.1 (draft, pre-pilot)";
  const CONSENT_VERSION = "draft-0.1";
  const params = new URLSearchParams(location.search);
  const AUTOTEST = params.get("autotest") === "1";
  const MODE = params.get("mode") || "main";
  // parts=A or parts=B runs one part only (Part A and Part B may be separate sessions or
  // separate listener groups: the analysis uses group-level thresholds)
  const PARTS = (params.get("parts") || "AB").toUpperCase();
  let BASE = params.get("stim") || "../../data/interim/study_s03/";
  if (!BASE.endsWith("/")) BASE += "/";
  const STORE_KEY = "pianolens_s03_session";
  const GAP_MS = 600;
  const HP_TRIALS = 6;
  const HP_PASS = 5;

  const D = window.S03Design;
  const $ = (id) => document.getElementById(id);
  let manifest = null;
  let state = null;
  let t0 = performance.now();
  const audioCache = new Map();

  // ---------------------------------------------------------------- storage (optional)
  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* no storage */ }
  }
  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "null"); } catch (e) { return null; }
  }
  function clearStore() {
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* ignore */ }
  }

  // ---------------------------------------------------------------- screens
  function show(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $(id).classList.add("active");
    window.scrollTo(0, 0);
  }
  function fail(msg) {
    $("error-msg").textContent = msg;
    show("screen-error");
    if (AUTOTEST) finishAutotest({ error: msg });
  }
  const later = (fn) => setTimeout(fn, 0);

  // ---------------------------------------------------------------- manifest
  function loadManifest() {
    return new Promise((resolve, reject) => {
      if (window.S03_MANIFEST) return resolve(window.S03_MANIFEST);
      const s = document.createElement("script");
      s.src = BASE + "manifest.js";
      s.onload = () => (window.S03_MANIFEST ? resolve(window.S03_MANIFEST)
        : reject(new Error("manifest.js did not define S03_MANIFEST")));
      s.onerror = () => reject(new Error("Could not load " + s.src +
        ". Build the stimuli (uv run python scripts/build_study_s03.py) and open the app " +
        "from the repository root (python3 -m http.server, then /study/app/)."));
      document.head.appendChild(s);
    });
  }

  // ---------------------------------------------------------------- audio
  function audioFor(id) {
    if (audioCache.has(id)) return audioCache.get(id);
    const stim = manifest.stimuli.find((s) => s.id === id);
    if (!stim) throw new Error("unknown stimulus " + id);
    const a = new Audio(BASE + stim.file);
    a.preload = "auto";
    audioCache.set(id, a);
    return a;
  }
  function preload(trial) {
    if (!trial || AUTOTEST) return;
    [trial.ref, trial.a, trial.b].filter(Boolean).forEach(audioFor);
  }
  function playClip(id) {
    if (AUTOTEST) return Promise.resolve();
    const a = audioFor(id);
    return new Promise((resolve, reject) => {
      const done = () => { a.removeEventListener("ended", done); a.removeEventListener("error", err); resolve(); };
      const err = () => { a.removeEventListener("ended", done); a.removeEventListener("error", err); reject(new Error("audio error: " + a.src)); };
      a.addEventListener("ended", done);
      a.addEventListener("error", err);
      a.currentTime = 0;
      a.play().catch(reject);
    });
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, AUTOTEST ? 0 : ms));

  // ---------------------------------------------------------------- headphone check
  // Woods, Siegel, Traer, McDermott 2017 (Atten. Percept. Psychophys. 79:2064): three 200 Hz
  // tones, one 6 dB quieter, one in antiphase between the ears. Over loudspeakers the antiphase
  // tone partly cancels and sounds quietest, so loudspeaker listeners tend to fail.
  let audioCtx = null;
  function tone(ctx, kind) {
    const sr = ctx.sampleRate;
    const n = Math.round(sr * 1.0);
    const buf = ctx.createBuffer(2, n, sr);
    const amp = kind === "quiet" ? 0.2 * Math.pow(10, -6 / 20) : 0.2;
    const ramp = Math.round(sr * 0.1);
    const L = buf.getChannelData(0);
    const R = buf.getChannelData(1);
    for (let i = 0; i < n; i++) {
      let env = 1;
      if (i < ramp) env = 0.5 * (1 - Math.cos((Math.PI * i) / ramp));
      else if (i > n - ramp) env = 0.5 * (1 - Math.cos((Math.PI * (n - i)) / ramp));
      const v = amp * env * Math.sin((2 * Math.PI * 200 * i) / sr);
      L[i] = v;
      R[i] = kind === "antiphase" ? -v : v;
    }
    return buf;
  }
  function playTones(order) {
    if (AUTOTEST) return Promise.resolve();
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const start = audioCtx.currentTime + 0.1;
    order.forEach((kind, k) => {
      const src = audioCtx.createBufferSource();
      src.buffer = tone(audioCtx, kind);
      src.connect(audioCtx.destination);
      src.start(start + k * 1.5);
    });
    return wait(100 + 3 * 1500);
  }
  function headphoneCheck() {
    show("screen-headphone");
    const rnd = D.rngFor(state.code + "|hp|" + state.headphone.attempts.length);
    const trials = [];
    for (let k = 0; k < HP_TRIALS; k++) trials.push(D.shuffle(["standard", "quiet", "antiphase"], rnd));
    const attempt = { trials: [], correct: 0 };
    let k = 0;
    $("hp-total").textContent = HP_TRIALS;
    const next = () => {
      if (k >= HP_TRIALS) {
        attempt.pass = attempt.correct >= HP_PASS;
        state.headphone.attempts.push(attempt);
        state.headphone.pass = attempt.pass;
        save();
        if (attempt.pass || state.headphone.attempts.length >= 2) {
          return later(() => startInstructions(PARTS.includes("A") ? "A" : "B"));
        }
        return show("screen-hp-fail");
      }
      $("hp-progress").textContent = `Question ${k + 1} of ${HP_TRIALS}`;
      $("hp-answers").hidden = true;
      $("btn-hp-play").disabled = false;
      const order = trials[k];
      const play = () => {
        $("btn-hp-play").disabled = true;
        playTones(order).then(() => {
          $("hp-answers").hidden = false;
          const answer = (choice) => {
            $("hp-answers").querySelectorAll("button").forEach((b) => (b.onclick = null));
            const ok = order[choice - 1] === "quiet";
            attempt.trials.push({ order, choice, correct: ok });
            if (ok) attempt.correct += 1;
            k += 1;
            later(next);
          };
          if (AUTOTEST) return answer(order.indexOf("quiet") + 1);
          $("hp-answers").querySelectorAll("button").forEach((b) => {
            b.onclick = () => answer(Number(b.dataset.hp));
          });
        });
      };
      if (AUTOTEST) play(); else $("btn-hp-play").onclick = play;
    };
    next();
  }

  // ---------------------------------------------------------------- instructions
  const INSTR = {
    A: {
      title: "Part A: spot the difference",
      body: `<p>Each question has three clips: first the <strong>reference</strong>, then
        <strong>A</strong>, then <strong>B</strong>. One of A and B is exactly the same as the
        reference. The other one is slightly changed.</p>
        <p>Answer: <strong>which one, A or B, is different from the reference?</strong>
        Each clip plays once. If you are not sure, make your best guess.</p>
        <p>First, three practice questions with feedback.</p>`,
    },
    A2: {
      title: "Part A",
      body: `<p>Now the real questions. There is no feedback from here on. Some changes are
        very small; guessing is fine. There is a break halfway.</p>`,
    },
    B: {
      title: "Part B: which do you prefer?",
      body: `<p>Each question has two versions of the same passage, <strong>A</strong> then
        <strong>B</strong>. Sometimes they differ a lot, sometimes a little, sometimes not at
        all.</p><p>Answer: <strong>which performance do you prefer?</strong> Go with your
        first impression. There are no right answers.</p><p>First, one practice question.</p>`,
    },
    B2: {
      title: "Part B",
      body: `<p>Now the real questions. There is a break halfway.</p>`,
    },
  };
  function startInstructions(which) {
    state.phase = "instr-" + which;
    save();
    $("instr-title").textContent = INSTR[which].title;
    $("instr-body").innerHTML = INSTR[which].body;
    show("screen-instructions");
    const go = () => {
      if (which === "A") runList("practiceA", () => startInstructions("A2"));
      else if (which === "A2") runList("partA", () => (PARTS.includes("B") ? startInstructions("B") : finish()));
      else if (which === "B") runList("practiceB", () => startInstructions("B2"));
      else runList("partB", finish);
    };
    if (AUTOTEST) later(go); else $("btn-instr").onclick = go;
  }

  // ---------------------------------------------------------------- trials
  function simulatedAnswer(trial, rnd) {
    // a plausible listener for the smoke test: better with larger x, 90% on catch trials
    let pc;
    if (trial.kind === "catch" || trial.kind === "practice") pc = 0.9;
    else if (trial.x === null || trial.x === undefined || trial.x <= 0) pc = 0.5;
    else pc = 0.5 + 0.45 / (1 + Math.exp(-3 * Math.log2(trial.x / 0.3)));
    const correctChoice = trial.part === "A" ? trial.degraded_position
      : (trial.original_position || 1);
    const right = rnd() < pc;
    return right ? correctChoice : 3 - correctChoice;
  }

  function runList(listName, onDone) {
    const list = state.session[listName];
    state.phase = listName;
    if (state.pos[listName] === undefined) state.pos[listName] = 0;
    save();
    const rnd = D.rngFor(state.code + "|auto|" + listName);
    const half = Math.floor(list.length / 2);
    const step = () => {
      const i = state.pos[listName];
      if (i >= list.length) return later(onDone);
      if (!listName.startsWith("practice") && i === half && !state.breaks.includes(listName)) {
        state.breaks.push(listName);
        save();
        show("screen-break");
        if (AUTOTEST) return later(step);
        $("btn-break").onclick = step;
        return;
      }
      runTrial(list[i], listName, i, list.length).then((resp) => {
        if (resp.ok === false) return;
        state.pos[listName] = i + 1;
        save();
        later(step);
      });
    };
    step();

    function runTrial(trial, listName, i, n) {
      show("screen-trial");
      const practice = listName.startsWith("practice");
      $("trial-progress").textContent = (practice ? "Practice " : "Question ") + (i + 1) + " of " + n;
      $("trial-question").textContent = trial.part === "A"
        ? "Which one, A or B, is different from the reference?"
        : "Which performance do you prefer?";
      $("trial-feedback").textContent = "";
      const names = trial.part === "A" ? ["Reference", "A", "B"] : ["A", "B"];
      const ids = trial.part === "A" ? [trial.ref, trial.a, trial.b] : [trial.a, trial.b];
      const box = $("clips");
      box.innerHTML = "";
      const els = names.map((nm) => {
        const d = document.createElement("div");
        d.className = "clip";
        d.textContent = nm;
        box.appendChild(d);
        return d;
      });
      const btnA = $("btn-ans-a");
      const btnB = $("btn-ans-b");
      btnA.disabled = btnB.disabled = true;
      preload(list[i + 1]);
      const tStart = performance.now();
      return new Promise((resolve) => {
        let chain = Promise.resolve();
        ids.forEach((id, k) => {
          chain = chain.then(() => {
            els[k].classList.add("playing");
            return playClip(id).then(() => {
              els[k].classList.remove("playing");
              els[k].classList.add("done");
              return k < ids.length - 1 ? wait(GAP_MS) : null;
            });
          });
        });
        chain.then(() => {
          const tReady = performance.now();
          let answered = false;
          const answer = (choice) => {
            if (answered) return;
            answered = true;
            btnA.disabled = btnB.disabled = true;
            document.removeEventListener("keydown", onKey);
            const rec = {
              list: listName, trial_id: trial.trial_id, part: trial.part, kind: trial.kind,
              excerpt: trial.excerpt, dimension: trial.dimension, level: trial.level,
              x: trial.x, rep: trial.rep, stim_ref: trial.ref || null, stim_a: trial.a,
              stim_b: trial.b, response: choice,
              rt_ms: Math.round(performance.now() - tReady),
              trial_ms: Math.round(performance.now() - tStart),
              t_session_s: Math.round((performance.now() - t0) / 100) / 10,
            };
            if (trial.part === "A") {
              rec.degraded_position = trial.degraded_position;
              rec.correct = choice === trial.degraded_position;
            } else {
              rec.original_position = trial.original_position;
              rec.chose_original = trial.original_position ? choice === trial.original_position : null;
            }
            state.responses.push(rec);
            save();
            if (practice && trial.part === "A") {
              $("trial-feedback").textContent = (rec.correct ? "Correct. " : "Not quite. ") +
                (trial.degraded_position === 1 ? "A" : "B") + " was the changed one.";
              return setTimeout(() => resolve({ ok: true }), AUTOTEST ? 0 : 1600);
            }
            resolve({ ok: true });
          };
          const onKey = (ev) => {
            if (ev.key === "1" || ev.key === "a" || ev.key === "A") answer(1);
            if (ev.key === "2" || ev.key === "b" || ev.key === "B") answer(2);
          };
          if (AUTOTEST) return answer(simulatedAnswer(trial, rnd));
          btnA.disabled = btnB.disabled = false;
          btnA.onclick = () => answer(1);
          btnB.onclick = () => answer(2);
          document.addEventListener("keydown", onKey);
        }).catch((e) => { fail(String(e && e.message ? e.message : e)); resolve({ ok: false }); });
      });
    }
  }

  // ---------------------------------------------------------------- export
  function exportObject() {
    return {
      study: "PianoLens S-03 perceptual cost", app_version: APP_VERSION,
      protocol_version: PROTOCOL_VERSION, consent_version: CONSENT_VERSION,
      stimuli: { spec_version: manifest.spec_version, built: manifest.built,
        code_state: manifest.code_state, n_stimuli: manifest.stimuli.length },
      participant: { code: state.code, background: state.background },
      session: { date: state.date, mode: state.mode, parts: state.parts, seed: state.seed,
        config: state.session.config, autotest: AUTOTEST,
        headphone: state.headphone, breaks: state.breaks,
        missing_stimuli: state.session.missing },
      responses: state.responses,
    };
  }
  function download() {
    const blob = new Blob([JSON.stringify(exportObject(), null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `S03_${state.code}_${state.date}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  function finish() {
    state.phase = "done";
    save();
    $("end-code").textContent = state.code;
    show("screen-end");
    $("btn-download").onclick = download;
    if (AUTOTEST) {
      // check that the browser can load and decode a stimulus (duration from its metadata)
      const orig = manifest.stimuli.find((x) => x.dimension === "original");
      const out = exportObject();
      let reported = false;
      const report = (ok, info) => {
        if (reported) return;
        reported = true;
        out.audio_probe = { file: orig.file, ok, ...info };
        finishAutotest(out);
      };
      setTimeout(() => report(false, { error: "timeout" }), 20000);
      fetch(BASE + orig.file)
        .then((r) => r.arrayBuffer())
        .then((buf) => new OfflineAudioContext(1, 1, 44100).decodeAudioData(buf))
        .then((ab) => report(true, { duration_s: ab.duration, sample_rate: ab.sampleRate }))
        .catch((e) => report(false, { error: String(e) }));
    }
  }
  function finishAutotest(obj) {
    const pre = $("autotest-result");
    pre.textContent = JSON.stringify(obj);
    pre.hidden = false;
    document.title = "S03 AUTOTEST DONE";
  }

  // ---------------------------------------------------------------- flow
  function newState() {
    const rnd = D.rngFor(String(Math.random()) + String(Date.now()));
    const code = D.participantCode(rnd);
    return {
      version: APP_VERSION, code, seed: code, mode: MODE, parts: PARTS,
      date: (() => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); })(),
      consent: null, background: null, headphone: { attempts: [], pass: null },
      session: null, phase: "consent", pos: {}, breaks: [], responses: [],
    };
  }
  function startConsent() {
    show("screen-consent");
    const s = D.buildSession(manifest, { mode: state.mode, seed: state.seed });
    const nA = PARTS.includes("A") ? s.partA.length : 0;
    const nB = PARTS.includes("B") ? s.partB.length : 0;
    const est = Math.round((nA * 25 + nB * 32) / 60 + 8);
    $("consent-minutes").textContent = String(est);
    const age = $("consent-age");
    const agree = $("consent-agree");
    const upd = () => ($("btn-consent").disabled = !(age.checked && agree.checked));
    age.onchange = agree.onchange = upd;
    $("btn-decline").onclick = () => { clearStore(); show("screen-declined"); };
    const go = () => {
      state.consent = { version: CONSENT_VERSION, agreed: true, adult: true };
      state.session = s;
      state.phase = "background";
      save();
      startBackground();
    };
    $("btn-consent").onclick = go;
    if (AUTOTEST) { age.checked = agree.checked = true; upd(); later(go); }
  }
  function startBackground() {
    show("screen-background");
    const form = $("bg-form");
    form.onsubmit = (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      state.background = Object.fromEntries(fd.entries());
      state.phase = "volume";
      save();
      startVolume();
    };
    if (AUTOTEST) {
      ["musician", "training_years", "plays_piano", "hearing", "device"].forEach((name) => {
        form.querySelector(`input[name="${name}"]`).checked = true;
      });
      later(() => form.requestSubmit());
    }
  }
  function startVolume() {
    show("screen-volume");
    const orig = manifest.stimuli.find((s) => s.span === "pref" && s.dimension === "original");
    $("btn-volume-play").onclick = () => { if (orig) playClip(orig.id).catch((e) => fail(e.message)); };
    const go = () => {
      if (orig && !AUTOTEST) { const a = audioFor(orig.id); a.pause(); }
      state.phase = "headphone";
      save();
      headphoneCheck();
    };
    $("btn-volume-done").onclick = go;
    $("btn-hp-retry").onclick = headphoneCheck;
    if (AUTOTEST) later(go);
  }
  function resume() {
    const p = state.phase;
    if (p === "background") return startBackground();
    if (p === "volume") return startVolume();
    if (p === "headphone") return headphoneCheck();
    if (p === "instr-A" || p === "practiceA") return startInstructions("A");
    if (p === "instr-A2" || p === "partA") return startInstructions("A2");
    if (p === "instr-B" || p === "practiceB") return startInstructions("B");
    if (p === "instr-B2" || p === "partB") return startInstructions("B2");
    if (p === "done") return finish();
    return startConsent();
  }

  function init() {
    if (!D) return fail("design.js did not load");
    loadManifest().then((m) => {
      manifest = m;
      const prev = AUTOTEST ? null : load();
      if (prev && prev.session && prev.phase !== "done" && prev.mode === MODE &&
          (prev.parts || "AB") === PARTS) {
        $("resume-code").textContent = prev.code;
        show("screen-resume");
        $("btn-resume").onclick = () => { state = prev; resume(); };
        $("btn-restart").onclick = () => { clearStore(); state = newState(); startConsent(); };
        return;
      }
      state = newState();
      if (AUTOTEST) state.code = state.seed = "PTEST01";
      startConsent();
    }).catch((e) => fail(e.message));
  }
  init();
})();
