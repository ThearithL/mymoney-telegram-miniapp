'use strict';
// Month-end forecast: projects this month's spending from the daily pace so far and
// compares it with the monthly budget. Pure client-side; uses data already loaded.
(()=>{
Object.assign(en,{fcTitle:'Month-end forecast',fcProjected:'Projected spending this month',fcPace:'At your current daily pace',fcNoData:'Add a few expenses and your forecast will appear here.',fcNoBudget:'Set a monthly budget to see whether you are on track.',fcOnTrack:'On track',fcUnder:'about {amount} under budget',fcOver:'Heading over',fcOverBody:'about {amount} over budget. Keep spending under {daily} a day to stay within it.',fcOverNow:'Already over budget by {amount}.',fcSoFar:'Spent so far',fcDaily:'Daily average'});
Object.assign(km,{fcTitle:'ការព្យាករណ៍ចុងខែ',fcProjected:'ចំណាយប៉ាន់ស្មានសម្រាប់ខែនេះ',fcPace:'តាមល្បឿនចំណាយប្រចាំថ្ងៃបច្ចុប្បន្ន',fcNoData:'បន្ថែមការចំណាយខ្លះ ការព្យាករណ៍នឹងបង្ហាញនៅទីនេះ។',fcNoBudget:'កំណត់ថវិកាប្រចាំខែ ដើម្បីដឹងថាអ្នកដើរត្រូវផ្លូវឬអត់។',fcOnTrack:'ដើរត្រូវផ្លូវ',fcUnder:'ក្រោមថវិកាប្រហែល {amount}',fcOver:'ទំនងជាលើសថវិកា',fcOverBody:'លើសថវិកាប្រហែល {amount}។ ចំណាយក្រោម {daily} ក្នុងមួយថ្ងៃ ដើម្បីរក្សាក្នុងថវិកា។',fcOverNow:'បានលើសថវិការួចហើយ {amount}។',fcSoFar:'បានចំណាយរហូតដល់ពេលនេះ',fcDaily:'មធ្យមប្រចាំថ្ងៃ'});

const card=node('article',undefined,'card forecast-card');
card.id='forecastCard';card.hidden=true;
document.querySelector('.wallet-block').append(card);
const fill=(text,values)=>text.replace(/\{(\w+)\}/g,(_,k)=>values[k]??'');

function renderForecast(){
  const today=state.today||'',month=$('month').value;
  if(!today||month!==today.slice(0,7)){card.hidden=true;return;}
  const currency=$('currency').value;
  const [year,mon,day]=today.split('-').map(Number);
  const daysInMonth=new Date(Date.UTC(year,mon,0)).getUTCDate();
  const spent=state.transactions.filter(r=>r.kind==='expense'&&r.currency===currency).reduce((sum,r)=>sum+r.amount,0);
  const budget=(state.budgets||[]).find(b=>b.currency===currency)?.amount;
  card.hidden=false;card.replaceChildren();
  card.append(node('h2',t('fcTitle')));
  if(!spent){card.append(node('p',t('fcNoData'),'muted'));return;}
  const daily=Math.round(spent/day),projected=Math.round(spent/day*daysInMonth);
  card.append(node('small',t('fcProjected'),'fc-label'),node('strong',money(projected,currency),'fc-amount'),node('p',`${t('fcPace')} · ${money(daily,currency)}/${t('dayWord')}`,'muted'));
  const stats=node('div',undefined,'fc-stats');
  for(const [label,value] of [[t('fcSoFar'),money(spent,currency)],[t('fcDaily'),money(daily,currency)]]){
    const box=node('div');box.append(node('small',label),node('b',value));stats.append(box);
  }
  card.append(stats);
  if(!budget){card.append(node('p',t('fcNoBudget'),'fc-note muted'));return;}
  const pct=Math.min(100,Math.round(projected*100/budget));
  const bar=node('div',undefined,'fc-bar');const fillBar=node('span');fillBar.style.width=pct+'%';bar.append(fillBar);
  card.append(bar);
  const daysLeft=daysInMonth-day+1;
  const note=node('p',undefined,'fc-note');
  if(spent>budget){note.className+=' fc-bad';note.textContent=fill(t('fcOverNow'),{amount:money(spent-budget,currency)});}
  else if(projected>budget){
    note.className+=' fc-warn';
    const allowed=Math.max(0,Math.floor((budget-spent)/daysLeft));
    note.textContent=`${t('fcOver')}: ${fill(t('fcOverBody'),{amount:money(projected-budget,currency),daily:money(allowed,currency)})}`;
  }else{note.className+=' fc-ok';note.textContent=`${t('fcOnTrack')}: ${fill(t('fcUnder'),{amount:money(budget-projected,currency)})}`;}
  card.append(note);
}
const baseRender=render;
render=function(){baseRender();renderForecast();};
renderForecast();
})();
