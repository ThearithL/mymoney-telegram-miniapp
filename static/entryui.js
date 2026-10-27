'use strict';
/* Entry form upgrade for Add expense / Add income / Edit.
   It drives the existing #entryForm controls (amount, currency, category, account, date, note, spending type),
   so validation, the /api/transactions call, itemised expenses and favorites are untouched. */
Object.assign(en,{exRiel:'Riel',exDollar:'Dollar',exToday:'Today',exYesterday:'Yesterday',exPick:'Pick date',exClear:'Clear',exSaveExpense:'Save expense',exSaveIncome:'Save income',exSaveEdit:'Save changes',
  exMemoExpense:['Breakfast','Lunch','Coffee','Taxi','Groceries'],exMemoIncome:['Salary','Bonus','Gift','Refund']});
Object.assign(km,{exRiel:'រៀល',exDollar:'ដុល្លារ',exToday:'ថ្ងៃនេះ',exYesterday:'ម្សិលមិញ',exPick:'ជ្រើសថ្ងៃ',exClear:'សម្អាត',exSaveExpense:'រក្សាទុកចំណាយ',exSaveIncome:'រក្សាទុកចំណូល',exSaveEdit:'រក្សាទុកការកែប្រែ',
  exMemoExpense:['អាហារពេលព្រឹក','អាហារថ្ងៃត្រង់','កាហ្វេ','តាក់ស៊ី','ផ្សារ'],exMemoIncome:['ប្រាក់ខែ','ប្រាក់រង្វាន់','អំណោយ','សងមកវិញ']});

