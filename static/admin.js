'use strict';
let adminSelectedUser = null;
let adminOverview = null;
let adminUsersCache = [];

async function loadAdminOverview(){
  try{
    adminOverview=await api('/api/admin/overview');
    const metrics=$('adminMetrics');metrics.replaceChildren();
    for(const [label,value] of [['Users / អ្នកប្រើ',adminOverview.user_count],['Transactions / កំណត់ត្រា',adminOverview.transaction_count]]){
      const card=node('div',undefined,'admin-metric');card.append(node('small',label),node('strong',String(value)));metrics.append(card);
    }
    for(const currency of ['USD','KHR']){
      const amount=adminOverview.expenses.find(item=>item.currency===currency)?.amount||0;
      const card=node('div',undefined,'admin-metric');card.append(node('small',`Expenses this month · ${currency}`),node('strong',money(amount,currency)));metrics.append(card);
    }
    const statuses=adminOverview.statuses, statusBox=$('adminStatusBreakdown');statusBox.replaceChildren(node('h4','User access / សិទ្ធិអ្នកប្រើ'));
    for(const [key,label] of [['admin','Admins'],['approved','Approved'],['pending','Pending'],['revoked','Revoked'],['not_requested','Not requested']]){
      statusBox.append(node('span',`${label}: ${statuses[key]||0}`,'admin-status-chip'));
    }
    renderAdminDonut();
  }catch(error){$('adminMetrics').replaceChildren(node('p',error.message,'form-status'));}
}

function renderAdminDonut(){
  if(!adminOverview)return;
  const currency=$('adminChartCurrency').value;
  const rows=adminOverview.categories.filter(row=>row.currency===currency&&row.amount>0).sort((a,b)=>b.amount-a.amount);
  const total=rows.reduce((sum,row)=>sum+row.amount,0), colors=['#18845b','#e39c35','#5477d4','#d95c67','#8b63c7','#36a6a0','#b5a33b','#78838c'];
  let angle=0;const stops=[];
  rows.forEach((row,index)=>{const next=angle+(row.amount/total*360);stops.push(`${colors[index%colors.length]} ${angle}deg ${next}deg`);angle=next;});
  $('adminDonut').style.background=total?`conic-gradient(${stops.join(',')})`:'conic-gradient(var(--line) 0deg 360deg)';
  $('adminDonutTotal').textContent=money(total,currency);$('adminDonutLabel').textContent=total?`${adminOverview.month} · ${currency}`:'No expenses';
  const legend=$('adminChartLegend');legend.replaceChildren();
  if(!rows.length)legend.append(node('p','No expenses recorded this month. / ខែនេះមិនទាន់មានចំណាយទេ។','muted'));
  rows.forEach((row,index)=>{const item=node('div',undefined,'admin-legend-item');item.append(node('i','',undefined));item.lastChild.style.background=colors[index%colors.length];item.append(node('span',row.category),node('strong',money(row.amount,currency)));legend.append(item);});
}

async function loadAdminConsole(){
  const status=$('adminStatus');
  status.textContent='Loading admin data… / កំពុងទាញទិន្នន័យ Admin…';
  $('adminUsers').replaceChildren();
  $('adminUserDetail').hidden=true;
  $('adminOwnerTools').hidden=!state.user?.is_owner;
  $('adminAddUserCard').hidden=!state.user?.is_owner;
  await loadAdminOverview();
  try{
    const result=await api('/api/admin/users');
    adminUsersCache=result.users;
    status.textContent=`${result.users.length} users / អ្នកប្រើ ${result.users.length} នាក់`;
    renderAdminUserList();
    if(state.user?.is_admin)await loadAdminAccounts();
  }catch(error){status.textContent=error.message;}
}

