'use strict';
// Reminders: notes with a date (dd/mm/yyyy) and optional time, attached to a bill, a debt,
// a savings goal or nothing in particular. The server stores yyyy-mm-dd; this file is the
// only place that formats or parses the visible dd/mm/yyyy text.
(()=>{
Object.assign(en,{reminders:'Reminders',remindersHelp:'Set a reminder for a bill, a debt, a savings goal or anything else. The nearest date comes first.',newReminder:'＋ Add',
  remTypeGeneral:'General',remTypeBill:'Bill',remTypeDebt:'Debt',remTypeGoal:'Savings goal',remType:'Type',remLinked:'Linked record',remPickRecord:'Choose a record…',remNoRecords:'No records of this type yet.',
  remTitle:'Title',remTitlePh:'e.g. Call landlord',remAmount:'Amount (optional)',remNote:'Details',remNotePh:'What should you remember?',remDate:'Reminder date',remDateHint:'Format: dd/mm/yyyy',remPickDate:'Pick a date',remTime:'Time (optional)',
  remDateRequired:'Enter the reminder date as dd/mm/yyyy.',remDateInvalid:'That date does not exist. Enter a real date as dd/mm/yyyy, for example 05/11/2026.',remTitleRequired:'Enter a title.',remTimeInvalid:'Enter a valid time.',
  remSaved:'Record saved',remSet:'Reminder set for {date}',remDeleted:'Reminder deleted',remDeleteConfirm:'Delete this reminder?',remEdit:'Edit reminder',remAdd:'Add reminder',remEditBtn:'Edit',remDeleteBtn:'Delete',
  remEmpty:'No reminders yet. Add one so you never forget a bill, debt or goal.',remHomeEmpty:'Add a reminder for a bill, debt or savings goal.',remSeeAll:'See all',
  remToday:'Today',remTomorrow:'Tomorrow',remIn:'in',remOverdueBy:'Overdue by',remDay:'day',remDays:'days',remAt:'at',
  remSumToday:'Today',remSumWeek:'This week',remSumOverdue:'Overdue',remBanner:'{n} overdue reminder(s)',remBannerView:'View',
  nReminderBody:'{when}',nOpenReminders:'Open reminders'});
Object.assign(km,{reminders:'ការរំលឹក',remindersHelp:'កំណត់ការរំលឹកសម្រាប់វិក្កយបត្រ បំណុល គោលដៅសន្សំ ឬកិច្ចការទូទៅ។ កាលបរិច្ឆេទជិតបំផុតនៅខាងលើ។',newReminder:'＋ បន្ថែម',
  remTypeGeneral:'ទូទៅ',remTypeBill:'វិក្កយបត្រ',remTypeDebt:'បំណុល',remTypeGoal:'គោលដៅសន្សំ',remType:'ប្រភេទ',remLinked:'កំណត់ត្រាភ្ជាប់',remPickRecord:'ជ្រើសកំណត់ត្រា…',remNoRecords:'មិនទាន់មានកំណត់ត្រាប្រភេទនេះទេ។',
  remTitle:'ចំណងជើង',remTitlePh:'ឧ. ទូរស័ព្ទទៅម្ចាស់ផ្ទះ',remAmount:'ចំនួនទឹកប្រាក់ (ស្រេចចិត្ត)',remNote:'ខ្លឹមសារ',remNotePh:'តើត្រូវចងចាំអ្វី?',remDate:'កាលបរិច្ឆេទរំលឹក',remDateHint:'ទម្រង់៖ dd/mm/yyyy',remPickDate:'ជ្រើសកាលបរិច្ឆេទ',remTime:'ម៉ោង (ស្រេចចិត្ត)',
  remDateRequired:'សូមបញ្ចូលកាលបរិច្ឆេទរំលឹកជា dd/mm/yyyy។',remDateInvalid:'កាលបរិច្ឆេទមិនត្រឹមត្រូវ មិនមានថ្ងៃនេះទេ។ សូមបញ្ចូលជា dd/mm/yyyy ឧ. 05/11/2026។',remTitleRequired:'សូមបញ្ចូលចំណងជើង។',remTimeInvalid:'ម៉ោងមិនត្រឹមត្រូវ។',
  remSaved:'បានរក្សាទុកកំណត់ត្រា',remSet:'បានកំណត់ការរំលឹកនៅ {date}',remDeleted:'បានលុបការរំលឹក',remDeleteConfirm:'លុបការរំលឹកនេះ?',remEdit:'កែការរំលឹក',remAdd:'បន្ថែមការរំលឹក',remEditBtn:'កែ',remDeleteBtn:'លុប',
  remEmpty:'មិនទាន់មានការរំលឹកទេ។ បន្ថែមមួយ ដើម្បីកុំភ្លេចវិក្កយបត្រ បំណុល ឬគោលដៅ។',remHomeEmpty:'បន្ថែមការរំលឹកសម្រាប់វិក្កយបត្រ បំណុល ឬគោលដៅសន្សំ។',remSeeAll:'មើលទាំងអស់',
  remToday:'ថ្ងៃនេះ',remTomorrow:'ថ្ងៃស្អែក',remIn:'ក្នុង',remOverdueBy:'ហួសកំណត់',remDay:'ថ្ងៃ',remDays:'ថ្ងៃ',remAt:'ម៉ោង',
  remSumToday:'ថ្ងៃនេះ',remSumWeek:'សប្តាហ៍នេះ',remSumOverdue:'ហួសកំណត់',remBanner:'មានការរំលឹកហួសកំណត់ {n}',remBannerView:'មើល',
  nReminderBody:'{when}',nOpenReminders:'បើកការរំលឹក'});

const $$=id=>document.getElementById(id);
const pad=n=>String(n).padStart(2,'0');
const ICONS={general:'🔔',bill:'🧾',debt:'🤝',goal:'🎯'};
const TYPE_KEY={general:'remTypeGeneral',bill:'remTypeBill',debt:'remTypeDebt',goal:'remTypeGoal'};
let items=[],summary={overdue:0,today:0,week:0,total:0},loaded=false,busyNow=false,editing=null;
let records={bill:null,debt:null,goal:null},autoTitle='',dateTouched=false;

// ---- dd/mm/yyyy <-> yyyy-mm-dd ------------------------------------------------------
function isoToDisplay(iso){
  const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(iso||'');
  return m?`${m[3]}/${m[2]}/${m[1]}`:'';
}
// Returns yyyy-mm-dd, or null for anything that is not a real calendar date (31/02/2026 -> null).
function displayToIso(text){
  const m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((text||'').trim());
  if(!m)return null;
  const day=Number(m[1]),month=Number(m[2]),year=Number(m[3]);
  if(year<2000||year>2100)return null;
  const probe=new Date(Date.UTC(year,month-1,day));
  if(probe.getUTCFullYear()!==year||probe.getUTCMonth()!==month-1||probe.getUTCDate()!==day)return null;
  return `${year}-${pad(month)}-${pad(day)}`;
}
function maskDate(raw){
  const digits=raw.replace(/\D/g,'').slice(0,8);
  if(digits.length<=2)return digits;
  if(digits.length<=4)return digits.slice(0,2)+'/'+digits.slice(2);
  return digits.slice(0,2)+'/'+digits.slice(2,4)+'/'+digits.slice(4);
}
window.reminderDate={isoToDisplay,displayToIso};

const fill=(text,values)=>text.replace(/\{(\w+)\}/g,(_,k)=>values[k]??'');
function whenText(item){
  const d=item.days_until,unit=n=>`${n} ${t(n===1?'remDay':'remDays')}`;
  if(d<0)return `${t('remOverdueBy')} ${unit(-d)}`;
  if(d===0)return t('remToday');
  if(d===1)return t('remTomorrow');
  return `${t('remIn')} ${unit(d)}`;
}
window.reminderWhenText=whenText;
const dateTimeText=item=>isoToDisplay(item.remind_date)+(item.remind_time?` · ${t('remAt')} ${item.remind_time}`:'');
window.reminderDateTimeText=dateTimeText;

// ---- rendering ----------------------------------------------------------------------
function reminderRow(item,compact){
  const row=node('div',undefined,'rem-row rem-'+item.status);
  row.append(node('span',ICONS[item.ref_type]||'🔔','rem-icon'));
  const copy=node('div',undefined,'rem-copy');
  copy.append(node('b',item.title),node('small',`${dateTimeText(item)} · ${whenText(item)}`,'rem-when'));
  if(!compact&&item.note)copy.append(node('small',item.note,'rem-note'));
  if(!compact)copy.append(node('small',t(TYPE_KEY[item.ref_type]),'rem-type'));
  row.append(copy);
  if(item.amount!=null&&item.currency)row.append(node('strong',money(item.amount,item.currency),'rem-amount'));
  if(compact){row.tabIndex=0;row.onclick=()=>openRemindersPage();}
  else{
    const tools=node('div',undefined,'rem-tools');
    const edit=node('button',t('remEditBtn'),'text-btn');edit.type='button';edit.onclick=()=>openDialog(item);
    const del=node('button',t('remDeleteBtn'),'text-btn rem-del');del.type='button';del.onclick=()=>removeItem(item,del);
    tools.append(edit,del);row.append(tools);
  }
  return row;
}
function chips(root){
  root.replaceChildren();
  for(const [key,label,cls] of [['overdue','remSumOverdue','is-red'],['today','remSumToday',''],['week','remSumWeek','']]){
    if(key==='overdue'&&!summary.overdue&&root.id==='remHomeSummary')continue;
    const chip=node('div',undefined,'rem-chip '+cls+(summary[key]?' has-items':''));
    chip.append(node('small',t(label)),node('b',String(summary[key])));root.append(chip);
  }
}
function renderBanner(){
  const banner=$$('reminderBanner');if(!banner)return;
  const overdue=items.filter(i=>i.status==='overdue');
  banner.hidden=!overdue.length;
  $$('home')?.classList.toggle('has-reminder-banner',overdue.length>0);
  if(!overdue.length)return;
  $$('reminderBannerText').textContent='⚠ '+fill(t('remBanner'),{n:overdue.length});
  $$('reminderBannerList').textContent=overdue.slice(0,2).map(i=>`${i.title} (${isoToDisplay(i.remind_date)})`).join(' · ')+(overdue.length>2?' …':'');
}
function renderHome(){
  const root=$$('remPreview');if(!root)return;
  chips($$('remHomeSummary'));
  root.replaceChildren();
  if(!items.length){root.append(node('p',t('remHomeEmpty'),'muted'));return;}
  for(const item of items.slice(0,3))root.append(reminderRow(item,true));
}
function renderList(){
  const root=$$('remList');if(!root)return;
  chips($$('remSummary'));
  root.replaceChildren();
  if(!items.length){root.append(node('div',t('remEmpty'),'empty'));return;}
  for(const item of items)root.append(reminderRow(item,false));
}
function renderAll(){renderBanner();renderHome();renderList();}

async function loadReminders(){
  if(!tg?.initData)return;
  try{
    const data=await api('/api/reminders');
    items=data.items;summary=data.summary;loaded=true;renderAll();
    if($$('remError'))$$('remError').textContent='';
  }catch(error){if($$('remError'))$$('remError').textContent=error.message;}
}
async function removeItem(item,button){
  if(busyNow||!confirm(t('remDeleteConfirm')))return;
  busyNow=true;busy(button,true);
  try{await api(`/api/reminders/${item.id}`,{method:'DELETE'});toast(t('remDeleted'));await loadReminders();window.refreshInbox?.();}
  catch(error){notify(error.message);}
  finally{busyNow=false;busy(button,false);}
}

// ---- linked records -----------------------------------------------------------------
async function fetchRecords(type){
  if(records[type])return records[type];
  let list=[];
  if(type==='bill'){
    list=(await api('/api/recurring')).items.map(r=>({id:r.id,label:`${r.title} · ${money(r.amount,r.currency)}`,title:r.title,amount:r.amount,currency:r.currency,date:r.due_date}));
  }else if(type==='debt'){
    list=(await api('/api/debts?status=open')).debts.map(d=>{
      const left=d.amount-(d.paid_total||0);
      const who=t(d.direction==='lent'?'remDebtOwed':'remDebtOwe');
      return {id:d.id,label:`${d.person} · ${money(left,d.currency)}`,title:`${who} ${d.person}`,amount:left,currency:d.currency,date:d.due_date};
    });
  }else{
    list=(await api('/api/goals')).goals.map(g=>({id:g.id,label:`${g.title} · ${money(g.target,g.currency)}`,title:g.title,amount:Math.max(0,g.target-g.saved),currency:g.currency,date:g.target_date}));
  }
  records[type]=list;return list;
}
en.remDebtOwed='Collect from';en.remDebtOwe='Pay';
km.remDebtOwed='ទារពី';km.remDebtOwe='សងទៅ';

async function fillRecordSelect(selectedId){
  const type=$$('remType').value,wrap=$$('remRecordWrap'),select=$$('remRecord');
  wrap.hidden=type==='general';
  if(type==='general')return;
  select.replaceChildren();
  const first=document.createElement('option');first.value='';first.textContent=t('remPickRecord');select.append(first);
  try{
    const list=await fetchRecords(type);
    if(type!==$$('remType').value)return;
    for(const r of list){const o=document.createElement('option');o.value=String(r.id);o.textContent=r.label;select.append(o);}
    if(!list.length)first.textContent=t('remNoRecords');
    if(selectedId&&[...select.options].some(o=>o.value===String(selectedId)))select.value=String(selectedId);
  }catch(error){$$('remFormError').textContent=error.message;}
}
function onRecordPicked(){
  const type=$$('remType').value,id=Number($$('remRecord').value);
  const record=(records[type]||[]).find(r=>r.id===id);
  if(!record)return;
  const title=$$('remTitleInput');
  if(!title.value.trim()||title.value===autoTitle){title.value=record.title.slice(0,80);autoTitle=title.value;}
  if(!$$('remAmount').value&&record.amount){
    $$('remAmount').value=String(record.amount/(record.currency==='USD'?100:1));$$('remCurrency').value=record.currency;
  }
  // A bill's next due date / a debt's due date / a goal's target date, unless the user already chose a date.
  if(!dateTouched&&record.date&&record.date>=todayIso())setDate(record.date);
}
const todayIso=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Phnom_Penh'}).format(new Date());

// ---- dialog -------------------------------------------------------------------------
function setDate(iso){$$('remDateText').value=isoToDisplay(iso);$$('remDatePicker').value=iso||'';$$('remDateText').setCustomValidity('');}
function openDialog(item,preset){
  if(!tg?.initData){notify(t('openTelegram'));return;}
  editing=item||null;autoTitle='';dateTouched=!!item;records={bill:null,debt:null,goal:null};
  $$('remDialogTitle').textContent=t(item?'remEdit':'remAdd');
  $$('remType').value=item?item.ref_type:(preset?.ref_type||'general');
  $$('remTitleInput').value=item?item.title:'';
  $$('remAmount').value=item&&item.amount!=null?String(item.amount/(item.currency==='USD'?100:1)):'';
  $$('remCurrency').value=item?.currency||$('currency')?.value||'KHR';
  $$('remNoteInput').value=item?item.note:'';
  setDate(item?item.remind_date:todayIso());
  $$('remTime').value=item?.remind_time||'';
  $$('remDelete').hidden=!item;$$('remFormError').textContent='';
  $$('remDateError').textContent='';
  $$('reminderDialog').showModal();
  fillRecordSelect(item?.ref_id);
}
function validateDate(){
  const text=$$('remDateText').value;
  if(!text.trim()){$$('remDateError').textContent=t('remDateRequired');return null;}
  const iso=displayToIso(text);
  if(!iso){$$('remDateError').textContent=t('remDateInvalid');return null;}
  $$('remDateError').textContent='';
  $$('remDateText').value=isoToDisplay(iso);$$('remDatePicker').value=iso;
  return iso;
}
async function saveReminder(event){
  event.preventDefault();
  if(busyNow)return;
  $$('remFormError').textContent='';
  const title=$$('remTitleInput').value.trim();
  const iso=validateDate();
  if(!title){$$('remFormError').textContent=t('remTitleRequired');return;}
  if(!iso)return;
  const type=$$('remType').value,amount=$$('remAmount').value.trim();
  const body={ref_type:type,ref_id:type==='general'?null:(Number($$('remRecord').value)||null),title,note:$$('remNoteInput').value,
    amount:amount||null,currency:amount?$$('remCurrency').value:null,remind_date:iso,remind_time:$$('remTime').value||null};
  busyNow=true;busy($$('remSave'),true);
  try{
    await api(editing?`/api/reminders/${editing.id}`:'/api/reminders',{method:editing?'PUT':'POST',body:JSON.stringify(body)});
    $$('reminderDialog').close();
    toast(`${t('remSaved')} · ${fill(t('remSet'),{date:isoToDisplay(iso)})}`);
    await loadReminders();window.refreshInbox?.();
  }catch(error){$$('remFormError').textContent=error.message;}
  finally{busyNow=false;busy($$('remSave'),false);}
}
async function deleteFromDialog(){
  if(!editing||busyNow||!confirm(t('remDeleteConfirm')))return;
  busyNow=true;
  try{await api(`/api/reminders/${editing.id}`,{method:'DELETE'});$$('reminderDialog').close();toast(t('remDeleted'));await loadReminders();window.refreshInbox?.();}
  catch(error){$$('remFormError').textContent=error.message;}
  finally{busyNow=false;}
}

function openRemindersPage(){showPage('reminders');loadReminders();}
window.openRemindersPage=openRemindersPage;
window.openReminderDialog=openDialog;

// Date field: type dd/mm/yyyy (slashes are added), or tap 📅 for the native date picker.
const dateText=$$('remDateText');
dateText.addEventListener('input',event=>{
  if(event.inputType&&event.inputType.startsWith('delete'))return;
  dateText.value=maskDate(dateText.value);$$('remDateError').textContent='';dateTouched=true;
});
dateText.addEventListener('blur',()=>{if(dateText.value.trim())validateDate();});
$$('remDatePicker').addEventListener('change',()=>{
  const iso=$$('remDatePicker').value;
  if(iso){setDate(iso);$$('remDateError').textContent='';dateTouched=true;}
});
$$('remType').addEventListener('change',()=>{$$('remRecord').value='';fillRecordSelect();});
$$('remRecord').addEventListener('change',onRecordPicked);
$$('reminderForm').addEventListener('submit',saveReminder);
$$('remDelete').onclick=deleteFromDialog;
$$('closeReminder').onclick=()=>$$('reminderDialog').close();
$$('newReminder').onclick=()=>openDialog(null);
$$('newReminderHome').onclick=()=>openDialog(null);
$$('openRemindersHome').onclick=openRemindersPage;
$$('remindersBack').onclick=()=>showPage('home');
$$('reminderBannerView').onclick=openRemindersPage;

const baseShowPage=showPage;
showPage=function(page){baseShowPage(page);if((page==='home'||page==='reminders')&&tg?.initData)loadReminders();};
const baseTranslate=translate;
translate=function(){
  baseTranslate();
  $$('remTitleInput').placeholder=t('remTitlePh');$$('remNoteInput').placeholder=t('remNotePh');
  $$('remDateText').placeholder='dd/mm/yyyy';
  $$('remDatePickBtn').setAttribute('aria-label',t('remPickDate'));
  if(loaded)renderAll();
};
translate();
loadReminders();
// Keep the red banner honest when the app stays open across midnight.
document.addEventListener('visibilitychange',()=>{if(!document.hidden)loadReminders();});
})();