(()=>{
const dlg=$('entryDialog'),form=$('entryForm'),amount=$('amount'),cur=$('entryCurrency'),cat=$('category'),acct=$('account'),
  day=$('day'),note=$('note'),stype=$('spendingType'),save=$('saveEntry'),del=$('deleteEntry'),entryId=$('entryId');
const tx=k=>(lang==='km'?km:en)[k]??en[k]??k;
const hap=()=>{try{tg?.HapticFeedback?.selectionChanged();}catch{}};
const el=(tag,cls)=>{const n=document.createElement(tag);if(cls)n.className=cls;return n;};
const btn=(cls,text)=>{const b=el('button',cls);b.type='button';if(text!==undefined)b.textContent=text;return b;};
const head=key=>{const s=el('span','ex-label');s.dataset.i=key;s.textContent=tx(key);return s;};
const fire=(sel,val)=>{sel.value=val;sel.dispatchEvent(new Event('change',{bubbles:true}));};
const fmt=n=>new Intl.NumberFormat('en-US',{maximumFractionDigits:cur.value==='USD'?2:0}).format(n);
const nowDay=()=>state.today||today();
const shift=(s,n)=>{const d=new Date(s+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);};

// Segmented control: items [{v,icon?,key}] -> a radio group that reads/writes a native select.
function seg(items,get,set,cls){
  const box=el('div','ex-seg'+(cls?' '+cls:''));box.setAttribute('role','radiogroup');
  box.buttons=items.map(it=>{
    const b=btn('');b.setAttribute('role','radio');b.dataset.v=it.v;
    if(it.icon){const i=el('span');i.setAttribute('aria-hidden','true');i.textContent=it.icon;b.append(i);}
    const s=el('span');s.dataset.i=it.key;s.textContent=tx(it.key);b.append(s);
    b.onclick=()=>{if(b.disabled)return;hap();set(it.v);sync();};
    box.append(b);return b;
  });
  box.refresh=()=>box.buttons.forEach(b=>b.setAttribute('aria-checked',String(b.dataset.v===get())));
  return box;
}

/* ---- amount hero: currency toggle, big amount, live conversion, quick-add chips ---- */
const hero=el('div','ex-hero'),amtRow=el('div','ex-amount'),sym=el('span','ex-sym'),conv=el('p','ex-conv'),quick=el('div','ex-quick');
conv.setAttribute('aria-live','polite');
const curSeg=seg([{v:'KHR',icon:'៛',key:'exRiel'},{v:'USD',icon:'$',key:'exDollar'}],()=>cur.value,v=>fire(cur,v),'ex-cur');
const amountRow=form.querySelector('.field-row');
amountRow.before(hero);amountRow.classList.add('ex-hide');
amtRow.append(sym,amount);hero.append(curSeg,amtRow,conv,quick);
amount.placeholder='0';amount.setAttribute('inputmode','decimal');amount.setAttribute('aria-label',tx('amount'));

/* ---- category chips ---- */
const catLabel=cat.closest('label');catLabel.classList.add('ex-hide');
const cats=el('div','ex-cats');cats.setAttribute('role','group');
catLabel.before(head('category'),cats);

/* ---- needs / wants (expenses only) ---- */
const typeLabel=$('spendingTypeLabel');typeLabel.classList.add('ex-hide');
const typeSeg=seg([{v:'essential',key:'essential'},{v:'want',key:'want'},{v:'none',key:'spendingNone'}],()=>stype.value,v=>fire(stype,v));
const typeBox=el('div','ex-need');typeBox.append(head('spendingType'),typeSeg);typeLabel.before(typeBox);

/* ---- account + date shortcuts ---- */
const accRow=acct.closest('.field-row');accRow.classList.add('ex-hide');
const accSeg=seg([{v:'cash',icon:'💵',key:'cash'},{v:'bank',icon:'🏦',key:'bank'}],()=>acct.value,v=>fire(acct,v));
const dateRow=el('div','ex-row'),dToday=btn('ex-chip'),dYest=btn('ex-chip'),dPick=btn('ex-chip');
dateRow.append(dToday,dYest,dPick);
const dateBox=el('div');dateBox.append(head('account'),accSeg,head('date'),dateRow,day);
day.classList.add('ex-sr');day.tabIndex=-1;accRow.before(dateBox);
const setDay=v=>{day.value=v;day.dispatchEvent(new Event('change',{bubbles:true}));};
dToday.onclick=()=>{hap();setDay(nowDay());};
dYest.onclick=()=>{hap();setDay(shift(nowDay(),-1));};
dPick.onclick=()=>{try{day.showPicker();}catch{day.focus();day.click();}};
day.addEventListener('change',renderDate);day.addEventListener('input',renderDate);

/* ---- note chips (recent notes first, then presets) ---- */
const noteLabel=note.closest('label');noteLabel.classList.add('ex-note');noteLabel.firstElementChild?.classList.add('ex-hide');
const memos=el('div','ex-row');noteLabel.before(head('note'),memos);
note.placeholder='…';

/* ---- sticky save bar ---- */
const footer=el('div','ex-footer');form.append(footer);footer.append(save,del);
save.removeAttribute('data-i');

function renderQuick(){
  const usd=cur.value==='USD',locked=amount.readOnly;
  quick.replaceChildren();
  (usd?[1,5,10,20]:[1000,5000,10000,50000]).forEach(n=>{
    const b=btn('ex-chip','+'+fmt(n));b.disabled=locked;
    b.onclick=()=>{hap();const v=Number(amount.value)||0;amount.value=String(usd?Math.round((v+n)*100)/100:v+n);amount.dispatchEvent(new Event('input',{bubbles:true}));};
    quick.append(b);
  });
  const c=btn('ex-chip ex-ghost',tx('exClear'));c.disabled=locked;
  c.onclick=()=>{hap();amount.value='';amount.dispatchEvent(new Event('input',{bubbles:true}));amount.focus();};
  quick.append(c);
}
function renderConv(){
  const v=Number(amount.value),rate=typeof fxRate==='number'&&fxRate>0?fxRate:0;
  if(!(v>0)||!rate){conv.textContent='';return;}
  conv.textContent=cur.value==='USD'?'≈ ៛'+Math.round(v*rate).toLocaleString('en-US'):'≈ $'+(v/rate).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function renderCats(){
  const opts=[...cat.options],sig=opts.map(o=>o.value+'\u0001'+o.textContent).join('\u0002');
  if(cats.dataset.sig!==sig){
    cats.replaceChildren();
    opts.forEach(o=>{
      const b=btn('ex-chip ex-cat'),m=o.textContent.trim().match(/^(\S+)\s+([\s\S]+)$/),ic=el('span','ex-ic'),lb=el('span','ex-tx');
      ic.textContent=m?m[1]:'•';lb.textContent=m?m[2]:o.textContent;b.title=lb.textContent;b.dataset.v=o.value;b.append(ic,lb);
      b.onclick=()=>{hap();fire(cat,o.value);sync();};cats.append(b);
    });
    cats.dataset.sig=sig;
  }
  [...cats.children].forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.v===cat.value)));
}
function renderDate(){
  const d=day.value,t0=nowDay(),y=shift(t0,-1);
  dToday.textContent=tx('exToday');dYest.textContent=tx('exYesterday');
  dToday.setAttribute('aria-pressed',String(d===t0));dYest.setAttribute('aria-pressed',String(d===y));
  const other=d&&d!==t0&&d!==y;dPick.setAttribute('aria-pressed',String(!!other));
  let label=tx('exPick');
  if(other){try{label=new Date(d+'T00:00:00Z').toLocaleDateString(lang==='km'?'km-KH':'en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});}catch{label=d;}}
  dPick.textContent='📅 '+label;
}
function memoList(){
  const k=dlg.dataset.kind,out=[];
  for(const r of state.transactions||[]){const n=(r.kind===k&&r.note||'').trim();if(n&&!out.includes(n))out.push(n);if(out.length>=4)break;}
  for(const p of tx(k==='income'?'exMemoIncome':'exMemoExpense')||[]){if(out.length>=7)break;if(!out.includes(p))out.push(p);}
  return out;
}
function renderMemos(){
  memos.replaceChildren();
  memoList().forEach(text=>{
    const b=btn('ex-chip',text.length>22?text.slice(0,21)+'…':text);b.title=text;b.dataset.v=text;
    b.onclick=()=>{hap();note.value=note.value===text?'':text;markMemos();};memos.append(b);
  });
  markMemos();
}
function markMemos(){[...memos.children].forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.v===note.value)));}
function renderSave(){
  const v=Number(amount.value);
  let text=tx(entryId.value?'exSaveEdit':dlg.dataset.kind==='income'?'exSaveIncome':'exSaveExpense');
  if(v>0)text+=' · '+(cur.value==='USD'?'$'+v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'៛'+fmt(v));
  save.textContent=text;
}
function sync(){
  dlg.dataset.kind=kind==='income'?'income':'expense';
  sym.textContent=cur.value==='USD'?'$':'៛';
  const locked=amount.readOnly||cur.disabled;
  curSeg.refresh();curSeg.buttons.forEach(b=>b.disabled=locked);
  typeSeg.refresh();accSeg.refresh();
  renderQuick();renderConv();renderCats();renderDate();markMemos();renderSave();
}

