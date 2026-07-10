/* asiai — Benchmark page v2 behavior.
   Type selection, form flow (01 Target → 02 Options → 03 Advanced),
   AJAX submit + SSE live progress, result panel, card-conditions rail.
   The form field contract (name= / values / routes) is owned by
   src/asiai/web/routes/bench.py and must not change here. */
(function () {
    'use strict';

    /* ── Element handles ─────────────────────────────────────── */
    var root = document.getElementById('bn-root');
    var stdForm = document.getElementById('bench-form');
    var modeForm = document.getElementById('mode-form');
    var stdSubmit = document.getElementById('bench-submit');
    var modeSubmit = document.getElementById('mode-submit');
    var quickBtn = document.getElementById('quick-bench-btn');
    var statusCard = document.getElementById('status-card');
    var statusDiv = document.getElementById('bench-status');
    var resultsDiv = document.getElementById('bench-results');
    var stdCard = document.getElementById('standard-form-card');
    var modeCard = document.getElementById('mode-form-card');
    var summaryBar = document.getElementById('bn-run-summary');
    var summaryType = document.getElementById('bn-summary-type');
    var summaryText = document.getElementById('bn-summary-text');
    var editRerunBtn = document.getElementById('bn-edit-rerun');
    var condBadge = document.getElementById('bn-cond-badge');
    var condRows = document.getElementById('bn-cond-rows');
    var typeDescEl = document.getElementById('bn-type-desc');

    var benchTokChart = null;
    var benchTtftChart = null;

    /* ── Bench type metadata ─────────────────────────────────── */
    /* per = very rough seconds per run, for the "~ est." hint only. */
    var TYPES = {
        '': {
            name: 'throughput',
            desc: 'Sustained generation speed — tok/s, TTFT, VRAM, watts. Winner vs runner-up on the card.',
            per: 15
        },
        'agentic': {
            name: 'agentic',
            desc: 'Prefix-cache reuse across multi-turn phases — cold vs warm TTFT, reuse fraction. Several minutes per repeat.',
            per: 180
        },
        'burst': {
            name: 'burst',
            desc: 'Concurrent request bursts — p50/p95/p99 latency per burst size, aggregate tok/s. Heavy load while it runs.',
            per: 60
        },
        'code': {
            name: 'code',
            desc: 'Code suites — deterministic dev-quality gates; the optional LLM judge grades coding tasks.',
            per: 90
        },
        'language': {
            name: 'language',
            desc: 'Multilingual retention — adherence & diacritics deterministic; fluency needs the judge.',
            per: 70
        },
        'instruct': {
            name: 'instruct',
            desc: 'Instruction following — IFEval-style verifiable checks + agentic deliverables.',
            per: 50
        },
        'thinking-ablation': {
            name: 'thinking',
            desc: 'Thinking on/off ablation on a tool-call-stress load — budget tracked on the card.',
            per: 120
        }
    };

    var webBenchType = '';
    var isRunning = false;
    var logLines = [];

    function fmtSec(s) {
        if (s < 60) return '~' + s + ' s';
        var m = Math.floor(s / 60);
        var r = s % 60;
        return '~' + m + ' m' + (r ? ' ' + r + ' s' : '');
    }

    /* ═══ Model picker (standard form): custom text toggle ═══ */
    var customToggle = document.getElementById('model-custom-toggle');
    var customInput = document.getElementById('model-custom');
    var modelSelect = document.getElementById('model-select');
    if (customToggle) {
        customToggle.addEventListener('click', function (e) {
            e.preventDefault();
            if (customInput.style.display === 'none') {
                customInput.style.display = '';
                modelSelect.style.display = 'none';
                customToggle.textContent = 'Use model dropdown';
            } else {
                customInput.style.display = 'none';
                modelSelect.style.display = '';
                customToggle.textContent = 'Type custom model name';
                customInput.value = '';
            }
            renderConditions();
        });
    }

    /* ═══ Compare mode toggle (standard form, Advanced) ═══ */
    var compareToggle = document.getElementById('compare-toggle');
    var compareGroup = document.getElementById('compare-group');
    var enginesGroup = document.getElementById('engines-group');
    var modelGroup = document.getElementById('model-group');
    if (compareToggle) {
        compareToggle.addEventListener('change', function () {
            if (this.checked) {
                compareGroup.style.display = '';
                if (enginesGroup) enginesGroup.style.display = 'none';
                if (modelGroup) modelGroup.style.display = 'none';
            } else {
                compareGroup.style.display = 'none';
                if (enginesGroup) enginesGroup.style.display = '';
                if (modelGroup) modelGroup.style.display = '';
            }
            updateStdAdvNote();
            renderConditions();
        });
    }

    function updateStdAdvNote() {
        var note = document.getElementById('std-adv-note');
        if (!note) return;
        var parts = ['compare: ' + (compareToggle && compareToggle.checked ? 'on' : 'off')];
        var card = stdForm.querySelector('input[name="card"]');
        var share = stdForm.querySelector('input[name="share"]');
        var flags = [];
        if (card && card.checked) flags.push('card');
        if (share && share.checked) flags.push('share');
        parts.push(flags.length ? flags.join(' + ') + ' on' : 'card off');
        note.textContent = parts.join(' · ');
    }

    /* ═══ Runs segmented controls (drive the hidden range inputs) ═══ */
    function wireSeg(segId, rangeId, noteId) {
        var seg = document.getElementById(segId);
        var range = document.getElementById(rangeId);
        var note = document.getElementById(noteId);
        if (!seg || !range) return;

        function paint() {
            var val = String(range.value);
            seg.querySelectorAll('button').forEach(function (b) {
                b.classList.toggle('active', b.dataset.val === val);
            });
            if (note) {
                var n = parseInt(val, 10) || 1;
                if (n >= 3) {
                    note.textContent = 'CI95 on every number · n=' + n;
                    note.classList.remove('bn-warn');
                } else {
                    note.textContent = 'n=' + n + ' — no CI95 · single-run numbers';
                    note.classList.add('bn-warn');
                }
            }
        }
        seg.querySelectorAll('button').forEach(function (b) {
            b.addEventListener('click', function () {
                range.value = b.dataset.val;
                paint();
                updateEstimates();
                renderConditions();
            });
        });
        paint();
        return paint;
    }
    var paintStdSeg = wireSeg('runs-seg', 'runs-range', 'runs-ci-note');
    var paintModeSeg = wireSeg('mode-runs-seg', 'mode-runs-range', 'mode-runs-ci-note');

    /* ═══ Bench type switcher ═══ */
    function setWebBenchType(type, btn) {
        webBenchType = type || '';
        document.querySelectorAll('.bn-chip[data-btype]').forEach(function (c) {
            c.classList.remove('active');
        });
        if (btn) btn.classList.add('active');

        var meta = TYPES[webBenchType] || TYPES[''];
        if (typeDescEl) typeDescEl.textContent = meta.desc;

        if (!isRunning) {
            summaryBar.hidden = true;
            if (!webBenchType) {
                modeCard.style.display = 'none';
                stdCard.style.display = '';
                quickBtn.disabled = false;
            } else {
                stdCard.style.display = 'none';
                modeCard.style.display = '';
                quickBtn.disabled = true;
            }
        }

        var optType = document.getElementById('mode-options-type');
        if (optType) optType.textContent = meta.name;
        var modeLabel = document.getElementById('mode-submit-label');
        if (modeLabel) modeLabel.textContent = 'Run ' + meta.name + ' bench';

        document.querySelectorAll('#mode-form .mode-group').forEach(function (g) {
            var modes = (g.dataset.modes || '').split(' ');
            g.style.display = modes.indexOf(webBenchType) >= 0 ? '' : 'none';
        });

        updateEstimates();
        renderConditions();
    }
    document.querySelectorAll('.bn-chip[data-btype]').forEach(function (chip) {
        chip.addEventListener('click', function () {
            setWebBenchType(chip.dataset.btype, chip);
        });
    });

    /* ═══ Mode engine cards (drive the hidden mode_engine select) ═══ */
    var modeEngineSelect = document.getElementById('mode-engine');
    var modeEngineCards = document.getElementById('mode-engine-cards');
    if (modeEngineCards && modeEngineSelect) {
        modeEngineCards.querySelectorAll('button[data-engine]').forEach(function (b) {
            b.addEventListener('click', function () {
                modeEngineCards.querySelectorAll('button[data-engine]').forEach(function (x) {
                    x.classList.remove('active');
                });
                b.classList.add('active');
                modeEngineSelect.value = b.dataset.engine;
                modeEngineSelect.dispatchEvent(new Event('change'));
            });
        });
    }

    /* ═══ Mode model picker: options follow the selected engine ═══ */
    var MODE_CUSTOM = '__custom__';
    var modeModelSelect = document.getElementById('mode-model-select');
    var modeModelCustom = document.getElementById('mode-model-custom');
    var modeEngineData = [];
    try {
        modeEngineData = JSON.parse(
            document.getElementById('mode-model-data').textContent || '[]');
    } catch (e) { /* malformed data: picker degrades to auto + custom */ }

    function rebuildModeModelOptions() {
        var engineName = modeEngineSelect ? modeEngineSelect.value : '';
        var entry = null;
        for (var i = 0; i < modeEngineData.length; i++) {
            if (modeEngineData[i].name === engineName) { entry = modeEngineData[i]; break; }
        }
        modeModelSelect.textContent = '';
        var autoOpt = document.createElement('option');
        autoOpt.value = '';
        autoOpt.textContent = '(auto — first loaded model)';
        modeModelSelect.appendChild(autoOpt);
        if (entry) {
            (entry.models || []).forEach(function (name) {
                var opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                modeModelSelect.appendChild(opt);
            });
            (entry.available || []).forEach(function (name) {
                var opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name + ' — will load';
                modeModelSelect.appendChild(opt);
            });
        }
        var customOpt = document.createElement('option');
        customOpt.value = MODE_CUSTOM;
        customOpt.textContent = 'Custom…';
        modeModelSelect.appendChild(customOpt);
        modeModelSelect.value = '';
        if (modeModelCustom) {
            modeModelCustom.style.display = 'none';
            modeModelCustom.value = '';
        }
        renderConditions();
    }
    if (modeModelSelect) {
        modeModelSelect.addEventListener('change', function () {
            if (modeModelCustom) {
                var isCustom = this.value === MODE_CUSTOM;
                modeModelCustom.style.display = isCustom ? '' : 'none';
                if (!isCustom) modeModelCustom.value = '';
            }
            renderConditions();
        });
        if (modeEngineSelect) {
            modeEngineSelect.addEventListener('change', rebuildModeModelOptions);
        }
        rebuildModeModelOptions();
    }

    /* ═══ Sampling presets → mode_extra_body ═══ */
    var presetsBox = document.getElementById('mode-presets');
    var extraBodyInput = document.getElementById('mode-extra-body');

    function activePresetLabel() {
        if (!presetsBox) return 'engine defaults';
        var on = presetsBox.querySelector('.bn-preset.active');
        return on ? on.textContent.toLowerCase() : 'custom';
    }

    function updateModeAdvNote() {
        var note = document.getElementById('mode-adv-note');
        if (!note) return;
        var judgeUrl = modeForm.querySelector('input[name="judge_url"]');
        var judgeOn = judgeUrl && judgeUrl.value.trim() !== '' &&
            ['code', 'language'].indexOf(webBenchType) >= 0;
        note.textContent = 'judge: ' + (judgeOn ? 'on' : 'off') +
            ' · sampling: ' + activePresetLabel();
    }

    if (presetsBox && extraBodyInput) {
        presetsBox.querySelectorAll('.bn-preset').forEach(function (b) {
            b.addEventListener('click', function () {
                presetsBox.querySelectorAll('.bn-preset').forEach(function (x) {
                    x.classList.remove('active');
                });
                b.classList.add('active');
                extraBodyInput.value = b.dataset.preset || '';
                updateModeAdvNote();
                renderConditions();
            });
        });
        extraBodyInput.addEventListener('input', function () {
            /* hand-edited JSON = no preset matches anymore */
            presetsBox.querySelectorAll('.bn-preset').forEach(function (x) {
                x.classList.toggle('active', (x.dataset.preset || '') === extraBodyInput.value.trim());
            });
            updateModeAdvNote();
            renderConditions();
        });
    }
    if (modeForm) {
        var judgeInput = modeForm.querySelector('input[name="judge_url"]');
        if (judgeInput) {
            judgeInput.addEventListener('input', function () {
                updateModeAdvNote();
                renderConditions();
            });
        }
    }
    if (stdForm) {
        stdForm.addEventListener('change', function () {
            updateStdAdvNote();
            updateEstimates();
            renderConditions();
        });
    }

    /* ═══ Estimates (rough, per-type × runs — a hint, not a promise) ═══ */
    function updateEstimates() {
        var stdEst = document.getElementById('std-est');
        var modeEst = document.getElementById('mode-est');
        if (stdEst) {
            var n = parseInt(document.getElementById('runs-range').value, 10) || 1;
            var prompts = stdForm.querySelectorAll('input[name="prompts"]:checked').length || 1;
            stdEst.textContent = fmtSec(TYPES[''].per * n * prompts) + ' est. · ' +
                n + (n > 1 ? ' runs' : ' run') + ' · conditions auto-stamped on the card';
        }
        if (modeEst && webBenchType) {
            var m = parseInt(document.getElementById('mode-runs-range').value, 10) || 1;
            var meta = TYPES[webBenchType] || TYPES[''];
            modeEst.textContent = fmtSec(meta.per * m) + ' est. · ' +
                m + (m > 1 ? ' runs' : ' run') + ' · conditions auto-stamped on the card';
        }
    }

    /* ═══ Card-conditions rail ═══ */
    function condRow(key, val, warn) {
        var row = document.createElement('div');
        var k = document.createElement('span');
        k.className = 'k';
        k.textContent = key;
        var v = document.createElement('span');
        v.className = warn ? 'v warn' : 'v';
        v.textContent = val;
        row.appendChild(k);
        row.appendChild(v);
        return row;
    }

    function currentTarget() {
        if (!webBenchType) {
            var names = [];
            stdForm.querySelectorAll('input[name="engines"]:checked').forEach(function (c) {
                names.push(c.value);
            });
            var model = (customInput && customInput.style.display !== 'none' && customInput.value.trim()) ||
                (modelSelect && modelSelect.value) || '';
            if (compareToggle && compareToggle.checked) {
                var cmp = stdForm.querySelectorAll('#compare-select option:checked').length;
                return { engine: 'compare', model: cmp + ' slots', runs: document.getElementById('runs-range').value };
            }
            return {
                engine: names.join(' + ') || 'none',
                model: model || 'auto',
                runs: document.getElementById('runs-range').value
            };
        }
        var mEngine = modeEngineSelect ? modeEngineSelect.value : '';
        var mModel = '';
        if (modeModelSelect) {
            mModel = modeModelSelect.value === MODE_CUSTOM
                ? (modeModelCustom ? modeModelCustom.value.trim() : '')
                : modeModelSelect.value;
        }
        return {
            engine: mEngine || 'none',
            model: mModel || 'auto',
            runs: document.getElementById('mode-runs-range').value
        };
    }

    function renderConditions() {
        if (!condRows) return;
        var meta = TYPES[webBenchType] || TYPES[''];
        var t = currentTarget();
        condRows.textContent = '';
        condRows.appendChild(condRow('type', meta.name));
        condRows.appendChild(condRow('engine', t.engine));
        condRows.appendChild(condRow('model', t.model));
        condRows.appendChild(condRow('runs', 'n=' + t.runs));
        if (webBenchType) {
            condRows.appendChild(condRow('sampling', activePresetLabel()));
            if (['code', 'language'].indexOf(webBenchType) >= 0) {
                var judgeUrl = modeForm.querySelector('input[name="judge_url"]');
                var judgeOn = judgeUrl && judgeUrl.value.trim() !== '';
                condRows.appendChild(condRow('judge', judgeOn ? 'on' : 'offline', !judgeOn));
            }
        }
    }

    function setCondBadge(state) {
        if (!condBadge) return;
        condBadge.classList.remove('is-measuring', 'is-done');
        if (state === 'measuring') {
            condBadge.textContent = 'measuring';
            condBadge.classList.add('is-measuring');
        } else if (state === 'as run') {
            condBadge.textContent = 'as run';
            condBadge.classList.add('is-done');
        } else {
            condBadge.textContent = 'auto';
        }
    }

    /* ═══ Collapse / expand the form flow around a run ═══ */
    function collapseForms(pill, text, running) {
        summaryType.textContent = pill;
        summaryText.textContent = text;
        editRerunBtn.hidden = !!running;
        summaryBar.hidden = false;
        stdCard.style.display = 'none';
        modeCard.style.display = 'none';
    }

    function expandForms() {
        summaryBar.hidden = true;
        if (webBenchType) {
            modeCard.style.display = '';
            stdCard.style.display = 'none';
        } else {
            stdCard.style.display = '';
            modeCard.style.display = 'none';
        }
    }

    editRerunBtn.addEventListener('click', expandForms);

    /* ═══ Status panel: running / completed / error ═══ */
    var progressFill = null;
    var progressPct = null;
    var progressLog = null;
    var progressMeta = null;

    function showBenchProgress(metaText) {
        isRunning = true;
        logLines = [];
        statusCard.classList.remove('is-done', 'is-error');
        statusCard.classList.add('is-running');
        setCondBadge('measuring');
        statusDiv.textContent = '';

        var stack = document.createElement('div');
        stack.className = 'bn-status-stack';

        var row = document.createElement('div');
        row.className = 'bn-status-row is-running';
        var dot = document.createElement('span');
        dot.className = 'bn-dot-live';
        row.appendChild(dot);
        var title = document.createElement('span');
        title.className = 'bn-status-title';
        title.textContent = 'Running';
        row.appendChild(title);
        progressMeta = document.createElement('span');
        progressMeta.className = 'bn-status-meta';
        progressMeta.textContent = metaText || 'starting…';
        row.appendChild(progressMeta);
        progressPct = document.createElement('span');
        progressPct.className = 'bn-status-pct';
        progressPct.textContent = 'MEASURING';
        row.appendChild(progressPct);
        stack.appendChild(row);

        var bar = document.createElement('div');
        bar.className = 'bn-progress';
        progressFill = document.createElement('div');
        progressFill.className = 'bn-progress-fill is-striped';
        bar.appendChild(progressFill);
        stack.appendChild(bar);

        progressLog = document.createElement('div');
        progressLog.className = 'bn-log';
        var first = document.createElement('div');
        first.textContent = 'starting benchmark…';
        progressLog.appendChild(first);
        stack.appendChild(progressLog);

        var foot = document.createElement('div');
        foot.className = 'bn-status-foot';
        var footLeft = document.createElement('span');
        footLeft.textContent = 'live progress via SSE';
        foot.appendChild(footLeft);
        var footRight = document.createElement('span');
        footRight.style.marginLeft = 'auto';
        footRight.textContent = 'card renders on completion';
        foot.appendChild(footRight);
        stack.appendChild(foot);

        statusDiv.appendChild(stack);
    }

    function pushLog(msg) {
        if (!progressLog) return;
        if (logLines.length && logLines[logLines.length - 1] === msg) return;
        logLines.push(msg);
        if (logLines.length > 4) logLines = logLines.slice(-4);
        progressLog.textContent = '';
        logLines.forEach(function (line) {
            var d = document.createElement('div');
            d.textContent = line;
            progressLog.appendChild(d);
        });
    }

    function updateProgress(msg) {
        if (msg) pushLog(msg);
        /* Percent only when the message carries a "current/total" — the
           server sends free-form progress strings, not a percentage. */
        var m = /(\d+)\s*\/\s*(\d+)/.exec(msg || '');
        if (m && progressFill && progressPct) {
            var cur = parseInt(m[1], 10);
            var tot = parseInt(m[2], 10);
            if (tot > 0 && cur <= tot) {
                var pct = Math.round((cur / tot) * 100);
                progressFill.style.width = pct + '%';
                progressPct.textContent = pct + '%';
            }
        }
    }

    function showCompleted(metaText) {
        isRunning = false;
        statusCard.classList.remove('is-running', 'is-error');
        statusCard.classList.add('is-done');
        setCondBadge('as run');
        statusDiv.textContent = '';

        var stack = document.createElement('div');
        stack.className = 'bn-status-stack';
        var row = document.createElement('div');
        row.className = 'bn-status-row is-done';
        var dot = document.createElement('span');
        dot.className = 'bn-dot-done';
        row.appendChild(dot);
        var title = document.createElement('span');
        title.className = 'bn-status-title';
        title.textContent = 'Completed';
        row.appendChild(title);
        var meta = document.createElement('span');
        meta.className = 'bn-status-meta';
        meta.textContent = metaText || '';
        row.appendChild(meta);
        var pct = document.createElement('span');
        pct.className = 'bn-status-pct';
        pct.textContent = '100%';
        row.appendChild(pct);
        stack.appendChild(row);

        var bar = document.createElement('div');
        bar.className = 'bn-progress';
        var fill = document.createElement('div');
        fill.className = 'bn-progress-fill is-done';
        fill.style.width = '100%';
        bar.appendChild(fill);
        stack.appendChild(bar);

        if (logLines.length) {
            var log = document.createElement('div');
            log.className = 'bn-log';
            logLines.slice(-3).forEach(function (line) {
                var d = document.createElement('div');
                d.textContent = line;
                log.appendChild(d);
            });
            stack.appendChild(log);
        }
        statusDiv.appendChild(stack);
    }

    function showError(msg) {
        isRunning = false;
        statusCard.classList.remove('is-running', 'is-done');
        statusCard.classList.add('is-error');
        setCondBadge('auto');
        statusDiv.textContent = '';

        var banner = document.createElement('div');
        banner.className = 'bn-error-banner';
        var label = document.createElement('span');
        label.className = 'bn-error-label';
        label.textContent = 'Failed';
        banner.appendChild(label);
        var text = document.createElement('span');
        text.textContent = String(msg || 'unknown error');
        banner.appendChild(text);
        statusDiv.appendChild(banner);

        enableAllBenchButtons();
        expandForms();
    }

    /* ═══ Button state ═══ */
    function disableAllBenchButtons() {
        stdSubmit.disabled = true;
        if (modeSubmit) modeSubmit.disabled = true;
        quickBtn.disabled = true;
    }

    function enableAllBenchButtons() {
        stdSubmit.disabled = false;
        if (modeSubmit) modeSubmit.disabled = false;
        quickBtn.disabled = !!webBenchType;
    }

    /* ═══ Submit flows ═══ */
    function summaryFor(kind) {
        var t = currentTarget();
        if (kind === 'quick') {
            return { pill: 'throughput', text: 'quick bench · first loaded model · 1 prompt · n=1' };
        }
        var meta = TYPES[webBenchType] || TYPES[''];
        var bits = [t.engine, t.model, 'n=' + t.runs];
        if (webBenchType) bits.push('sampling: ' + activePresetLabel());
        return { pill: meta.name, text: bits.join(' · ') };
    }

    function launchRun(formData, summary) {
        disableAllBenchButtons();
        collapseForms(summary.pill, summary.text, true);
        showBenchProgress(summary.pill + ' · ' + summary.text);

        fetch('/bench/run', { method: 'POST', body: formData })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.error) {
                    showError(data.error);
                    return;
                }
                startBenchSSE();
            })
            .catch(function (err) {
                showError(err.message);
            });
    }

    quickBtn.addEventListener('click', function () {
        var formData = new FormData();
        formData.append('quick', 'on');
        launchRun(formData, summaryFor('quick'));
    });

    stdForm.addEventListener('submit', function (e) {
        e.preventDefault();
        launchRun(new FormData(stdForm), summaryFor('std'));
    });

    modeForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!webBenchType) return;
        var formData = new FormData(modeForm);
        formData.append('bench_type', webBenchType);
        if (modeModelSelect && modeModelSelect.value === MODE_CUSTOM) {
            /* The custom input has no name= — its value replaces the select's.
               Empty custom = auto, same server behavior as an empty field. */
            formData.set('mode_model', modeModelCustom ? modeModelCustom.value.trim() : '');
        }
        launchRun(formData, summaryFor('mode'));
    });

    /* ═══ Reset buttons ═══ */
    var stdReset = document.getElementById('std-reset');
    if (stdReset) {
        stdReset.addEventListener('click', function () {
            stdForm.reset();
            if (customInput) { customInput.style.display = 'none'; customInput.value = ''; }
            if (modelSelect) modelSelect.style.display = '';
            if (customToggle) customToggle.textContent = 'Type custom model name';
            if (compareGroup) compareGroup.style.display = 'none';
            if (enginesGroup) enginesGroup.style.display = '';
            if (modelGroup) modelGroup.style.display = '';
            if (paintStdSeg) paintStdSeg();
            updateStdAdvNote();
            updateEstimates();
            renderConditions();
        });
    }
    var modeReset = document.getElementById('mode-reset');
    if (modeReset) {
        modeReset.addEventListener('click', function () {
            modeForm.reset();
            if (modeEngineCards && modeEngineSelect) {
                var first = modeEngineCards.querySelector('button[data-engine]');
                modeEngineCards.querySelectorAll('button[data-engine]').forEach(function (x) {
                    x.classList.remove('active');
                });
                if (first) {
                    first.classList.add('active');
                    modeEngineSelect.value = first.dataset.engine;
                }
            }
            rebuildModeModelOptions();
            if (presetsBox) {
                presetsBox.querySelectorAll('.bn-preset').forEach(function (x) {
                    x.classList.toggle('active', (x.dataset.preset || '') === '');
                });
            }
            if (paintModeSeg) paintModeSeg();
            updateModeAdvNote();
            updateEstimates();
            renderConditions();
        });
    }

    /* ═══ SSE stream ═══ */
    function startBenchSSE() {
        var evtSource = new EventSource('/bench/stream');

        evtSource.onmessage = function (event) {
            var data = JSON.parse(event.data);

            if (data.progress) updateProgress(data.progress);

            if (data.error) {
                evtSource.close();
                showError(data.error);
                return;
            }

            if (data.done) {
                evtSource.close();
                showCompleted(data.progress || 'benchmark complete');
                enableAllBenchButtons();
                editRerunBtn.hidden = false;

                if (data.bench_type && data.result_run_id) {
                    /* Mode bench: render the result panel (card + report). */
                    renderModeResult(data);
                    return;
                }

                /* Standard bench: share panel + results table + charts. */
                renderShareSection(data);
                fetchAndRenderResults();
            }
        };

        evtSource.onerror = function () {
            evtSource.close();
            showError('Lost connection to benchmark stream');
        };
    }

    /* ═══ Mode bench result panel (1b) ═══ */
    function renderModeResult(data) {
        resultsDiv.textContent = '';
        var mdUrl = '/bench/report/' + data.result_run_id + '.md';
        var svgUrl = '/bench/card/' + data.result_run_id + '.svg';

        var panel = document.createElement('div');
        panel.className = 'bn-result fade-in';

        var head = document.createElement('div');
        head.className = 'bn-result-head';
        var title = document.createElement('span');
        title.className = 'bn-section-title';
        title.textContent = 'Result';
        head.appendChild(title);
        var tag = document.createElement('span');
        tag.className = 'bn-result-tag';
        tag.textContent = 'shareable card';
        head.appendChild(tag);
        var dim = document.createElement('span');
        dim.className = 'bn-result-dim';
        dim.textContent = data.bench_type + ' · run #' + data.result_run_id + ' · SVG';
        head.appendChild(dim);
        panel.appendChild(head);

        var img = document.createElement('img');
        img.src = svgUrl;
        img.alt = 'benchmark result card';
        img.className = 'bn-result-card-img';
        img.addEventListener('error', function () { img.remove(); });
        panel.appendChild(img);

        var actions = document.createElement('div');
        actions.className = 'bn-result-actions';
        var copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'bn-action-primary';
        copyBtn.textContent = 'Copy markdown';
        actions.appendChild(copyBtn);
        var mdLink = document.createElement('a');
        mdLink.className = 'bn-action';
        mdLink.textContent = 'Open .md';
        mdLink.href = mdUrl;
        mdLink.target = '_blank';
        actions.appendChild(mdLink);
        var svgLink = document.createElement('a');
        svgLink.className = 'bn-action';
        svgLink.textContent = 'Open .svg';
        svgLink.href = svgUrl;
        svgLink.target = '_blank';
        actions.appendChild(svgLink);
        var histLink = document.createElement('a');
        histLink.className = 'bn-history-link';
        histLink.textContent = 'View in History →';
        histLink.href = '/history';
        actions.appendChild(histLink);
        panel.appendChild(actions);

        var saved = document.createElement('div');
        saved.className = 'bn-result-saved';
        saved.textContent = 'saved · ' + mdUrl + ' · ' + svgUrl;
        panel.appendChild(saved);

        var details = document.createElement('details');
        details.className = 'bn-report-details';
        var summary = document.createElement('summary');
        summary.textContent = 'View markdown report';
        details.appendChild(summary);
        var pre = document.createElement('pre');
        pre.className = 'bn-report-pre';
        pre.textContent = 'Loading report…';
        details.appendChild(pre);
        panel.appendChild(details);

        resultsDiv.appendChild(panel);

        fetch(mdUrl)
            .then(function (res) { return res.ok ? res.text() : null; })
            .then(function (md) {
                pre.textContent = md || 'Report unavailable.';
                copyBtn.addEventListener('click', function () {
                    navigator.clipboard.writeText(md || '').then(function () {
                        copyBtn.textContent = 'Copied ✓';
                        copyBtn.classList.add('is-copied');
                        setTimeout(function () {
                            copyBtn.textContent = 'Copy markdown';
                            copyBtn.classList.remove('is-copied');
                        }, 1500);
                    });
                });
            })
            .catch(function () { pre.textContent = 'Report unavailable.'; });
    }

    /* ═══ Standard bench: results table + charts (unchanged logic) ═══ */
    function fetchAndRenderResults() {
        fetch('/api/benchmarks?hours=1')
            .then(function (res) { return res.json(); })
            .then(function (rows) {
                if (!rows || rows.length === 0) return;

                var engines = {};
                rows.forEach(function (r) {
                    if (!engines[r.engine]) {
                        engines[r.engine] = {
                            tok_s_sum: 0, ttft_sum: 0, ttft_client_sum: 0,
                            ttft_client_count: 0, count: 0, vram: r.vram_bytes
                        };
                    }
                    engines[r.engine].tok_s_sum += r.tok_per_sec;
                    engines[r.engine].ttft_sum += r.ttft_ms;
                    if (r.ttft_client_ms && r.ttft_client_ms > 0) {
                        engines[r.engine].ttft_client_sum += r.ttft_client_ms;
                        engines[r.engine].ttft_client_count++;
                    }
                    engines[r.engine].count++;
                });

                renderResultsTable(engines);
                renderResultsCharts(engines);
            })
            .catch(function () { /* ignore render errors */ });
    }

    function renderResultsTable(engines) {
        resultsDiv.textContent = '';

        var card = document.createElement('div');
        card.className = 'card fade-in';

        var title = document.createElement('h3');
        title.className = 'card-title';
        title.textContent = 'Results';
        card.appendChild(title);

        var wrapper = document.createElement('div');
        wrapper.className = 'overflow-x-auto';

        var table = document.createElement('table');
        table.className = 'results-table';

        var thead = document.createElement('thead');
        var headerRow = document.createElement('tr');
        ['Engine', 'Avg tok/s', 'Avg TTFT', 'Avg TTFT Client', 'VRAM'].forEach(function (text) {
            var th = document.createElement('th');
            th.textContent = text;
            th.className = text === 'Engine' ? 'text-left' : 'text-right';
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        var bestTokS = 0;
        var winnerName = '';
        Object.keys(engines).forEach(function (name) {
            var avg = engines[name].tok_s_sum / engines[name].count;
            if (avg > bestTokS) { bestTokS = avg; winnerName = name; }
        });

        var tbody = document.createElement('tbody');
        Object.keys(engines).forEach(function (name) {
            var e = engines[name];
            var avgTok = e.tok_s_sum / e.count;
            var avgTtft = e.ttft_sum / e.count;

            var tr = document.createElement('tr');
            if (name === winnerName && Object.keys(engines).length > 1) {
                tr.className = 'winner-row';
            }

            var tdName = document.createElement('td');
            tdName.className = 'font-medium';
            tdName.style.fontFamily = 'var(--font-sans)';
            tdName.textContent = name;
            tr.appendChild(tdName);

            var tdTok = document.createElement('td');
            tdTok.className = 'text-right font-mono';
            tdTok.textContent = avgTok.toFixed(1);
            tr.appendChild(tdTok);

            var tdTtft = document.createElement('td');
            tdTtft.className = 'text-right font-mono';
            tdTtft.textContent = avgTtft.toFixed(0) + ' ms';
            tr.appendChild(tdTtft);

            var tdTtftClient = document.createElement('td');
            tdTtftClient.className = 'text-right font-mono';
            if (e.ttft_client_count > 0) {
                var avgTtftClient = e.ttft_client_sum / e.ttft_client_count;
                if (Math.abs(avgTtftClient - avgTtft) > 10) {
                    tdTtftClient.textContent = avgTtftClient.toFixed(0) + ' ms';
                } else {
                    tdTtftClient.textContent = '—';
                }
            } else {
                tdTtftClient.textContent = '—';
            }
            tr.appendChild(tdTtftClient);

            var tdVram = document.createElement('td');
            tdVram.className = 'text-right font-mono';
            var vramText = formatBytes(e.vram);
            var nativeVramEngines = ['ollama', 'lmstudio'];
            if (e.vram > 0 && nativeVramEngines.indexOf(name) === -1) {
                vramText += ' (est.)';
            }
            tdVram.textContent = vramText;
            tr.appendChild(tdVram);

            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        wrapper.appendChild(table);
        card.appendChild(wrapper);
        resultsDiv.appendChild(card);
    }

    function renderResultsCharts(engines) {
        var names = Object.keys(engines);
        if (names.length === 0) return;

        var tokValues = names.map(function (n) {
            return parseFloat((engines[n].tok_s_sum / engines[n].count).toFixed(1));
        });
        var ttftValues = names.map(function (n) {
            return parseFloat((engines[n].ttft_sum / engines[n].count).toFixed(0));
        });
        var ttftClientValues = names.map(function (n) {
            if (engines[n].ttft_client_count > 0) {
                return parseFloat(
                    (engines[n].ttft_client_sum / engines[n].ttft_client_count).toFixed(0));
            }
            return 0;
        });
        var hasClientTtft = ttftClientValues.some(function (v) { return v > 0; });

        document.getElementById('bench-charts-row').style.display = '';

        if (benchTokChart) { benchTokChart.destroy(); benchTokChart = null; }
        if (benchTtftChart) { benchTtftChart.destroy(); benchTtftChart = null; }

        benchTokChart = createBarChart('bench-tok-chart', names, tokValues, {
            label: 'Throughput', unit: 'tok/s', height: 200,
        });
        if (hasClientTtft) {
            benchTtftChart = createBarChart('bench-ttft-chart', names, ttftValues, {
                label: 'TTFT', unit: 'ms', height: 200,
                extraSeries: [{ name: 'TTFT Client', data: ttftClientValues }],
            });
        } else {
            benchTtftChart = createBarChart('bench-ttft-chart', names, ttftValues, {
                label: 'TTFT', unit: 'ms', height: 200,
            });
        }
    }

    /* ═══ Share section (standard bench) ═══ */
    function renderShareSection(data) {
        var section = document.getElementById('bench-share-section');
        section.textContent = '';

        var cardImgUrl = data.card_png_url || data.card_svg_url;
        if (!cardImgUrl && !data.share_url) {
            section.style.display = 'none';
            return;
        }

        section.style.display = '';
        var panel = document.createElement('div');
        panel.className = 'bn-result fade-in';

        var head = document.createElement('div');
        head.className = 'bn-result-head';
        var title = document.createElement('span');
        title.className = 'bn-section-title';
        title.textContent = 'Share';
        head.appendChild(title);
        var tag = document.createElement('span');
        tag.className = 'bn-result-tag';
        tag.textContent = 'shareable card';
        head.appendChild(tag);
        panel.appendChild(head);

        if (cardImgUrl) {
            var img = document.createElement('img');
            img.src = cardImgUrl;
            img.alt = 'Benchmark card';
            img.className = 'bn-result-card-img';
            panel.appendChild(img);
        }

        if (data.share_url) {
            var urlRow = document.createElement('div');
            urlRow.className = 'share-url-row';

            var urlInput = document.createElement('input');
            urlInput.type = 'text';
            urlInput.readOnly = true;
            urlInput.value = data.share_url;
            urlInput.className = 'bn-input share-url-input';
            urlRow.appendChild(urlInput);

            var copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'bn-action-primary';
            copyBtn.textContent = 'Copy link';
            copyBtn.addEventListener('click', function () {
                /* Clipboard API requires HTTPS; fallback for HTTP */
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(data.share_url).then(function () {
                        copyBtn.textContent = 'Copied!';
                        setTimeout(function () { copyBtn.textContent = 'Copy link'; }, 2000);
                    });
                } else {
                    urlInput.select();
                    document.execCommand('copy');
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function () { copyBtn.textContent = 'Copy link'; }, 2000);
                }
            });
            urlRow.appendChild(copyBtn);
            panel.appendChild(urlRow);
        }

        var actions = document.createElement('div');
        actions.className = 'bn-result-actions';

        var downloadUrl = data.card_png_url || data.card_svg_url;
        if (downloadUrl) {
            var dlBtn = document.createElement('a');
            dlBtn.href = downloadUrl;
            dlBtn.download = '';
            dlBtn.className = 'bn-action-primary';
            dlBtn.textContent = data.card_png_url ? 'Download PNG' : 'Download SVG';
            actions.appendChild(dlBtn);
        }

        if (data.share_url) {
            var xBtn = document.createElement('a');
            xBtn.href = 'https://twitter.com/intent/tweet?url=' +
                encodeURIComponent(data.share_url) + '&text=' +
                encodeURIComponent('My local LLM benchmark results via asiai');
            xBtn.target = '_blank';
            xBtn.rel = 'noopener noreferrer';
            xBtn.className = 'bn-action';
            xBtn.textContent = 'Share on X';
            actions.appendChild(xBtn);

            var redditBtn = document.createElement('a');
            redditBtn.href = 'https://reddit.com/submit?url=' +
                encodeURIComponent(data.share_url) + '&title=' +
                encodeURIComponent('asiai benchmark results');
            redditBtn.target = '_blank';
            redditBtn.rel = 'noopener noreferrer';
            redditBtn.className = 'bn-action';
            redditBtn.textContent = 'Share on Reddit';
            actions.appendChild(redditBtn);
        }

        var exportBtn = document.createElement('a');
        exportBtn.href = '/bench/export';
        exportBtn.className = 'bn-action';
        exportBtn.textContent = 'Export JSON';
        actions.appendChild(exportBtn);
        panel.appendChild(actions);

        if (data.card_error) {
            var errP = document.createElement('div');
            errP.className = 'bn-note';
            errP.textContent = 'Card generation note: ' + data.card_error;
            panel.appendChild(errP);
        }

        section.appendChild(panel);
    }

    /* ═══ Cleanup: destroy charts when leaving page ═══ */
    function cleanupBench() {
        if (benchTokChart) { benchTokChart.destroy(); benchTokChart = null; }
        if (benchTtftChart) { benchTtftChart.destroy(); benchTtftChart = null; }
    }
    window.addEventListener('pagehide', cleanupBench);
    window.addEventListener('beforeunload', cleanupBench);

    /* ═══ Initial state ═══ */
    setWebBenchType('', document.querySelector('.bn-chip[data-btype=""]'));
    updateStdAdvNote();
    updateModeAdvNote();
    updateEstimates();
    renderConditions();

    /* A bench was already running when the page loaded (another tab or a
       reload mid-run): attach to the live stream instead of sitting blind. */
    if (root && root.dataset.benchRunning === '1') {
        disableAllBenchButtons();
        showBenchProgress('benchmark in progress (started elsewhere)');
        startBenchSSE();
    }
})();
