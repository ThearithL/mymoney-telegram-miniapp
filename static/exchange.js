'use strict';
Object.assign(en,{baseCurrency:'Show totals in',conversionRate:'KHR per USD',rateHelp:'Conversion is for display only. Entries stay saved in their original currency. Updating this rate also updates older totals.',rateError:'Enter an exchange rate from 1 to 100,000 KHR per USD, with up to 4 decimal places.',originalCurrency:'Original currency',conversion:'Display rate',separate:'USD and KHR entries appear together. Choose the currency for totals above.'});
Object.assign(km,{baseCurrency:'បង្ហាញសរុបជា',conversionRate:'រៀលក្នុងមួយដុល្លារ',rateHelp:'អត្រានេះប្រើសម្រាប់បង្ហាញប៉ុណ្ណោះ។ កំណត់ត្រានៅតែរក្សារូបិយប័ណ្ណដើម។ ការប្ដូរអត្រានឹងគណនាសរុបចាស់ឡើងវិញ។',rateError:'បញ្ចូលអត្រា 1–100,000៛ ក្នុងមួយដុល្លារ និងមិនលើស 4 ខ្ទង់ទសភាគ។',originalCurrency:'រូបិយប័ណ្ណដើម',conversion:'អត្រាបម្លែង',separate:'កំណត់ត្រា USD និង KHR បង្ហាញរួមគ្នា។ ជ្រើសរូបិយប័ណ្ណសម្រាប់សរុបនៅខាងលើ។'});
Object.assign(en,{budgetCurrencyNote:'USD and KHR limits are tracked separately. Budget figures are not converted.',saveBudget:'Save limit',updateBudget:'Update limit'});
Object.assign(km,{budgetCurrencyNote:'ថវិកា USD និង KHR តាមដានដាច់ដោយឡែក។ លេខថវិកាមិនបម្លែងរូបិយប័ណ្ណទេ។',saveBudget:'រក្សាកម្រិត',updateBudget:'កែប្រែកម្រិត'});
Object.assign(en,{accountMode:'Account mode',accountModeHelp:'Choose your personal workspace or the admin console. This only changes the interface; it does not remove admin permissions.',userMode:'User mode',adminMode:'Admin mode',switchToUserMode:'Switch to User Mode',switchToAdminMode:'Switch to Admin Mode',userModeEnabled:'User mode enabled',adminModeEnabled:'Admin mode enabled'});
Object.assign(km,{accountMode:'ទម្រង់គណនី',accountModeHelp:'ជ្រើសរើសផ្ទាំងប្រើប្រាស់ផ្ទាល់ខ្លួន ឬផ្ទាំង Admin។ វាប្ដូរតែរូបរាងកម្មវិធី មិនដកសិទ្ធិ Admin ទេ។',userMode:'ទម្រង់អ្នកប្រើ',adminMode:'ទម្រង់ Admin',switchToUserMode:'ប្ដូរទៅ User Mode',switchToAdminMode:'ប្ដូរទៅ Admin Mode',userModeEnabled:'បានបើក User Mode',adminModeEnabled:'បានបើក Admin Mode'});
let fxRate=4000,fxReady=false,fxSaving=false,budgetCurrencyTouched=false;
$('budgetCurrency').addEventListener('change',()=>{budgetCurrencyTouched=true;});
function convertUnits(units,from,to=$('currency').value){if(from===to)return Number(units);if(from==='USD'&&to==='KHR')return Math.round(Number(units)/100*fxRate);if(from==='KHR'&&to==='USD')return Math.round(Number(units)/fxRate*100);throw Error('Unsupported currency');}
function baseMoney(units,from){return money(convertUnits(units,from));}
function baseSum(records,kind){return records.filter(r=>r.kind===kind).reduce((sum,r)=>sum+convertUnits(r.amount,r.currency),0);}
async function loadFx(){try{const data=await api('/api/fx');fxRate=data.rate_khr_per_usd;$('currency').value=data.base_currency;if(!budgetCurrencyTouched)$('budgetCurrency').value=data.base_currency;$('conversionRateInput').value=fxRate;fxReady=true;render();renderSummary();if(typeof renderFeatures==='function')renderFeatures();}catch(e){$('fxError').textContent=e.message;}}
$('currency').setAttribute('aria-label',t('baseCurrency'));$('currencyHelp').textContent=t('baseCurrency');
$('currency').onchange=async()=>{render();renderSummary();if(typeof renderFeatures==='function')renderFeatures();if(fxReady)await saveFx();};
$('conversionRateInput').step='0.0001';$('conversionRateInput').min='1';$('conversionRateInput').max='100000';
$('fxForm').onsubmit=async e=>{e.preventDefault();if(fxSaving)return;const rate=Number($('conversionRateInput').value);if(!Number.isFinite(rate)||rate<1||rate>100000||Number(rate.toFixed(4))!==rate){$('fxError').textContent=t('rateError');return;}fxRate=rate;render();renderSummary();if(typeof renderFeatures==='function')renderFeatures();await saveFx();};
async function saveFx(){fxSaving=true;const button=$('fxForm').querySelector('button');busy(button,true);$('fxError').textContent='';try{await api('/api/fx',{method:'PUT',body:JSON.stringify({base_currency:$('currency').value,rate_khr_per_usd:fxRate})});toast(t('saved'));}catch(e){$('fxError').textContent=e.message;}finally{fxSaving=false;busy(button,false);}}

