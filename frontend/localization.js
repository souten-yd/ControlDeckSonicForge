/* ローカライズスタジオ。
   本体の task/asset 転送は app.js と共有し、こちらは「行を編む」ことだけを持つ。
   1 行ずつ設定を繰り返さずに、日英のセリフを同じ条件でまとめて作れるようにする。 */

const LOCALIZATION_TEXT = {
  ja: {
    rowsLabel: "セリフの行",
    rowsPlaceholder: "hello|主人公|こんにちは|Hello\nbye|主人公|またね|See you",
    voiceByCharacter: "キャラクターごとのボイス",
    voiceByCharacterHint: "行を書くと、出てきたキャラクターがここに並びます。まとめて声を割り当てられます。",
    parsed: "読み取った行",
    batchId: "バッチID",
    openBatchHint: "生成済みのバッチIDを入れると、その表をもう一度開けます。",
    open: "開く",
    qaNotChecked: "未確認",
    qaPassed: "確認済み",
    qaFailed: "要確認",
    pending: "未生成",
    rendering: "生成中",
    done: "完了",
    failed: "失敗",
    queued: "待機中",
    draft: "下書き",
    complete: "生成済み",
    partial: "一部未生成",
    renderingBatch: "生成しています…",
    exportLine: "書き出す",
  },
  en: {
    rowsLabel: "Dialogue rows",
    rowsPlaceholder: "hello|Hero|こんにちは|Hello\nbye|Hero|またね|See you",
    voiceByCharacter: "Voice per character",
    voiceByCharacterHint: "Characters found in your rows appear here so you can assign voices in one place.",
    parsed: "Rows parsed",
    batchId: "Batch ID",
    openBatchHint: "Paste a batch ID to reopen its table.",
    open: "Open",
    qaNotChecked: "Not checked",
    qaPassed: "Checked",
    qaFailed: "Needs review",
    pending: "Pending",
    rendering: "Rendering",
    done: "Done",
    failed: "Failed",
    queued: "Waiting",
    draft: "Draft",
    complete: "Rendered",
    partial: "Partly rendered",
    renderingBatch: "Rendering…",
    exportLine: "Export",
  },
};

const lt = (key) => LOCALIZATION_TEXT[state.locale]?.[key] ?? LOCALIZATION_TEXT.ja[key] ?? key;

function localizationState() {
  if (!state.localization) {
    state.localization = {
      name: "Dialogue",
      filename: "{line_id}_{locale}.wav",
      rows: "",
      locales: ["ja", "en"],
      voiceByCharacter: {},
      batchId: "",
      batch: null,
      error: "",
      note: "",
    };
    try {
      const saved = localStorage.getItem("sonicforge.localizationBatch");
      if (saved) state.localization.batchId = saved;
    } catch { /* 覚えられなくても、IDを貼れば開ける */ }
  }
  return state.localization;
}

/* 「ID | キャラ | 日本語 | English」を基本に、CSV とタブ区切りも受ける。
   区切りを 1 つに強制すると、表計算から貼っただけで全部 1 列になる。 */
function parseLocalizationRows(value) {
  const seen = new Set();
  return String(value || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.includes("|") ? line.split("|") : line.split(/\t|,/);
      const [lineId, character, ja, en] = parts.map((part) => String(part || "").trim());
      return {
        line_id: lineId,
        character: character || null,
        ja_text: ja || null,
        en_text: en || null,
      };
    })
    .filter((row) => {
      if (!row.line_id || seen.has(row.line_id)) return false;
      if (!row.ja_text && !row.en_text) return false;
      seen.add(row.line_id);
      return true;
    });
}

function localizationCharacters(rows) {
  return [...new Set(rows.map((row) => row.character).filter(Boolean))];
}

/* 表に出る言葉は、状態の語彙を小さく保つ（UX 仕様 §20）。サーバ側の生の語を
   そのまま出すと、同じ意味の言葉が日英で混ざって並ぶ。 */
