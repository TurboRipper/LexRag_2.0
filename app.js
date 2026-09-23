const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
let lastResult = null;
let busy = false;
let historyItems = [];
let turnNumber = 0;
async function status() {
  try {
    const r = await fetch('/api/status'), d = await r.json();
    $('researchMode').checked = false;
    $('researchMode').disabled = !d.research_available;
    $('verifyBtn').disabled = !d.research_available;
    $('modelStatus').textContent = d.research_available ? 'Models stored on this laptop. The first request may take longer while the index loads.' : 'Basic search is available. Run setup_research_windows.cmd to install the research models.';
    $('statusDot').classList.toggle('bad', !d.ready);
    $('statusText').textContent = d.ready ? 'Local index ready' : 'Dataset unavailable';
    $('datasetText').textContent = d.ready ? `${d.judgments} cases · ${d.chunks} chunks · ${d.source}` : d.error;
    if (d.ready && !d.dated_chunks) {
      $('asOf').disabled = true;
      $('dateHint').textContent = 'This dataset has no decision dates, so a date filter is unavailable.';
    }
  } catch { $('statusText').textContent = 'Backend unavailable'; }
}
function evidenceCard(e, i) {
  return `<details class="evidence-card" ${i === 0 ? 'open' : ''}><summary><span><b>Evidence ${i+1}: ${esc(e.title)}</b><small>${esc(e.citation_id)} · ${esc(e.court)} · ${esc(e.decision_date || 'Date unknown')}</small></span><strong>${e.final.toFixed(3)}</strong></summary><div class="score-row"><span>BM25 <b>${e.bm25.toFixed(3)}</b></span><span>TF-IDF <b>${e.tfidf.toFixed(3)}</b></span><span>RRF <b>${e.relevance.toFixed(3)}</b></span><span>Authority <b>${e.authority.toFixed(2)}</b></span>${e.dense === undefined ? '' : `<span>Semantic <b>${e.dense.toFixed(3)}</b></span><span>Reranker <b>${e.reranker_logit == null ? 'off' : e.reranker_logit.toFixed(2)}</b></span>`}</div><p>${esc(e.text)}</p></details>`;
}
function claimCard(c, i) {
  return `<article class="claim-card supported"><div class="claim-top"><span>Extract ${i+1}</span><b>${esc(c.label)}</b></div><h3>${esc(c.claim)}</h3><p><small>SOURCE CHUNK</small>${esc(c.citation_id)}</p></article>`;
}
function comparisonRows(normal, lex) {
  const n = normal.metrics, l = lex.metrics;
  const rows = [
    ['Retrieved chunks', n.retrieved_chunks, l.retrieved_chunks, 'Up to 5 relevant candidates'],
    ['Distinct cases', n.distinct_cases, l.distinct_cases, 'Source diversity'],
    ['Chunks with known court', n.known_court_chunks, l.known_court_chunks, 'Metadata coverage'],
    ['Source-linked extracts', n.source_linked_extracts, l.source_linked_extracts, 'Traceability, not accuracy'],
    ['Insufficient evidence', n.abstained ? 'Yes' : 'No', l.abstained ? 'Yes' : 'No', 'No answer when evidence is weak'],
    ['Response time', n.response_time_seconds.toFixed(3)+' s', l.response_time_seconds.toFixed(3)+' s', 'Single-run timing']
  ];
  return rows.map(r => `<tr>${r.map(x => `<td>${esc(x)}</td>`).join('')}</tr>`).join('');
}
function renderSystem(prefix, data) {
  $(prefix+'Answer').textContent = data.answer;
  $(prefix+'Evidence').innerHTML = data.evidence.map(evidenceCard).join('') || '<p>No matching evidence.</p>';
  $(prefix+'Claims').innerHTML = data.claims.map(claimCard).join('') || '<p>No extracts returned.</p>';
}
async function research() {
  if (busy) return;
  const q = $('question').value.trim();
  if (q.length < 3 || q.length > 2000) { showError('Enter a question between 3 and 2,000 characters.'); return; }
  setBusy(true);
  lastResult = null;
  $('verificationOutput').replaceChildren(); $('verifyStatus').textContent = '';
  $('error').classList.add('hidden'); $('results').classList.add('hidden');
  $('loader').classList.remove('hidden'); $('researchBtn').disabled = true; $('verifyBtn').disabled = true;
  try {
    const r = await fetch('/api/research', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:q, as_of:$('asOf').value || null, research_mode:$('researchMode').checked})});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Research failed');
    showDetails(d);
    appendTurn(d);
  } catch(e) { showError(e.message); }
  finally { $('loader').classList.add('hidden'); setBusy(false); }
}
function setBusy(value) {
  busy = value;
  for (const id of ['researchBtn', 'newChat', 'clearHistory']) $(id).disabled = value;
  $('verifyBtn').disabled = value || $('researchMode').disabled;
  document.querySelectorAll('.suggestion, .history-item').forEach(button => { button.disabled = value; });
}
function showDetails(d) {
  lastResult = d;
  renderSystem('normal', d.normal_rag); renderSystem('lex', d.lex_rag);
  $('comparisonRows').innerHTML = comparisonRows(d.normal_rag, d.lex_rag);
  $('metricNote').textContent = d.metric_note;
  $('comparisonNote').textContent = d.comparison_note;
  $('results').classList.remove('hidden');
}
function appendTurn(d, existingId = null) {
  const id = existingId ?? ++turnNumber;
  const article = document.createElement('article');
  article.className = 'chat-turn'; article.id = `turn-${id}`;
  const result = d.lex_rag;
  const sourceLinks = new Map(result.evidence.map((e, i) => [e.citation_id, `source-${id}-${i}`]));
  const answer = esc(result.answer).replace(/\[([^\]]+)\]/g, (match, citation) => {
    const raw = result.evidence.find(e => esc(e.citation_id) === citation);
    return raw ? `<a class="source-chip" href="#${sourceLinks.get(raw.citation_id)}">${citation}</a>` : match;
  });
  article.innerHTML = `<p class="user-message">${esc(d.question)}</p><div class="assistant-heading"><span>⚖</span> LEX-RAG</div><div class="chat-answer">${answer}</div><p class="chat-footnote">${result.abstained ? 'No sufficient match in the current index.' : 'Extracted from judgments · Read the source passages for context.'}</p><details class="chat-sources"><summary>${result.evidence.length} source passages</summary>${result.evidence.map((e, i) => `<div id="source-${id}-${i}">${evidenceCard(e, i)}</div>`).join('')}</details>`;
  article.querySelectorAll('.source-chip').forEach(link => link.addEventListener('click', () => {
    article.querySelector('.chat-sources').open = true;
    const source = $(link.hash.slice(1));
    if (source) source.querySelector('details').open = true;
  }));
  $('conversation').append(article);
  document.body.classList.add('chat-active');
  if (existingId === null) historyItems.unshift({id, data:d});
  renderHistory();
  article.scrollIntoView({behavior:'smooth', block:'start'});
}
function renderHistory() {
  $('history').replaceChildren();
  if (!historyItems.length) $('history').innerHTML = '<p class="empty-history">Your questions will appear here.</p>';
  historyItems.forEach(item => {
    const button = document.createElement('button');
    button.className = 'history-item'; button.textContent = item.data.question; button.title = item.data.question;
    button.addEventListener('click', () => {
      if (busy) return;
      $('question').value = item.data.question;
      $('asOf').value = item.data.as_of || '';
      $('researchMode').checked = item.data.research_mode;
      $('verificationOutput').replaceChildren(); $('verifyStatus').textContent = '';
      showDetails(item.data);
      if (!$(`turn-${item.id}`)) {
        appendTurn(item.data, item.id);
      }
      $(`turn-${item.id}`).scrollIntoView({behavior:'smooth'});
    });
    $('history').append(button);
  });
}
function resetResearch() {
  if (busy) return;
  $('conversation').replaceChildren();
  document.body.classList.remove('chat-active');
  $('results').classList.add('hidden'); $('error').classList.add('hidden');
  $('question').value = ''; $('claimsInput').value = ''; $('asOf').value = '';
  $('verificationOutput').replaceChildren(); $('verifyStatus').textContent = '';
  lastResult = null;
  $('question').focus();
  window.scrollTo({top:0, behavior:'smooth'});
}
$('newChat').addEventListener('click', resetResearch);
$('clearHistory').addEventListener('click', () => { historyItems = []; renderHistory(); resetResearch(); });
document.querySelectorAll('.suggestion').forEach(button => button.addEventListener('click', () => {
  $('question').value = button.dataset.question;
  research();
}));
document.querySelector('a[href="#tools"]').addEventListener('click', () => { $('tools').open = true; });
function showError(x) { $('error').textContent = x; $('error').classList.remove('hidden'); }
$('researchBtn').addEventListener('click', research);
$('question').addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') research(); });
$('exportBtn').addEventListener('click', () => {
  if (!lastResult) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastResult, null, 2)], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = 'lexrag-research.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