// Monthly limits are tracked in the transaction's original currency. Keep USD
// and KHR separate here so changing the display conversion rate cannot alter a
// budget, its spending total, or its remaining amount.
function renderBudgetCurrencies(items){
  const root=$('budgetSummary');
  root.replaceChildren();
  for(const currency of ['KHR','USD']){
    const spent=items.filter(row=>row.kind==='expense'&&row.currency===currency)
      .reduce((sum,row)=>sum+Number(row.amount),0);
    const budget=state.budgets.find(row=>row.currency===currency);
    const section=node('div',undefined,'budget-currency-row');
    const heading=node('div',undefined,'budget-currency-heading');
    heading.append(node('strong',currency));
    heading.append(node('b',budget?`${money(spent,currency)} / ${money(budget.amount,currency)}`:
      `${money(spent,currency)} · ${t('noBudget')}`));
    section.append(heading);
    if(budget){
      const limit=Number(budget.amount);
      const progress=node('progress');
      progress.max=limit>0?limit:1;
      progress.value=limit>0?Math.min(spent,limit):0;
      progress.setAttribute('aria-label',`${currency} ${t('budget')}`);
      section.append(progress);
      const status=node('p',undefined,'muted budget-currency-status');
      if(limit===0){
        status.textContent=t('budgetZero');
      }else{
        const percent=spent*100/limit;
        status.textContent=(spent>limit?
          `${t('over')}: ${money(spent-limit,currency)}`:
          `${t('remaining')}: ${money(limit-spent,currency)}`)+
          (percent>=80?` · ${percent.toFixed(1)}% · ${t('budgetReachedWarning')}`:'');
        status.classList.toggle('budget-warning',percent>=80);
      }
      section.append(status);
    }
    root.append(section);
  }
}

