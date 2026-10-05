'use strict';
Object.assign(en,{reports:'Insights',calculator:'Calculator',quickEntry:'Quick-entry presets',greetingTag:'Your money, a little clearer.',recent:'Recent activity',quickSummary:'At a glance'});
Object.assign(km,{reports:'របាយការណ៍',calculator:'គណនា',quickEntry:'បញ្ចូលចំណាយរហ័ស',greetingTag:'មើលលុយរបស់អ្នកបានច្បាស់ជាងមុន',quickSummary:'សង្ខេបខ្លី'});
const iconPaths={
 home:'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
 history:'M8 4h12v17H4V4h4m0-2v4m8-4v4M8 11h8M8 15h5',
 reports:'M4 20V10m8 10V4m8 16v-7',
 goals:'M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5m-5 0 9-9m-5 0h5v5',
 settings:'M4 7h16M4 17h16M8 4v6m8 4v6',
 wallet:'M4 6h15v14H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12v2m3 5h-6v5h6m-3-2.5h.01',
 plus:'M12 5v14M5 12h14',income:'M12 3v13m-5-5 5 5 5-5M4 18v3h16v-3',
 calculator:'M5 2h14v20H5ZM8 6h8M8 11h1m6 0h1M8 15h1m6 0h1M8 19h1m6 0h1',
 receipt:'M5 3l3 2 4-2 4 2 3-2v18l-3-2-4 2-4-2-3 2ZM8 9h8M8 13h8',
 food:'M5 3v6m4-6v6M3 3v6a4 4 0 0 0 8 0V3M7 13v8M18 3c-4 5-4 10 1 10V3m0 10v8',
 coffee:'M4 6h12v8a6 6 0 0 1-12 0ZM16 7h2a3 3 0 0 1 0 6h-2M3 22h15M7 2v1m5-1v1',
 transport:'M5 16H3v-6l3-6h12l3 6v6h-2M5 16h14M5 16v4H3v-4m16 0v4h2v-4M3 10h18M6 13h2m8 0h2',
 shopping:'M4 7h16l1 14H3ZM8 7V5a4 4 0 0 1 8 0v2',
 bills:'M5 3h14v18l-3-2-4 2-4-2-3 2ZM8 8h8M8 12h8',
 study:'m2 8 10-5 10 5-10 5ZM6 10v7c4 3 8 3 12 0v-7M22 8v9',
 health:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z',
 other:'M5 12h.01M12 12h.01M19 12h.01',debt:'M4 5h16v15H4Zm3 4h10m-10 4h10m-10 4h5M7 2v3m10-3v3',salary:'M3 7h18v14H3ZM8 7V3h8v4M3 12h18m-11 0v3h4v-3'
};
function uiIcon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [k,v] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.65','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}))svg.setAttribute(k,v);const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',iconPaths[name]||iconPaths.other);svg.append(path);return svg;}
document.querySelectorAll('[data-ui-icon]').forEach(el=>el.replaceChildren(uiIcon(el.dataset.uiIcon)));
const receiptRows=rows;
rows=function(target,items){receiptRows(target,items);$(target).querySelectorAll('.row-icon').forEach((el,i)=>el.replaceChildren(uiIcon(items[i].category)));};
const baseTranslate=translate;
translate=function(){baseTranslate();document.querySelectorAll('nav button').forEach(b=>{if(b.classList.contains('active'))b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});};
const baseShowPage=showPage;
showPage=function(page){baseShowPage(page);document.querySelectorAll('nav button').forEach(b=>{if(b.dataset.page===page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});};
translate();
Object.assign(en,{categoryShare:'Spending breakdown',topCategory:'Largest category',ofSpending:'of spending',noSpending:'No expenses in this period'});
Object.assign(km,{categoryShare:'ភាគរយចំណាយ',topCategory:'ប្រភេទចាយច្រើនបំផុត',ofSpending:'នៃចំណាយ',noSpending:'មិនមានចំណាយក្នុងរយៈពេលនេះ'});
const donutPanel=node('div',undefined,'donut-panel');donutPanel.id='donutPanel';$('chart').before(donutPanel);
const palette=['#4f8961','#aac58b','#d5b66b','#839faa','#bba5c6','#cc9985','#81b8a5','#b6bab0'];
function renderDonut(){const currency=$('currency').value,groups={};state.transactions.filter(r=>r.kind==='expense'&&r.currency===currency).forEach(r=>groups[r.category]=(groups[r.category]||0)+r.amount);const entries=Object.entries(groups).sort((a,b)=>b[1]-a[1]),total=entries.reduce((n,[,v])=>n+v,0);donutPanel.replaceChildren();
 const svg=svgNode('svg',{viewBox:'0 0 240 240',role:'img','aria-label':t('categoryShare')+': '+(total?entries.map(([k,v])=>t(k)+' '+(100*v/total).toFixed(1)+'%').join(', '):t('noSpending'))});
 svg.append(svgNode('circle',{cx:120,cy:120,r:89,fill:'none',stroke:'var(--soft)','stroke-width':23}));
 let offset=0;entries.forEach(([category,amount],i)=>{const percent=amount/total*100,circle=svgNode('circle',{cx:120,cy:120,r:89,fill:'none',stroke:palette[i%palette.length],'stroke-width':23,pathLength:100,'stroke-dasharray':`${percent} ${100-percent}`,'stroke-dashoffset':-offset,transform:'rotate(-90 120 120)'});const title=svgNode('title');title.textContent=t(category)+': '+money(amount,currency)+' ('+percent.toFixed(1)+'%)';circle.append(title);svg.append(circle);offset+=percent;});
 const label=svgNode('text',{x:120,y:109,'text-anchor':'middle',class:'donut-caption'});label.textContent=t('expense');const value=svgNode('text',{x:120,y:138,'text-anchor':'middle',class:'donut-value'});value.textContent=money(total,currency);if(value.textContent.length>16)value.style.fontSize='12px';svg.append(label,value);donutPanel.append(svg);
 if(total){const insight=node('div',undefined,'donut-insight');insight.append(node('small',t('topCategory')),node('strong',t(entries[0][0])),node('span',(entries[0][1]/total*100).toFixed(1)+'% '+t('ofSpending')));donutPanel.append(insight);}else donutPanel.append(node('p',t('noSpending'),'muted'));
 const legend=node('ul',undefined,'donut-legend');entries.forEach(([category,amount],i)=>{const li=node('li'),dot=node('i');dot.style.backgroundColor=palette[i%palette.length];li.append(dot,node('span',t(category)),node('b',(100*amount/total).toFixed(1)+'%'));legend.append(li);});donutPanel.append(legend);
}
const baseRender=render;render=function(){baseRender();renderDonut();};render();
