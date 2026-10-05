'use strict';
Object.assign(en,{customCategories:'My categories',customCategoriesHelp:'Create your own categories, choose whether they are for income, expenses or both, then select them when adding an entry.',categoryName:'Category name',categoryType:'Use for',expenseOnly:'Expenses',incomeOnly:'Income',bothKinds:'Both',addCategory:'＋ Add category',renameCategory:'Save name',removeCategory:'Delete',categoryEmpty:'No custom categories yet.'});
Object.assign(km,{customCategories:'ប្រភេទផ្ទាល់ខ្លួន',customCategoriesHelp:'បង្កើតប្រភេទផ្ទាល់ខ្លួន ជ្រើសថាជាចំណូល ចំណាយ ឬទាំងពីរ រួចជ្រើសវាពេលកត់ត្រា។',categoryName:'ឈ្មោះប្រភេទ',categoryType:'ប្រើសម្រាប់',expenseOnly:'ចំណាយ',incomeOnly:'ចំណូល',bothKinds:'ទាំងពីរ',addCategory:'＋ បន្ថែមប្រភេទ',renameCategory:'រក្សាឈ្មោះ',removeCategory:'លុប',categoryEmpty:'មិនទាន់មានប្រភេទផ្ទាល់ខ្លួនទេ។'});
window.customCategories=[];

function fillEntryCategories(){
  if(!$('category')||!$('entryDialog').open)return;
  const selected=$('category').value;
  $('category').replaceChildren();
  const builtin=Object.keys(icons).filter(key=>kind==='income'?['salary','other'].includes(key):key!=='salary');
  for(const key of builtin){const option=node('option',icons[key]+' '+t(key));option.value=key;$('category').append(option);}
  for(const item of window.customCategories.filter(item=>item.kind==='both'||item.kind===kind)){const option=node('option','✳ '+item.name);option.value=item.key;$('category').append(option);}
  if([...$('category').options].some(option=>option.value===selected))$('category').value=selected;
  else $('category').value=kind==='income'?'salary':'food';
}
const openEntryWithCategories=openEntry;
openEntry=function(...args){openEntryWithCategories(...args);fillEntryCategories();};

function renderCategoryManager(){
  const root=$('customCategoryList');root.replaceChildren();
  if(!window.customCategories.length){root.append(node('p',t('categoryEmpty'),'muted'));return;}
  for(const category of window.customCategories){
    const card=node('article',undefined,'custom-category card');
    const heading=node('div',undefined,'section-title');heading.append(node('strong','✳ '+category.name),node('small',t(category.kind==='both'?'bothKinds':category.kind==='income'?'incomeOnly':'expenseOnly'),'muted'));
    const form=node('form',undefined,'category-rename');const input=node('input');input.value=category.name;input.maxLength=40;input.required=true;input.setAttribute('aria-label',t('categoryName'));const save=node('button',t('renameCategory'),'secondary');save.type='submit';const remove=node('button',t('removeCategory'),'danger');remove.type='button';const error=node('p',undefined,'muted');error.setAttribute('role','status');form.append(input,save,remove,error);
    form.onsubmit=async event=>{event.preventDefault();busy(save,true);error.textContent='';try{await api('/api/categories/'+encodeURIComponent(category.key),{method:'PUT',body:JSON.stringify({name:input.value})});await loadCustomCategories();toast(t('saved'));}catch(e){error.textContent=e.message;}finally{busy(save,false);}};
    remove.onclick=async()=>{busy(remove,true);error.textContent='';try{await api('/api/categories/'+encodeURIComponent(category.key),{method:'DELETE'});await loadCustomCategories();toast(t('saved'));}catch(e){error.textContent=e.message;}finally{busy(remove,false);}};
    card.append(heading,form);root.append(card);
  }
}
async function loadCustomCategories(){
  if(!tg?.initData)return;
  try{
    window.customCategories=(await api('/api/categories')).categories;
    for(const category of window.customCategories){en[category.key]=category.name;km[category.key]=category.name;}
    translate();renderCategoryManager();fillEntryCategories();
    if(typeof renderFeatures==='function')renderFeatures();
  }catch(error){$('categoryManagerError').textContent=error.message;}
}
$('customCategoryForm').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;busy(button,true);$('categoryManagerError').textContent='';
  try{await api('/api/categories',{method:'POST',body:JSON.stringify({name:$('newCategoryName').value,kind:$('newCategoryType').value})});$('newCategoryName').value='';await loadCustomCategories();toast(t('saved'));}
  catch(error){$('categoryManagerError').textContent=error.message;}
  finally{busy(button,false);}
};
translate();
loadCustomCategories();