function lineStatusLabel(value) {
  return {
    pending: lt("pending"), queued: lt("queued"), running: lt("rendering"),
    rendering: lt("rendering"), succeeded: lt("done"), done: lt("done"),
    complete: lt("done"), failed: lt("failed"),
  }[value] || value || lt("pending");
}

function batchStateLabel(value) {
  return {
    draft: lt("draft"), queued: lt("queued"), running: lt("rendering"),
    rendering: lt("rendering"), complete: lt("complete"), completed: lt("complete"),
    partial: lt("partial"), failed: lt("failed"),
  }[value] || value || "";
}

function qaLabel(value) {
  return {
    not_checked: lt("qaNotChecked"), passed: lt("qaPassed"), failed: lt("qaFailed"),
    succeeded: lt("qaPassed"), pending: lt("pending"), queued: lt("queued"),
    running: lt("rendering"),
  }[value] || value || lt("qaNotChecked");
}

window.renderLocalizationStudio = function renderLocalizationStudio() {
  const panel = byId("localization-panel");
  if (!panel || state.task !== "localization") return;
  const value = localizationState();
  const rows = parseLocalizationRows(value.rows);
  const characters = localizationCharacters(rows);

  panel.replaceChildren();

  const editor = document.createElement("div");
  editor.className = "panel";

  const title = document.createElement("p");
  title.className = "field-label";
  title.textContent = t("localizationTitle");
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = t("localizationHint");
  editor.append(title, hint);

  const head = document.createElement("div");
  head.className = "form-row";
  const name = document.createElement("input");
  name.type = "text";
  name.maxLength = 160;
  name.value = value.name;
  name.oninput = () => { value.name = name.value; };
  head.append(labelled(t("batchName"), name));
  const filename = document.createElement("input");
  filename.type = "text";
  filename.maxLength = 240;
  filename.value = value.filename;
  filename.oninput = () => { value.filename = filename.value; };
  head.append(labelled(t("filenamePattern"), filename));
  editor.append(head);

  const rowsArea = document.createElement("textarea");
  rowsArea.rows = 8;
  rowsArea.value = value.rows;
  rowsArea.placeholder = lt("rowsPlaceholder");
  rowsArea.oninput = () => {
    value.rows = rowsArea.value;
    const current = parseLocalizationRows(value.rows);
    byId("localization-parsed").textContent = `${lt("parsed")}: ${current.length}`;
    renderLocalizationCharacters(localizationCharacters(current));
    const createButton = byId("localization-create");
    if (createButton) createButton.disabled = current.length === 0;
  };
  editor.append(labelled(lt("rowsLabel"), rowsArea));
  const parsed = document.createElement("p");
  parsed.id = "localization-parsed";
  parsed.className = "hint";
  parsed.textContent = `${lt("parsed")}: ${rows.length}`;
  editor.append(parsed);

  const localesLabel = document.createElement("p");
  localesLabel.className = "section-label";
  localesLabel.textContent = t("locales");
  const localeChips = document.createElement("div");
  localeChips.className = "chips";
  editor.append(localesLabel, localeChips);
  renderChips(localeChips, LANGUAGES.slice(1), value.locales, (id) => {
    const next = new Set(value.locales);
    next.has(id) ? next.delete(id) : next.add(id);
    value.locales = [...next];
    if (!value.locales.length) value.locales = [id];
    window.renderLocalizationStudio();
  }, {multi: true});

  const charactersBlock = document.createElement("div");
  charactersBlock.id = "localization-characters";
  charactersBlock.className = "panel-fields";
  editor.append(charactersBlock);

  if (value.error) {
    const error = document.createElement("p");
    error.className = "error";
    error.textContent = value.error;
    editor.append(error);
  }
  if (value.note) {
    const note = document.createElement("p");
    note.className = "hint";
    note.setAttribute("role", "status");
    note.textContent = value.note;
    editor.append(note);
  }

  const create = document.createElement("button");
  create.type = "button";
  create.id = "localization-create";
  create.className = "primary";
  create.textContent = t("createBatch");
  create.disabled = rows.length === 0;
  create.onclick = () => void createLocalizationBatch();
  editor.append(create);

  const openRow = document.createElement("div");
  openRow.className = "form-row";
  const batchInput = document.createElement("input");
  batchInput.type = "text";
  batchInput.maxLength = 200;
  batchInput.value = value.batchId;
  batchInput.placeholder = "loc:…";
  batchInput.oninput = () => { value.batchId = batchInput.value.trim(); };
  openRow.append(labelled(lt("batchId"), batchInput));
  const open = document.createElement("button");
  open.type = "button";
  open.textContent = lt("open");
  open.onclick = () => void showLocalizationBatch(value.batchId);
  openRow.append(open);
  const openHint = document.createElement("p");
  openHint.className = "hint";
  openHint.textContent = lt("openBatchHint");
  editor.append(openRow, openHint);

  panel.append(editor);
  renderLocalizationCharacters(characters);
  if (value.batch) panel.append(localizationTable(value.batch));
};

