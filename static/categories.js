'use strict';

Object.assign(en, {
  customCategories:'My categories',
  customCategoriesHelp:'Create a category, choose its icon and where to use it. You can update the name or icon later.',
  categoryName:'Category name', categoryIcon:'Icon', categoryType:'Use for',
  expenseOnly:'Expenses', incomeOnly:'Income', bothKinds:'Both',
  addCategory:'＋ Add category', saveCategory:'✓ Save changes', removeCategory:'🗑 Delete',
  categoryEmpty:'No custom categories yet.', categoryCreated:'Category added.',
  deleteCategoryConfirm:'Delete this category? Existing records keep their saved details.',
  categoryGroceries:'Shopping', categoryFuel:'Fuel', categoryCoffee:'Coffee', categoryFood:'Food',
  categoryHome:'Home', categoryTransport:'Transport', categoryHealth:'Health', categoryStudy:'Study',
  categoryBills:'Bills', categoryFun:'Entertainment', categoryCard:'Card', categoryOther:'Other',
  categoryPets:'Pets', categoryTravel:'Travel', categoryPhone:'Phone', categoryClothing:'Clothing',
  categoryPlants:'Plants', categoryGifts:'Gifts'
});
Object.assign(km, {
  customCategories:'ប្រភេទផ្ទាល់ខ្លួន',
  customCategoriesHelp:'បង្កើតប្រភេទ ជ្រើសរូបតំណាង និងជ្រើសថាប្រើសម្រាប់ចំណូល ឬចំណាយ។ អ្នកអាចកែឈ្មោះ និងរូបតំណាងពេលក្រោយបាន។',
  categoryName:'ឈ្មោះប្រភេទ', categoryIcon:'រូបតំណាង', categoryType:'ប្រើសម្រាប់',
  expenseOnly:'ចំណាយ', incomeOnly:'ចំណូល', bothKinds:'ទាំងពីរ',
  addCategory:'＋ បន្ថែមប្រភេទ', saveCategory:'✓ រក្សាទុកការកែប្រែ', removeCategory:'🗑 លុប',
  categoryEmpty:'មិនទាន់មានប្រភេទផ្ទាល់ខ្លួនទេ។', categoryCreated:'បានបន្ថែមប្រភេទ។',
  deleteCategoryConfirm:'តើអ្នកចង់លុបប្រភេទនេះមែនទេ? កំណត់ត្រាចាស់នឹងនៅដដែល។',
  categoryGroceries:'ទិញទំនិញ', categoryFuel:'ប្រេងឥន្ធនៈ', categoryCoffee:'កាហ្វេ', categoryFood:'អាហារ',
  categoryHome:'ផ្ទះ', categoryTransport:'ធ្វើដំណើរ', categoryHealth:'សុខភាព', categoryStudy:'សិក្សា',
  categoryBills:'វិក្កយបត្រ', categoryFun:'កម្សាន្ត', categoryCard:'កាត', categoryOther:'ផ្សេងៗ',
  categoryPets:'សត្វចិញ្ចឹម', categoryTravel:'ដំណើរកម្សាន្ត', categoryPhone:'ទូរស័ព្ទ', categoryClothing:'សម្លៀកបំពាក់',
  categoryPlants:'រុក្ខជាតិ', categoryGifts:'កាដូ'
});

window.customCategories=[];
const categoryIconOptions=[
  ['✨','categoryOther'],['🛒','categoryGroceries'],['⛽','categoryFuel'],['☕','categoryCoffee'],
  ['🍜','categoryFood'],['🏠','categoryHome'],['🚗','categoryTransport'],['💊','categoryHealth'],
  ['🎓','categoryStudy'],['🧾','categoryBills'],['🎮','categoryFun'],['💳','categoryCard'],
  ['🐶','categoryPets'],['🐱','categoryPets'],['✈️','categoryTravel'],['📱','categoryPhone'],
  ['👕','categoryClothing'],['🌱','categoryPlants'],['🎁','categoryGifts'],['🛍️','categoryGroceries']
];

function fillIconSelect(select,selected='✨'){
  select.replaceChildren();
  for(const [icon,label] of categoryIconOptions){
    const option=node('option',icon+'  '+t(label));
    option.value=icon;
    select.append(option);
  }
  select.value=categoryIconOptions.some(([icon])=>icon===selected)?selected:'✨';
}

function fillEntryCategories(){
  if(!$('category')||!$('entryDialog').open)return;
  const selected=$('category').value;
  $('category').replaceChildren();
  const builtin=Object.keys(icons).filter(key=>kind==='income'?['salary','other'].includes(key):key!=='salary');
  for(const key of builtin){const option=node('option',icons[key]+' '+t(key));option.value=key;$('category').append(option);}
  for(const item of window.customCategories.filter(item=>item.kind==='both'||item.kind===kind)){
    const option=node('option',(item.icon||'✨')+' '+item.name);option.value=item.key;$('category').append(option);
  }
  if([...$('category').options].some(option=>option.value===selected))$('category').value=selected;
  else $('category').value=kind==='income'?'salary':'food';
}
const openEntryWithCategories=openEntry;
openEntry=function(...args){openEntryWithCategories(...args);fillEntryCategories();};

