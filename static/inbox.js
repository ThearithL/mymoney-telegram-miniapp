'use strict';
// Notification center: a bell in the header with a list of alerts computed by the server
// (budget, debts, bills, savings goals, "nothing logged today"). Read state is per device.
(()=>{
Object.assign(en,{inboxTitle:'Notifications',inboxEmpty:'You are all caught up. Nothing needs your attention right now.',inboxMarkRead:'Mark all as read',inboxSettings:'Settings',inboxNew:'New',inboxEarlier:'Earlier',inboxRefresh:'Refresh',
  nBudgetWarn:'Budget {pct}% used',nBudgetReached:'Budget fully used',nBudgetOver:'Over budget',nBudgetWarnBody:'{spent} of {budget} spent · {left} left ({cur})',nBudgetReachedBody:'{spent} of {budget} spent ({cur})',nBudgetOverBody:'Over by {over} · {spent} of {budget} ({cur})',
  nDebtOwed:'{person} owes you {amount}',nDebtOwe:'You owe {person} {amount}',nBillTitle:'{title}',nBillBody:'{amount} · {due}',nGoalDone:'Goal reached: {title}',nGoalNear:'{title} is {level}% funded',nGoalBody:'{saved} of {target}',nNoLog:'Nothing logged today',nNoLogBody:'Add today’s spending to keep your records accurate.',
  nOpenBudget:'Open budget',nOpenDebts:'Open debts',nOpenGoals:'Open goals',nAddEntry:'Add entry',
  notifBillLabel:'Bill & subscription reminders',notifWeeklyLabel:'Weekly summary (Sunday evening)',
  inboxClearAll:'Clear all',inboxClearItem:'Clear',inboxCleared:'Notifications cleared',nReminderToday:'Reminder: {title}',nReminderOver:'Overdue reminder: {title}'});
Object.assign(km,{inboxTitle:'ការជូនដំណឹង',inboxEmpty:'អ្វីៗរួចរាល់ហើយ។ មិនមានអ្វីត្រូវការការយកចិត្តទុកដាក់ទេពេលនេះ។',inboxMarkRead:'សម្គាល់ថាបានអានទាំងអស់',inboxSettings:'ការកំណត់',inboxNew:'ថ្មី',inboxEarlier:'មុននេះ',inboxRefresh:'ផ្ទុកឡើងវិញ',
  nBudgetWarn:'ថវិកាបានប្រើ {pct}%',nBudgetReached:'ថវិកាប្រើអស់ហើយ',nBudgetOver:'លើសថវិកា',nBudgetWarnBody:'ចំណាយ {spent} ពី {budget} · នៅសល់ {left} ({cur})',nBudgetReachedBody:'ចំណាយ {spent} ពី {budget} ({cur})',nBudgetOverBody:'លើស {over} · {spent} ពី {budget} ({cur})',
  nDebtOwed:'{person} ជំពាក់អ្នក {amount}',nDebtOwe:'អ្នកជំពាក់ {person} {amount}',nBillTitle:'{title}',nBillBody:'{amount} · {due}',nGoalDone:'សម្រេចគោលដៅ៖ {title}',nGoalNear:'{title} បានសន្សំ {level}%',nGoalBody:'{saved} ពី {target}',nNoLog:'ថ្ងៃនេះមិនទាន់កត់ត្រា',nNoLogBody:'សូមបន្ថែមការចំណាយថ្ងៃនេះ ដើម្បីរក្សាកំណត់ត្រាឱ្យត្រឹមត្រូវ។',
  nOpenBudget:'បើកថវិកា',nOpenDebts:'បើកបំណុល',nOpenGoals:'បើកគោលដៅ',nAddEntry:'បន្ថែមកំណត់ត្រា',
  notifBillLabel:'រំលឹកវិក្កយបត្រ និងការជាវ',notifWeeklyLabel:'សង្ខេបប្រចាំសប្តាហ៍ (ល្ងាចថ្ងៃអាទិត្យ)',
  inboxClearAll:'សម្អាតទាំងអស់',inboxClearItem:'សម្អាត',inboxCleared:'បានសម្អាតការជូនដំណឹង',nReminderToday:'ការរំលឹក៖ {title}',nReminderOver:'ការរំលឹកហួសកំណត់៖ {title}'});

const KEY='mymoney-notif-read',CLEARED_KEY='mymoney-notif-cleared';
let feed=[],read=new Set(),cleared=new Set(),timer=null,loading=false;
try{read=new Set(JSON.parse(localStorage.getItem(KEY)||'[]'));}catch{}
try{cleared=new Set(JSON.parse(localStorage.getItem(CLEARED_KEY)||'[]'));}catch{}
// Cleared ids stay hidden on this device. Ids change when the situation changes (new budget
// level, new due date), so a genuinely new alert still shows up.
const visible=()=>feed.filter(i=>!cleared.has(i.id));
function saveCleared(){
  const live=new Set(feed.map(i=>i.id));
  cleared=new Set([...cleared].filter(id=>live.has(id)));
  try{localStorage.setItem(CLEARED_KEY,JSON.stringify([...cleared].slice(-300)));}catch{}
}
function saveRead(){
  // Keep only ids that still exist, so the stored list cannot grow forever.
  const live=new Set(feed.map(i=>i.id));
  read=new Set([...read].filter(id=>live.has(id)));
  try{localStorage.setItem(KEY,JSON.stringify([...read].slice(-200)));}catch{}
}
const fill=(text,values)=>text.replace(/\{(\w+)\}/g,(_,k)=>values[k]??'');
const unreadCount=()=>visible().filter(i=>!read.has(i.id)).length;

function describe(item){
  const d=item.data;
  switch(item.type){
    case 'budget':{
      const base={pct:Math.floor(Number(d.percent)||0),spent:money(d.spent,d.currency),budget:money(d.budget,d.currency),left:money(Math.max(0,d.remaining??0),d.currency),over:money(d.overspent,d.currency),cur:d.currency};
      const key=d.status==='warning'?'nBudgetWarn':d.status==='reached'?'nBudgetReached':'nBudgetOver';
      return {icon:d.status==='warning'?'📊':'⚠️',title:fill(t(key),base),body:fill(t(key+'Body'),base),action:'nOpenBudget',go:()=>{showPage('budget');if(typeof updateBudgetContext==='function')updateBudgetContext();}};
    }
    case 'debt':{
      const values={person:d.person,amount:money(d.remaining,d.currency)};
      return {icon:'🤝',title:fill(t(d.direction==='lent'?'nDebtOwed':'nDebtOwe'),values),body:window.billDueText?window.billDueText(d.days_until):'',action:'nOpenDebts',go:()=>{if(typeof openDebtPage==='function')openDebtPage();}};
    }
    case 'bill':
      return {icon:d.kind==='income'?'💵':'🧾',title:fill(t('nBillTitle'),{title:d.title}),body:fill(t('nBillBody'),{amount:money(d.amount,d.currency),due:window.billDueText?window.billDueText(d.days_until):''}),action:null,bill:d};
    case 'reminder':{
      const when=[window.reminderDateTimeText?window.reminderDateTimeText(d):d.remind_date,window.reminderWhenText?window.reminderWhenText(d):''].filter(Boolean).join(' · ');
      const amount=d.amount!=null&&d.currency?' · '+money(d.amount,d.currency):'';
      return {icon:'⏰',title:fill(t(d.days_until<0?'nReminderOver':'nReminderToday'),{title:d.title}),body:when+amount+(d.note?'\n'+d.note:''),action:'nOpenReminders',go:()=>{if(window.openRemindersPage)window.openRemindersPage();}};
    }
    case 'goal':
      return {icon:d.level>=100?'🎉':'🎯',title:fill(t(d.level>=100?'nGoalDone':'nGoalNear'),{title:d.title,level:d.level}),body:fill(t('nGoalBody'),{saved:money(d.saved,d.currency),target:money(d.target,d.currency)}),action:'nOpenGoals',go:()=>showPage('goals')};
    default:
      return {icon:'📝',title:t('nNoLog'),body:t('nNoLogBody'),action:'nAddEntry',go:()=>openEntry('expense')};
  }
}

function renderBadge(){
  const badge=document.getElementById('bellBadge'),n=unreadCount();
  if(!badge)return;
  badge.hidden=n===0;badge.textContent=n>9?'9+':String(n);
  document.getElementById('bellBtn').setAttribute('aria-label',`${t('inboxTitle')}${n?` (${n})`:''}`);
}
function renderList(){
  const root=$('inboxList');root.replaceChildren();
  const shown=visible();
  $('inboxClearAll').hidden=!shown.length;
  if(!shown.length){root.append(node('div',t('inboxEmpty'),'empty'));return;}
  const section=(label,list)=>{
    if(!list.length)return;
    root.append(node('h3',label,'inbox-group'));
    for(const item of list){
      const info=describe(item);
      const card=node('article',undefined,`inbox-item level-${item.level}${read.has(item.id)?' is-read':''}`);
      const dismiss=node('button','✕','inbox-dismiss');dismiss.type='button';
      dismiss.setAttribute('aria-label',t('inboxClearItem'));dismiss.title=t('inboxClearItem');
      dismiss.onclick=()=>clearItems([item.id]);
      card.append(node('span',info.icon,'inbox-icon'));
      const copy=node('div',undefined,'inbox-copy');
      copy.append(node('b',info.title));if(info.body)copy.append(node('small',info.body));
      const actions=node('div',undefined,'inbox-actions');
      if(info.bill){
        const pay=node('button',t(info.bill.kind==='income'?'markReceived':'markPaid'),'bill-pay');pay.type='button';
        pay.onclick=async()=>{
          busy(pay,true);
          try{await api(`/api/recurring/${info.bill.recurring_id}/post`,{method:'POST',body:'{}'});toast(t(info.bill.kind==='income'?'billReceivedDone':'billPaidDone'));if(typeof load==='function')load();await refresh();}
          catch(error){notify(error.message);busy(pay,false);}
        };
        actions.append(pay);
      }else if(info.action){
        const go=node('button',t(info.action),'text-btn');go.type='button';
        go.onclick=()=>{$('inboxDialog').close();info.go();};actions.append(go);
      }
      copy.append(actions);card.append(copy,dismiss);root.append(card);
    }
  };
  section(t('inboxNew'),shown.filter(i=>!read.has(i.id)));
  section(t('inboxEarlier'),shown.filter(i=>read.has(i.id)));
}
async function refresh(){
  if(loading||!tg?.initData)return;
  loading=true;
  try{
    feed=(await api('/api/notifications/feed')).items;
    renderBadge();if($('inboxDialog').open)renderList();
  }catch{/* the bell simply keeps its last state */}
  finally{loading=false;}
}
function markAllRead(){for(const i of visible())read.add(i.id);saveRead();renderBadge();renderList();}
function clearItems(ids,announce){
  for(const id of ids)cleared.add(id);
  saveCleared();renderBadge();renderList();
  if(announce)toast(t('inboxCleared'));
}
async function openInbox(){
  if(!tg?.initData){notify(t('openTelegram'));return;}
  renderList();$('inboxDialog').showModal();
  await refresh();renderList();
}

// Header bell
const bell=document.createElement('button');
bell.id='bellBtn';bell.type='button';bell.className='pill bell-btn';
bell.append(document.createTextNode('🔔'));
const badge=node('span','','bell-badge');badge.id='bellBadge';badge.hidden=true;bell.append(badge);
document.querySelector('header').insertBefore(bell,document.getElementById('privacyToggle'));
bell.onclick=openInbox;
$('closeInbox').onclick=()=>{$('inboxDialog').close();};
$('inboxDialog').addEventListener('close',markAllRead);
$('inboxRefresh').onclick=()=>refresh();
$('inboxClearAll').onclick=()=>clearItems(visible().map(i=>i.id),true);
$('inboxSettings').onclick=()=>{$('inboxDialog').close();showPage('settings');};
window.refreshInbox=refresh;

const baseTranslate=translate;
translate=function(){baseTranslate();renderBadge();if($('inboxDialog').open)renderList();};
translate();
refresh();
timer=setInterval(()=>{if(!document.hidden)refresh();},5*60*1000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