/* 行に出てきたキャラクターにだけ声を割り当てられるようにする。何百行あっても
   設定を繰り返さずに済むのが、この画面の存在意義である。 */
function renderLocalizationCharacters(characters) {
  const block = byId("localization-characters");
  if (!block) return;
  const value = localizationState();
  block.replaceChildren();
  if (!characters.length) return;
  const label = document.createElement("p");
  label.className = "section-label";
  label.textContent = lt("voiceByCharacter");
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = lt("voiceByCharacterHint");
  block.append(label, hint);
  for (const character of characters) {
    const select = selectNode(`localization-voice-${character}`, [
      {value: "", text: t("builtInVoice")},
      ...state.voices.map((voice) => ({value: voice.id, text: voice.name})),
    ]);
    select.value = value.voiceByCharacter[character] || "";
    select.onchange = () => { value.voiceByCharacter[character] = select.value; };
    block.append(labelled(character, select));
  }
}

function localizationTable(batch) {
  const value = localizationState();
  const card = document.createElement("div");
  card.className = "panel";

  const head = document.createElement("div");
  head.className = "view-head";
  const title = document.createElement("p");
  title.className = "field-label";
  title.textContent = `${batch.name} · ${batchStateLabel(batch.state)}`;
  head.append(title);
  card.append(head);

  const actions = document.createElement("div");
  actions.className = "actions";
  for (const [mode, key] of [["pending", "renderPending"], ["failed", "renderFailed"],
    ["changed", "renderChanged"], ["all", "renderAll"]]) {
    const button = document.createElement("button");
    button.type = "button";
    if (mode === "pending") button.className = "cta-secondary";
    button.textContent = t(key);
    button.onclick = () => void renderLocalizationBatch(batch.id, mode);
    actions.append(button);
  }
  card.append(actions);

  const lines = batch.lines || [];
  if (!lines.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = t("noLines");
    card.append(empty);
    return card;
  }

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.className = "lines";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const text of [t("lineId"), t("character"), t("status"), "日本語", "English"]) {
    const cell = document.createElement("th");
    cell.textContent = text;
    headRow.append(cell);
  }
  thead.append(headRow);
  const body = document.createElement("tbody");
  for (const line of lines) {
    const row = document.createElement("tr");
    row.append(
      cell("name", t("lineId"), line.line_id),
      cell("", t("character"), line.character || "—"),
      cell("", t("status"), `${lineStatusLabel(line.status)} · ${qaLabel(line.qa?.state)}`),
      localeCell(line, "ja"),
      localeCell(line, "en"),
    );
    body.append(row);
  }
  table.append(thead, body);
  wrap.append(table);
  card.append(wrap);
  if (value.note) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = value.note;
    card.append(note);
  }
  return card;
}

