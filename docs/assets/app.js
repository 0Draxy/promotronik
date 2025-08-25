(function(){
  const $ = s=>document.querySelector(s);
  const $$ = s=>Array.from(document.querySelectorAll(s));
  const cardsEl = $('#cards');
  const themeBtn = $('#modeToggle');
  const root = document.documentElement;
  const storeKey = 'pt_theme';

  // Theme toggle
  const stored = localStorage.getItem(storeKey);
  if(stored==='light') root.classList.add('light');
  themeBtn.textContent = root.classList.contains('light') ? '🌙' : '☀️';
  themeBtn.addEventListener('click', ()=>{
    root.classList.toggle('light');
    localStorage.setItem(storeKey, root.classList.contains('light')?'light':'dark');
    themeBtn.textContent = root.classList.contains('light') ? '🌙' : '☀️';
  });

  let items = [];
  let filtered = [];
  const favs = new Set(JSON.parse(localStorage.getItem('pt_favs')||'[]'));
  function saveFavs(){ localStorage.setItem('pt_favs', JSON.stringify([...favs])); }

  fetch('./data.json').then(r=>r.json()).then(data=>{
    items = data.map(x => ({...x, price_num:(x.price_num||null)}));
    filtered = items.slice();
    buildChips(items);
    render(filtered);
  }).catch(()=>{});

  function cardHTML(it){
    const host = (it.link||'').split('/')[2]||'';
    const favCls = favs.has(it.link) ? 'fav active' : 'fav';
    const price = it.price ? `<span class="badge price">${it.price}${it.currency? ' '+it.currency: ''}</span>` : '';
    return `<article class="card">
      ${it.image ? `<div class="thumb" style="background-image:url('${it.image}')"></div>`:''}
      <div class="card-body">
        <div class="row">
          <div class="card-title">
            <img class="favicon" src="https://www.google.com/s2/favicons?domain=${host}&sz=32" alt="" width="16" height="16">
            <h3><a href="${it.link}" rel="nofollow sponsored noopener" target="_blank">${it.title}</a></h3>
          </div>
          <button class="${favCls}" data-href="${it.link}" title="Ajouter aux favoris">♡</button>
        </div>
        ${it.summary ? `<p class="summary">${it.summary}</p>` : ''}
        <div class="meta">
          <span class="time">🕒 ${it.published_human||''}</span>
          ${it.source ? `<span class="dot">•</span><span class="src">${it.source}</span>`:''}
          ${price}
          <a class="cta" href="${it.link}" target="_blank" rel="nofollow sponsored noopener">Voir l’offre →</a>
        </div>
      </div>
    </article>`;
  }
  function render(arr){ cardsEl.innerHTML = arr.map(cardHTML).join(''); bindFavs(); }

  // Search / sort
  const q = $('#q'), clear=$('#clear'), sortSel = $('#sort');
  function apply(){
    const term=(q.value||'').toLowerCase();
    filtered = items.filter(it => {
      if(!term) return true;
      return (it.title||'').toLowerCase().includes(term) || (it.summary||'').toLowerCase().includes(term) || (it.source||'').toLowerCase().includes(term);
    });
    if(sortSel.value==='az') filtered.sort((a,b)=>(a.title||'').localeCompare(b.title||''));
    else if(sortSel.value==='price') filtered.sort((a,b)=> (a.price_num||Infinity)-(b.price_num||Infinity));
    else filtered.sort((a,b)=> new Date(b.published||0)-new Date(a.published||0));
    render(filtered);
  }
  q.addEventListener('input', apply);
  clear.addEventListener('click', ()=>{ q.value=''; apply(); q.focus(); });
  sortSel.addEventListener('change', apply);

  // Chips based on top hosts
  function buildChips(arr){
    const box = $('#chips'); if(!box) return;
    const hosts = {};
    arr.forEach(it=>{ try{ const h = new URL(it.link).host.replace('www.',''); hosts[h]=(hosts[h]||0)+1 }catch(e){} });
    const top = Object.entries(hosts).sort((a,b)=>b[1]-a[1]).slice(0,6).map(x=>x[0]);
    const html = ['Tout',...top].map(h => `<button data-host="${h==='Tout'?'':h}">${h}</button>`).join('');
    box.innerHTML = html;
    box.querySelectorAll('button').forEach(b=> b.addEventListener('click', ()=>{
      const host = b.dataset.host;
      if(!host) { apply(); return; }
      filtered = items.filter(it => (it.link||'').includes(host));
      render(filtered);
    }));
  }

  // Favs
  function bindFavs(){
    $$('.fav').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const href = btn.getAttribute('data-href');
        if(favs.has(href)) favs.delete(href); else favs.add(href);
        saveFavs();
        btn.classList.toggle('active');
      });
    });
  }
})();