function categoryTypeLabel(type){
  const symbol=type==='income'?'↗':type==='both'?'⇄':'↘';
  const label=type==='both'?'bothKinds':type==='income'?'incomeOnly':'expenseOnly';
  return [symbol,t(label),type];
}

function renderCategoryManager(){
  const root=$('customCategoryList');
  root.replaceChildren();
  if(!window.customCategories.length){root.append(node('p',t('categoryEmpty'),'category-empty muted'));return;}

  for(const category of window.customCategories){
    const card=node('article',undefined,'custom-category-card');
    const heading=node('div',undefined,'custom-category-heading');
    const iconBadge=node('span',category.icon||'✨','custom-category-icon');
    iconBadge.setAttribute('aria-hidden','true');
    const info=node('div',undefined,'custom-category-info');
    info.append(node('strong',category.name),node('small',t('categoryName'),'muted'));
    const [symbol,typeText,typeClass]=categoryTypeLabel(category.kind);
    const typeBadge=node('span',symbol+' '+typeText,'category-kind '+typeClass);
    heading.append(iconBadge,info,typeBadge);

    const form=node('form',undefined,'category-edit-form');
    const nameLabel=node('label');
    nameLabel.append(node('span',t('categoryName')));
    const input=node('input');input.value=category.name;input.maxLength=40;input.required=true;
    input.setAttribute('aria-label',t('categoryName'));
    nameLabel.append(input);
    const iconLabel=node('label');
    iconLabel.append(node('span',t('categoryIcon')));
    const iconSelect=node('select');iconSelect.setAttribute('aria-label',t('categoryIcon'));
    fillIconSelect(iconSelect,category.icon||'✨');iconLabel.append(iconSelect);
    const actions=node('div',undefined,'category-actions');
    const save=node('button',t('saveCategory'),'secondary');save.type='submit';
    const remove=node('button',t('removeCategory'),'category-delete-button');remove.type='button';
    actions.append(save,remove);
    const error=node('p',undefined,'category-error');error.setAttribute('role','status');
    form.append(nameLabel,iconLabel,actions,error);

    const originalName=category.name,originalIcon=category.icon||'✨';
    const updateSaveState=()=>{save.disabled=input.value.trim()===originalName&&iconSelect.value===originalIcon;};
    input.addEventListener('input',updateSaveState);
    iconSelect.addEventListener('change',()=>{iconBadge.textContent=iconSelect.value;updateSaveState();});
    updateSaveState();
    form.onsubmit=async event=>{
      event.preventDefault();if(save.disabled)return;
      busy(save,true);error.textContent='';
      try{
        await api('/api/categories/'+encodeURIComponent(category.key),{
          method:'PUT',body:JSON.stringify({name:input.value,icon:iconSelect.value})
        });
        await loadCustomCategories();toast(t('saved'));
      }catch(e){error.textContent=e.message;}
      finally{busy(save,false);}
    };
    remove.onclick=async()=>{
      if(!confirm(t('deleteCategoryConfirm')))return;
      busy(remove,true);error.textContent='';
      try{
        await api('/api/categories/'+encodeURIComponent(category.key),{method:'DELETE'});
        await loadCustomCategories();toast(t('deleted'));
      }catch(e){error.textContent=e.message;}
      finally{busy(remove,false);}
    };
    card.append(heading,form);root.append(card);
  }
}

async function loadCustomCategories(){
  if(!tg?.initData)return;
  try{
    window.customCategories=(await api('/api/categories')).categories;
    for(const category of window.customCategories){en[category.key]=category.name;km[category.key]=category.name;}
    translate();
    fillIconSelect($('newCategoryIcon'),$('newCategoryIcon').value||'✨');
    renderCategoryManager();fillEntryCategories();
    if(typeof renderFeatures==='function')renderFeatures();
  }catch(error){$('categoryManagerError').textContent=error.message;}
}

fillIconSelect($('newCategoryIcon'));
$('customCategoryForm').onsubmit=async event=>{
  event.preventDefault();
  const button=event.submitter;busy(button,true);$('categoryManagerError').textContent='';
  try{
    await api('/api/categories',{method:'POST',body:JSON.stringify({
      name:$('newCategoryName').value,kind:$('newCategoryType').value,icon:$('newCategoryIcon').value
    })});
    $('newCategoryName').value='';$('newCategoryIcon').value='✨';
    await loadCustomCategories();toast(t('categoryCreated'));
  }catch(error){$('categoryManagerError').textContent=error.message;}
  finally{busy(button,false);}
};
translate();
loadCustomCategories();