function renderAdminUserList(){
    const list=$('adminUsers');list.replaceChildren();
    const query=$('adminUserSearch').value.trim().toLowerCase(),status=$('adminUserStatusFilter').value;
    const users=adminUsersCache.filter(user=>(status?user.status===status:user.status!=='deleted')&&(!query||`${user.name} ${user.id}`.toLowerCase().includes(query)));
    if(!users.length){list.append(node('p','No users match these filters. / រកមិនឃើញអ្នកប្រើតាមលក្ខខណ្ឌនេះទេ។','muted'));return;}
    for(const user of users){
      const row=node('div',undefined,'admin-user-row');
      const summary=node('div',undefined,'admin-user-copy');
      summary.append(node('strong',`${user.name} · ${user.id}`),node('small',`${user.status} · ${user.transaction_count} records`));
      const view=node('button','View / មើល','secondary');view.type='button';view.onclick=()=>loadAdminUser(user.id);
      row.append(summary,view);
      if(state.user?.is_owner&&!['admin','deleted'].includes(user.status)){const remove=node('button','Delete / លុប','text-btn');remove.type='button';remove.onclick=()=>deleteAdminUser(user.id,user.name);row.append(remove);}
      list.append(row);
    }
}

async function deleteAdminUser(id,name){
  if(!confirm(`Permanently delete ${name} (${id}) and all of their MyMoney data? This cannot be undone.`))return;
  const typed=prompt(`Type Telegram ID ${id} to confirm permanent deletion:`);
  if(typed!==String(id))return;
  try{await api(`/api/admin/users/${id}`,{method:'DELETE',body:JSON.stringify({confirm_id:typed})});toast('User and data deleted / បានលុបអ្នកប្រើ និងទិន្នន័យ');$('adminUserDetail').hidden=true;await loadAdminConsole();}
  catch(error){$('adminStatus').textContent=error.message;}
}

async function loadAdminAccounts(){
  try{
    const result=await api('/api/admin/admins');
    const list=$('adminList');list.replaceChildren();
    if(!result.admins.length){list.append(node('p','No additional administrators. / មិនទាន់មាន Admin បន្ថែម។','muted'));return;}
    for(const admin of result.admins){
      const row=node('div',undefined,'admin-user-row');
      row.append(node('span',`${admin.name} · ${admin.user_id}`));
      if(result.can_manage){
        const remove=node('button','Remove / ដក','text-btn');remove.type='button';
        remove.onclick=async()=>{
          if(!confirm(`Remove admin access from ${admin.user_id}? Their regular account access will remain.`))return;
          remove.disabled=true;
          try{await api(`/api/admin/admins/${admin.user_id}`,{method:'DELETE'});toast('Admin removed / បានដក Admin');await loadAdminConsole();}
          catch(error){$('addAdminStatus').textContent=error.message;remove.disabled=false;}
        };
        row.append(remove);
      }
      list.append(row);
    }
  }catch(error){$('adminList').textContent=error.message;}
}

