const state = { applications: [], profile: null, activeView: "dashboard", selectedApplication: null };
const config = window.CAREER_CONFIG;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Error ${response.status}`);
  }
  return response.json();
}

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, 4200);
}

const titles = {
  dashboard: ["Candidaturas", "Tu búsqueda, en perspectiva"],
  "new-application": ["Nueva candidatura", "Convierte una oferta en documentos"],
  profile: ["Perfil profesional", "Tu experiencia, siempre actualizada"],
};

function navigate(view) {
  state.activeView = view;
  $$(".view").forEach(node => node.classList.toggle("active", node.id === `view-${view}`));
  $$(".nav-item").forEach(node => node.classList.toggle("active", node.dataset.view === view));
  $("#page-eyebrow").textContent = titles[view][0];
  $("#page-title").textContent = titles[view][1];
  document.body.classList.remove("menu-open");
  if (view === "profile" && !state.profile) loadProfile();
  history.replaceState(null, "", `#${view}`);
}

function metricCard(label, value, note) {
  return `<article class="metric-card"><p>${escapeHtml(label)}</p><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`;
}

function renderMetrics() {
  const apps = state.applications;
  const interviews = apps.filter(item => item.interviews?.length || item.status.includes("Entrevista")).length;
  const offers = apps.filter(item => item.status === "Oferta").length;
  const applied = apps.filter(item => !["Nueva", "Analizada", "Documentos listos"].includes(item.status)).length;
  const average = apps.length ? Math.round(apps.reduce((sum, item) => sum + (item.fit_score || 0), 0) / apps.length) : 0;
  $("#metrics").innerHTML = [
    metricCard("Candidaturas", apps.length, "registradas en total"),
    metricCard("Enviadas", applied, apps.length ? `${Math.round(applied / apps.length * 100)}% del pipeline` : "sin candidaturas aún"),
    metricCard("Entrevistas", interviews, applied ? `${Math.round(interviews / applied * 100)}% de respuesta` : "esperando primeras respuestas"),
    metricCard("Afinidad media", `${average}%`, `${offers} oferta${offers === 1 ? "" : "s"} recibida${offers === 1 ? "" : "s"}`),
  ].join("");
}

