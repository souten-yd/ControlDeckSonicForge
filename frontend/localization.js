/* Localization Studio durable render helpers.
   This file is intentionally separate from the main workspace UI so the stable
   task/asset transport remains shared with the other SonicForge tools. */

async function renderLocalizationBatch(batchId, mode = "pending", lineIds = []) {
  try {
    const body = {
      task: "speech.localization.batch",
      input: {
        batch_id: batchId,
        locales: ["ja", "en"],
        mode,
        line_ids: lineIds,
      },
      profile: "localization-default",
      quality: "balanced",
      content_language: "auto",
      output: {format: "wav", sample_rate: null, channels: null},
      routing: {engine: null, model: null, device: "auto"},
      seed: null,
      project_output_grant: null,
    };
    const created = await api("/tasks", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify(body),
    });
    state.localizationBatchId = batchId;
    state.activeJob = created.job_id;
    const panel = document.getElementById("locResult");
    if (panel) panel.innerHTML = `<p><b>${escapeHtml(created.job_id)}</b> — queued</p>`;
    await showJob(created.job_id);
    await showLocalizationBatch(batchId);
  } catch (error) {
    alert(errorText(error));
  }
}

async function showLocalizationBatch(batchId) {
  try {
    const batch = await api(`/localization/batches/${encodeURIComponent(batchId)}`);
    const panel = document.getElementById("locResult");
    if (!panel) return;
    const rows = (batch.lines || []).map((line) => {
      const ja = line.outputs?.ja;
      const en = line.outputs?.en;
      const jaState = line.qa?.locales?.ja?.state || "pending";
      const enState = line.qa?.locales?.en?.state || "pending";
      return `<tr>
        <td>${escapeHtml(line.line_id)}</td>
        <td>${escapeHtml(line.character || "")}</td>
        <td>${escapeHtml(line.ja_text || "")}<br><small>${escapeHtml(jaState)}</small>${ja ? `<br><audio controls src="${apiUrl(`/assets/${encodeURIComponent(ja)}/content`)}"></audio>` : ""}</td>
        <td>${escapeHtml(line.en_text || "")}<br><small>${escapeHtml(enState)}</small>${en ? `<br><audio controls src="${apiUrl(`/assets/${encodeURIComponent(en)}/content`)}"></audio>` : ""}</td>
      </tr>`;
    }).join("");
    panel.innerHTML = `<div class="card">
      <div class="row">
        <b>${escapeHtml(batch.name)}</b>
        <span class="muted">${escapeHtml(batch.state)}</span>
      </div>
      <div class="row">
        <button onclick="renderLocalizationBatch('${escapeHtml(batch.id)}','failed')">Retry failed</button>
        <button onclick="renderLocalizationBatch('${escapeHtml(batch.id)}','changed')">Render changed</button>
        <button onclick="renderLocalizationBatch('${escapeHtml(batch.id)}','all')">Render all</button>
      </div>
      <div style="overflow:auto"><table><thead><tr><th>ID</th><th>Character</th><th>Japanese</th><th>English</th></tr></thead><tbody>${rows}</tbody></table></div>
    </div>`;
  } catch (error) {
    const panel = document.getElementById("locResult");
    if (panel) panel.textContent = errorText(error);
  }
}

window.createBatchFromRows = async function createBatchFromRowsDurable() {
  try {
    const rows = (document.getElementById("locRows")?.value || "")
      .split("\n")
      .map((value) => value.trim())
      .filter(Boolean)
      .map((line) => {
        const [line_id, character, ja_text, en_text] = line.split("|");
        return {
          line_id,
          character: character || null,
          ja_text: ja_text || null,
          en_text: en_text || null,
          voice_id: null,
        };
      });
    const created = await api("/localization/batches", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({
        name: document.getElementById("locName")?.value || "Dialogue",
        profile: {filename: "{line_id}_{locale}.wav"},
        lines: rows,
      }),
    });
    state.localizationBatchId = created.id;
    await showLocalizationBatch(created.id);
    await renderLocalizationBatch(created.id, "pending");
  } catch (error) {
    alert(errorText(error));
  }
};

const sonicForgeBaseShowJob = window.showJob;
if (typeof sonicForgeBaseShowJob === "function") {
  window.showJob = async function showJobWithLocalization(id) {
    await sonicForgeBaseShowJob(id);
    if (!state.localizationBatchId) return;
    try {
      const job = await api(`/jobs/${encodeURIComponent(id)}`);
      if (!["queued", "running"].includes(job.state)) {
        await showLocalizationBatch(state.localizationBatchId);
      }
    } catch {
      // The main job renderer owns transport errors.
    }
  };
}