async function loadAdminUser(id){
  const panel=$('adminUserDetail');panel.hidden=false;panel.replaceChildren(node('p','Loading…','muted'));adminSelectedUser=id;
  try{
    const data=await api(`/api/admin/users/${id}`);panel.replaceChildren();
    const heading=node('div',undefined,'section-title');heading.append(node('h3',`${data.user.name} · ${id}`),node('span',data.user.status,'pill'));panel.append(heading);
    panel.append(node('p',`Last active: ${data.user.last_seen?new Date(data.user.last_seen*1000).toLocaleString():'Not seen yet'}`,'muted'));
    if(state.user?.is_owner&&!['admin','deleted'].includes(data.user.status)){
      const rename=document.createElement('form');rename.className='admin-crud';rename.append(node('h4','Edit user display name / កែឈ្មោះអ្នកប្រើ'));
      const field=document.createElement('input');field.maxLength=80;field.required=true;field.value=data.user.name;
      const label=document.createElement('label');label.append(node('span','Name / ឈ្មោះ'),field);rename.append(label);
      const save=node('button','Save name / រក្សាទុកឈ្មោះ','secondary');save.type='submit';rename.append(save);
      rename.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{await api(`/api/admin/users/${id}`,{method:'PUT',body:JSON.stringify({name:field.value})});toast('User name updated');await loadAdminConsole();await loadAdminUser(id);}catch(error){panel.append(node('p',error.message,'form-status'));save.disabled=false;}};
      panel.append(rename);
      const deleteButton=node('button','Delete user and all data / លុបអ្នកប្រើ និងទិន្នន័យ','danger');deleteButton.type='button';deleteButton.onclick=()=>deleteAdminUser(id,data.user.name);panel.append(deleteButton);
    }
    if(data.user.status!=='deleted'){
      const actions=node('div',undefined,'history-actions');
      for(const [status,label] of [['approved','Approve access / អនុញ្ញាត'],['revoked','Revoke access / ដកសិទ្ធិ']]){
        const button=node('button',label,status==='approved'?'secondary':'text-btn');button.type='button';button.disabled=data.user.status===status;
        button.onclick=async()=>{
          if(!confirm(`${status==='approved'?'Approve':'Revoke'} access for ${data.user.name} (${id})?`))return;
          button.disabled=true;
          try{await api(`/api/admin/users/${id}/access`,{method:'PUT',body:JSON.stringify({status,confirm:true})});toast('Access updated / បានធ្វើបច្ចុប្បន្នភាពសិទ្ធិ');await loadAdminConsole();await loadAdminUser(id);}
          catch(error){panel.append(node('p',error.message,'form-status'));button.disabled=false;}
        };
        actions.append(button);
      }
      panel.append(actions);
    }else panel.append(node('p','Account removed; create this Telegram ID again to restore access. / គណនីបានលុបរួចហើយ។ បញ្ចូល ID ម្ដងទៀតដើម្បីបើកឡើងវិញ។','muted'));
    panel.append(node('h4','All-time totals / សរុបកំណត់ត្រា'));
    if(data.totals.length){for(const item of data.totals)panel.append(node('p',`${item.kind}: ${money(item.amount,item.currency)}`));}
    else panel.append(node('p','No transactions. / មិនទាន់មានកំណត់ត្រា។','muted'));
    panel.append(node('h4','Monthly budgets / ថវិកាប្រចាំខែ'));
    if(data.budgets.length){for(const budget of data.budgets)panel.append(node('p',`${budget.month} · ${money(budget.amount,budget.currency)}`));}
    else panel.append(node('p','No budgets. / មិនទាន់កំណត់ថវិកា។','muted'));
    panel.append(node('h4','Recent transactions / កំណត់ត្រាថ្មីៗ'));
    if(state.user?.is_owner)panel.append(buildAdminTransactionForm(id));
    for(const tx of data.transactions){
      const item=node('div',undefined,'admin-record');
      item.append(node('strong',`${tx.day} · ${tx.kind==='expense'?'−':'+'}${money(tx.amount,tx.currency)}`),node('small',`${tx.category} · ${tx.account}${tx.note?' · '+tx.note:''}`));panel.append(item);
      if(state.user?.is_owner){
        const actions=node('div',undefined,'admin-record-actions');
        const edit=node('button','Edit / កែ','secondary');edit.type='button';edit.onclick=()=>fillAdminTransactionForm(panel,tx);
        const remove=node('button','Delete / លុប','text-btn');remove.type='button';remove.onclick=async()=>{
          if(!confirm(`Move transaction #${tx.id} to this user's Trash? They can restore it.`))return;
          remove.disabled=true;try{await api(`/api/admin/users/${id}/transactions/${tx.id}`,{method:'DELETE'});toast('Moved to user Trash / បានដាក់ក្នុងធុងសំរាម');await loadAdminUser(id);await loadAdminOverview();}
          catch(error){panel.append(node('p',error.message,'form-status'));remove.disabled=false;}
        };
        actions.append(edit,remove);item.append(actions);
      }
    }
    if(state.user?.is_owner)await appendAdminMessages(panel,id);
  }catch(error){panel.replaceChildren(node('p',error.message,'form-status'));}
}

