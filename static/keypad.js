'use strict';
/* Quick-entry keypad screen: ៛/$ toggle, big amount, category + memo chips, numeric keypad, save bar.
   It drives the existing #entryForm (same validation, same /api/transactions call), so nothing server-side changes.
   Edits, favorites, quick buttons and itemised expenses keep using the full form. */
Object.assign(en,{padSaveExpense:'Save expense',padSaveIncome:'Save income',padEnterAmount:'Enter amount',padRiel:'Riel',padDollar:'Dollar',padAccount:'Account',padNote:'Note:',padWrite:'Write',padWritePlaceholder:'Type a note…',padMore:'More options',padNeed:'Need',padWant:'Want',padNoType:'Unset',padToday:'Today',padCategory:'Category:',padClose:'Close',padExpense:'Expense',padIncome:'Income',padBackspace:'Delete digit',
  padMemoExpense:['Breakfast','Lunch','Coffee','Taxi','Groceries'],padMemoIncome:['Salary','Bonus','Gift','Refund']});
Object.assign(km,{padSaveExpense:'រក្សាទុកចំណាយ',padSaveIncome:'រក្សាទុកចំណូល',padEnterAmount:'បញ្ចូលចំនួនប្រាក់',padRiel:'រៀល',padDollar:'ដុល្លារ',padAccount:'គណនី',padNote:'ចំណាំ:',padWrite:'សរសេរ',padWritePlaceholder:'សរសេរចំណាំ…',padMore:'ជម្រើសបន្ថែម',padNeed:'ចាំបាច់',padWant:'ចង់បាន',padNoType:'មិនកំណត់',padToday:'ថ្ងៃនេះ',padCategory:'ប្រភេទ:',padClose:'បិទ',padExpense:'ចំណាយ',padIncome:'ចំណូល',padBackspace:'លុបលេខ',
  padMemoExpense:['អាហារពេលព្រឹក','អាហារថ្ងៃត្រង់','កាហ្វេ','តាក់ស៊ី','ផ្សារ'],padMemoIncome:['ប្រាក់ខែ','ប្រាក់រង្វាន់','អំណោយ','សងមកវិញ']});

