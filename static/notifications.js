'use strict';
(()=>{
Object.assign(en,{notifications:'Notifications',notificationsHelp:'Get reminders from the bot in Telegram. Open the bot chat and send /start once so it can message you. The daily reminder is skipped if you already logged something today.',notifDailyLabel:'Daily spending reminder',notifDailyHourLabel:'Remind me at (Phnom Penh time)',notifDebtLabel:'Debt due-date reminders',notifDebtDaysLabel:'Remind me before the due date',notifOn:'On',notifOff:'Off',notifOnDueDay:'Only on the due day',notifDay:'day before',notifDays:'days before',notifTest:'Send a test message',notifSaved:'Notification settings saved',notifTestSent:'Test message sent. Check Telegram.'});
Object.assign(km,{notifications:'ការជូនដំណឹង',notificationsHelp:'ទទួលការរំលឹកពី Bot ក្នុង Telegram។ សូមបើកការសន្ទនា Bot ហើយផ្ញើ /start ម្ដង ដើម្បីឲ្យ Bot អាចផ្ញើសារមកអ្នកបាន។ ការរំលឹកប្រចាំថ្ងៃនឹងមិនផ្ញើទេ ប្រសិនបើអ្នកបានកត់ត្រារួចហើយថ្ងៃនេះ។',notifDailyLabel:'រំលឹកកត់ត្រាចំណាយប្រចាំថ្ងៃ',notifDailyHourLabel:'រំលឹកនៅម៉ោង (ម៉ោងភ្នំពេញ)',notifDebtLabel:'រំលឹកថ្ងៃដល់កំណត់បំណុល',notifDebtDaysLabel:'រំលឹកមុនថ្ងៃដល់កំណត់',notifOn:'បើក',notifOff:'បិទ',notifOnDueDay:'តែថ្ងៃដល់កំណត់',notifDay:'ថ្ងៃមុន',notifDays:'ថ្ងៃមុន',notifTest:'ផ្ញើសារសាកល្បង',notifSaved:'បានរក្សាទុកការកំណត់ការជូនដំណឹង',notifTestSent:'បានផ្ញើសារសាកល្បង។ សូមពិនិត្យ Telegram។'});

const prefs={daily_enabled:false,daily_hour:20,debt_enabled:true,debt_days_before:1};
let loaded=false,busy=false;
const setStatus=message=>{$('notifStatus').textContent=message||'';};
function fill(select,options,value){
  select.replaceChildren();
  for(const [optionValue,label] of options){const option=document.createElement('option');option.value=String(optionValue);option.textContent=label;select.append(option);}
  select.value=String(value);
}
function readForm(){
  return {daily_enabled:$('notifDaily').value==='1',daily_hour:Number($('notifDailyHour').value),
    debt_enabled:$('notifDebt').value==='1',debt_days_before:Number($('notifDebtDays').value)};
}
function renderNotif(){
  const onOff=[[0,t('notifOff')],[1,t('notifOn')]];
  fill($('notifDaily'),onOff,prefs.daily_enabled?1:0);
  fill($('notifDailyHour'),Array.from({length:24},(_,hour)=>[hour,String(hour).padStart(2,'0')+':00']),prefs.daily_hour);
  fill($('notifDebt'),onOff,prefs.debt_enabled?1:0);
  fill($('notifDebtDays'),Array.from({length:8},(_,days)=>[days,days===0?t('notifOnDueDay'):days+' '+t(days===1?'notifDay':'notifDays')]),prefs.debt_days_before);
  $('notifDailyHour').disabled=!prefs.daily_enabled;
  $('notifDebtDays').disabled=!prefs.debt_enabled;
}
async function loadNotif(){
  try{Object.assign(prefs,await api('/api/notifications'));loaded=true;renderNotif();setStatus('');}
  catch(error){setStatus(error.message);}
}
for(const id of ['notifDaily','notifDailyHour','notifDebt','notifDebtDays'])
  $(id).addEventListener('change',()=>{Object.assign(prefs,readForm());renderNotif();});
$('notifSave').onclick=async()=>{
  if(busy)return;busy=true;setStatus(t('loading'));
  try{Object.assign(prefs,await api('/api/notifications',{method:'PUT',body:JSON.stringify(readForm())}));loaded=true;renderNotif();setStatus('');toast(t('notifSaved'));}
  catch(error){setStatus(error.message);}
  finally{busy=false;}
};
$('notifTest').onclick=async()=>{
  if(busy)return;busy=true;setStatus(t('loading'));
  try{await api('/api/notifications/test',{method:'POST',body:'{}'});setStatus('');toast(t('notifTestSent'));}
  catch(error){setStatus(error.message);}
  finally{busy=false;}
};

const baseShowPage=showPage;
showPage=function(page){baseShowPage(page);if(page==='settings'&&!loaded)loadNotif();};
const baseTranslate=translate;
translate=function(){baseTranslate();renderNotif();};
translate();
})();