function buildAdminTransactionForm(userId){
  const section=node('section',undefined,'admin-crud');section.append(node('h4','＋ Add or edit a transaction / បន្ថែម ឬកែប្រតិបត្តិការ'));
  const form=document.createElement('form');form.id='adminTransactionForm';
  const kind=adminSelect('kind',[['expense','Expense'],['income','Income']]);
  const amount=document.createElement('input');amount.type='number';amount.min='0.01';amount.step='0.01';amount.required=true;amount.inputMode='decimal';
  const currency=adminSelect('currency',[['USD','USD'],['KHR','KHR']]);
  const category=adminSelect('category',[]);
  const account=adminSelect('account',[['cash','Cash'],['bank','Bank']]);
  const spending=adminSelect('spending_type',[['essential','Essential'],['want','Want'],['none','None']]);
  const day=document.createElement('input');day.type='date';day.max=adminLocalDate();day.required=true;
  const note=document.createElement('input');note.maxLength=300;
  for(const [label,input] of [['Type',kind],['Amount',amount],['Currency',currency],['Category',category],['Account',account],['Spending type',spending],['Date',day],['Note',note]]){
    const wrap=document.createElement('label');wrap.append(node('span',label),input);form.append(wrap);
  }
  const updateCategories=()=>{const options=kind.value==='income'?[['salary','Salary'],['other','Other']]:[['food','Food'],['coffee','Coffee'],['transport','Transport'],['shopping','Shopping'],['bills','Bills'],['study','Study'],['health','Health'],['other','Other']];category.replaceChildren(...options.map(([v,l])=>new Option(l,v)));spending.disabled=kind.value==='income';};
  kind.onchange=updateCategories;updateCategories();
  const status=node('p','','form-status');status.setAttribute('role','status');form.append(status);
  const save=node('button','Save transaction / រក្សាទុក','primary');save.type='submit';form.append(save);
  form.onsubmit=async event=>{
    event.preventDefault();save.disabled=true;status.textContent='Saving…';
    const payload={kind:kind.value,amount:amount.value,currency:currency.value,category:category.value,account:account.value,
      spending_type:kind.value==='income'?null:spending.value,day:day.value,note:note.value};
    try{
      const editing=form.dataset.transactionId;
      if(editing)await api(`/api/admin/users/${userId}/transactions/${editing}`,{method:'PUT',body:JSON.stringify(payload)});
      else await api(`/api/admin/users/${userId}/transactions`,{method:'POST',body:JSON.stringify({...payload,request_id:crypto.randomUUID()})});
      toast(editing?'Transaction updated':'Transaction added');await loadAdminUser(userId);await loadAdminOverview();
    }catch(error){status.textContent=error.message;save.disabled=false;}
  };
  section.append(form);return section;
}

function adminSelect(name,options){const select=document.createElement('select');select.name=name;for(const [value,label] of options)select.add(new Option(label,value));return select;}
function adminLocalDate(){const now=new Date();return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;}

function fillAdminTransactionForm(panel,tx){
  const form=panel.querySelector('#adminTransactionForm');if(!form)return;
  form.dataset.transactionId=tx.id;form.elements.kind.value=tx.kind;form.elements.kind.dispatchEvent(new Event('change'));
  form.elements.amount.value=tx.amount/(tx.currency==='USD'?100:1);form.elements.currency.value=tx.currency;
  form.elements.category.value=tx.category;form.elements.account.value=tx.account;form.elements.spending_type.value=tx.spending_type||'none';
  form.elements.day.value=tx.day;form.elements.note.value=tx.note||'';form.scrollIntoView({behavior:'smooth',block:'center'});
}

