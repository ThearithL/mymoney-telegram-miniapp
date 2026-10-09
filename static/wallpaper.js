'use strict';
(() => {
  const select = document.getElementById('wallpaper');
  if (!select) return;
  const allowed = new Set(['default', 'meadow', 'sunset', 'lavender', 'ocean']);
  let current = 'default';
  try {
    const stored = localStorage.getItem('mymoney-wallpaper');
    if (allowed.has(stored)) current = stored;
  } catch (error) {
    console.warn('Wallpaper preference could not be read:', error);
  }
  const apply = value => {
    current = allowed.has(value) ? value : 'default';
    document.body.dataset.wallpaper = current;
    select.value = current;
  };
  select.addEventListener('change', () => {
    apply(select.value);
    try {
      localStorage.setItem('mymoney-wallpaper', current);
    } catch (error) {
      console.warn('Wallpaper preference could not be saved:', error);
    }
  });
  apply(current);
})();