function cell(className, label, text) {
  const node = document.createElement("td");
  if (className) node.className = className;
  node.dataset.label = label;
  node.textContent = text;
  return node;
}

function localeCell(line, locale) {
  const node = document.createElement("td");
  node.dataset.label = locale === "ja" ? "日本語" : "English";
  const wrap = document.createElement("div");
  wrap.className = "locale-cell";
  const text = document.createElement("span");
  text.textContent = (locale === "ja" ? line.ja_text : line.en_text) || "—";
  wrap.append(text);
  const state_ = line.qa?.locales?.[locale]?.state;
  if (state_) {
    const badge = document.createElement("small");
    badge.className = "hint";
    badge.textContent = qaLabel(state_);
    wrap.append(badge);
  }
  const assetId = line.outputs?.[locale];
  if (assetId) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "none";
    audio.src = apiUrl(`/assets/${encodeURIComponent(assetId)}/content`);
    wrap.append(audio);
  }
  node.append(wrap);
  return node;
}

async function createLocalizationBatch() {
  const value = localizationState();
  const rows = parseLocalizationRows(value.rows).map((row) => ({
    ...row,
    voice_id: (row.character && value.voiceByCharacter[row.character]) || null,
  }));
  value.error = "";
  value.note = "";
  try {
    const created = await jsonPost("/localization/batches", {
      name: value.name || "Dialogue",
      profile: {filename: value.filename || "{line_id}_{locale}.wav"},
      lines: rows,
    });
    value.batchId = created.id;
    try { localStorage.setItem("sonicforge.localizationBatch", created.id); } catch { /* 任意 */ }
    await showLocalizationBatch(created.id);
    await renderLocalizationBatch(created.id, "pending");
  } catch (error) {
    value.error = errorText(error);
    window.renderLocalizationStudio();
  }
}

async function showLocalizationBatch(batchId) {
  const value = localizationState();
  if (!batchId) return;
  try {
    value.batch = await api(`/localization/batches/${encodeURIComponent(batchId)}`);
    value.batchId = batchId;
    value.error = "";
  } catch (error) {
    value.batch = null;
    value.error = errorText(error);
  }
  window.renderLocalizationStudio();
}

async function renderLocalizationBatch(batchId, mode = "pending", lineIds = []) {
  const value = localizationState();
  value.error = "";
  try {
    const created = await jsonPost("/tasks", {
      task: "speech.localization.batch",
      input: {batch_id: batchId, locales: value.locales, mode, line_ids: lineIds},
      profile: "localization-default",
      quality: state.form.quality || "balanced",
      content_language: "auto",
      output: {format: "wav", sample_rate: null, channels: null},
      routing: {engine: null, model: null, device: "auto"},
      seed: null,
      project_output_grant: null,
    });
    state.activeJob = created.job_id;
    value.note = lt("renderingBatch");
    window.renderLocalizationStudio();
    await showJob(created.job_id);
    value.note = "";
    await showLocalizationBatch(batchId);
  } catch (error) {
    value.error = errorText(error);
    window.renderLocalizationStudio();
  }
}

/* 生成が終わるたびに表を引き直す。ジョブ側の描画は app.js が持つので、
   ここでは「終わったら表を更新する」だけを足す。 */
const sonicForgeBaseShowJob = window.showJob;
if (typeof sonicForgeBaseShowJob === "function") {
  window.showJob = async function showJobWithLocalization(id) {
    await sonicForgeBaseShowJob(id);
    const value = state.localization;
    if (!value?.batchId || state.task !== "localization") return;
    try {
      const job = await api(`/jobs/${encodeURIComponent(id)}`);
      if (!["queued", "running"].includes(job.state)) await showLocalizationBatch(value.batchId);
    } catch { /* ジョブ表示の失敗は app.js が持つ */ }
  };
}
