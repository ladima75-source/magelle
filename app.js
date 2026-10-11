(() => {
  const measurementId = "G-1RM1S55BZW";
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag(){ window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", measurementId);
  const script = document.createElement("script");
  script.async = true;
  script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
  document.head.appendChild(script);
})();

(() => {
  const API_BASE = 'https://api.magelle.com.ua';
  const CART_KEY = 'magelle_cart_v1';
  const body = document.body;
  const PILOT_VARIANTS = {
    GRA:{sku:'MG-OF-VYR-GRA',label:'Графіт',swatch:'gra'},
    MLK:{sku:'MG-OF-VYR-MLK',label:'Молочний',swatch:'mlk'},
    WHT:{sku:'MG-OF-VYR-WHT',label:'Білий',swatch:'wht'},
    CHO:{sku:'MG-OF-VYR-CHO',label:'Шоколад',swatch:'cho'}
  };
  const PILOT_GRA_IMAGE = 'https://drive.google.com/thumbnail?id=1es3QEWbwENjx7vfbkkrPz7x2OadMpS00&sz=w1600';

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
  const setQty = (sku, qty) => {
    const cart = getCart();
    const item = cart.find(x => x.sku === sku);
    if (!item) return;
    if (qty <= 0) saveCart(cart.filter(x => x.sku !== sku));
    else { item.qty = Math.min(20, Math.max(1, Number(qty) || 1)); saveCart(cart); }
    renderCart();
    document.dispatchEvent(new CustomEvent('magelle:cart-change'));
  };
  const money = v => new Intl.NumberFormat('uk-UA').format(Number(v || 0)) + ' грн';

  let activeProducts = new Map();

  function pilotMeta(info, sku) {
    if (!info?.classList.contains('pilot-variant-pdp')) return {};
    return {
      family: info.dataset.family || 'Organic Flare',
      design: info.dataset.design || 'Мед',
      size: info.dataset.variantSize || 'Виразний',
      vase_color: info.dataset.selectedColor || '',
      sku
    };
  }

  function addToCart(sku, meta={}) {
    const p = activeProducts.get(sku);
    if (!p || p.price_uah == null || !['stock','preorder'].includes(p.status)) return;
    const cart = getCart();
    const item = cart.find(x => x.sku === sku);
    if (item) {
      item.qty += 1;
      Object.assign(item, meta);
    } else cart.push({sku, qty:1, ...meta});
    saveCart(cart);
    renderCart();
    setCart(true);
  }

  function itemTitle(item, p) {
    if (item.design) return (item.family || p?.series || '') + ' «' + item.design + '» — ' + (item.size || p?.size_name || '');
    return p?.title_ua || item.sku;
  }

  function itemDetails(item) {
    const parts=[];
    if (item.vase_color) parts.push('Ваза: '+item.vase_color);
    parts.push(item.sku);
    return parts.join(' · ');
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
      if (!p) return '<div class="cart-line"><div><b>'+itemTitle(item,p)+'</b><small>'+itemDetails(item)+' · Тимчасово недоступно</small></div><button type="button" data-cart-remove="'+item.sku+'">×</button></div>';
      total += Number(p.price_uah || 0) * item.qty;
      return '<div class="cart-line"><div class="cart-line-main"><b>'+itemTitle(item,p)+'</b><small>'+itemDetails(item)+' · '+money(p.price_uah)+'</small><div class="cart-qty"><button type="button" data-cart-dec="'+item.sku+'" aria-label="Зменшити кількість">−</button><span>'+item.qty+'</span><button type="button" data-cart-inc="'+item.sku+'" aria-label="Збільшити кількість">+</button></div></div><div class="cart-line-side"><b>'+money(Number(p.price_uah||0)*item.qty)+'</b><button type="button" data-cart-remove="'+item.sku+'" aria-label="Видалити">×</button></div></div>';
    }).join('');
    host.innerHTML = rows + '<div class="cart-total"><span>Разом</span><b>'+money(total)+'</b></div><a class="btn dark wide cart-checkout" href="/checkout.html">Оформити замовлення</a>';
    host.querySelectorAll('[data-cart-remove]').forEach(btn => btn.onclick = () => setQty(btn.dataset.cartRemove, 0));
    host.querySelectorAll('[data-cart-dec]').forEach(btn => btn.onclick = () => {
      const item = getCart().find(x => x.sku === btn.dataset.cartDec); if (item) setQty(item.sku, item.qty - 1);
    });
    host.querySelectorAll('[data-cart-inc]').forEach(btn => btn.onclick = () => {
      const item = getCart().find(x => x.sku === btn.dataset.cartInc); if (item) setQty(item.sku, item.qty + 1);
    });
  }

  function renderPilotCatalog(card, code, temporary=false) {
    const v=PILOT_VARIANTS[code] || PILOT_VARIANTS.GRA;
    const stage=card.querySelector('.pilot-media-stage');
    const backLabel=card.querySelector('.pilot-media-back strong');
    const link=card.querySelector('.pilot-hero-link');
    if (backLabel && code!=='GRA') backLabel.textContent=v.label;
    if (stage) stage.classList.toggle('is-flipped',code!=='GRA');
    if (!temporary) {
      card.dataset.sku=v.sku;
      card.dataset.color=code;
      card.querySelectorAll('.pilot-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));
      const label=card.querySelector('.pilot-selected-color'); if(label) label.textContent=v.label;
      if(link) link.href='/organic-flare-vyraznyi-hrafit.html?color='+code;
      const p=activeProducts.get(v.sku), price=card.querySelector('.product-meta>b');
      if(price){
        if(p && Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.remove('price-pending');}
        else {price.textContent='Ціну уточнюємо';price.classList.add('price-pending');}
      }
    }
  }

  function initPilotCatalog() {
    document.querySelectorAll('.pilot-variant-card').forEach(card=>{
      let selected=card.dataset.color || 'GRA';
      card.querySelectorAll('.pilot-color').forEach(btn=>{
        btn.addEventListener('mouseenter',()=>renderPilotCatalog(card,btn.dataset.variantColor,true));
        btn.addEventListener('mouseleave',()=>renderPilotCatalog(card,selected,true));
        btn.addEventListener('focus',()=>renderPilotCatalog(card,btn.dataset.variantColor,true));
        btn.addEventListener('blur',()=>renderPilotCatalog(card,selected,true));
        btn.addEventListener('click',e=>{
          e.preventDefault(); e.stopPropagation();
          selected=btn.dataset.variantColor;
          renderPilotCatalog(card,selected,false);
        });
      });
      renderPilotCatalog(card,selected,false);
    });
  }

  function skuFromPdp() {
    const info=document.querySelector('.sku-pdp');
    if(info?.dataset.selectedSku) return info.dataset.selectedSku;
    const values = [...document.querySelectorAll('.sku-identity strong')];
    return values.map(x => x.textContent.trim()).find(x => /^MG-[A-Z0-9-]+$/.test(x)) || '';
  }

  function applyPdpProduct(info, sku) {
    const p=activeProducts.get(sku);
    if(!p || !info) return;
    let price = info.querySelector('.price-placeholder');
    if (!price) {
      price = document.createElement('div');
      price.className = 'price-placeholder';
      const anchor = info.querySelector('.sku-identity') || info.querySelector('.product-subtitle') || info.querySelector('h1');
      anchor?.after(price);
    }
    if (p.price_uah != null && Number(p.price_uah) > 0) {
      price.textContent = money(p.price_uah); price.classList.add('real-price');
    } else {
      price.textContent = 'Ціну уточнюємо'; price.classList.remove('real-price');
    }
    const h1=info.querySelector('h1');
    if(h1 && p.title_ua && !info.classList.contains('pilot-variant-pdp')) h1.textContent="Інтер'єрна композиція "+p.title_ua;
    let badge=info.querySelector('.api-availability');
    if(!badge){badge=document.createElement('p');badge.className='api-availability';price.after(badge);}
    badge.textContent=p.status==='stock'?'В наявності':(p.status==='preorder'?'Під замовлення'+(p.lead_time_days?' · '+p.lead_time_days+' дн.':''):'Недоступно');
    const cta=info.querySelector('.disabled-buy, [data-add-sku]');
    if(cta){
      if(p.price_uah != null && ['stock','preorder'].includes(p.status)){
        cta.disabled=false; cta.classList.remove('disabled-buy'); cta.dataset.addSku=sku;
        cta.textContent=p.status==='stock'?'Додати в кошик':'Замовити';
        cta.onclick=()=>addToCart(sku,pilotMeta(info,sku));
      }else{
        cta.disabled=true; cta.classList.add('disabled-buy'); cta.textContent='Доступність уточнюється'; cta.onclick=null;
      }
    }
  }

  function selectPilotPdp(code, updateUrl=true) {
    const info=document.querySelector('.pilot-variant-pdp');
    if(!info) return;
    const v=PILOT_VARIANTS[code] || PILOT_VARIANTS.GRA;
    info.dataset.selectedSku=v.sku;
    info.dataset.selectedColor=v.label;
    const sku=document.getElementById('pilot-selected-sku'); if(sku) sku.textContent=v.sku;
    const label=document.getElementById('pilot-pdp-color-label'); if(label) label.textContent=v.label;
    const color=document.getElementById('pilot-pdp-color'); if(color) color.innerHTML='<i class="swatch swatch-'+v.swatch+'"></i><span>'+v.label+'</span>';
    const spec=document.getElementById('pilot-spec-color'); if(spec) spec.textContent=v.label;
    info.querySelectorAll('.pilot-pdp-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));
    const main=document.getElementById('product-main-image');
    const ph=document.getElementById('pilot-photo-placeholder');
    const phLabel=document.getElementById('pilot-photo-placeholder-label');
    const thumbs=document.querySelector('.real-gallery .thumbs');
    if(code==='GRA'){
      if(main){main.hidden=false;main.src=PILOT_GRA_IMAGE;}
      if(ph) ph.hidden=true;
      if(thumbs) thumbs.style.display='';
    }else{
      if(main) main.hidden=true;
      if(ph){ph.hidden=false;if(phLabel) phLabel.textContent=v.label;}
      if(thumbs) thumbs.style.display='none';
    }
    if(updateUrl){
      const url=new URL(location.href); url.searchParams.set('color',code); history.replaceState({},'',url);
    }
    applyPdpProduct(info,v.sku);
  }

  function initPilotPdp(){
    const info=document.querySelector('.pilot-variant-pdp'); if(!info) return;
    const requested=new URL(location.href).searchParams.get('color') || 'GRA';
    const initial=PILOT_VARIANTS[requested]?requested:'GRA';
    info.querySelectorAll('.pilot-pdp-color').forEach(btn=>btn.addEventListener('click',()=>selectPilotPdp(btn.dataset.variantColor,true)));
    selectPilotPdp(initial,false);
  }

  function applyProductData(products) {
    activeProducts = new Map(products.map(p => [p.sku,p]));
    document.querySelectorAll('.sku-card').forEach(card => {
      const sku = card.dataset.sku || card.dataset.name?.match(/MG-[A-Z0-9-]+/)?.[0];
      const p = activeProducts.get(sku);
      const meta = card.querySelector('.product-meta');
      if (!meta) return;
      let price = meta.querySelector(':scope > b');
      if (!price) { price=document.createElement('b'); price.className='api-price'; meta.append(price); }
      if (p && Number(p.price_uah)>0) {
        price.textContent=money(p.price_uah); price.classList.remove('price-pending'); card.classList.add('api-active-product'); card.dataset.status=p.status||'';
      } else {
        price.textContent='Ціну уточнюємо'; price.classList.add('price-pending'); card.classList.remove('api-active-product');
      }
    });
    document.querySelectorAll('.pilot-variant-card').forEach(card=>renderPilotCatalog(card,card.dataset.color||'GRA',false));
    const info=document.querySelector('.sku-pdp');
    const sku=skuFromPdp();
    if(sku && info) applyPdpProduct(info,sku);
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

  window.MaGelleStore = { getCart, saveCart, setQty, money, API_BASE, getProducts: () => activeProducts };
  initPilotCatalog();
  initPilotPdp();
  updateCartCount();
  renderCart();
  loadProducts();
})();