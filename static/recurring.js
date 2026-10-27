'use strict';
// Bills & subscriptions: recurring templates the user marks as paid each month.
(()=>{
Object.assign(en,{billEditBtn:'Edit',billsTitle:'Bills & subscriptions',billsHelp:'Save rent, subscriptions or regular income once. Each month tap “Mark paid” and it is recorded as a normal entry. You get a reminder before the due day.',newBill:'＋ Add',billsEmpty:'No bills yet. Add rent, internet or a subscription to never miss a due date.',billsHomeEmpty:'Add rent, internet or subscriptions and get reminded before they are due.',billName:'Name',billNamePh:'e.g. Rent, Netflix, Salary',billType:'Type',billExpense:'Bill / expense',billIncome:'Regular income',billDay:'Day of the month',billDayHelp:'On months with fewer days it falls on the last day.',billRemind:'Remind me',billRemindDay:'day before',billRemindDays:'days before',billRemindSame:'On the due day',billEdit:'Edit bill',billAdd:'Add bill',billSaved:'Bill saved',billDeleted:'Bill deleted',billPaidDone:'Recorded as paid',billReceivedDone:'Recorded as received',markPaid:'Mark paid',markReceived:'Mark received',billPause:'Pause',billResume:'Resume',billDeleteConfirm:'Delete this recurring item? Entries already recorded are kept.',billMonthly:'Monthly bills total',billPaidThisMonth:'Paid this month',billStatusOverdue:'overdue',billStatusPaid:'Paid ✓',billStatusPaused:'Paused',billDueToday:'Due today',billDueIn:'Due in',billOverdueBy:'Overdue by',billNextOn:'Next',dayWord:'day',daysWord:'days',billEveryMonth:'Every month on day',billSeeAll:'See all'});
Object.assign(km,{billEditBtn:'កែ',billsTitle:'វិក្កយបត្រ និងការជាវ',billsHelp:'រក្សាទុកថ្លៃផ្ទះ ការជាវ ឬចំណូលទៀងទាត់ម្ដង។ រៀងរាល់ខែ ចុច «សម្គាល់ថាបានបង់» ហើយវានឹងកត់ជាកំណត់ត្រាធម្មតា។ អ្នកនឹងទទួលបានការរំលឹកមុនថ្ងៃកំណត់។',newBill:'＋ បន្ថែម',billsEmpty:'មិនទាន់មានវិក្កយបត្រទេ។ បន្ថែមថ្លៃផ្ទះ អ៊ីនធឺណិត ឬការជាវ ដើម្បីកុំភ្លេចថ្ងៃកំណត់។',billsHomeEmpty:'បន្ថែមថ្លៃផ្ទះ អ៊ីនធឺណិត ឬការជាវ ដើម្បីទទួលការរំលឹកមុនដល់កំណត់។',billName:'ឈ្មោះ',billNamePh:'ឧ. ថ្លៃផ្ទះ, Netflix, ប្រាក់ខែ',billType:'ប្រភេទ',billExpense:'វិក្កយបត្រ / ចំណាយ',billIncome:'ចំណូលទៀងទាត់',billDay:'ថ្ងៃនៃខែ',billDayHelp:'ខែណាមានថ្ងៃតិចជាង វានឹងធ្លាក់លើថ្ងៃចុងក្រោយ។',billRemind:'រំលឹកខ្ញុំ',billRemindDay:'ថ្ងៃមុន',billRemindDays:'ថ្ងៃមុន',billRemindSame:'នៅថ្ងៃដល់កំណត់',billEdit:'កែវិក្កយបត្រ',billAdd:'បន្ថែមវិក្កយបត្រ',billSaved:'បានរក្សាទុកវិក្កយបត្រ',billDeleted:'បានលុបវិក្កយបត្រ',billPaidDone:'បានកត់ត្រាថាបានបង់',billReceivedDone:'បានកត់ត្រាថាបានទទួល',markPaid:'សម្គាល់ថាបានបង់',markReceived:'សម្គាល់ថាបានទទួល',billPause:'ផ្អាក',billResume:'បន្ត',billDeleteConfirm:'លុបវិក្កយបត្រនេះ? កំណត់ត្រាដែលបានកត់រួចនឹងនៅដដែល។',billMonthly:'សរុបវិក្កយបត្រប្រចាំខែ',billPaidThisMonth:'បានបង់ខែនេះ',billStatusOverdue:'ហួសកំណត់',billStatusPaid:'បានបង់ ✓',billStatusPaused:'បានផ្អាក',billDueToday:'ដល់កំណត់ថ្ងៃនេះ',billDueIn:'ដល់កំណត់ក្នុង',billOverdueBy:'ហួសកំណត់',billNextOn:'បន្ទាប់',dayWord:'ថ្ងៃ',daysWord:'ថ្ងៃ',billEveryMonth:'រៀងរាល់ខែ ថ្ងៃទី',billSeeAll:'មើលទាំងអស់'});

let items=[],totals={},loaded=false,busyNow=false,editing=null;
const BUILTIN={expense:['food','coffee','transport','shopping','bills','study','health','other'],income:['salary','other']};
const $$=id=>document.getElementById(id);
const dayText=n=>n+' '+t(n===1?'dayWord':'daysWord');
window.billDueText=function(days){
  if(days===0)return t('billDueToday');
  return days>0?`${t('billDueIn')} ${dayText(days)}`:`${t('billOverdueBy')} ${dayText(-days)}`;
};
function statusText(item){
  if(item.status==='paused')return t('billStatusPaused');
  if(item.status==='paid')return `${t('billStatusPaid')} · ${t('billNextOn')} ${item.due_date.slice(5)}`;
  if(item.status==='upcoming')return `${t('billNextOn')} ${item.due_date.slice(5)}`;
  return window.billDueText(item.days_until);
}
function categoryLabel(item){
  const custom=(window.customCategories||[]).find(c=>c.key===item.category);
  return custom?`${custom.icon||'✨'} ${custom.name}`:`${icons[item.category]||'📦'} ${t(item.category)}`;
}
function actionLabel(item){return t(item.kind==='income'?'markReceived':'markPaid');}

function billRow(item,compact){
  const row=node('div',undefined,'bill-row bill-'+item.status);
  row.append(node('span',item.kind==='income'?'💵':(icons[item.category]||'🧾'),'bill-icon'));
  const copy=node('div',undefined,'bill-copy');
  copy.append(node('b',item.title),node('small',statusText(item),'bill-status'));
  if(!compact)copy.append(node('small',`${categoryLabel(item)} · ${t('billEveryMonth')} ${item.day_of_month}`,'bill-meta'));
  const side=node('div',undefined,'bill-side');
  side.append(node('strong',(item.kind==='income'?'+ ':'')+money(item.amount,item.currency),'bill-amount'));
  if(['overdue','today','soon','upcoming'].includes(item.status)&&(!compact||item.status!=='upcoming')){
    const pay=node('button',actionLabel(item),'bill-pay');pay.type='button';
    pay.onclick=()=>markDone(item,pay);
    side.append(pay);
  }
  row.append(copy,side);
  if(!compact){
    const tools=node('div',undefined,'bill-tools');
    const edit=node('button',t('billEditBtn'),'text-btn');edit.type='button';edit.onclick=()=>openDialog(item);
    const pause=node('button',t(item.active?'billPause':'billResume'),'text-btn');pause.type='button';
    pause.onclick=()=>toggleActive(item);
    tools.append(edit,pause);row.append(tools);
  }
  return row;
}

function renderPreview(){
  const root=$$('billsPreview');if(!root)return;
  root.replaceChildren();
  const active=items.filter(i=>['overdue','today','soon'].includes(i.status)||(i.status==='upcoming'));
  const show=active.slice(0,3);
  if(!items.length){root.append(node('p',t('billsHomeEmpty'),'muted'));return;}
  if(!show.length){const paid=items.filter(i=>i.status==='paid').length;root.append(node('p',`${t('billStatusPaid')} ${paid}/${items.length}`,'muted'));return;}
  for(const item of show)root.append(billRow(item,true));
}
function renderList(){
  const root=$$('billsList');if(!root)return;
  root.replaceChildren();
  const summary=$$('billsSummary');summary.replaceChildren();
  const entries=Object.entries(totals);
  for(const [currency,amount] of entries){
    const box=node('div');box.append(node('small',t('billMonthly')),node('strong',money(amount,currency)));summary.append(box);
  }
  summary.hidden=!entries.length;
  if(!items.length){root.append(node('div',t('billsEmpty'),'empty'));return;}
  for(const item of items)root.append(billRow(item,false));
}
function renderAll(){renderPreview();renderList();}

async function loadBills(){
  try{
    const data=await api('/api/recurring');
    items=data.items;totals=data.monthly_expense_totals;loaded=true;renderAll();
    $$('billsError').textContent='';
  }catch(error){if($$('billsError'))$$('billsError').textContent=error.message;}
}
async function markDone(item,button){
  if(busyNow)return;busyNow=true;busy(button,true);
  try{
    await api(`/api/recurring/${item.id}/post`,{method:'POST',body:'{}'});
    toast(t(item.kind==='income'?'billReceivedDone':'billPaidDone'));
    await loadBills();
    if(typeof load==='function')load();
    window.refreshInbox?.();
  }catch(error){toast_error(error.message);}
  finally{busyNow=false;busy(button,false);}
}
function toast_error(message){notify(message);}
async function toggleActive(item){
  try{await api(`/api/recurring/${item.id}/active`,{method:'POST',body:JSON.stringify({active:!item.active})});await loadBills();window.refreshInbox?.();}
  catch(error){toast_error(error.message);}
}

// ---- add / edit dialog ----
function fillCategories(selected){
  const select=$$('billCategory'),kindValue=$$('billKind').value;
  select.replaceChildren();
  const add=(value,label)=>{const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);};
  for(const key of BUILTIN[kindValue])add(key,`${icons[key]||'📦'} ${t(key)}`);
  for(const c of (window.customCategories||[]).filter(c=>c.kind==='both'||c.kind===kindValue))add(c.key,`${c.icon||'✨'} ${c.name}`);
  if(selected&&[...select.options].some(o=>o.value===selected))select.value=selected;
}
function fillSelects(){
  const day=$$('billDay');if(!day.options.length)for(let d=1;d<=31;d++){const o=document.createElement('option');o.value=String(d);o.textContent=String(d);day.append(o);}
  const remind=$$('billRemind');const keep=remind.value;remind.replaceChildren();
  for(let d=0;d<=7;d++){const o=document.createElement('option');o.value=String(d);o.textContent=d===0?t('billRemindSame'):`${d} ${t(d===1?'billRemindDay':'billRemindDays')}`;remind.append(o);}
  remind.value=keep||'1';
}
function openDialog(item){
  if(!tg?.initData){notify(t('openTelegram'));return;}
  editing=item||null;fillSelects();
  $$('billDialogTitle').textContent=t(item?'billEdit':'billAdd');
  $$('billKind').value=item?item.kind:'expense';
  $$('billTitle').value=item?item.title:'';
  $$('billAmount').value=item?String(item.amount/(item.currency==='USD'?100:1)):'';
  $$('billCurrency').value=item?item.currency:($('currency')?.value||'KHR');
  $$('billAccount').value=item?item.account:'cash';
  $$('billDay').value=String(item?item.day_of_month:new Date().getDate());
  $$('billRemind').value=String(item?item.remind_days:1);
  fillCategories(item?.category);
  $$('billDelete').hidden=!item;$$('billFormError').textContent='';
  $$('billDialog').showModal();
}
async function saveBill(event){
  event.preventDefault();
  if(busyNow)return;
  const body={title:$$('billTitle').value.trim(),kind:$$('billKind').value,amount:$$('billAmount').value,currency:$$('billCurrency').value,
    category:$$('billCategory').value,account:$$('billAccount').value,day_of_month:Number($$('billDay').value),remind_days:Number($$('billRemind').value)};
  busyNow=true;busy($$('billSave'),true);$$('billFormError').textContent='';
  try{
    await api(editing?`/api/recurring/${editing.id}`:'/api/recurring',{method:editing?'PUT':'POST',body:JSON.stringify(body)});
    $$('billDialog').close();toast(t('billSaved'));await loadBills();window.refreshInbox?.();
  }catch(error){$$('billFormError').textContent=error.message;}
  finally{busyNow=false;busy($$('billSave'),false);}
}
async function deleteBill(){
  if(!editing||busyNow||!confirm(t('billDeleteConfirm')))return;
  busyNow=true;
  try{await api(`/api/recurring/${editing.id}`,{method:'DELETE'});$$('billDialog').close();toast(t('billDeleted'));await loadBills();window.refreshInbox?.();}
  catch(error){$$('billFormError').textContent=error.message;}
  finally{busyNow=false;}
}

function openBills(){showPage('recurring');loadBills();}
window.openBillsPage=openBills;
$$('openBills').onclick=openBills;
$$('openBillsHome').onclick=openBills;
$$('newBill').onclick=()=>openDialog(null);
$$('closeBill').onclick=()=>$$('billDialog').close();
$$('billsBack').onclick=()=>showPage('home');
$$('billForm').addEventListener('submit',saveBill);
$$('billDelete').onclick=deleteBill;
$$('billKind').onchange=()=>fillCategories();

const baseShowPage=showPage;
showPage=function(page){baseShowPage(page);if(page==='home'&&!loaded)loadBills();};
const baseTranslate=translate;
translate=function(){baseTranslate();if(loaded)renderAll();$$('billTitle').placeholder=t('billNamePh');};
translate();
if(tg?.initData)loadBills();
})();