(()=>{
const pad={cur:'KHR',raw:'',memo:'',account:'cash',type:'essential',category:'food',day:'',kind:'expense'};
const MAX_INT={KHR:12,USD:9};
const SPENDING=['essential','want','none'];
const DIGIT_KEYS=['1','2','3','4','5','6','7','8','9'];

const dialog=document.createElement('dialog');
dialog.id='padDialog';
dialog.setAttribute('aria-label','Quick entry');
dialog.innerHTML=`
<div class="pad-bg" aria-hidden="true"><span class="pad-bg-symbol">៛</span></div>
<div class="pad-top">
  <button type="button" class="pad-icon" id="padClose" aria-label="Close">✕</button>
  <button type="button" class="pad-more" id="padMore"></button>
</div>
<div class="pad-who"><div class="pad-avatar" id="padAvatar">M</div><div class="pad-name" id="padName"></div><div class="pad-kind" id="padKind"></div></div>
<div class="pad-currency" role="tablist"><button type="button" role="tab" data-cur="KHR" id="padKhr"></button><button type="button" role="tab" data-cur="USD" id="padUsd"></button></div>
<div class="pad-amount" id="padAmount" aria-live="polite"><span class="pad-sym" id="padSym">៛</span><span class="pad-num" id="padNum">0</span><i class="pad-caret"></i></div>
<div class="pad-meta">
  <span class="pad-meta-label" id="padAccountLabel"></span>
  <button type="button" class="pad-pill" id="padAccount"></button>
  <button type="button" class="pad-pill" id="padDay"></button>
  <button type="button" class="pad-pill" id="padType"></button>
  <input type="date" id="padDayInput" class="pad-day-input" min="2000-01-01" tabindex="-1" aria-hidden="true">
</div>
<div class="pad-chip-block"><span class="pad-chip-label" id="padCatLabel"></span><div class="pad-chips" id="padCats"></div></div>
<div class="pad-chip-block"><span class="pad-chip-label" id="padNoteLabel"></span><div class="pad-chips" id="padMemos"></div></div>
<input id="padNoteInput" class="pad-note-input" maxlength="300" hidden>
<p id="padError" class="pad-error" role="alert"></p>
<div class="pad-keys" id="padKeys"></div>
<button type="button" class="pad-save" id="padSave" disabled></button>`;
document.body.append(dialog);

const $p=id=>dialog.querySelector('#'+id);
const keysRoot=$p('padKeys');
DIGIT_KEYS.forEach(k=>keysRoot.append(keyButton(k,k)));
const extraKey=keyButton('extra','00');keysRoot.append(extraKey,keyButton('0','0'));
const back=keyButton('back','⌫');back.classList.add('pad-back');back.setAttribute('aria-label','Delete digit');keysRoot.append(back);

function keyButton(key,label){const b=document.createElement('button');b.type='button';b.className='pad-key';b.dataset.key=key;b.textContent=label;return b;}
function haptic(kind='light'){try{tg?.HapticFeedback?.impactOccurred(kind);}catch{}}
function fmtInt(digits){return digits.replace(/\B(?=(\d{3})+(?!\d))/g,',');}

function display(){
  const [i='',d]=pad.raw.split('.');
  const intPart=fmtInt(i||'0');
  $p('padNum').textContent=d===undefined?intPart:intPart+'.'+d;
  $p('padSym').textContent=pad.cur==='KHR'?'៛':'$';
  $p('padAmount').classList.toggle('pad-has',Number(pad.raw||0)>0);
  extraKey.textContent=pad.cur==='USD'?'.':'00';
  extraKey.dataset.key=pad.cur==='USD'?'dot':'00';
  extraKey.setAttribute('aria-label',pad.cur==='USD'?'Decimal point':'Double zero');
  $p('padSave').disabled=!(Number(pad.raw||0)>0);
  const n=$p('padNum').textContent.length;
  $p('padAmount').dataset.size=n>13?'xs':n>10?'s':n>8?'m':'l';
}

function press(key){
  haptic();
  $p('padError').textContent='';
  if(key==='back'){pad.raw=pad.raw.slice(0,-1);if(pad.raw==='0')pad.raw='';return display();}
  if(key==='dot'){if(pad.cur!=='USD'||pad.raw.includes('.'))return;pad.raw=(pad.raw||'0')+'.';return display();}
  const add=key==='00'?'00':key;
  const [i,d]=pad.raw.split('.');
  if(d!==undefined){if(pad.cur!=='USD'||d.length+add.length>2)return;pad.raw+=add;return display();}
  if(!pad.raw&&/^0+$/.test(add))return; // no leading zeros
  const next=(i||'')+add;
  if(next.length>MAX_INT[pad.cur])return;
  pad.raw=next;display();
}

function setCurrency(cur){
  if(pad.cur===cur)return;
  pad.cur=cur;
  if(cur==='KHR'&&pad.raw.includes('.'))pad.raw=pad.raw.split('.')[0]; // riel is whole units
  if(cur==='USD'&&pad.raw.length>MAX_INT.USD)pad.raw=pad.raw.slice(0,MAX_INT.USD);
  $p('padKhr').classList.toggle('on',cur==='KHR');$p('padUsd').classList.toggle('on',cur==='USD');
  $p('padKhr').setAttribute('aria-selected',String(cur==='KHR'));$p('padUsd').setAttribute('aria-selected',String(cur==='USD'));
  display();
}

function topMemos(){
  const counts=new Map();
  for(const r of state.transactions||[]){
    if(r.kind!==pad.kind)continue;
    const n=(r.note||'').trim();if(!n||n.length>40)continue;
    counts.set(n,(counts.get(n)||0)+1);
  }
  const recent=[...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,5).map(e=>e[0]);
  const presets=t(pad.kind==='expense'?'padMemoExpense':'padMemoIncome');
  const list=Array.isArray(presets)?presets:[];
  return [...new Set([...recent,...list])].slice(0,9);
}

function renderMemos(){
  const root=$p('padMemos');root.replaceChildren();
  const write=document.createElement('button');write.type='button';write.className='pad-chip pad-chip-write';
  write.textContent='✎ '+t('padWrite');
  write.onclick=()=>{const input=$p('padNoteInput');input.hidden=!input.hidden;if(!input.hidden){input.value=pad.memo;input.placeholder=t('padWritePlaceholder');input.focus();}};
  root.append(write);
  const memos=topMemos();
  if(pad.memo&&!memos.includes(pad.memo))memos.unshift(pad.memo);
  for(const m of memos){
    const b=document.createElement('button');b.type='button';b.className='pad-chip'+(m===pad.memo?' on':'');b.textContent=m;
    b.onclick=()=>{pad.memo=pad.memo===m?'':m;$p('padNoteInput').value=pad.memo;haptic();renderMemos();};
    root.append(b);
  }
}

function renderCats(){
  const root=$p('padCats');root.replaceChildren();
  for(const opt of $('category').options){
    const b=document.createElement('button');b.type='button';b.className='pad-chip'+(opt.value===pad.category?' on':'');b.textContent=opt.textContent;b.dataset.value=opt.value;
    b.onclick=()=>{pad.category=opt.value;haptic();renderCats();};
    root.append(b);
  }
  const on=root.querySelector('.on');if(on)on.scrollIntoView({inline:'center',block:'nearest'});
}

function renderPills(){
  $p('padAccount').textContent=(pad.account==='cash'?'💵 ':'🏦 ')+t(pad.account);
  $p('padDay').textContent='📅 '+(pad.day===(state.today||today())?t('padToday'):pad.day);
  const typeLabel={essential:'padNeed',want:'padWant',none:'padNoType'}[pad.type];
  $p('padType').textContent='🏷 '+t(typeLabel);
  $p('padType').hidden=pad.kind!=='expense';
}

function renderText(){
  $p('padKind').textContent=t(pad.kind==='expense'?'padExpense':'padIncome');
  $p('padKind').dataset.kind=pad.kind;
  $p('padKhr').textContent=t('padRiel');$p('padUsd').textContent=t('padDollar');
  $p('padAccountLabel').textContent=t('padAccount')+':';
  $p('padCatLabel').textContent=t('padCategory');$p('padNoteLabel').textContent=t('padNote');
  $p('padSave').textContent=t(pad.kind==='expense'?'padSaveExpense':'padSaveIncome');
  $p('padMore').textContent=t('padMore')+' ›';
  $p('padClose').setAttribute('aria-label',t('padClose'));
  back.setAttribute('aria-label',t('padBackspace'));
  const name=(state.user?.name||'MyMoney').trim();
  $p('padName').textContent=name;
  $p('padAvatar').textContent=name.split(/\s+/).filter(Boolean).slice(0,2).map(w=>[...w][0]).join('').toUpperCase()||'M';
  dialog.dataset.kind=pad.kind;
}

function openPad(entryKind){
  openEntry(entryKind);                       // reuses guards, request id and category list
  if(!$('entryDialog').open)return;           // blocked (not in Telegram / no access)
  $('entryDialog').close();
  pad.kind=entryKind;pad.cur=$('entryCurrency').value==='USD'?'USD':'KHR';pad.raw='';pad.memo='';
  pad.account='cash';pad.type=entryKind==='expense'?'essential':'none';
  pad.category=$('category').value;pad.day=state.today||today();
  $p('padNoteInput').hidden=true;$p('padNoteInput').value='';$p('padError').textContent='';
  renderText();renderCats();renderMemos();renderPills();
  $p('padKhr').classList.toggle('on',pad.cur==='KHR');$p('padUsd').classList.toggle('on',pad.cur==='USD');
  display();
  if(!dialog.open)dialog.showModal();
}

function syncForm(){
  $('amount').value=pad.raw.replace(/\.$/,'');
  $('entryCurrency').value=pad.cur;precision();
  $('category').value=pad.category;
  $('account').value=pad.account;
  $('day').value=pad.day;
  $('note').value=pad.memo;
  if(pad.kind==='expense')$('spendingType').value=pad.type;
}

function submit(){
  if(!(Number(pad.raw||0)>0)){$p('padError').textContent=t('padEnterAmount');return;}
  syncForm();
  if(!$('entryForm').checkValidity()){$p('padError').textContent=$('entryForm').querySelector(':invalid')?.validationMessage||t('padEnterAmount');return;}
  $('entryForm').requestSubmit($('saveEntry'));
}

function toFullForm(){
  syncForm();
  dialog.close();
  if(!$('entryDialog').open)$('entryDialog').showModal();
}

// Reflect the existing form's save state (busy / success / error) on the keypad screen.
new MutationObserver(()=>{
  const busyNow=$('saveEntry').getAttribute('aria-busy')==='true';
  $p('padSave').classList.toggle('busy',busyNow);
  if(dialog.open)$p('padSave').disabled=busyNow||!(Number(pad.raw||0)>0);
}).observe($('saveEntry'),{attributes:true,attributeFilter:['aria-busy']});
new MutationObserver(()=>{
  const message=$('formError').textContent;
  if(dialog.open&&message)$p('padError').textContent=message;
}).observe($('formError'),{childList:true,characterData:true,subtree:true});
// A successful save calls #entryDialog.close(); close the keypad too (errors keep it open).
const entryClose=$('entryDialog').close.bind($('entryDialog'));
$('entryDialog').close=(...a)=>{if(dialog.open&&!$('formError').textContent)dialog.close();return entryClose(...a);};

keysRoot.addEventListener('click',e=>{const b=e.target.closest('.pad-key');if(b)press(b.dataset.key);});
$p('padKhr').onclick=()=>{haptic();setCurrency('KHR');};
$p('padUsd').onclick=()=>{haptic();setCurrency('USD');};
$p('padAccount').onclick=()=>{pad.account=pad.account==='cash'?'bank':'cash';haptic();renderPills();};
$p('padType').onclick=()=>{pad.type=SPENDING[(SPENDING.indexOf(pad.type)+1)%SPENDING.length];haptic();renderPills();};
$p('padDay').onclick=()=>{const input=$p('padDayInput');input.max=state.today||today();input.value=pad.day;try{input.showPicker();}catch{input.focus();input.click();}};
$p('padDayInput').onchange=e=>{if(e.target.value){pad.day=e.target.value;renderPills();}};
$p('padNoteInput').oninput=e=>{pad.memo=e.target.value;renderMemos();};
$p('padClose').onclick=()=>dialog.close();
$p('padMore').onclick=toFullForm;
$p('padSave').onclick=submit;

dialog.addEventListener('keydown',e=>{
  if(e.target===$p('padNoteInput')){if(e.key==='Enter'){e.preventDefault();$p('padNoteInput').hidden=true;}return;}
  if(e.ctrlKey||e.metaKey||e.altKey)return;
  if(/^[0-9]$/.test(e.key)){press(e.key);e.preventDefault();}
  else if(e.key==='.'||e.key===','){press('dot');e.preventDefault();}
  else if(e.key==='Backspace'){press('back');e.preventDefault();}
  else if(e.key==='Enter'&&e.target.tagName!=='BUTTON'){submit();e.preventDefault();}
});

// Entry points: the plain Add buttons open the keypad; everything else keeps the full form.
[['addExpense','expense'],['addIncome','income'],['historyAdd','expense'],['historyIncome','income']].forEach(([id,k])=>{const b=$(id);if(b)b.onclick=()=>openPad(k);});

// Keep labels in sync when the language is switched while the keypad is open.
const origTranslate=translate;
translate=function(...a){const r=origTranslate.apply(this,a);if(dialog.open){renderText();renderMemos();renderPills();}return r;};
window.openQuickPad=openPad;
})();
