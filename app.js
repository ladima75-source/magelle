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

  const catalogItems = [...document.querySelectorAll('.filter-item')];
  if (catalogItems.length) {
    const size = document.getElementById('filter-size');
    const color = document.getElementById('filter-color');
    const collection = document.getElementById('filter-collection');
    const search = document.getElementById('catalog-search');
    const count = document.getElementById('catalog-count');
    const apply = () => {
      let shown = 0;
      const q = (search?.value || '').trim().toLowerCase();
      catalogItems.forEach(item => {
        const ok = (!size?.value || item.dataset.size === size.value)
          && (!color?.value || item.dataset.color === color.value)
          && (!collection?.value || item.dataset.collection === collection.value)
          && (!q || (item.dataset.name || '').includes(q));
        item.hidden = !ok;
        if (ok) shown++;
      });
      document.querySelectorAll('.family-block').forEach(section => {
        section.hidden = ![...section.querySelectorAll('.filter-item')].some(x => !x.hidden);
      });
      if (count) count.textContent = shown + (shown === 1 ? ' позиція' : ' позицій');
    };
    [size,color,collection,search].forEach(el => el && el.addEventListener('input', apply));
    document.getElementById('reset-filters')?.addEventListener('click', () => {
      [size,color,collection].forEach(el => { if (el) el.value=''; });
      if (search) search.value='';
      apply();
    });
    apply();
  }
})();

document.querySelectorAll('[data-gallery]').forEach(gallery => {
  const main = gallery.querySelector('#product-main-image') || document.getElementById('product-main-image');
  gallery.querySelectorAll('[data-gallery-src]').forEach(btn => {
    btn.addEventListener('click', () => {
      gallery.querySelectorAll('[data-gallery-src]').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      if (main) main.src = btn.dataset.gallerySrc;
    });
  });
});

document.querySelectorAll('.product-info[data-sku-prefix]').forEach(product => {
  const skuEl = product.querySelector('#selected-sku');
  const sizeGroup = product.querySelector('[data-variant="size"]');
  const colorGroup = product.querySelector('[data-variant="color"]');
  const read = group => group?.querySelector('.active')?.dataset.value || '';
  const refresh = () => {
    if (skuEl) skuEl.textContent = [product.dataset.skuPrefix, read(sizeGroup), read(colorGroup)].filter(Boolean).join('-');
  };
  product.querySelectorAll('.variant-group button').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.variant-group');
      group.querySelectorAll('button').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      refresh();
    });
  });
  refresh();
});
