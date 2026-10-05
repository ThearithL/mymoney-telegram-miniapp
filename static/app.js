'use strict';
const $ = id => document.getElementById(id);
const tg = window.Telegram?.WebApp;
const en = {month:'Month',net:'Income − expenses this month',netHelp:'Based on entries in the selected month',income:'Income',expense:'Expenses',addExpense:'Add expense',addIncome:'Add income',budget:'Monthly budget',manage:'Manage',categories:'Spending by category',recent:'Recent activity',viewAll:'View all',history:'History',all:'All',more:'Load more',budgetHelp:'Set a spending limit for the month and currency selected above.',limit:'Spending limit',save:'Save',budgetNote:'In-app alerts appear when spending reaches 80% or exceeds your budget.',settings:'Settings',language:'Language',export:'Export your data',exportHelp:'Download all transactions as a CSV for Excel.',download:'Download CSV',privacy:'Privacy',privacyHelp:'Entries belong to your Telegram ID. Cash and bank are labels; this app does not connect to your bank.',separate:'USD and KHR entries appear together. Choose the currency for totals above.',home:'Home',amount:'Amount',currency:'Currency',category:'Category',account:'Account',cash:'Cash',bank:'Bank',date:'Date',note:'Note (optional)',delete:'Delete entry',empty:'No entries yet. Add your first transaction.',noBudget:'No budget set for this month.',remaining:'Remaining',over:'Over budget',warning:'You have used at least 80% of your budget.',saved:'Saved successfully',budgetUpdated:'Budget limit updated to',deleted:'Entry deleted',confirmDelete:'Delete this entry permanently?',loading:'Loading…',openTelegram:'Open this Mini App from your Telegram bot’s menu to use your account.',edit:'Edit entry',exportFail:'Download unavailable here. Try Telegram Desktop or another Telegram client.',food:'Food',coffee:'Drinks',transport:'Transport',shopping:'Shopping',bills:'Bills',study:'Education',health:'Health',other:'Other',salary:'Salary',spendingType:'Spending type',essential:'Needs',want:'Wants',budgetContext:'Set the expense limit for this month and currency:',annualSummary:'Yearly summary',annualHelp:'Income, expenses, top category, and needs vs wants for the selected year.',annualIncome:'Income',annualExpense:'Expenses',annualTop:'Top spending category',annualNoData:'No entries for this year.',annualMonths:'Monthly expenses',annualMonthlyBudget:'Monthly limit',noExpenseThisMonth:'No expenses recorded for this month.',budgetInputError:'Choose a month and enter a positive spending limit.',budgetSavedMessage:'Monthly spending limit saved:',budgetInputHelp:'Enter numbers only. For USD, use decimals (137.00); for KHR, use whole riel. Do not type a currency symbol or commas.'};
const km = {month:'ខែ',net:'ចំណូល − ចំណាយក្នុងខែ',netHelp:'គណនាពីកំណត់ត្រាក្នុងខែដែលបានជ្រើស',income:'ចំណូល',expense:'ចំណាយ',addExpense:'កត់ចំណាយ',addIncome:'កត់ចំណូល',budget:'ថវិកាប្រចាំខែ',manage:'កំណត់',categories:'ចំណាយតាមប្រភេទ',recent:'កំណត់ត្រាថ្មីៗ',viewAll:'មើលទាំងអស់',history:'ប្រវត្តិ',all:'ទាំងអស់',more:'បង្ហាញបន្ថែម',budgetHelp:'កំណត់ថវិកាសម្រាប់ខែ និងរូបិយប័ណ្ណដែលបានជ្រើសខាងលើ។',limit:'កម្រិតចំណាយ',save:'រក្សាទុក',budgetNote:'បង្ហាញការជូនដំណឹងក្នុង App ពេលចំណាយដល់ 80% ឬលើសថវិកា។',settings:'ការកំណត់',language:'ភាសា',export:'នាំចេញទិន្នន័យ',exportHelp:'ទាញយកកំណត់ត្រាទាំងអស់ជា CSV សម្រាប់ Excel។',download:'ទាញយក CSV',privacy:'ឯកជនភាព',privacyHelp:'ទិន្នន័យភ្ជាប់នឹង Telegram ID របស់អ្នក។ សាច់ប្រាក់/ធនាគារគ្រាន់តែជាស្លាក មិនភ្ជាប់ទៅធនាគារទេ។',separate:'កំណត់ត្រា USD និង KHR បង្ហាញរួមគ្នា។ ជ្រើសរូបិយប័ណ្ណសម្រាប់សរុបនៅខាងលើ។',home:'ទំព័រដើម',amount:'ចំនួនប្រាក់',currency:'រូបិយប័ណ្ណ',category:'ប្រភេទ',account:'គណនី',cash:'សាច់ប្រាក់',bank:'ធនាគារ',date:'ថ្ងៃ',note:'កំណត់ចំណាំ (ជាជម្រើស)',delete:'លុបកំណត់ត្រា',empty:'មិនទាន់មានកំណត់ត្រា។ ចាប់ផ្ដើមកត់ចំណាយរបស់អ្នក។',noBudget:'មិនទាន់កំណត់ថវិកាខែនេះ។',remaining:'នៅសល់',over:'លើសថវិកា',warning:'អ្នកបានប្រើថវិកាដល់ 80% ហើយ។',saved:'បានរក្សាទុក',budgetUpdated:'បានធ្វើបច្ចុប្បន្នភាពកម្រិតថវិកាទៅជា',deleted:'បានលុបកំណត់ត្រា',confirmDelete:'តើចង់លុបកំណត់ត្រានេះជាអចិន្ត្រៃយ៍មែនទេ?',loading:'កំពុងទាញយក…',openTelegram:'សូមបើក Mini App តាមប៊ូតុង Menu ក្នុង Telegram Bot។',edit:'កែកំណត់ត្រា',exportFail:'សូមសាកទាញយកតាម Telegram Desktop។',food:'អាហារ',coffee:'ភេសជ្ជៈ',transport:'ដឹកជញ្ជូន',shopping:'ទិញទំនិញ',bills:'វិក្កយបត្រ',study:'ការសិក្សា',health:'សុខភាព',other:'ផ្សេងៗ',salary:'ប្រាក់ខែ',spendingType:'ប្រភេទចំណាយ',essential:'ចំណាយចាំបាច់',want:'ចំណាយចង់បាន',budgetContext:'កំណត់កម្រិតចំណាយសម្រាប់ខែ និងរូបិយប័ណ្ណនេះ៖',annualSummary:'សង្ខេបប្រចាំឆ្នាំ',annualHelp:'មើលចំណូល ចំណាយ ប្រភេទដែលចាយច្រើនបំផុត និងចំណាយចាំបាច់/ចង់បានតាមឆ្នាំ។',annualIncome:'ចំណូល',annualExpense:'ចំណាយ',annualTop:'ប្រភេទចំណាយច្រើនបំផុត',annualNoData:'មិនទាន់មានកំណត់ត្រាក្នុងឆ្នាំនេះទេ។',annualMonths:'ចំណាយតាមខែ',annualMonthlyBudget:'ថវិកាប្រចាំខែ',noExpenseThisMonth:'ខែនេះមិនទាន់មានកំណត់ត្រាចំណាយទេ។',budgetInputError:'សូមជ្រើសខែ និងបញ្ចូលកម្រិតចំណាយជាចំនួនវិជ្ជមាន។',budgetSavedMessage:'បានរក្សាទុកកម្រិតចំណាយប្រចាំខែ៖',budgetInputHelp:'បញ្ចូលតែលេខប៉ុណ្ណោះ។ USD អាចដាក់ខ្ទង់ទសភាគ (137.00); KHR ដាក់ជារៀលគត់។ កុំដាក់សញ្ញារូបិយប័ណ្ណ ឬសញ្ញាក្បៀស។'};
Object.assign(en, {
  quickSummary:'Current summary', today:'Today', thisWeek:'This week', thisMonth:'This month', refresh:'Refresh',
  netShort:'Net', dailyTrend:'Daily spending', trendHelp:'For the selected month above. Tap a bar to see its amount.',
  dailyAllowance:'How much can I spend today?', dailyAllowanceHelp:'Average daily amount from your remaining monthly budget, counting today.',
  dailyAllowanceNoBudget:'Set a monthly budget to calculate your daily amount.', dailyAllowanceReached:'Your monthly budget is used up. Daily amount: 0.',
  daysIncludingToday:'days left, including today', monthlyLeft:'Monthly budget left',
  dailyAverage:'Average / day', highestDay:'Highest spending day', viewDailyData:'View daily data table',
  adminHelp:'Open your bot chat and tap Admin or send /admin to manage users and review data.',
  privacyHelp:'Other users cannot access your records. The owner/admin can review recorded transactions and budgets. Cash/bank are labels; no bank connection.'
});
Object.assign(km, {
  quickSummary:'សង្ខេបបច្ចុប្បន្ន', today:'ថ្ងៃនេះ', thisWeek:'សប្ដាហ៍នេះ', thisMonth:'ខែនេះ', refresh:'ធ្វើបច្ចុប្បន្នភាព',
  netShort:'នៅសល់សុទ្ធ', dailyTrend:'ចំណាយប្រចាំថ្ងៃ', trendHelp:'សម្រាប់ខែដែលបានជ្រើសខាងលើ។ ចុចលើជួរដើម្បីមើលចំនួនប្រាក់។',
  dailyAllowance:'ថ្ងៃនេះអាចចាយបានប៉ុន្មាន?', dailyAllowanceHelp:'ប្រាក់ថវិកានៅសល់ចែកតាមថ្ងៃដែលនៅសល់ ដោយរាប់បញ្ចូលថ្ងៃនេះ។',
  dailyAllowanceNoBudget:'កំណត់ថវិកាប្រចាំខែជាមុន ដើម្បីគណនាចំនួនចាយប្រចាំថ្ងៃ។', dailyAllowanceReached:'បានប្រើថវិកាអស់ហើយ។ ថ្ងៃនេះអាចចាយបាន៖ 0។',
  daysIncludingToday:'ថ្ងៃនៅសល់ រាប់ទាំងថ្ងៃនេះ', monthlyLeft:'ថវិកានៅសល់ក្នុងខែ',
  dailyAverage:'មធ្យម/ថ្ងៃ', highestDay:'ថ្ងៃចាយច្រើនបំផុត', viewDailyData:'មើលតារាងប្រចាំថ្ងៃ',
  adminHelp:'បើក Chat របស់ Bot ហើយចុច Admin ឬផ្ញើ /admin ដើម្បីគ្រប់គ្រងអ្នកប្រើ និងមើលទិន្នន័យ។',
  privacyHelp:'អ្នកប្រើផ្សេងមិនអាចមើលទិន្នន័យអ្នកបានទេ។ ម្ចាស់ Bot/Admin អាចមើលកំណត់ត្រាចំណូល ចំណាយ និងថវិកា។ App មិនភ្ជាប់ធនាគារទេ។'
});
Object.assign(en,{goals:'Savings',newGoal:'+ New goal',goalsHelp:'Track your total saved amount manually. Goals do not transfer money or create expenses.',goalName:'Goal name',goalTarget:'Target amount',goalSaved:'Total saved',deleteGoal:'Delete goal',emptyGoals:'Your next goal starts here. Add a laptop, tuition or travel fund.',appearance:'Appearance',system:'Use device setting',light:'Light',dark:'Dark',fullscreen:'Fullscreen',retry:'Try again',greetingTag:'Small entries. A clearer picture.',welcome:'Hello',saving:'Saving…',fullscreenUnavailable:'Fullscreen is unavailable in this Telegram client.',goalComplete:'Goal reached!',confirmGoalDelete:'Delete this savings goal? Your expense history will be kept.'});
Object.assign(km,{goals:'សន្សំ',newGoal:'＋ គោលដៅថ្មី',goalsHelp:'កត់ប្រាក់សន្សំសរុបដោយខ្លួនឯង។ វាមិនផ្ទេរប្រាក់ ឬរាប់ជាចំណាយទេ។',goalName:'ឈ្មោះគោលដៅ',goalTarget:'គោលដៅប្រាក់',goalSaved:'សន្សំបានសរុប',deleteGoal:'លុបគោលដៅ',emptyGoals:'ចាប់ផ្ដើមគោលដៅថ្មី៖ Laptop ថ្លៃសាលា ឬដំណើរកម្សាន្ត។',appearance:'រូបរាង',system:'តាមឧបករណ៍',light:'ភ្លឺ',dark:'ងងឹត',fullscreen:'ពេញអេក្រង់',retry:'ព្យាយាមម្ដងទៀត',greetingTag:'កត់ត្រាបន្តិច រៀបចំបានច្បាស់',welcome:'សួស្ដី',saving:'កំពុងរក្សាទុក…',fullscreenUnavailable:'Telegram នេះមិនអាចបើកពេញអេក្រង់បានទេ។',goalComplete:'សម្រេចគោលដៅហើយ!',confirmGoalDelete:'លុបគោលដៅសន្សំនេះ? ប្រវត្តិចំណាយនៅតែរក្សាទុក។'});
let goalsState=[],currentGoal=null,goalRequestId='',goalsVersion=0,toastTimer;
let appTheme='system';
try{appTheme=localStorage.getItem('mymoney-theme')||'system';}catch{}
function applyTheme(){
  const dark=appTheme==='dark'||(appTheme==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme=dark?'dark':'light';
  $('theme').value=appTheme;
}
function toast(message){clearTimeout(toastTimer);$('toast').textContent='✓ '+message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,3500);}
function bootDone(){$('bootLoader').hidden=true;}
function busy(button,on){button.classList.toggle('busy',on);button.disabled=on;button.setAttribute('aria-busy',String(on));}
let summaryState = null, summaryPeriod = 'today', summaryVersion = 0;
const icons = {food:'🍚',coffee:'☕',transport:'🚗',shopping:'🛍️',bills:'🧾',study:'📚',health:'💊',other:'📦',salary:'💵'};
let lang = 'km';
try {lang = localStorage.getItem('mymoney-language') === 'en' ? 'en' : 'km';} catch {}
let state = {transactions:[],budgets:[]}, filter = 'all', pageSize = 20, kind = 'expense', requestId = '', loadVersion = 0;
const t = key => (lang === 'en' ? en : km)[key] || key;
const money = (units, currency=$('currency').value) => new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits:currency==='KHR'?0:2}).format(units/(currency==='USD'?100:1));
function notify(message){const success=message===t('saved')||message===t('deleted')||message.startsWith(t('budgetUpdated'));$('notice').textContent=message;$('notice').classList.toggle('warning-notice',!!message&&message!==t('loading')&&!success);if(success)toast(message);}
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function translate(){document.documentElement.lang=lang;document.querySelectorAll('[data-i]').forEach(n=>n.textContent=t(n.dataset.i));$('language').textContent=lang==='km'?'EN':'ខ្មែរ';render();renderGoals();}
function toggleLanguage(){lang=lang==='km'?'en':'km';try{localStorage.setItem('mymoney-language',lang);}catch{}translate();}
async function api(path,options={}){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),20000);try{const response=await fetch(path,{...options,signal:controller.signal,headers:{'Authorization':'tma '+(tg?.initData||''),'Content-Type':'application/json',...options.headers}});if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error||`Request failed (${response.status})`);}return options.blob?await response.blob():await response.json();}catch(e){if(e.name==='AbortError')throw new Error('Connection timed out. Please try again.');throw e;}finally{clearTimeout(timer);}}
async function load(){
  const version=++loadVersion;
  $('retryLoad').hidden=true;document.querySelector('main').classList.add('is-loading');notify(t('loading'));
  try{
    const next=await api('/api/data?month='+encodeURIComponent($('month').value));
    if(version!==loadVersion)return false;
    state=next;notify('');render();loadSummary();loadGoals();return true;
  }catch(e){
    if(version===loadVersion){state={transactions:[],budgets:[]};summaryState=null;summaryVersion++;goalsVersion++;goalsState=[];renderGoals();$('summaryDates').textContent='';$('summaryError').textContent='';render();notify(e.message);$('retryLoad').hidden=false;}
    return false;
  }finally{if(version===loadVersion){document.querySelector('main').classList.remove('is-loading');bootDone();}}
}

