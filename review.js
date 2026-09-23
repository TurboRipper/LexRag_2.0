const el = id => document.getElementById(id);
const safe = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const examples = {
  argument: ['Are municipal property taxes deductible from income from property?', 'The appellant claimed a deduction for municipal and urban property taxes.'],
  tax: ['Are municipal property taxes deductible from income from property?', 'Municipal property taxes are deductible from rental income.'],
  later: ['What is the nature of the municipal property tax charge?', 'The liability and the charge both co-exist and are co-extensive.'],
  unsupported: ['Are municipal property taxes deductible from income from property?', 'The judgment states that quantum computers are required to calculate municipal property tax.']
};
let record = null;
function choose() {
  const pair = examples[el('example').value];
  if (pair) { el('demoQuestion').value = pair[0]; el('demoClaim').value = pair[1]; }
}
el('example').addEventListener('change',choose);
for (const id of ['demoQuestion','demoClaim']) el(id).addEventListener('input',()=>{el('example').value='custom';});
choose();
function windowCard(w, title) {
  if (!w) return '';
  return `<details class="evidence-window"><summary>${safe(title)}</summary><small>${safe(w.citation_id)} · characters ${w.char_start}–${w.char_end}</small><p>${safe(w.text)}</p><small>NLI outputs: support ${w.entailment.toFixed(3)} · contradiction ${w.contradiction.toFixed(3)} · neutral ${w.neutral.toFixed(3)}</small></details>`;
}
function render(d) {
  const [a,b,c] = d.variants;
  el('runIdentity').innerHTML = `<b>Question:</b> ${safe(d.question)}<br><b>Claim:</b> ${safe(d.claim)}<br><small>Recorded ${safe(d.recorded_at)} · ${safe(d.source)} · ${d.indexed_cases} indexed cases / ${d.indexed_chunks} chunks</small>`;
  const transitions = [];
  if (a.check.label !== b.check.label) transitions.push(`Wider evidence changed A’s “${a.check.label}” to B’s “${b.check.label}”.`);
  else transitions.push(`A and B returned the same label: “${b.check.label}”.`);
  if (b.check.label !== c.check.label) transitions.push(`Re-search changed the label to “${c.check.label}”.`);
  else transitions.push(d.retry_attempted ? `Re-search added ${c.added_passages} passage(s), but did not change the label.` : 'Re-search was skipped because B already found model support.');
  transitions.push('A changed label is an observable effect, not proof of a correct legal answer.');
  el('outcome').textContent = transitions.join(' ');
  el('strategyCards').innerHTML = d.variants.map(v=>{
    const x=v.check;
    return `<article class="strategy-card ${x.label==='Model-supported'?'supported':'uncertain'}"><h3>${safe(v.name)}</h3><strong class="label">${safe(x.label)}</strong><div class="score"><span>Highest support score</span><b>${x.best_match ? x.best_match.entailment.toFixed(3) : 'No evidence'}</b></div><small>Uncalibrated NLI score · threshold 0.800</small>${x.support.map(w=>windowCard(w,'Inspect supporting signal')).join('')}${x.contradiction.map(w=>windowCard(w,'Inspect contradicting signal')).join('')}${!x.support.length&&!x.contradiction.length?windowCard(x.best_match,'Inspect closest checked passage'):''}</article>`;
  }).join('');
  const metrics = [
    ['Eligible source characters',v=>v.eligible_characters.toLocaleString()],
    ['Passages supplied',v=>v.passages],
    ['Windows checked / available',v=>`${v.check.windows_checked} / ${v.check.windows_available}`],
    ['Window coverage complete',v=>v.check.coverage_complete?'Yes, within supplied evidence':'No, budget limited'],
    ['Search rounds',v=>v.retrieval_rounds],
    ['Extra passages from re-search',v=>v.added_passages],
    ['Strategy work (seconds)',v=>v.strategy_seconds.toFixed(3)],
    ['Shared retrieval + strategy (seconds)',v=>v.estimated_pipeline_seconds.toFixed(3)]
  ];
  el('demoMetrics').innerHTML = metrics.map(([name,get])=>`<tr><th>${name}</th>${d.variants.map(v=>`<td>${safe(get(v))}</td>`).join('')}</tr>`).join('');
  el('demoEvidence').innerHTML = [...d.initial_evidence.map(e=>({...e,round:'Initial search'})),...d.additional_evidence.map(e=>({...e,round:'Claim-focused re-search'}))].map(e=>`<details class="evidence-window"><summary>${safe(e.round)} · ${safe(e.citation_id)}</summary><p>${safe(e.text)}</p></details>`).join('');
  el('provenance').textContent = JSON.stringify({corpus_sha256:d.corpus_sha256,models:d.models,controls:d.controls,initial_retrieval_seconds:d.initial_retrieval_seconds,model_setup_seconds:d.setup_seconds,scope:d.scope},null,2);
  el('comparisonOutput').hidden=false;
  el('comparisonOutput').scrollIntoView({behavior:'smooth'});
}
el('compareBtn').addEventListener('click',async()=>{
  const question=el('demoQuestion').value.trim(), claim=el('demoClaim').value.trim();
  el('runError').hidden=true;
  if(question.length<3||claim.length<5) {el('runError').textContent='Enter a question and a statement to check.';el('runError').hidden=false;return;}
  el('compareBtn').disabled=true; el('example').disabled=true; el('savedBtn').disabled=true;
  el('demoQuestion').disabled=true; el('demoClaim').disabled=true;
  el('comparisonOutput').hidden=true; record=null;
  const started=Date.now();
  const update=()=>{el('runStatus').textContent=`Running on this laptop · ${Math.floor((Date.now()-started)/1000)} seconds. First use may take a few minutes to load the models and index.`;};
  update(); const timer=setInterval(update,1000);
  try {
    const response=await fetch('/api/compare-verification',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,claim})});
    const data=await response.json();
    if(!response.ok) throw new Error(data.error||'Comparison failed.');
    record=data; render(data); el('runStatus').textContent='Completed using the real local models. Download the record to keep the exact results.';
  } catch(e) {el('runError').textContent=e.message;el('runError').hidden=false;el('runStatus').textContent='Comparison did not complete.';}
  finally {clearInterval(timer);for(const id of ['compareBtn','example','demoQuestion','demoClaim','savedBtn'])el(id).disabled=false;}
});
el('savedBtn').addEventListener('click',async()=>{
  const name=el('example').value;
  el('runError').hidden=true;
  if(!examples[name]){el('runError').textContent='Choose one of the four examples to view its recorded run.';el('runError').hidden=false;return;}
  for(const id of ['compareBtn','savedBtn','example','demoQuestion','demoClaim'])el(id).disabled=true;
  try {
    const response=await fetch(`/api/review-record/${encodeURIComponent(name)}`);
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'Recorded example unavailable.');
    record=data;render(data);
    el('runStatus').textContent=`RECORDED RUN · ${data.recorded_at} · ${data.matches_current_corpus?'Matches the current corpus.':'Corpus has changed; run again for current results.'} This is saved output, not a new model run.`;
    el('runIdentity').insertAdjacentHTML('afterbegin','<b>RECORDED EXAMPLE · not a live run</b><br>');
  }catch(e){el('runError').textContent=e.message;el('runError').hidden=false;}
  finally{for(const id of ['compareBtn','savedBtn','example','demoQuestion','demoClaim'])el(id).disabled=false;}
});
el('downloadDemo').addEventListener('click',()=>{
  if(!record)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='lexrag-review-comparison.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
fetch('/api/status').then(r=>r.json()).then(d=>{
  el('indexStatus').textContent=d.ready?`${d.judgments} cases · ${d.chunks} chunks · Local inference`:'Dataset unavailable';
  if(!d.ready||!d.research_available){el('compareBtn').disabled=true;el('runError').hidden=false;el('runError').textContent=d.error||'Install the local research models to run this comparison.';}
}).catch(()=>{el('indexStatus').textContent='Server unavailable';});
