(function(){
  const $ = s=>document.querySelector(s);
  const cardsEl = $('#cards');
  const themeBtn = $('#modeToggle');
  const root = document.documentElement;
  const stored = localStorage.getItem('pt_theme');
  if(stored==='light') root.classList.add('light');
  themeBtn.textContent = root.classList.contains('light') ? '🌙' : '☀️';
  themeBtn.addEventListener('click', ()=>{
    root.classList.toggle('light');
    localStorage.setItem('pt_theme', root.classList.contains('light')?'light':'dark');
    themeBtn.textContent = root.classList.contains('light') ? '🌙' : '☀️';
  });

  let items = [];
  fetch('./data.json').then(r=>r.json()).then(data=>{ items = data; render(items); }).catch(()=>{});

  function cardHTML(it){
    const host = (it.link||'').split('/')[2]||'';
    const fav = `https://www.google.com/s2/favicons?domain=${host}&sz=32`;
    return `<article class="card">
      <div class="card-body">
        <div class="card-title">
          <img class="favicon" src="${fav}" alt="" width="16" height="16">
          <h3><a href="${it.link}" rel="nofollow sponsored noopener" target="_blank">${it.title}</a></h3>
        </div>
        ${it.summary ? `<p class="summary">${it.summary}</p>` : ''}
        <div class="meta">
          <span class="time">🕒 ${it.published_human||''}</span>
          ${it.source ? `<span class="dot">•</span><span class="src">${it.source}</span>`:''}
          <a class="cta" href="${it.link}" target="_blank" rel="nofollow sponsored noopener">Voir l’offre →</a>
        </div>
      </div>
    </article>`;
  }
  function render(arr){ cardsEl.innerHTML = arr.map(cardHTML).join(''); }

  const q = $('#q'), clear=$('#clear'), sortSel = $('#sort');
  function apply(){
    const term=(q.value||'').toLowerCase();
    let arr=items.slice();
    if(term) arr=arr.filter(it => (it.title||'').toLowerCase().includes(term) || (it.summary||'').toLowerCase().includes(term));
    if(sortSel.value==='az') arr.sort((a,b)=>(a.title||'').localeCompare(b.title||''));
    else arr.sort((a,b)=> new Date(b.published||0)-new Date(a.published||0));
    render(arr);
  }
  q.addEventListener('input', apply);
  clear.addEventListener('click', ()=>{ q.value=''; apply(); q.focus(); });
  sortSel.addEventListener('change', apply);
  document.querySelectorAll('#chips button').forEach(b=> b.addEventListener('click', ()=>{ q.value=b.dataset.k; apply(); }));
})();