function nliWindow(w, label) {
  if (!w) return '';
  return `<details class="nli-window"><summary>${esc(label)}: ${esc(w.citation_id)} (characters ${w.char_start}-${w.char_end})</summary><p>${esc(w.text)}</p><small>Model outputs: support ${Number(w.entailment).toFixed(3)}, contradiction ${Number(w.contradiction).toFixed(3)}, neutral ${Number(w.neutral).toFixed(3)}</small></details>`;
}
$('verifyBtn').addEventListener('click', async () => {
  if (busy) return;
  const question = $('question').value.trim();
  const claims = $('claimsInput').value.split(/\n+/).map(x => x.trim()).filter(Boolean);
  if (question.length < 3 || claims.length < 1 || claims.length > 3) { showError('Enter a question above and 1 to 3 statements, one per line.'); return; }
  setBusy(true);
  $('error').classList.add('hidden');
  $('verifyBtn').disabled = true; $('researchBtn').disabled = true;
  $('verifyStatus').textContent = 'Checking evidence on this laptop. Model loading and the first index build can take a few minutes.';
  $('verificationOutput').innerHTML = '';
  try {
    const r = await fetch('/api/verify', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,claims,as_of:$('asOf').value || null,retry:$('retryEvidence').checked})});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Verification failed');
    $('verifyStatus').textContent = d.decision;
    $('verificationOutput').innerHTML = d.checks.map(c => `<article class="claim-card ${c.label === 'Model-supported' ? 'supported' : 'partial'}"><div class="claim-top"><b>${esc(c.label)}</b></div><h3>${esc(c.claim)}</h3><p>${c.windows_checked}/${c.windows_available} evidence windows checked · ${c.retrieval_rounds} search round(s) · ${c.added_chunks} extra passages${c.coverage_complete ? '' : ' · Partial coverage: CPU budget reached'}</p>${c.support.map(w => nliWindow(w,'Supporting signal')).join('')}${c.contradiction.map(w => nliWindow(w,'Contradicting signal')).join('')}${!c.support.length && !c.contradiction.length ? nliWindow(c.best_match,'Closest checked passage') : ''}</article>`).join('') + `<p class="metric-note">${esc(d.note)}</p>`;
    lastResult = {...(lastResult || {}), verification:d};
  } catch(e) { $('verifyStatus').textContent = e.message; }
  finally { setBusy(false); }
});
status();
