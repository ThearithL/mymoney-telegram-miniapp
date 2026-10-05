'use strict';
let adminSelectedUser = null;

async function loadAdminConsole(){
  const status=$('adminStatus');
  status.textContent='Loading admin data… / កំពុងទាញទិន្នន័យ Admin…';
  $('adminUsers').replaceChildren();
  $('adminUserDetail').hidden=true;
  $('adminOwnerTools').hidden=!state.user?.is_owner;
  try{
    const result=await api('/api/admin/users');
    status.textContent=`${result.users.length} users / អ្នកប្រើ ${result.users.length} នាក់`;
    if(!result.users.length)$('adminUsers').append(node('p','No users found. / រកមិនឃើញអ្នកប្រើទេ។','muted'));
    for(const user of result.users){
      const row=node('div',undefined,'admin-user-row');
      const summary=node('div',undefined,'admin-user-copy');
      summary.append(node('strong',`${user.name} · ${user.id}`),node('small',`${user.status} · ${user.transaction_count} records`));
      const view=node('button','View / មើល','secondary');view.type='button';view.onclick=()=>loadAdminUser(user.id);
      row.append(summary,view);$('adminUsers').append(row);
    }
    if(state.user?.is_admin)await loadAdminAccounts();
  }catch(error){status.textContent=error.message;}
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
    panel.append(node('h4','All-time totals / សរុបកំណត់ត្រា'));
    if(data.totals.length){for(const item of data.totals)panel.append(node('p',`${item.kind}: ${money(item.amount,item.currency)}`));}
    else panel.append(node('p','No transactions. / មិនទាន់មានកំណត់ត្រា។','muted'));
    panel.append(node('h4','Monthly budgets / ថវិកាប្រចាំខែ'));
    if(data.budgets.length){for(const budget of data.budgets)panel.append(node('p',`${budget.month} · ${money(budget.amount,budget.currency)}`));}
    else panel.append(node('p','No budgets. / មិនទាន់កំណត់ថវិកា។','muted'));
    panel.append(node('h4','Recent transactions / កំណត់ត្រាថ្មីៗ'));
    for(const tx of data.transactions){
      const item=node('div',undefined,'admin-record');
      item.append(node('strong',`${tx.day} · ${tx.kind==='expense'?'−':'+'}${money(tx.amount,tx.currency)}`),node('small',`${tx.category} · ${tx.account}${tx.note?' · '+tx.note:''}`));panel.append(item);
    }
  }catch(error){panel.replaceChildren(node('p',error.message,'form-status'));}
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
$('addAdminForm').onsubmit=async event=>{
  event.preventDefault();const input=$('newAdminId'),status=$('addAdminStatus'),button=event.submitter||$('addAdminForm').querySelector('button');
  const userId=Number(input.value);if(!Number.isSafeInteger(userId)||userId<=0){status.textContent='Enter a valid Telegram ID.';return;}
  if(!confirm(`Add Telegram user ${userId} as an administrator? They will be able to review all users’ records and manage access.`))return;
  button.disabled=true;status.textContent='';
  try{const result=await api('/api/admin/admins',{method:'POST',body:JSON.stringify({user_id:userId,confirm:true})});status.textContent=result.notification_sent?'Admin added and notified.':'Admin added; Telegram notification could not be sent.';input.value='';await loadAdminConsole();}
  catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
};
