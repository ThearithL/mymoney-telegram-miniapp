'use strict';
Object.assign(en,{calculator:'🧮 Calculator',receipts:'My receipts',personalReceipt:'Personal expense record',receiptHelp:'A summary of your saved entry, not a merchant-issued receipt.',expression:'Calculation',calcHelp:'× and ÷ are calculated before + and −. Parentheses are supported.',useAmount:'Use this amount',calcReview:'Review the amount and currency before saving.',calcInvalid:'Enter a valid calculation. Division by zero is not allowed.',calcPositive:'Use a positive amount within 1,000,000,000,000.',reference:'Reference',receiptNote:'Description / shop',receiptOwner:'Recorded by'});
Object.assign(km,{calculator:'🧮 គណនា',receipts:'បង្កាន់ដៃរបស់ខ្ញុំ',personalReceipt:'កំណត់ត្រាចំណាយផ្ទាល់ខ្លួន',receiptHelp:'សង្ខេបពីកំណត់ត្រារបស់អ្នក មិនមែនបង្កាន់ដៃចេញដោយហាងទេ។',expression:'រូបមន្ត',calcHelp:'× និង ÷ គណនាមុន + និង −។ អាចប្រើវង់ក្រចកបាន។',useAmount:'ប្រើចំនួននេះ',calcReview:'ពិនិត្យចំនួនប្រាក់ និងរូបិយប័ណ្ណមុនរក្សាទុក។',calcInvalid:'សូមបញ្ចូលរូបមន្តត្រឹមត្រូវ។ មិនអាចចែកនឹងសូន្យបានទេ។',calcPositive:'ប្រើចំនួនវិជ្ជមាន មិនលើស 1,000,000,000,000។',reference:'លេខកំណត់ត្រា',receiptNote:'ពណ៌នា / ហាង',receiptOwner:'អ្នកកត់ត្រា'});
// Strict recursive-descent arithmetic parser. No eval, Function or executable input.
function calculateExpression(source) {
  source=source.replace(/×/g,'*').replace(/[÷]/g,'/').replace(/−/g,'-');
  if(source.length>160 || !/^[\d\s.+*/()\-]+$/.test(source))throw Error('Invalid expression');
  const tokens=source.match(/(?:\d+(?:\.\d*)?|\.\d+)|[+*/()\-]/g)||[];let at=0;
  function atom(){const tok=tokens[at++];if(tok==='+'||tok==='-')return (tok==='-'?-1:1)*atom();if(tok==='('){const n=sum();if(tokens[at++]!==')')throw Error('Parenthesis');return n;}if(!tok||!/^\d|^\.\d/.test(tok))throw Error('Number');return Number(tok);}
  function product(){let n=atom();while(['*','/'].includes(tokens[at])){const op=tokens[at++],v=atom();if(op==='/'&&v===0)throw Error('Zero');n=op==='*'?n*v:n/v;}return n;}
  function sum(){let n=product();while(['+','-'].includes(tokens[at])){const op=tokens[at++],v=product();n=op==='+'?n+v:n-v;}return n;}
  const value=sum();if(at!==tokens.length||!Number.isFinite(value)||Math.abs(value)>1e12)throw Error('Range');return value;
}
let calculationTarget=false,calculationValue=null,receiptEntry=null;
function refreshCalculation(){try{calculationValue=calculateExpression($('calcExpression').value);$('calcResult').textContent=new Intl.NumberFormat(lang==='km'?'km-KH':'en-US',{maximumFractionDigits:8}).format(calculationValue);$('calcError').textContent='';}catch{calculationValue=null;$('calcResult').textContent='—';$('calcError').textContent=$('calcExpression').value?t('calcInvalid'):'';}$('useCalculation').disabled=calculationValue===null||calculationValue<=0;}
function openCalculator(fromEntry){calculationTarget=fromEntry;$('calcExpression').value=fromEntry?$('amount').value:'';refreshCalculation();$('calculatorDialog').showModal();}
for(const key of ['7','8','9','÷','4','5','6','×','1','2','3','−','0','.','(',')','C','⌫','+','=']){const b=node('button',key,'secondary');b.type='button';b.onclick=()=>{const input=$('calcExpression');if(key==='C')input.value='';else if(key==='⌫')input.value=input.value.slice(0,-1);else if(key==='='){if(calculationValue!==null)input.value=String(calculationValue);}else if(input.value.length<160)input.value+=key;refreshCalculation();};$('calcKeys').append(b);}
$('calcExpression').oninput=refreshCalculation;
$('openCalculator').onclick=()=>openCalculator(false);
$('entryCalculator').onclick=()=>openCalculator(true);
$('closeCalculator').onclick=()=>$('calculatorDialog').close();
$('useCalculation').onclick=()=>{if(calculationValue===null||calculationValue<=0)return;const currency=calculationTarget?$('entryCurrency').value:$('currency').value;const digits=currency==='USD'?2:0;const amount=Number(calculationValue.toFixed(digits));if(amount<=0){$('calcError').textContent=t('calcPositive');return;}if(!calculationTarget){openEntry('expense');if(!$('entryDialog').open)return;}$('amount').value=amount.toFixed(digits);$('calculatorDialog').close();$('amount').focus();};
function openReceipt(r){receiptEntry=r;const box=$('receiptContent');box.replaceChildren();box.append(node('div',money(r.amount,r.currency),'receipt-total'));const fields=[[t('reference'),'#'+r.id],[t('receiptOwner'),state.user?.name||''],[t('date'),r.day],[t('category'),t(r.category)],[t('account'),t(r.account)],[t('receiptNote'),r.note||'—']];for(const [label,value]of fields){const row=node('div',undefined,'receipt-line');row.append(node('span',label,'muted'),node('strong',value));box.append(row);}$('receiptDialog').showModal();}
const originalRows=rows;
rows=function(target,items){originalRows(target,items);const buttons=$(target).querySelectorAll('.row');buttons.forEach((b,i)=>{if(items[i].kind==='expense'){const replacement=b.cloneNode(true);replacement.addEventListener('click',()=>openReceipt(items[i]));b.replaceWith(replacement);}});};
$('closeReceipt').onclick=()=>$('receiptDialog').close();
$('editReceipt').onclick=()=>{$('receiptDialog').close();if(receiptEntry)openEntry(receiptEntry.kind,receiptEntry);};
$('openReceipts').onclick=()=>{filter='expense';pageSize=20;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('selected',b.dataset.filter===filter));renderHistory();showPage('history');};
translate();