// Preserve the existing UI wrappers (selection controls, icon rows, etc.), then
// replace only currency-dependent values with the chosen display currency.
const previousRender=render;
render=function(){if(!state.transactions)return;previousRender();const currency=$('currency').value,items=state.transactions,expense=baseSum(items,'expense'),income=baseSum(items,'income');$('net').textContent=money(income-expense);$('income').textContent=money(income);$('expense').textContent=money(expense);const formCurrency=$('budgetCurrency').value,formBudget=state.budgets.find(b=>b.currency===formCurrency);$('budgetAmount').value=formBudget?formBudget.amount/(formCurrency==='USD'?100:1):'';$('budgetAmount').step=formCurrency==='USD'?'0.01':'1';$('budgetAmount').min='0';$('budgetContext').textContent=t('budgetContext')+' '+$('month').value+' · '+formCurrency;$('saveBudget').textContent=t(formBudget?'updateBudget':'saveBudget');renderBudgetCurrencies(items);const chart=$('chart');chart.replaceChildren();const grouped={};items.filter(r=>r.kind==='expense').forEach(r=>grouped[r.category]=(grouped[r.category]||0)+convertUnits(r.amount,r.currency));if(!expense)chart.append(node('p',t('empty'),'muted'));Object.entries(grouped).sort((a,b)=>b[1]-a[1]).forEach(([category,amount])=>{const label=node('div',undefined,'bar-label');label.append(node('span',t(category)),node('b',money(amount)));const bar=node('progress');bar.max=expense;bar.value=amount;bar.setAttribute('aria-label',t(category));chart.append(label,bar);});rows('recent',items.slice(0,4));renderHistory();renderTrend(items);renderSummary();renderSpendingTypes(currency,items.filter(row=>row.currency===currency));renderDonut();};
renderSummary=function(){if(!summaryState){['summaryIncome','summaryExpense','summaryNet'].forEach(id=>$(id).textContent='—');return;}const totals=summaryState.totals;const totalIncome=baseSum(totals,'income'),totalExpense=baseSum(totals,'expense');$('summaryDates').textContent=summaryState.start+' → '+summaryState.end;$('summaryIncome').textContent=money(totalIncome);$('summaryExpense').textContent=money(totalExpense);$('summaryNet').textContent=money(totalIncome-totalExpense);};
renderHistory=function(){const query=$('search').value.toLowerCase();const items=state.transactions.filter(r=>(filter==='all'||r.kind===filter)&&[r.note,t(r.category),r.day,t(r.account),r.currency].join(' ').toLowerCase().includes(query));rows('historyList',items.slice(0,pageSize));$('more').hidden=items.length<=pageSize;};
const previousRows=rows;rows=function(target,items){previousRows(target,items);$(target).querySelectorAll('.row').forEach((el,i)=>{const item=items[i],amount=el.querySelector('.row-money');if(amount)amount.textContent=(item.kind==='expense'?'−':'+')+baseMoney(item.amount,item.currency);const small=el.querySelector('.row-copy small');if(small)small.textContent=item.day+' · '+t(item.account)+' · '+item.currency;});};
const previousTrend=renderTrend;renderTrend=function(items){return previousTrend(items.map(r=>({...r,amount:convertUnits(r.amount,r.currency)})));};
renderDonut=function(){const groups={};state.transactions.filter(r=>r.kind==='expense').forEach(r=>groups[r.category]=(groups[r.category]||0)+convertUnits(r.amount,r.currency));const entries=Object.entries(groups).sort((a,b)=>b[1]-a[1]),total=entries.reduce((n,[,v])=>n+v,0);donutPanel.replaceChildren();const svg=svgNode('svg',{viewBox:'0 0 240 240',role:'img','aria-label':t('categoryShare')+': '+(total?entries.map(([k,v])=>t(k)+' '+(100*v/total).toFixed(1)+'%').join(', '):t('noSpending'))});svg.append(svgNode('circle',{cx:120,cy:120,r:89,fill:'none',stroke:'var(--soft)','stroke-width':23}));let offset=0;entries.forEach(([category,amount],i)=>{const percent=amount/total*100,circle=svgNode('circle',{cx:120,cy:120,r:89,fill:'none',stroke:palette[i%palette.length],'stroke-width':23,pathLength:100,'stroke-dasharray':`${percent} ${100-percent}`,'stroke-dashoffset':-offset,transform:'rotate(-90 120 120)'});const title=svgNode('title');title.textContent=t(category)+': '+money(amount)+' ('+percent.toFixed(1)+'%)';circle.append(title);svg.append(circle);offset+=percent;});const label=svgNode('text',{x:120,y:109,'text-anchor':'middle',class:'donut-caption'});label.textContent=t('expense');const value=svgNode('text',{x:120,y:138,'text-anchor':'middle',class:'donut-value'});value.textContent=money(total);if(value.textContent.length>16)value.style.fontSize='12px';svg.append(label,value);donutPanel.append(svg);if(total){const insight=node('div',undefined,'donut-insight');insight.append(node('small',t('topCategory')),node('strong',t(entries[0][0])),node('span',(entries[0][1]/total*100).toFixed(1)+'% '+t('ofSpending')));donutPanel.append(insight);}else donutPanel.append(node('p',t('noSpending'),'muted'));const legend=node('ul',undefined,'donut-legend');entries.forEach(([category,amount],i)=>{const li=node('li'),dot=node('i');dot.style.backgroundColor=palette[i%palette.length];li.append(dot,node('span',t(category)),node('b',(100*amount/total).toFixed(1)+'%'));legend.append(li);});donutPanel.append(legend);};
$('fxInfo').textContent=t('rateHelp');loadFx();
