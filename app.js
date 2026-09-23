(() => {
  const API_BASE = 'https://api.magelle.com.ua';
  const CART_KEY = 'magelle_cart_v1';
  const body = document.body;

  const menuButton = document.querySelector('.menu-button');
  if (menuButton) menuButton.addEventListener('click', () => {
    const open = body.classList.toggle('nav-open');
    menuButton.setAttribute('aria-expanded', String(open));
  });

  const cartDrawer = document.getElementById('cart-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const openButtons = document.querySelectorAll('.cart-button');
  const closeButton = document.querySelector('.close-cart');
  const setCart = (open) => {
    if (!cartDrawer || !backdrop) return;
    cartDrawer.classList.toggle('open', open);
    backdrop.classList.toggle('open', open);
    cartDrawer.setAttribute('aria-hidden', String(!open));
  };
  openButtons.forEach(b => b.addEventListener('click', () => { renderCart(); setCart(true); }));
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
          && (!q || (item.dataset.name || '').toLowerCase().includes(q));
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

  const getCart = () => {
    try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); }
    catch { return []; }
  };
  const saveCart = cart => {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartCount();
  };
  const updateCartCount = () => {
    const n = getCart().reduce((s,x) => s + Number(x.qty || 0), 0);
    document.querySelectorAll('#cart-count').forEach(el => el.textContent = String(n));
  };
  const money = v => new Intl.NumberFormat('uk-UA').format(Number(v || 0)) + ' грн';

  let activeProducts = new Map();

  function addToCart(sku) {
    const p = activeProducts.get(sku);
    if (!p || p.price_uah == null || !['stock','preorder'].includes(p.status)) return;
    const cart = getCart();
    const item = cart.find(x => x.sku === sku);
    if (item) item.qty += 1;
    else cart.push({sku, qty:1});
    saveCart(cart);
    renderCart();
    setCart(true);
  }

  function renderCart() {
    if (!cartDrawer) return;
    const host = cartDrawer.querySelector('.cart-empty');
    if (!host) return;
    const cart = getCart();
    if (!cart.length) {
      host.innerHTML = '<p>Кошик порожній.</p><a class="text-link" href="/catalog.html">Перейти до каталогу →</a>';
      return;
    }
    let total = 0;
    const rows = cart.map(item => {
      const p = activeProducts.get(item.sku);
      if (!p) return '<div class="cart-line"><div><b>'+item.sku+'</b><small>Тимчасово недоступно</small></div><button type="button" data-cart-remove="'+item.sku+'">×</button></div>';
      total += Number(p.price_uah || 0) * item.qty;
      return '<div class="cart-line"><div><b>'+p.title_ua+'</b><small>'+item.sku+' · '+item.qty+' × '+money(p.price_uah)+'</small></div><button type="button" data-cart-remove="'+item.sku+'">×</button></div>';
    }).join('');
    host.innerHTML = rows + '<div class="cart-total"><span>Разом</span><b>'+money(total)+'</b></div><a class="btn dark wide cart-checkout" href="/checkout.html">Оформити замовлення</a>';
    host.querySelectorAll('[data-cart-remove]').forEach(btn => btn.onclick = () => {
      saveCart(getCart().filter(x => x.sku !== btn.dataset.cartRemove));
      renderCart();
    });
  }

  function skuFromPdp() {
    const skuLabel = [...document.querySelectorAll('.sku-identity>div')].find(x => x.querySelector('span')?.textContent.trim().toUpperCase() === 'SKU');
    return skuLabel?.querySelector('strong')?.textContent.trim() || '';
  }

  function applyProductData(products) {
    activeProducts = new Map(products.map(p => [p.sku,p]));
    document.querySelectorAll('.sku-card').forEach(card => {
      const sku = card.querySelector('.sku-code')?.textContent.trim();
      const p = activeProducts.get(sku);
      if (!p) return;
      const price = card.querySelector('.product-meta>b');
      if (price && p.price_uah != null) price.textContent = money(p.price_uah);
      card.classList.add('api-active-product');
      card.dataset.status = p.status;
    });

    const sku = skuFromPdp();
    if (sku) {
      const p = activeProducts.get(sku);
      const info = document.querySelector('.sku-pdp');
      if (p && info) {
        const price = info.querySelector('.price-placeholder');
        if (price && p.price_uah != null) {
          price.textContent = money(p.price_uah);
          price.classList.add('real-price');
        }
        const h1 = info.querySelector('h1');
        if (h1 && p.title_ua) h1.textContent = "Інтер'єрна композиція " + p.title_ua;
        const cta = info.querySelector('.disabled-buy, [data-add-sku]');
        if (cta && p.price_uah != null && ['stock','preorder'].includes(p.status)) {
          cta.disabled = false;
          cta.classList.remove('disabled-buy');
          cta.dataset.addSku = sku;
          cta.textContent = p.status === 'stock' ? 'Додати в кошик' : 'Замовити';
          cta.onclick = () => addToCart(sku);
          if (!info.querySelector('.api-availability')) {
            const badge = document.createElement('p');
            badge.className = 'api-availability';
            badge.textContent = p.status === 'stock' ? 'В наявності' : ('Під замовлення' + (p.lead_time_days ? ' · ' + p.lead_time_days + ' дн.' : ''));
            price?.after(badge);
          }
        }
      }
    }
    renderCart();
  }

  async function loadProducts() {
    try {
      const r = await fetch(API_BASE + '/api/products', {headers:{'Accept':'application/json'}});
      if (!r.ok) return;
      const products = await r.json();
      applyProductData(products);
    } catch (_) {}
  }

  window.MaGelleStore = { getCart, saveCart, money, API_BASE, getProducts: () => activeProducts };
  updateCartCount();
  renderCart();
  loadProducts();
})();