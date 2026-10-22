'use strict';
(()=>{
Object.assign(en,{calendar:'Spending calendar',calendarHelp:'Darker days mean more spending. Tap a day to see its entries.',calendarBusiest:'Busiest day',calendarAvg:'Daily average',calendarLess:'Less',calendarMore:'More',calendarPick:'Tap a day to see its entries.',calendarNone:'No entries on this day.',calendarSpent:'Spent',calendarDow:'S,M,T,W,T,F,S'});
Object.assign(km,{calendar:'ប្រតិទិនចំណាយ',calendarHelp:'ថ្ងៃកាន់តែខ្មៅ គឺចាយកាន់តែច្រើន។ ចុចលើថ្ងៃដើម្បីមើលកំណត់ត្រា។',calendarBusiest:'ថ្ងៃចាយច្រើនបំផុត',calendarAvg:'មធ្យមភាគប្រចាំថ្ងៃ',calendarLess:'តិច',calendarMore:'ច្រើន',calendarPick:'ចុចលើថ្ងៃដើម្បីមើលកំណត់ត្រា។',calendarNone:'គ្មានកំណត់ត្រាក្នុងថ្ងៃនេះទេ។',calendarSpent:'បានចាយ',calendarDow:'អា,ច,អ,ពុ,ព្រ,សុ,សៅ'});

const page=$('reports');
if(!page)return;
const card=node('article',undefined,'card');
card.id='calendarCard';
card.innerHTML='<div class="cal-head"><h2 id="calTitle"></h2><span id="calMonth" class="muted"></span></div><p id="calHelp" class="muted"></p><div id="calStats" class="cal-stats"></div><div id="calGrid" class="cal-grid"></div><div class="cal-legend"><span id="calLess"></span><i data-level="0"></i><i data-level="1"></i><i data-level="2"></i><i data-level="3"></i><i data-level="4"></i><span id="calMore"></span></div><h3 id="calendarDayTitle"></h3><div id="calendarDayList"></div>';
page.append(card);

let selected=null;
const pad=n=>String(n).padStart(2,'0');
function expensesByDay(currency){
  const totals={};
  for(const row of state.transactions||[]){
    if(row.kind!=='expense')continue;
    const units=typeof convertUnits==='function'?convertUnits(row.amount,row.currency,currency):row.amount;
    totals[row.day]=(totals[row.day]||0)+units;
  }
  return totals;
}
function showDay(day){
  selected=day;
  const items=(state.transactions||[]).filter(r=>r.day===day);
  $('calendarDayTitle').textContent=day;
  if(items.length)rows('calendarDayList',items);
  else{$('calendarDayList').replaceChildren(node('p',t('calendarNone'),'muted'));}
  renderCalendar();
}
function renderCalendar(){
  const month=$('month')?.value||'';
  if(!/^\d{4}-\d{2}$/.test(month))return;
  const [year,mon]=month.split('-').map(Number);
  if(!$('currency').value)return;
  const currency=$('currency').value,days=new Date(year,mon,0).getDate(),first=new Date(year,mon-1,1).getDay();
  const totals=expensesByDay(currency),values=Object.values(totals),max=Math.max(0,...values),sum=values.reduce((a,b)=>a+b,0);
  const todayText=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Phnom_Penh'}).format(new Date());
  $('calTitle').textContent=t('calendar');$('calHelp').textContent=t('calendarHelp');$('calMonth').textContent=month;
  $('calLess').textContent=t('calendarLess');$('calMore').textContent=t('calendarMore');
  const busiest=Object.entries(totals).sort((a,b)=>b[1]-a[1])[0];
  const stats=$('calStats');stats.replaceChildren();
  for(const [label,value] of [[t('calendarBusiest'),busiest?busiest[0].slice(8)+' · '+money(busiest[1],currency):'—'],[t('calendarAvg'),money(Math.round(sum/days),currency)]]){
    const box=node('div',undefined,'cal-stat');box.append(node('small',label),node('b',value));stats.append(box);
  }
  const grid=$('calGrid');grid.replaceChildren();
  for(const label of t('calendarDow').split(','))grid.append(node('div',label,'cal-dow'));
  for(let i=0;i<first;i++)grid.append(node('div',undefined,'cal-day cal-blank'));
  for(let d=1;d<=days;d++){
    const day=month+'-'+pad(d),amount=totals[day]||0;
    const button=node('button',String(d),'cal-day'+(day===todayText?' today':'')+(day===selected?' selected':''));
    button.type='button';
    button.dataset.level=String(amount&&max?Math.min(4,Math.ceil(amount/max*4)):0);
    button.setAttribute('aria-label',day+(amount?' · '+t('calendarSpent')+' '+money(amount,currency):''));
    button.addEventListener('click',()=>showDay(day));
    grid.append(button);
  }
  if(!selected||!selected.startsWith(month)){selected=null;$('calendarDayTitle').textContent='';$('calendarDayList').replaceChildren(node('p',t('calendarPick'),'muted'));}
}
const baseRender=render;
render=function(){baseRender();renderCalendar();};
const baseTranslate=translate;
translate=function(){baseTranslate();renderCalendar();};
$('currency')?.addEventListener('change',renderCalendar);
translate();
})();
