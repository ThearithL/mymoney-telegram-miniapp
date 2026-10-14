'use strict';
const tg = window.Telegram?.WebApp;
const $ = id => document.getElementById(id);
const month = $('month');
let sequence = 0;
function money(units, currency) {
  const value = units / (currency === 'USD' ? 100 : 1);
  return value.toLocaleString('en-US', {minimumFractionDigits: currency === 'USD' ? 2 : 0, maximumFractionDigits: currency === 'USD' ? 2 : 0}) + ' ' + currency;
}
async function api(path, options = {}) {
  if (!tg?.initData) throw new Error('សូមបើកពី Telegram Bot / Open this page using /insights in the Telegram bot.');
  const response = await fetch(path, {...options, headers: {'Authorization': 'tma ' + tg.initData, 'Content-Type': 'application/json'}, cache: 'no-store'});
  let data;
  try { data = await response.json(); } catch { throw new Error('Server unavailable. Please retry / សូមព្យាយាមម្ដងទៀត។'); }
  if (!response.ok) throw new Error(data.error || 'Request failed. Reopen from Telegram.');
  return data;
}
function entry(dl, label, value) {
  const row = document.createElement('div');
  const dt = document.createElement('dt'); dt.textContent = label;
  const dd = document.createElement('dd'); dd.textContent = value;
  row.append(dt, dd); dl.append(row);
}
function render(data) {
  month.value = data.month;
  $('greeting').textContent = `👤 ${data.user.name} · ${data.user.is_admin ? 'Admin' : 'My account'}`;
  if (document.activeElement !== $('name')) $('name').value = data.user.name;
  $('cards').replaceChildren();
  const states = {unset:'មិនទាន់កំណត់ / Not set', within:'ក្នុងថវិកា / Within budget', warning:'ជិតដល់កំណត់ / Near limit', reached:'ដល់កំណត់ / Limit reached', over:'លើសថវិកា / Over budget'};
  for (const row of data.currencies) {
    const card = $('card-template').content.firstElementChild.cloneNode(true);
    card.dataset.status = row.status;
    card.querySelector('.currency').textContent = row.currency;
    card.querySelector('.state').textContent = states[row.status];
    card.querySelector('.spent').textContent = money(row.expense, row.currency);
    card.querySelector('.budget').textContent = row.budget === null ? 'មិនទាន់កំណត់ថវិកា / No monthly budget set' : 'ថវិកា / Budget: ' + money(row.budget, row.currency);
    const progress = card.querySelector('progress');
    progress.hidden = row.used_percent === null;
    progress.value = Math.min(100, Number(row.used_percent || 0));
    progress.setAttribute('aria-valuetext', (row.used_percent || '0') + '% used');
    card.querySelector('.percent').textContent = row.used_percent === null ? (row.budget === 0 ? 'ថវិកាសូន្យ / Zero budget · no percentage' : '') : row.used_percent + '% បានប្រើ / used';
    const dl = card.querySelector('dl');
    entry(dl, row.overspent ? 'លើសថវិកា / Over budget' : 'នៅសល់ / Remaining', row.remaining === null ? '—' : money(row.overspent || row.remaining, row.currency));
    entry(dl, 'ថ្ងៃនេះអាចចាយ / Daily allowance', row.daily_allowance === null ? '—' : money(row.daily_allowance, row.currency));
    entry(dl, 'ចំណូល / Income', money(row.income, row.currency));
    entry(dl, 'ចំណូលដកចំណាយ / Net', money(row.net, row.currency));
    card.querySelector('.comparison').textContent = `${data.previous_month} · Previous full month expenses: ${money(row.previous_month_expense, row.currency)}. Change: ${row.expense_change > 0 ? '+' : ''}${money(row.expense_change, row.currency)}.`;
    $('cards').append(card);
  }
  $('period-note').textContent = data.is_current_month ? `${data.days_left} ថ្ងៃនៅសល់ រាប់ទាំងថ្ងៃនេះ / days remaining including today. This month is still in progress; the comparison uses the previous full month.` : 'Historical or future month: daily allowance is shown only for the current month.';
}
async function load() {
  const requestId = ++sequence;
  $('refresh').disabled = true;
  $('status').textContent = 'កំពុងផ្ទុក / Loading…';
  $('cards').replaceChildren(); $('period-note').textContent = '';
  try {
    const data = await api('/api/budget-status' + (month.value ? '?month=' + encodeURIComponent(month.value) : ''));
    if (requestId !== sequence) return;
    render(data); $('status').textContent = '';
  } catch (error) { if (requestId === sequence) $('status').textContent = error.message; }
  finally { if (requestId === sequence) $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', load);
month.addEventListener('change', load);
$('profile-form').addEventListener('submit', async event => {
  event.preventDefault(); $('save').disabled = true; $('profile-status').textContent = 'កំពុងរក្សាទុក / Saving…';
  try {
    // Omitting bio preserves it; this form edits only the display name.
    await api('/api/display-name', {method:'PUT', body:JSON.stringify({name:$('name').value})});
    $('profile-status').textContent = '✅ បានរក្សាទុក / Name saved'; await load();
  } catch (error) { $('profile-status').textContent = error.message; }
  finally { $('save').disabled = false; }
});
if (tg?.initData) { tg.ready(); tg.expand(); }
load();