async function appendAdminMessages(panel,userId){
  const section=node('section',undefined,'admin-crud');section.append(node('h4','✉️ Message this user / ផ្ញើសារទៅអ្នកប្រើ'));
  const form=document.createElement('form');const text=document.createElement('textarea');text.maxLength=1000;text.required=true;text.rows=3;text.placeholder='Write a message (up to 1000 characters)';
  const label=document.createElement('label');label.append(node('span','Message / សារ'),text);form.append(label);
  const status=node('p','','form-status');status.setAttribute('role','status');form.append(status);
  const send=node('button','Send message / ផ្ញើសារ','secondary');send.type='submit';form.append(send);
  form.onsubmit=async event=>{event.preventDefault();if(!confirm(`Send this message to Telegram user ${userId}?`))return;send.disabled=true;status.textContent='Sending…';
    try{const result=await api(`/api/admin/users/${userId}/message`,{method:'POST',body:JSON.stringify({text:text.value})});if(!result.delivered){status.textContent='Telegram could not deliver this message; it is saved in history.';send.disabled=false;return;}toast('Message sent');await loadAdminUser(userId);}
    catch(error){status.textContent=error.message;send.disabled=false;}};
  section.append(form);panel.append(section);
  try{const result=await api(`/api/admin/users/${userId}/messages`);section.append(node('h4','Message history / ប្រវត្តិសារ'));
    if(!result.messages.length)section.append(node('p','No messages sent yet.','muted'));
    for(const message of result.messages){const row=node('div',undefined,'admin-record');row.append(node('strong',`${new Date(message.created_at*1000).toLocaleString()} · ${message.delivered?'Delivered':'Failed'}`),node('small',message.text));section.append(row);}
  }catch(error){section.append(node('p',error.message,'form-status'));}
}

$('openAdminConsole').onclick=()=>{showPage('admin');loadAdminConsole();};
$('toggleAdminMode').onclick=()=>{
  if(!state.user?.is_admin)return;
  const next=getAdminMode()==='admin'?'user':'admin';
  adminModeOverride=next;
  try{localStorage.setItem('mymoney-admin-mode-'+state.user.id,next);}catch{}
  syncAdminModeUI();
  toast(t(next==='admin'?'adminModeEnabled':'userModeEnabled'));
};
$('adminBack').onclick=()=>showPage('settings');
$('refreshAdmin').onclick=loadAdminConsole;
$('adminUserSearch').oninput=renderAdminUserList;
$('adminUserStatusFilter').onchange=renderAdminUserList;
$('adminAddUserForm').onsubmit=async event=>{
  event.preventDefault();const status=$('adminAddUserStatus'),button=event.submitter||$('adminAddUserForm').querySelector('button');
  const userId=Number($('adminNewUserId').value),name=$('adminNewUserName').value;
  if(!Number.isSafeInteger(userId)||userId<=0){status.textContent='Enter a valid Telegram ID.';return;}
  if(!confirm(`Create and approve MyMoney access for Telegram user ${userId}?`))return;
  button.disabled=true;status.textContent='Creating user…';
  try{const result=await api('/api/admin/users',{method:'POST',body:JSON.stringify({user_id:userId,name})});status.textContent=result.notification_sent?'User created, approved and notified.':'User created and approved. They need to start the bot before Telegram can message them.';$('adminAddUserForm').reset();await loadAdminConsole();}
  catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
};
$('adminChartCurrency').onchange=renderAdminDonut;
$('refreshAdminDashboard').onclick=loadAdminOverview;
$('addAdminForm').onsubmit=async event=>{
  event.preventDefault();const input=$('newAdminId'),status=$('addAdminStatus'),button=event.submitter||$('addAdminForm').querySelector('button');
  const userId=Number(input.value);if(!Number.isSafeInteger(userId)||userId<=0){status.textContent='Enter a valid Telegram ID.';return;}
  if(!confirm(`Add Telegram user ${userId} as an administrator? They will be able to review all users’ records and manage access.`))return;
  button.disabled=true;status.textContent='';
  try{const result=await api('/api/admin/admins',{method:'POST',body:JSON.stringify({user_id:userId,confirm:true})});status.textContent=result.notification_sent?'Admin added and notified.':'Admin added; Telegram notification could not be sent.';input.value='';await loadAdminConsole();}
  catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
};
