(() => {
  const body = document.body;
  const menuButton = document.querySelector('.menu-button');
  if (menuButton) menuButton.addEventListener('click', () => {
    const open = body.classList.toggle('nav-open');
    menuButton.setAttribute('aria-expanded', String(open));
  });

  const cart = document.getElementById('cart-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const openButtons = document.querySelectorAll('.cart-button');
  const closeButton = document.querySelector('.close-cart');
  const setCart = (open) => {
    if (!cart || !backdrop) return;
    cart.classList.toggle('open', open);
    backdrop.classList.toggle('open', open);
    cart.setAttribute('aria-hidden', String(!open));
  };
  openButtons.forEach(b => b.addEventListener('click', () => setCart(true)));
  if (closeButton) closeButton.addEventListener('click', () => setCart(false));
  if (backdrop) backdrop.addEventListener('click', () => setCart(false));

  const grid = document.getElementById('catalog-grid');
  if (grid) {
    const items = [...grid.querySelectorAll('.filter-item')];
    const size = document.getElementById('filter-size');
    const tone = document.getElementById('filter-tone');
    const collection = document.getElementById('filter-collection');
    const search = document.getElementById('catalog-search');
    const count = document.getElementById('catalog-count');
    const apply = () => {
      let shown = 0;
      const q = (search?.value || '').trim().toLowerCase();
      items.forEach(item => {
        const ok = (!size?.value || item.dataset.size === size.value)
          && (!tone?.value || item.dataset.tone === tone.value)
          && (!collection?.value || item.dataset.collection === collection.value)
          && (!q || (item.dataset.name || '').includes(q));
        item.hidden = !ok;
        if (ok) shown++;
      });
      if (count) count.textContent = shown + (shown === 1 ? ' позиція' : ' позиції');
    };
    [size,tone,collection,search].forEach(el => el && el.addEventListener('input', apply));
    document.getElementById('reset-filters')?.addEventListener('click', () => {
      [size,tone,collection].forEach(el => { if (el) el.value=''; });
      if (search) search.value='';
      apply();
    });
    apply();
  }
})();