function dateLabel(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-FR", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

function renderApplications() {
  const search = $("#application-search").value.trim().toLowerCase();
  const filter = $("#status-filter").value;
  const visible = state.applications.filter(item => {
    const matchesText = `${item.company} ${item.role}`.toLowerCase().includes(search);
    return matchesText && (!filter || item.status === filter);
  });
  $("#applications-empty").hidden = state.applications.length !== 0;
  $(".table-wrap").hidden = state.applications.length === 0;
  $("#applications-body").innerHTML = visible.map(item => `
    <tr>
      <td class="company-cell"><strong>${escapeHtml(item.company || "Empresa por identificar")}</strong><small>${escapeHtml(item.role || "Puesto")}</small></td>
      <td><span class="fit-pill">${Math.round(item.fit_score || 0)}%</span></td>
      <td><select class="status-select" data-status-id="${item.id}">${config.statuses.map(status => `<option ${status === item.status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select></td>
      <td>${dateLabel(item.created_at)}</td>
      <td><div class="doc-links">${item.has_cv ? `<a class="doc-link" href="/api/applications/${item.id}/cv">CV</a>` : ""}${item.has_letter ? `<a class="doc-link" href="/api/applications/${item.id}/letter">Carta</a>` : ""}</div></td>
      <td><button class="text-button" data-detail-id="${item.id}">Ver →</button></td>
    </tr>`).join("");
  $$('[data-status-id]').forEach(select => select.addEventListener("change", async event => {
    try {
      const updated = await api(`/api/applications/${event.target.dataset.statusId}`, { method: "PATCH", body: JSON.stringify({ status: event.target.value }) });
      state.applications = state.applications.map(item => item.id === updated.id ? updated : item);
      renderMetrics(); toast("Estado actualizado");
    } catch (error) { toast(error.message, true); }
  }));
  $$('[data-detail-id]').forEach(button => button.addEventListener("click", () => openDrawer(Number(button.dataset.detailId))));
}

async function loadApplications() {
  try {
    state.applications = await api("/api/applications");
    renderMetrics(); renderApplications();
  } catch (error) { toast(error.message, true); }
}

function renderGenerationResult(item) {
  const analysis = item.analysis || {};
  const result = $("#generation-result");
  result.hidden = false;
  result.innerHTML = `
    <div class="result-head"><div><p class="eyebrow">Documentos listos</p><h2>${escapeHtml(item.company)} · ${escapeHtml(item.role)}</h2><p>${escapeHtml(analysis.fit_summary || "Candidatura creada correctamente.")}</p></div><div class="score-ring" style="--score:${Math.round(item.fit_score || 0)}%"><strong>${Math.round(item.fit_score || 0)}%</strong></div></div>
    <div class="result-grid"><div class="result-box"><h3>Coincidencias principales</h3><div class="chip-list">${(analysis.matched_skills || []).slice(0,12).map(value => `<span class="chip">${escapeHtml(value)}</span>`).join("") || '<span class="chip">Perfil analizado</span>'}</div></div><div class="result-box"><h3>Brechas detectadas</h3><div class="chip-list">${(analysis.missing_skills || []).slice(0,10).map(value => `<span class="chip">${escapeHtml(value)}</span>`).join("") || '<span class="chip">Sin brechas explícitas</span>'}</div></div></div>
    <div class="download-row"><a class="download-card" href="/api/applications/${item.id}/cv"><div><strong>Curriculum vitae</strong><p>PDF · LaTeX · una página</p></div><span>Descargar ↓</span></a><a class="download-card" href="/api/applications/${item.id}/letter"><div><strong>Carta de motivación</strong><p>PDF · idioma ${escapeHtml(item.language.toUpperCase())}</p></div><span>Descargar ↓</span></a></div>`;
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitOffer(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  const button = $("#generate-button");
  const original = button.innerHTML;
  button.disabled = true; button.innerHTML = "<span>Analizando y compilando…</span><span>◌</span>";
  try {
    const item = await api("/api/applications/generate", { method: "POST", body: JSON.stringify(payload) });
    state.applications.unshift(item);
    renderMetrics(); renderApplications(); renderGenerationResult(item);
    toast("CV y carta generados correctamente");
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; button.innerHTML = original; }
}

function localizedInputs(basePath, value, multiline = false) {
  return `<div class="language-fields">${["es","en","fr"].map(lang => `<label>${lang.toUpperCase()}${multiline ? `<textarea data-profile-path="${basePath}.${lang}" data-type="lines">${escapeHtml((value?.[lang] || []).join("\n"))}</textarea>` : `<input data-profile-path="${basePath}.${lang}" value="${escapeHtml(value?.[lang] || "")}">`}</label>`).join("")}</div>`;
}

function renderProfile() {
  const data = state.profile;
  const editor = $("#profile-editor");
  const person = data.person || {};
  editor.innerHTML = `
    <section class="profile-section"><div class="profile-section-head"><h3>Identidad profesional</h3><span>Datos de contacto y posicionamiento</span></div><div class="profile-fields">
      <label>Nombre<input data-profile-path="person.name" value="${escapeHtml(person.name)}"></label>
      <label>Email<input data-profile-path="person.email" value="${escapeHtml(person.email)}"></label>
      <label>Teléfono<input data-profile-path="person.phoneDisplay" value="${escapeHtml(person.phoneDisplay)}"></label>
      <label>GitHub<input data-profile-path="person.githubUrl" value="${escapeHtml(person.githubUrl)}"></label>
      <label>LinkedIn<input data-profile-path="person.linkedinUrl" value="${escapeHtml(person.linkedinUrl)}"></label>
      <label>Puestos objetivo<input data-profile-path="preferences.target_roles" data-type="csv" value="${escapeHtml((data.preferences?.target_roles || []).join(", "))}"></label>
    </div><div class="profile-card"><h4>Título profesional</h4>${localizedInputs("person.role", person.role)}</div><div class="profile-card"><h4>Ubicación</h4>${localizedInputs("person.location", person.location)}</div></section>
    <section class="profile-section"><div class="profile-section-head"><h3>Experiencia</h3><span>${data.experiences?.length || 0} experiencias importadas</span></div><div class="profile-list">${(data.experiences || []).map((item, index) => `<article class="profile-card"><h4>${escapeHtml(item.org)} · ${escapeHtml(item.id)}</h4><div class="profile-fields"><label>Organización<input data-profile-path="experiences.${index}.org" value="${escapeHtml(item.org)}"></label><label>Fecha ES<input data-profile-path="experiences.${index}.dateLabel.es" value="${escapeHtml(item.dateLabel?.es)}"></label><label>Fecha EN<input data-profile-path="experiences.${index}.dateLabel.en" value="${escapeHtml(item.dateLabel?.en)}"></label></div><h4>Título</h4>${localizedInputs(`experiences.${index}.title`, item.title)}<h4>Logros y responsabilidades</h4>${localizedInputs(`experiences.${index}.bullets`, item.bullets, true)}</article>`).join("")}</div></section>
    <section class="profile-section"><div class="profile-section-head"><h3>Formación</h3><span>${data.education?.length || 0} programas</span></div><div class="profile-list">${(data.education || []).map((item, index) => `<article class="profile-card"><h4>${escapeHtml(item.org)}</h4><div class="profile-fields"><label>Institución<input data-profile-path="education.${index}.org" value="${escapeHtml(item.org)}"></label><label>Fecha ES<input data-profile-path="education.${index}.dateLabel.es" value="${escapeHtml(item.dateLabel?.es)}"></label><label>Fecha EN<input data-profile-path="education.${index}.dateLabel.en" value="${escapeHtml(item.dateLabel?.en)}"></label></div><h4>Diploma</h4>${localizedInputs(`education.${index}.degree`, item.degree)}<h4>Detalles</h4>${localizedInputs(`education.${index}.bullets`, item.bullets, true)}</article>`).join("")}</div></section>
    <section class="profile-section"><div class="profile-section-head"><h3>Tecnologías y competencias</h3><span>Selección automática por oferta</span></div><div class="profile-fields">${(data.skills || []).map((group, index) => `<label>${escapeHtml(group.name?.es || group.name?.en)}<textarea rows="5" data-profile-path="skills.${index}.items" data-type="csv">${escapeHtml((group.items || []).join(", "))}</textarea></label>`).join("")}</div></section>
    <section class="profile-section"><div class="profile-section-head"><h3>Otros datos importados</h3><span>Editables desde JSON avanzado</span></div><div class="profile-fields"><div><strong>Proyectos</strong><p>${countProjects(data.projects)} proyectos académicos</p></div><div><strong>Certificaciones</strong><p>${countCertifications(data.certifications)} credenciales</p></div><div><strong>Idiomas</strong><p>${(data.languages || []).map(x => `${x.name?.es}: ${x.level?.es}`).join(" · ")}</p></div></div></section>`;
  $("#profile-json").value = JSON.stringify(data, null, 2);
}

function countProjects(catalog = []) { return catalog.reduce((sum, institution) => sum + (institution.courses || []).reduce((courseSum, course) => courseSum + (course.items || []).length, 0), 0); }
function countCertifications(certifications = {}) { return (certifications.groups || []).reduce((sum, group) => sum + (group.items || []).length, 0); }

function setDeep(target, path, value) {
  const parts = path.split(".");
  let cursor = target;
  parts.slice(0, -1).forEach(part => { cursor = cursor[Number.isNaN(Number(part)) ? part : Number(part)]; });
  cursor[parts.at(-1)] = value;
}

async function loadProfile() {
  $("#profile-loading").hidden = false;
  try { const response = await api("/api/profile"); state.profile = response.data; renderProfile(); }
  catch (error) { toast(error.message, true); }
  finally { $("#profile-loading").hidden = true; }
}

async function saveProfile() {
  try {
    if (!$("#advanced-editor").hidden) {
      state.profile = JSON.parse($("#profile-json").value);
    } else {
      $$('[data-profile-path]').forEach(input => {
        let value = input.value;
        if (input.dataset.type === "lines") value = value.split("\n").map(line => line.trim()).filter(Boolean);
        if (input.dataset.type === "csv") value = value.split(",").map(part => part.trim()).filter(Boolean);
        setDeep(state.profile, input.dataset.profilePath, value);
      });
    }
    const response = await api("/api/profile", { method: "PUT", body: JSON.stringify({ data: state.profile }) });
    state.profile = response.data; renderProfile(); toast("Perfil profesional actualizado");
  } catch (error) { toast(error.message, true); }
}

async function resetProfile() {
  if (!confirm("¿Restaurar el perfil con la última importación del portafolio?")) return;
  try { const response = await api("/api/profile/reset", { method: "POST" }); state.profile = response.data; renderProfile(); toast("Perfil restaurado"); }
  catch (error) { toast(error.message, true); }
}

function openDrawer(id) {
  const item = state.applications.find(value => value.id === id);
  if (!item) return;
  state.selectedApplication = item;
  const analysis = item.analysis || {};
  $("#drawer-content").innerHTML = `<div class="drawer-title"><p class="eyebrow">Candidatura #${item.id}</p><h2>${escapeHtml(item.company)}</h2><p>${escapeHtml(item.role)}</p></div>
    <div class="download-row"><a class="download-card" href="/api/applications/${item.id}/cv"><strong>CV</strong><span>↓</span></a><a class="download-card" href="/api/applications/${item.id}/letter"><strong>Carta</strong><span>↓</span></a></div>
    <section class="drawer-section"><h3>Seguimiento</h3><div class="drawer-form"><label>Estado<select id="drawer-status">${config.statuses.map(status => `<option ${status === item.status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select></label><label>Fecha de aplicación<input id="drawer-applied" type="date" value="${item.applied_at || ""}"></label><label>Próximo seguimiento<input id="drawer-followup" type="date" value="${item.next_follow_up || ""}"></label><label>Contacto<input id="drawer-contact" value="${escapeHtml(item.contact_name)}"></label><label class="full">Notas<textarea id="drawer-notes" rows="4">${escapeHtml(item.notes)}</textarea></label><button class="button primary full" id="save-application-detail">Guardar seguimiento</button></div></section>
    <section class="drawer-section"><h3>Coincidencias</h3><div class="chip-list">${(analysis.matched_skills || []).map(value => `<span class="chip">${escapeHtml(value)}</span>`).join("")}</div></section>
    <section class="drawer-section"><h3>Registrar entrevista</h3><div class="drawer-form"><label>Tipo<select id="interview-kind"><option>Entrevista RH</option><option>Entrevista técnica</option><option>Prueba técnica</option><option>Entrevista final</option></select></label><label>Fecha<input id="interview-date" type="datetime-local"></label><label class="full">Entrevistador<input id="interviewer"></label><button class="button secondary full" id="add-interview">Añadir entrevista</button></div></section>`;
  $("#drawer-backdrop").hidden = false; $("#detail-drawer").classList.add("open"); $("#detail-drawer").setAttribute("aria-hidden", "false");
  $("#save-application-detail").addEventListener("click", saveApplicationDetail);
  $("#add-interview").addEventListener("click", addInterview);
}

function closeDrawer() { $("#detail-drawer").classList.remove("open"); $("#detail-drawer").setAttribute("aria-hidden", "true"); setTimeout(() => { $("#drawer-backdrop").hidden = true; }, 220); }

async function saveApplicationDetail() {
  const id = state.selectedApplication.id;
  const payload = { status: $("#drawer-status").value, applied_at: $("#drawer-applied").value || null, next_follow_up: $("#drawer-followup").value || null, contact_name: $("#drawer-contact").value, notes: $("#drawer-notes").value };
  try { const updated = await api(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(payload) }); state.applications = state.applications.map(item => item.id === id ? updated : item); state.selectedApplication = updated; renderApplications(); renderMetrics(); toast("Seguimiento guardado"); }
  catch (error) { toast(error.message, true); }
}

async function addInterview() {
  const id = state.selectedApplication.id;
  const payload = { kind: $("#interview-kind").value, scheduled_at: $("#interview-date").value || null, interviewer: $("#interviewer").value };
  try { await api(`/api/applications/${id}/interviews`, { method: "POST", body: JSON.stringify(payload) }); await loadApplications(); closeDrawer(); toast("Entrevista registrada"); }
  catch (error) { toast(error.message, true); }
}

document.addEventListener("DOMContentLoaded", () => {
  $$("[data-view]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.view)));
  $$("[data-view-target]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.viewTarget)));
  $("#mobile-menu").addEventListener("click", () => document.body.classList.toggle("menu-open"));
  $("#application-search").addEventListener("input", renderApplications);
  $("#status-filter").addEventListener("change", renderApplications);
  $("#offer-form").addEventListener("submit", submitOffer);
  $("#save-profile").addEventListener("click", saveProfile);
  $("#reset-profile").addEventListener("click", resetProfile);
  $("#toggle-advanced").addEventListener("click", () => { const node = $("#advanced-editor"); node.hidden = !node.hidden; if (!node.hidden) $("#profile-json").value = JSON.stringify(state.profile, null, 2); });
  $("#drawer-close").addEventListener("click", closeDrawer); $("#drawer-backdrop").addEventListener("click", closeDrawer);
  navigate(location.hash.replace("#", "") || "dashboard"); loadApplications();
});