amount.addEventListener('input',()=>{renderConv();renderSave();});
note.addEventListener('input',markMemos);
cur.addEventListener('change',sync);
form.addEventListener('reset',()=>setTimeout(sync,0));
new MutationObserver(()=>{if(dlg.open)renderCats();}).observe(cat,{childList:true});
new MutationObserver(()=>{if(dlg.open)sync();}).observe(amount,{attributes:true,attributeFilter:['readonly']});
new MutationObserver(()=>{if(dlg.open)sync();}).observe(cur,{attributes:true,attributeFilter:['disabled']});
new MutationObserver(()=>{
  if(!dlg.open)return;
  sync();renderMemos();dlg.scrollTop=0;
  setTimeout(()=>{if(dlg.open&&!entryId.value&&!amount.readOnly)amount.focus({preventScroll:true});},90);
}).observe(dlg,{attributes:true,attributeFilter:['open']});

// Tap outside the sheet to close (only when the press also started outside, so text selection drags don't close it).
let downOnBackdrop=false;
dlg.addEventListener('pointerdown',e=>{downOnBackdrop=e.target===dlg;});
dlg.addEventListener('click',e=>{if(e.target===dlg&&downOnBackdrop)dlg.close();});

// Keep labels right when the language is switched while the sheet is open.
const origTranslate=translate;
translate=function(...a){const r=origTranslate.apply(this,a);if(dlg.open){sync();renderMemos();}return r;};
})();
