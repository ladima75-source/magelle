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
  const API_BASE='https://api.magelle.com.ua';
  const CART_KEY='magelle_cart_v1';
  const COLORS={
    GRA:{label:'Графіт',swatch:'gra'},
    MLK:{label:'Молочний',swatch:'mlk'},
    WHT:{label:'Білий',swatch:'wht'},
    CHO:{label:'Шоколад',swatch:'cho'}
  };
  const body=document.body;

  const canonicalSku=(sizeCode,color)=>'MG-OF-'+sizeCode+'-'+color;
  const designSku=(designCode,sizeCode,color)=>'MG-OF-'+designCode+'-'+sizeCode+'-'+color;

  const menuButton=document.querySelector('.menu-button');
  if(menuButton) menuButton.addEventListener('click',()=>{
    const open=body.classList.toggle('nav-open');
    menuButton.setAttribute('aria-expanded',String(open));
  });

  const cartDrawer=document.getElementById('cart-drawer');
  const backdrop=document.getElementById('drawer-backdrop');
  const openButtons=document.querySelectorAll('.cart-button');
  const closeButton=document.querySelector('.close-cart');
  const setCart=open=>{
    if(!cartDrawer||!backdrop)return;
    cartDrawer.classList.toggle('open',open);
    backdrop.classList.toggle('open',open);
    cartDrawer.setAttribute('aria-hidden',String(!open));
  };
  openButtons.forEach(b=>b.addEventListener('click',()=>{renderCart();setCart(true)}));
  if(closeButton) closeButton.addEventListener('click',()=>setCart(false));
  if(backdrop) backdrop.addEventListener('click',()=>setCart(false));

  const catalogItems=[...document.querySelectorAll('.filter-item')];
  if(catalogItems.length){
    const size=document.getElementById('filter-size');
    const color=document.getElementById('filter-color');
    const collection=document.getElementById('filter-collection');
    const search=document.getElementById('catalog-search');
    const count=document.getElementById('catalog-count');
    const apply=()=>{
      let shown=0;
      const q=(search?.value||'').trim().toLowerCase();
      catalogItems.forEach(item=>{
        const colorOk=!color?.value || (item.classList.contains('design-variant-card') ? !!COLORS[color.value] : item.dataset.color===color.value);
        const ok=(!size?.value||item.dataset.size===size.value)
          && colorOk
          &&(!collection?.value||item.dataset.collection===collection.value)
          &&(!q||(item.dataset.name||'').toLowerCase().includes(q));
        item.hidden=!ok;
        if(ok) shown++;
      });
      document.querySelectorAll('.family-block').forEach(section=>{
        section.hidden=![...section.querySelectorAll('.filter-item')].some(x=>!x.hidden);
      });
      if(count) count.textContent=shown+(shown===1?' позиція':' позицій');
    };
    [size,color,collection,search].forEach(el=>el&&el.addEventListener('input',apply));
    document.getElementById('reset-filters')?.addEventListener('click',()=>{
      [size,color,collection].forEach(el=>{if(el)el.value=''});
      if(search)search.value='';
      apply();
    });
    apply();
  }

  document.querySelectorAll('[data-gallery]').forEach(gallery=>{
    const main=gallery.querySelector('#product-main-image')||document.getElementById('product-main-image');
    gallery.querySelectorAll('[data-gallery-src]').forEach(btn=>{
      btn.addEventListener('click',()=>{
        gallery.querySelectorAll('[data-gallery-src]').forEach(x=>x.classList.remove('active'));
        btn.classList.add('active');
        if(main) main.src=btn.dataset.gallerySrc;
      });
    });
  });

  const getCart=()=>{
    try{return JSON.parse(localStorage.getItem(CART_KEY)||'[]')}catch{return[]}
  };
  const saveCart=cart=>{
    localStorage.setItem(CART_KEY,JSON.stringify(cart));
    updateCartCount();
  };
  const updateCartCount=()=>{
    const n=getCart().reduce((s,x)=>s+Number(x.qty||0),0);
    document.querySelectorAll('#cart-count').forEach(el=>el.textContent=String(n));
  };
  const money=v=>new Intl.NumberFormat('uk-UA').format(Number(v||0))+' грн';
  let activeProducts=new Map();

  const productForItem=item=>activeProducts.get(item.base_sku||item.sku);

  const setQty=(sku,qty)=>{
    const cart=getCart(),item=cart.find(x=>x.sku===sku);
    if(!item)return;
    if(qty<=0) saveCart(cart.filter(x=>x.sku!==sku));
    else {item.qty=Math.min(20,Math.max(1,Number(qty)||1));saveCart(cart)}
    renderCart();
    document.dispatchEvent(new CustomEvent('magelle:cart-change'));
  };

  function addToCart(itemSku,baseSku,meta={}){
    const p=activeProducts.get(baseSku||itemSku);
    if(!p||p.price_uah==null||!['stock','preorder'].includes(p.status))return;
    const cart=getCart();
    const item=cart.find(x=>x.sku===itemSku);
    if(item){item.qty+=1;Object.assign(item,{base_sku:baseSku||itemSku},meta)}
    else cart.push({sku:itemSku,base_sku:baseSku||itemSku,qty:1,...meta});
    saveCart(cart);renderCart();setCart(true);
  }

  function itemTitle(item,p){
    if(item.design)return (item.family||p?.series||'')+' «'+item.design+'» — '+(item.size||p?.size_name||'');
    return p?.title_ua||item.sku;
  }
  function itemDetails(item){
    const parts=[];
    if(item.vase_color)parts.push('Ваза: '+item.vase_color);
    parts.push(item.sku);
    return parts.join(' · ');
  }
  function renderCart(){
    if(!cartDrawer)return;
    const host=cartDrawer.querySelector('.cart-empty');
    if(!host)return;
    const cart=getCart();
    if(!cart.length){
      host.innerHTML='<p>Кошик порожній.</p><a class="text-link" href="/catalog.html">Перейти до каталогу →</a>';
      return;
    }
    let total=0;
    const rows=cart.map(item=>{
      const p=productForItem(item);
      if(!p)return '<div class="cart-line"><div><b>'+itemTitle(item,p)+'</b><small>'+itemDetails(item)+' · Тимчасово недоступно</small></div><button type="button" data-cart-remove="'+item.sku+'">×</button></div>';
      total+=Number(p.price_uah||0)*item.qty;
      return '<div class="cart-line"><div class="cart-line-main"><b>'+itemTitle(item,p)+'</b><small>'+itemDetails(item)+' · '+money(p.price_uah)+'</small><div class="cart-qty"><button type="button" data-cart-dec="'+item.sku+'">−</button><span>'+item.qty+'</span><button type="button" data-cart-inc="'+item.sku+'">+</button></div></div><div class="cart-line-side"><b>'+money(Number(p.price_uah||0)*item.qty)+'</b><button type="button" data-cart-remove="'+item.sku+'">×</button></div></div>';
    }).join('');
    host.innerHTML=rows+'<div class="cart-total"><span>Разом</span><b>'+money(total)+'</b></div><a class="btn dark wide cart-checkout" href="/checkout.html">Оформити замовлення</a>';
    host.querySelectorAll('[data-cart-remove]').forEach(btn=>btn.onclick=()=>setQty(btn.dataset.cartRemove,0));
    host.querySelectorAll('[data-cart-dec]').forEach(btn=>btn.onclick=()=>{const item=getCart().find(x=>x.sku===btn.dataset.cartDec);if(item)setQty(item.sku,item.qty-1)});
    host.querySelectorAll('[data-cart-inc]').forEach(btn=>btn.onclick=()=>{const item=getCart().find(x=>x.sku===btn.dataset.cartInc);if(item)setQty(item.sku,item.qty+1)});
  }

  function renderDesignCard(card,code,temporary=false){
    const color=COLORS[code]||COLORS.GRA;
    const photoColor=card.dataset.photoColor||'';
    const photoSrc=card.dataset.photoSrc||'';
    const stage=card.querySelector('.pilot-media-stage');
    const backLabel=card.querySelector('.pilot-media-back strong');
    const link=card.querySelector('.pilot-hero-link');
    const showPhoto=!!photoSrc;
    if(backLabel) backLabel.textContent=color.label;
    if(stage) stage.classList.toggle('is-flipped',!showPhoto);
    if(!temporary){
      const sizeCode=card.dataset.sizeCode;
      const designCode=card.dataset.designCode;
      const baseSku=canonicalSku(sizeCode,code);
      const itemSku=designSku(designCode,sizeCode,code);
      card.dataset.color=code;
      card.dataset.sku=itemSku;
      card.dataset.baseSku=baseSku;
      card.querySelectorAll('.pilot-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));
      const label=card.querySelector('.pilot-selected-color');if(label)label.textContent=color.label;
      if(link)link.href=(card.dataset.pdpUrl||'#')+'?color='+code;
      const p=activeProducts.get(baseSku),price=card.querySelector('.product-meta>b');
      if(price){
        if(p&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.remove('price-pending')}
        else{price.textContent='Ціну уточнюємо';price.classList.add('price-pending')}
      }
    }
  }

  function initDesignCards(){
    document.querySelectorAll('.design-variant-card').forEach(card=>{
      let selected=card.dataset.defaultColor||'GRA';
      card.querySelectorAll('.pilot-color').forEach(btn=>{
        btn.addEventListener('mouseenter',()=>renderDesignCard(card,btn.dataset.variantColor,true));
        btn.addEventListener('mouseleave',()=>renderDesignCard(card,selected,true));
        btn.addEventListener('focus',()=>renderDesignCard(card,btn.dataset.variantColor,true));
        btn.addEventListener('blur',()=>renderDesignCard(card,selected,true));
        btn.addEventListener('click',e=>{
          e.preventDefault();e.stopPropagation();
          selected=btn.dataset.variantColor;
          renderDesignCard(card,selected,false);
        });
      });
      renderDesignCard(card,selected,false);
    });
  }

  function applyPdpProduct(info,itemSku,baseSku){
    const p=activeProducts.get(baseSku);
    if(!p||!info)return;
    let price=info.querySelector('.price-placeholder');
    if(!price){
      price=document.createElement('div');
      price.className='price-placeholder';
      const anchor=info.querySelector('.sku-identity')||info.querySelector('.product-subtitle')||info.querySelector('h1');
      anchor?.after(price);
    }
    if(p.price_uah!=null&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.add('real-price')}
    else{price.textContent='Ціну уточнюємо';price.classList.remove('real-price')}
    let badge=info.querySelector('.api-availability');
    if(!badge){badge=document.createElement('p');badge.className='api-availability';price.after(badge)}
    badge.textContent=p.status==='stock'?'В наявності':(p.status==='preorder'?'Під замовлення'+(p.lead_time_days?' · '+p.lead_time_days+' дн.':''):'Недоступно');
    const cta=info.querySelector('.disabled-buy,[data-add-sku]');
    if(cta){
      if(p.price_uah!=null&&['stock','preorder'].includes(p.status)){
        cta.disabled=false;cta.classList.remove('disabled-buy');cta.dataset.addSku=itemSku;
        cta.textContent=p.status==='stock'?'Додати в кошик':'Замовити';
        cta.onclick=()=>addToCart(itemSku,baseSku,{
          family:info.dataset.family||'Organic Flare',
          design:info.dataset.design||'',
          size:info.dataset.variantSize||'',
          vase_color:info.dataset.selectedColor||''
        });
      }else{
        cta.disabled=true;cta.classList.add('disabled-buy');cta.textContent='Доступність уточнюється';cta.onclick=null;
      }
    }
  }

  function selectDesignPdp(code,updateUrl=true){
    const info=document.querySelector('.design-variant-pdp');
    if(!info)return;
    const color=COLORS[code]||COLORS.GRA;
    const sizeCode=info.dataset.sizeCode;
    const designCode=info.dataset.designCode;
    const baseSku=canonicalSku(sizeCode,code);
    const itemSku=designSku(designCode,sizeCode,code);
    info.dataset.selectedSku=itemSku;
    info.dataset.selectedBaseSku=baseSku;
    info.dataset.selectedColor=color.label;

    const sku=document.getElementById('design-selected-sku');if(sku)sku.textContent=itemSku;
    const label=document.getElementById('design-pdp-color-label');if(label)label.textContent=color.label;
    const colorEl=document.getElementById('design-pdp-color');if(colorEl)colorEl.innerHTML='<i class="swatch swatch-'+color.swatch+'"></i><span>'+color.label+'</span>';
    const spec=document.getElementById('design-spec-color');if(spec)spec.textContent=color.label;
    info.querySelectorAll('.design-pdp-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));

    const gallery=document.querySelector('[data-design-gallery]');
    if(gallery){
      const photoColor=gallery.dataset.photoColor||'';
      const main=document.getElementById('product-main-image');
      const ph=document.getElementById('design-photo-placeholder');
      const phLabel=document.getElementById('design-photo-placeholder-label');
      const thumbs=gallery.querySelector('.thumbs');
      const showPhoto=!!main;
      if(main)main.hidden=!showPhoto;
      if(ph){ph.hidden=showPhoto;if(phLabel)phLabel.textContent=color.label}
      if(thumbs)thumbs.style.display=showPhoto?'':'none';
    }

    if(updateUrl){
      const url=new URL(location.href);url.searchParams.set('color',code);history.replaceState({},'',url);
    }
    applyPdpProduct(info,itemSku,baseSku);
  }

  function initDesignPdp(){
    const info=document.querySelector('.design-variant-pdp');if(!info)return;
    const requested=new URL(location.href).searchParams.get('color')||info.dataset.defaultColor||'GRA';
    const initial=COLORS[requested]?requested:(info.dataset.defaultColor||'GRA');
    info.querySelectorAll('.design-pdp-color').forEach(btn=>btn.addEventListener('click',()=>selectDesignPdp(btn.dataset.variantColor,true)));
    selectDesignPdp(initial,false);
  }

  function skuFromPdp(){
    const info=document.querySelector('.sku-pdp');
    if(info?.dataset.selectedBaseSku)return info.dataset.selectedBaseSku;
    const values=[...document.querySelectorAll('.sku-identity strong')];
    return values.map(x=>x.textContent.trim()).find(x=>/^MG-[A-Z0-9-]+$/.test(x))||'';
  }

  function applyProductData(products){
    activeProducts=new Map(products.map(p=>[p.sku,p]));
    document.querySelectorAll('.sku-card:not(.design-variant-card)').forEach(card=>{
      const sku=card.dataset.sku||card.dataset.name?.match(/MG-[A-Z0-9-]+/)?.[0];
      const p=activeProducts.get(sku);
      const meta=card.querySelector('.product-meta');if(!meta)return;
      let price=meta.querySelector(':scope > b');if(!price){price=document.createElement('b');price.className='api-price';meta.append(price)}
      if(p&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.remove('price-pending');card.classList.add('api-active-product')}
      else{price.textContent='Ціну уточнюємо';price.classList.add('price-pending');card.classList.remove('api-active-product')}
    });
    document.querySelectorAll('.design-variant-card').forEach(card=>renderDesignCard(card,card.dataset.color||card.dataset.defaultColor||'GRA',false));
    const designInfo=document.querySelector('.design-variant-pdp');
    if(designInfo){
      const code=new URL(location.href).searchParams.get('color')||designInfo.dataset.defaultColor||'GRA';
      selectDesignPdp(COLORS[code]?code:(designInfo.dataset.defaultColor||'GRA'),false);
    }else{
      const info=document.querySelector('.sku-pdp'),sku=skuFromPdp();
      if(sku&&info){
        const p=activeProducts.get(sku);
        if(p){
          let price=info.querySelector('.price-placeholder');
          if(!price){price=document.createElement('div');price.className='price-placeholder';(info.querySelector('.sku-identity')||info.querySelector('.product-subtitle')||info.querySelector('h1'))?.after(price)}
          price.textContent=p.price_uah!=null?money(p.price_uah):'Ціну уточнюємо';
        }
      }
    }
    renderCart();
  }

  async function loadProducts(){
    try{
      const r=await fetch(API_BASE+'/api/products',{headers:{Accept:'application/json'}});
      if(!r.ok)return;
      applyProductData(await r.json());
    }catch(_){}
  }

  window.MaGelleStore={getCart,saveCart,setQty,money,API_BASE,getProducts:()=>activeProducts};
  initDesignCards();
  initDesignPdp();
  updateCartCount();
  renderCart();
  loadProducts();
})();