function showPage(page){document.querySelectorAll('.page').forEach(n=>n.hidden=n.id!==page);document.querySelectorAll('[data-page]').forEach(n=>n.classList.toggle('active',n.dataset.page===page));window.scrollTo({top:0,behavior:'smooth'});if(tg?.initData){if(page==='home')tg.BackButton.hide();else tg.BackButton.show();}}
function rows(target,items){const root=$(target);root.replaceChildren();if(!items.length){root.append(node('div',t('empty'),'empty'));return;}for(const r of items){const button=node('button',undefined,'row');button.type='button';const copy=node('span',undefined,'row-copy');copy.append(node('b',r.note||t(r.category)),node('small',r.day+' · '+t(r.account)));button.append(node('span',icons[r.category],'row-icon'),copy,node('span',(r.kind==='expense'?'−':'+')+money(r.amount,r.currency),'row-money '+(r.kind==='expense'?'negative':'positive')));button.addEventListener('click',()=>openEntry(r.kind,r));root.append(button);}}
function renderHistory(){const query=$('search').value.toLowerCase();const items=state.transactions.filter(r=>r.currency===$('currency').value&&(filter==='all'||r.kind===filter)&&[r.note,t(r.category),r.day,t(r.account)].join(' ').toLowerCase().includes(query));rows('historyList',items.slice(0,pageSize));$('more').hidden=items.length<=pageSize;}
function renderDailyAllowance(currency, expense, budget){
  const card=$('dailyAllowanceCard');
  const todayDate=state.today||'';
  if(!todayDate||$('month').value!==todayDate.slice(0,7)){card.hidden=true;return;}
  card.hidden=false;
  const [year,month,day]=todayDate.split('-').map(Number);
  const daysLeft=new Date(Date.UTC(year,month,0)).getUTCDate()-day+1;
  $('dailyAllowanceDays').textContent=`${daysLeft} ${t('daysIncludingToday')}`;
  if(!budget){$('dailyAllowanceAmount').textContent='—';$('dailyAllowanceHint').textContent=t('dailyAllowanceNoBudget');return;}
  const remaining=Math.max(0,budget.amount-expense);
  $('dailyAllowanceAmount').textContent=money(Math.floor(remaining/daysLeft),currency);
  $('dailyAllowanceHint').textContent=remaining>0
    ?`${t('monthlyLeft')}: ${money(remaining,currency)} ÷ ${daysLeft} ${t('daysIncludingToday')}`
    :t('dailyAllowanceReached');
}
function renderSpendingTypes(currency,items){const root=$('monthlySpendingTypes');if(!root)return;root.replaceChildren();const expenses=items.filter(r=>r.kind==='expense');if(!expenses.length){root.append(node('p',t('noExpenseThisMonth'),'muted'));return;}const totals={essential:0,want:0,none:0};for(const row of expenses){const amount=typeof convertUnits==='function'?convertUnits(row.amount,row.currency,currency):row.amount;const type=['essential','want','none'].includes(row.spending_type)?row.spending_type:'essential';totals[type]+=amount;}const all=totals.essential+totals.want+totals.none;for(const type of ['essential','want','none']){const block=node('div',undefined,'spending-type-row'),heading=node('div',undefined,'bar-label');heading.append(node('span',t(type)),node('b',money(totals[type],currency)));const progress=node('progress');progress.max=all;progress.value=totals[type];progress.setAttribute('aria-label',t(type));block.append(heading,progress);root.append(block);}}
function render(){const currency=$('currency').value;const items=state.transactions.filter(r=>r.currency===currency);renderSpendingTypes(currency,items);$('budgetContext').textContent=t('budgetContext')+' '+$('month').value+' · '+currency;const expense=items.filter(r=>r.kind==='expense').reduce((n,r)=>n+r.amount,0);const income=items.filter(r=>r.kind==='income').reduce((n,r)=>n+r.amount,0);$('net').textContent=money(income-expense);$('income').textContent=money(income);$('expense').textContent=money(expense);const budget=state.budgets.find(b=>b.currency===currency);renderDailyAllowance(currency,expense,budget);$('budgetAmount').value=budget?budget.amount/(currency==='USD'?100:1):'';$('budgetAmount').step=currency==='USD'?'0.01':'1';$('budgetAmount').min=$('budgetAmount').step;$('budgetSummary').textContent=budget?money(expense)+' / '+money(budget.amount):t('noBudget');$('budgetProgress').value=budget?Math.min(100,expense/budget.amount*100):0;$('budgetHint').classList.toggle('budget-warning',!!budget&&expense>=budget.amount*.8);$('budgetHint').setAttribute('role','status');$('budgetHint').textContent=budget?(expense>budget.amount?t('over')+': '+money(expense-budget.amount):t('remaining')+': '+money(budget.amount-expense))+(expense>=budget.amount*.8?' · '+t('warning'):''):'';const chart=$('chart');chart.replaceChildren();const grouped={};items.filter(r=>r.kind==='expense').forEach(r=>grouped[r.category]=(grouped[r.category]||0)+r.amount);if(!expense)chart.append(node('p',t('empty'),'muted'));Object.entries(grouped).sort((a,b)=>b[1]-a[1]).forEach(([category,amount])=>{const label=node('div',undefined,'bar-label');label.append(node('span',t(category)),node('b',money(amount)));const bar=node('progress');bar.max=expense;bar.value=amount;bar.setAttribute('aria-label',t(category));chart.append(label,bar);});rows('recent',items.slice(0,4));renderHistory();renderTrend(items);renderSummary();$('adminHint').hidden=!state.user?.is_admin;$('greetingName').textContent=state.user?t('welcome')+', '+state.user.name:'MyMoney';}
function svgNode(tag, attributes={}) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attributes).forEach(([key,value]) => element.setAttribute(key,String(value)));
  return element;
}
function renderTrend(items) {
  const month = $('month').value;
  if (!/^\d{4}-\d{2}$/.test(month)) return;
  const [year,monthNumber] = month.split('-').map(Number);
  const count = new Date(Date.UTC(year,monthNumber,0)).getUTCDate();
  const todayValue = state.today || today();
  const days = month === todayValue.slice(0,7) ? Number(todayValue.slice(8)) : month > todayValue.slice(0,7) ? 0 : count;
  const amounts = Array.from({length:days},(_,i)=>({day:month+'-'+String(i+1).padStart(2,'0'),amount:0}));
  items.filter(r=>r.kind==='expense').forEach(r=>{const index=Number(r.day.slice(8))-1;if(amounts[index])amounts[index].amount+=r.amount;});
  const sum=amounts.reduce((n,r)=>n+r.amount,0), peak=Math.max(0,...amounts.map(r=>r.amount));
  const best=amounts.find(r=>r.amount===peak);
  $('trendMonth').textContent=month;
  $('dailyAverage').textContent=money(days?Math.round(sum/days):0);
  $('highestDay').textContent=peak?best.day.slice(8)+' · '+money(peak):'—';
  $('trendDetail').textContent='';
  const root=$('trendChart');root.replaceChildren();
  if(!days || !sum) root.append(node('p',t('empty'),'muted'));
  else {
    const width=360,height=190,left=52,right=8,top=16,bottom=30,plot=width-left-right;
    const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':t('dailyTrend')});
    const max=peak || 1;
    for(const fraction of [0,.5,1]){
      const y=height-bottom-(height-top-bottom)*fraction;
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:y,y2:y,class:'chart-grid'}));
      const label=svgNode('text',{x:left-5,y:y+4,'text-anchor':'end',class:'chart-label'});
      label.textContent=new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(max*fraction/($('currency').value==='USD'?100:1));svg.append(label);
    }
    amounts.forEach((r,i)=>{
      const gap=plot/days,x=left+i*gap+gap*.12,barHeight=(height-top-bottom)*r.amount/max;
      const bar=svgNode('rect',{x,y:height-bottom-barHeight,width:Math.max(2,gap*.76),height:Math.max(1,barHeight),rx:2,class:'chart-bar',tabindex:0,role:'button','aria-label':r.day+' '+money(r.amount)});
      const title=svgNode('title');title.textContent=r.day+' · '+money(r.amount);bar.append(title);
      const show=()=>{$('trendDetail').textContent=r.day+' · '+money(r.amount);};
      bar.addEventListener('click',show);bar.addEventListener('focus',show);bar.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show();}});svg.append(bar);
      if(i===0||i===days-1||(i+1)%5===0){const label=svgNode('text',{x:x+gap*.38,y:height-8,'text-anchor':'middle',class:'chart-label'});label.textContent=i+1;svg.append(label);}
    });
    root.append(svg);
  }
  const table=node('table'),head=node('tr');head.append(node('th',t('date')),node('th',t('expense')));table.append(head);
  for(const r of amounts){const row=node('tr');row.append(node('td',r.day),node('td',money(r.amount)));table.append(row);}
  $('dailyTable').replaceChildren(table);
}
function renderSummary(){
  if(!summaryState){['summaryIncome','summaryExpense','summaryNet'].forEach(id=>$(id).textContent='—');return;}
  const totals=summaryState.totals.filter(r=>r.currency===$('currency').value);
  const income=totals.find(r=>r.kind==='income')?.amount||0,expense=totals.find(r=>r.kind==='expense')?.amount||0;
  $('summaryDates').textContent=summaryState.start+' → '+summaryState.end;
  $('summaryIncome').textContent=money(income);$('summaryExpense').textContent=money(expense);$('summaryNet').textContent=money(income-expense);
}
async function loadSummary(){
  const version=++summaryVersion;
  $('summaryError').textContent=t('loading');
  try{const data=await api('/api/summary?period='+summaryPeriod);if(version!==summaryVersion)return;summaryState=data;$('summaryError').textContent='';renderSummary();}
  catch(error){if(version===summaryVersion){summaryState=null;$('summaryDates').textContent='';$('summaryError').textContent=error.message;renderSummary();}}
}
function precision(){const usd=$('entryCurrency').value==='USD';$('amount').step=usd?'0.01':'1';$('amount').min=$('amount').step;}
function today(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Phnom_Penh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function openEntry(entryKind,entry=null){if(!tg?.initData){notify(t('openTelegram'));return;}if(!state.user){notify('Please refresh and request access first.');return;}kind=entryKind;requestId=crypto.randomUUID();$('entryForm').reset();$('formError').textContent='';$('entryId').value=entry?.id||'';$('entryTitle').textContent=entry?t('edit'):t(kind==='expense'?'addExpense':'addIncome');$('entryCurrency').value=entry?.currency||$('currency').value;precision();$('category').replaceChildren();Object.keys(icons).filter(c=>kind==='income'?['salary','other'].includes(c):c!=='salary').forEach(c=>{const option=node('option',icons[c]+' '+t(c));option.value=c;$('category').append(option);});$('category').value=entry?.category||(kind==='income'?'salary':'food');$('account').value=entry?.account||'cash';$('day').value=entry?.day||state.today||today();$('day').max=state.today||today();$('note').value=entry?.note||'';$('spendingType').value=entry?.spending_type||'essential';$('spendingTypeLabel').hidden=kind!=='expense';$('amount').value=entry?entry.amount/(entry.currency==='USD'?100:1):'';$('deleteEntry').hidden=!entry;$('entryDialog').showModal();}
$('entryForm').addEventListener('submit',async e=>{e.preventDefault();const button=$('saveEntry');busy(button,true);$('deleteEntry').disabled=true;$('formError').textContent='';const id=$('entryId').value;try{await api('/api/transactions'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify({kind,amount:$('amount').value,currency:$('entryCurrency').value,category:$('category').value,account:$('account').value,day:$('day').value,note:$('note').value,spending_type:kind==='expense'?$('spendingType').value:null,request_id:requestId})});$('month').value=$('day').value.slice(0,7);$('entryDialog').close();await load();if(!$('notice').textContent)notify(t('saved'));}catch(e){$('formError').textContent=e.message;}finally{busy(button,false);$('deleteEntry').disabled=false;}});
$('deleteEntry').addEventListener('click',async()=>{if(!confirm(t('confirmDelete')))return;$('deleteEntry').disabled=true;$('saveEntry').disabled=true;try{await api('/api/transactions/'+$('entryId').value,{method:'DELETE'});$('entryDialog').close();await load();if(!$('notice').textContent)notify(t('deleted'));}catch(e){$('formError').textContent=e.message;}finally{$('deleteEntry').disabled=false;$('saveEntry').disabled=false;}});
$('budgetForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const button=e.submitter||$('saveBudget')||$('budgetForm').querySelector('button[type=submit]');
 const error=$('budgetError');error.textContent='';busy(button,true);
 try{
  const amount=$('budgetAmount').value,month=$('month').value,currency=$('currency').value;
  if(!amount||!month)throw new Error(t('budgetInputError'));
  const saved=await api('/api/budget',{method:'PUT',body:JSON.stringify({month,currency,amount})});
  if(saved.month===$('month').value){
   state.budgets=state.budgets||[];
   const index=state.budgets.findIndex(b=>b.currency===saved.currency);
   const row={month:saved.month,currency:saved.currency,amount:saved.amount};
   if(index<0)state.budgets.push(row);else state.budgets[index]={...state.budgets[index],...row};
   render();
  }
  error.textContent=t('budgetSavedMessage')+' '+money(saved.amount,saved.currency)+' · '+saved.month;
  notify(t('budgetUpdated')+' '+money(saved.amount,saved.currency)+' · '+saved.month);
 }catch(e){error.textContent=e.message;notify(e.message);}
 finally{busy(button,false);}
});
$('export').addEventListener('click',async()=>{$('export').disabled=true;try{const blob=await api('/api/export',{blob:true});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download='mymoney.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){notify(e.message||t('exportFail'));}finally{$('export').disabled=false;}});
$('language').onclick=toggleLanguage;$('switchLanguage').onclick=toggleLanguage;
$('addExpense').onclick=()=>openEntry('expense');$('addIncome').onclick=()=>openEntry('income');$('closeDialog').onclick=()=>$('entryDialog').close();$('entryCurrency').onchange=precision;$('manageBudget').onclick=()=>showPage('budget');$('viewAll').onclick=()=>showPage('history');$('month').onchange=()=>{pageSize=20;load();};$('currency').onchange=()=>{pageSize=20;render();};$('month').addEventListener('change',()=>{$('budgetContext').textContent=t('budgetContext')+' '+$('month').value+' · '+$('currency').value;});$('search').oninput=()=>{pageSize=20;renderHistory();};$('more').onclick=()=>{pageSize+=20;renderHistory();};document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>showPage(b.dataset.page));document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;pageSize=20;document.querySelectorAll('[data-filter]').forEach(n=>n.classList.toggle('selected',n===b));renderHistory();});
function renderGoals(){
  const root=$('goalList');root.replaceChildren();
  if(!goalsState.length){root.append(node('div',t('emptyGoals'),'empty'));return;}
  for(const goal of goalsState){
    const card=node('button',undefined,'card goal-card');card.type='button';
    const top=node('div',undefined,'section-title');top.append(node('h3','🎯 '+goal.title),node('span',Math.min(100,Math.round(goal.saved/goal.target*100))+'%','goal-percent'));
    const progress=node('progress');progress.max=goal.target;progress.value=Math.min(goal.saved,goal.target);progress.setAttribute('aria-label',goal.title);
    card.append(top,node('strong',money(goal.saved,goal.currency)),node('p','/ '+money(goal.target,goal.currency),'muted'),progress);
    if(goal.saved>=goal.target)card.append(node('p',t('goalComplete'),'positive'));
    card.onclick=()=>openGoal(goal);root.append(card);
  }
}
async function loadGoals(){
  const version=++goalsVersion;$('goalsError').textContent=t('loading');
  try{const data=await api('/api/goals');if(version!==goalsVersion)return;goalsState=data.goals;$('goalsError').textContent='';renderGoals();}
  catch(e){if(version===goalsVersion){goalsState=[];renderGoals();$('goalsError').textContent=e.message;}}
}
function goalPrecision(){const step=$('goalCurrency').value==='USD'?'0.01':'1';$('goalTarget').step=step;$('goalTarget').min=step;$('goalSaved').step=step;}
function openGoal(goal=null){
  if(!state.user){notify(tg?.initData?'Please refresh and request access first.':t('openTelegram'));return;}
  currentGoal=goal;goalRequestId=crypto.randomUUID();$('goalForm').reset();$('goalError').textContent='';
  $('goalName').value=goal?.title||'';$('goalCurrency').value=goal?.currency||$('currency').value;$('goalCurrency').disabled=!!goal;goalPrecision();
  const scale=$('goalCurrency').value==='USD'?100:1;
  $('goalTarget').value=goal?goal.target/scale:'';$('goalSaved').value=goal?goal.saved/scale:0;$('deleteGoal').hidden=!goal;$('goalDialog').showModal();
}
$('newGoal').onclick=()=>openGoal();$('closeGoal').onclick=()=>$('goalDialog').close();$('goalCurrency').onchange=goalPrecision;$('refreshGoals').onclick=loadGoals;
$('goalForm').onsubmit=async e=>{
  e.preventDefault();busy($('saveGoal'),true);$('deleteGoal').disabled=true;$('goalError').textContent='';
  try{await api('/api/goals'+(currentGoal?'/'+currentGoal.id:''),{method:currentGoal?'PUT':'POST',body:JSON.stringify({title:$('goalName').value,currency:$('goalCurrency').value,target:$('goalTarget').value,saved:$('goalSaved').value,version:currentGoal?.version,request_id:goalRequestId})});$('goalDialog').close();await loadGoals();toast(t('saved'));}
  catch(e){$('goalError').textContent=e.message;}
  finally{busy($('saveGoal'),false);$('deleteGoal').disabled=false;}
};
$('deleteGoal').onclick=async()=>{
  if(!currentGoal||!confirm(t('confirmGoalDelete')))return;
  busy($('deleteGoal'),true);$('saveGoal').disabled=true;
  try{await api('/api/goals/'+currentGoal.id,{method:'DELETE'});$('goalDialog').close();await loadGoals();toast(t('deleted'));}
  catch(e){$('goalError').textContent=e.message;}
  finally{busy($('deleteGoal'),false);$('saveGoal').disabled=false;}
};
$('theme').onchange=()=>{appTheme=$('theme').value;try{localStorage.setItem('mymoney-theme',appTheme);}catch{}applyTheme();};
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',applyTheme);applyTheme();
$('fullscreen').onclick=()=>{if(tg?.initData&&tg.isVersionAtLeast('8.0')){try{tg.requestFullscreen();}catch{notify(t('fullscreenUnavailable'));}}else notify(t('fullscreenUnavailable'));};
$('retryLoad').onclick=()=>load();
document.querySelectorAll('[data-quick]').forEach(button=>button.onclick=()=>{
  const category=button.dataset.quick;openEntry('expense');if(!$('entryDialog').open)return;
  $('entryCurrency').value=category==='transport'?'USD':'KHR';precision();$('amount').value=category==='food'?'12000':category==='coffee'?'6000':'5';$('category').value=category;
});
document.querySelectorAll('[data-period]').forEach(button=>button.onclick=()=>{
  summaryPeriod=button.dataset.period;
  document.querySelectorAll('[data-period]').forEach(n=>n.classList.toggle('selected',n===button));
  loadSummary();
});
$('refreshSummary').onclick=()=>loadSummary();
$('month').value=today().slice(0,7);translate();
// Open the Mini App in fullscreen when the Telegram client supports it.
// Unsupported clients keep the normal expanded view and can still use the app.
if (tg?.initData) {
  tg.ready();
  tg.expand();

  if (tg.isVersionAtLeast('8.0')) {
    tg.onEvent('fullscreenFailed', (event) => {
      console.warn('Fullscreen unavailable:', event.error);notify(t('fullscreenUnavailable'));
    });

    // Keep content away from Telegram controls and device navigation bars.
    const syncSafeArea = () => {
      const top = (tg.safeAreaInset?.top || 0) + (tg.contentSafeAreaInset?.top || 0);
      const bottom = (tg.safeAreaInset?.bottom || 0) + (tg.contentSafeAreaInset?.bottom || 0);
      const shell = document.querySelector('.shell');
      const nav = document.querySelector('nav');
      shell.style.paddingTop = Math.max(24, top + 12) + 'px';
      shell.style.paddingBottom = (100 + bottom) + 'px';
      nav.style.paddingBottom = (10 + bottom) + 'px';
    };
    tg.onEvent('safeAreaChanged', syncSafeArea);
    tg.onEvent('contentSafeAreaChanged', syncSafeArea);
    tg.onEvent('fullscreenChanged', syncSafeArea);
    syncSafeArea();

    try {
      if (!tg.isFullscreen) tg.requestFullscreen();
    } catch (error) {
      console.warn('Fullscreen unavailable:', error);
    }
  }

  tg.BackButton.onClick(() => {
    if ($('bulkDialog')?.open) {if(!$('confirmBulk').classList.contains('busy'))$('bulkDialog').close();}
    else if ($('receiptDialog')?.open) $('receiptDialog').close();
    else if ($('goalDialog').open) $('goalDialog').close();
    else if ($('entryDialog').open) $('entryDialog').close();
    else showPage('home');
  });
  load().then(ok=>{
    const action=new URLSearchParams(location.search).get('action');
    if(ok && ['expense','income'].includes(action)) openEntry(action);else if(ok&&['reports','budget','goals'].includes(action)){showPage(action);if(action==='reports')loadAnnual();if(action==='budget')$('budgetContext').textContent=t('budgetContext')+' '+$('month').value+' · '+$('currency').value;}
  });
} else {
  bootDone();notify(t('openTelegram'));
}
