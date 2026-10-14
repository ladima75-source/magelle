(() => {
  // A gallery image can recover when the selected color changes to a working URL.
  document.addEventListener('load',event=>{
    const img=event.target;
    if(!(img instanceof HTMLImageElement))return;
    if(!img.closest('.product-photo,.hero-photo,.collection-photo-card,.pilot-media-front,.product-main-photo'))return;
    if(!img.naturalWidth)return;
    img.style.removeProperty('display');
    img.removeAttribute('data-fallback-done');
    const label=img.parentElement?.querySelector(':scope > .media-unavailable');
    if(label)label.remove();
  },true);
  // Protect product cards from Drive previews that return HTML instead of images.
  document.addEventListener('error',event=>{
    const img=event.target;
    if(!(img instanceof HTMLImageElement) || img.dataset.fallbackDone)return;
    if(!img.closest('.product-photo,.hero-photo,.collection-photo-card,.pilot-media-front,.product-main-photo'))return;
    img.dataset.fallbackDone='1';
    img.style.display='none';
    const frame=img.parentElement;
    if(!frame || frame.querySelector('.media-unavailable'))return;
    const label=document.createElement('span');
    label.className='media-unavailable';
    label.textContent='Фото готуємо';
    frame.appendChild(label);
  },true);

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
    SND:{label:'Пісочний',swatch:'snd'},
    CHO:{label:'Шоколад',swatch:'cho'}
  };
  const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let catalogModel=null;
  const body=document.body;

  const familyCode=el=>el?.dataset?.familyCode||(el?.dataset?.family==='Architectural Step'?'AS':'OF');
  const canonicalSku=(family,sizeCode,color)=>'MG-'+family+'-'+sizeCode+'-'+color;
  const designSku=(family,designCode,sizeCode,color)=>'MG-'+family+'-'+designCode+'-'+sizeCode+'-'+color;

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

  const mobileFilterToggle=document.querySelector('.mobile-filter-toggle');
  mobileFilterToggle?.addEventListener('click',()=>{
    const expanded=mobileFilterToggle.getAttribute('aria-expanded')==='true';
    mobileFilterToggle.setAttribute('aria-expanded',String(!expanded));
    mobileFilterToggle.querySelector('span').textContent=expanded?'Показати ▾':'Сховати ▴';
  });
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
      document.querySelectorAll('.filter-item').forEach(item=>{
        const colorOk=!color?.value || (item.classList.contains('design-variant-card') ? (item.dataset.availableColors||'GRA,MLK,WHT,SND,CHO').split(',').includes(color.value) : item.dataset.color===color.value);
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
    document.addEventListener('magelle:catalog-refresh',apply);
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
  // Exact Admin 2.0 SKU analytics, never buyer names/phones or email.
  const GA_MEASUREMENT_ID='G-1RM1S55BZW';
  const analyticsItem=(p,qty=1)=>({
    item_id:p.sku,item_name:p.title_ua||p.sku,
    item_brand:'MaGelle',item_category:p.series||'Інтер’єрні композиції',
    item_variant:p.color||'',price:Number(p.price_uah),quantity:Number(qty)
  });
  const gaEvent=(name,params)=>{
    if(typeof window.gtag==='function')window.gtag('event',name,{send_to:GA_MEASUREMENT_ID,...params});
  };
  let lastViewedSku='';
  const trackViewItem=p=>{
    if(!p||!p.sku||!(Number(p.price_uah)>0)||p.sku===lastViewedSku)return;
    lastViewedSku=p.sku;
    gaEvent('view_item',{currency:'UAH',value:Number(p.price_uah),items:[analyticsItem(p)]});
  };
  const trackBeginCheckout=cart=>{
    const lines=(cart||[]).map(x=>({p:activeProducts.get(x.sku),qty:Number(x.qty)}));
    if(!lines.length||lines.some(x=>!x.p||!(Number(x.p.price_uah)>0)||!Number.isInteger(x.qty)||x.qty<1))return false;
    const items=lines.map(x=>analyticsItem(x.p,x.qty));
    gaEvent('begin_checkout',{currency:'UAH',value:items.reduce((sum,x)=>sum+x.price*x.quantity,0),items});
    return true;
  };
  const getAnalyticsClientId=()=>{
    // _ga is a first-party GA4 pseudonymous client identifier; never send PII.
    const cookie=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('_ga='));
    if(!cookie)return '';
    const match=decodeURIComponent(cookie.split('=').slice(1).join('=')).match(/(?:^|\.)([0-9]{1,30}\.[0-9]{1,30})$/);
    return match?match[1]:'';
  };
  const trackOrderRequest=(response,cart)=>{
    // The server returns status=new, payment_status=unpaid. It is an accepted
    // order *request*, not a sale. The checkout MUST NEVER fire purchase.
    if(response?.ok!==true||!Number.isSafeInteger(Number(response.order_id))||Number(response.order_id)<1)return false;
    const items=(cart||[]).map(x=>({p:activeProducts.get(x.sku),qty:Number(x.qty)})).filter(x=>x.p&&x.qty>0).map(x=>analyticsItem(x.p,x.qty));
    gaEvent('generate_lead',{currency:'UAH',value:Number(response.total_uah)||0,lead_source:'website_checkout',items});
    return true;
  };


  const productForItem=item=>activeProducts.get(item.sku)||(!catalogModel?.enabled?activeProducts.get(item.base_sku||item.sku):null);

  const setQty=(sku,qty)=>{
    const cart=getCart(),item=cart.find(x=>x.sku===sku);
    if(!item)return;
    if(qty<=0) saveCart(cart.filter(x=>x.sku!==sku));
    else {item.qty=Math.min(20,Math.max(1,Number(qty)||1));saveCart(cart)}
    renderCart();
    document.dispatchEvent(new CustomEvent('magelle:cart-change'));
  };

  function addToCart(itemSku,baseSku,meta={}){
    const p=activeProducts.get(itemSku)||(!catalogModel?.enabled?activeProducts.get(baseSku||itemSku):null);
    if(!p||p.price_uah==null||!['stock','preorder'].includes(p.status))return;
    const cart=getCart();
    const item=cart.find(x=>x.sku===itemSku);
    if(item){item.qty=Math.min(20,item.qty+1);Object.assign(item,{base_sku:baseSku||itemSku},meta)}
    else cart.push({sku:itemSku,base_sku:baseSku||itemSku,qty:1,...meta});
    saveCart(cart);renderCart();setCart(true);
    gaEvent('add_to_cart',{currency:'UAH',value:Number(p.price_uah),items:[analyticsItem(p,1)]});
  }

  function itemTitle(item,p){
    if(p?.design_id)return p.title_ua;
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
      if(!p)return '<div class="cart-line"><div><b>'+escapeHtml(itemTitle(item,p))+'</b><small>'+escapeHtml(itemDetails(item))+' · Тимчасово недоступно</small></div><button type="button" data-cart-remove="'+escapeHtml(item.sku)+'">×</button></div>';
      total+=Number(p.price_uah||0)*item.qty;
      return '<div class="cart-line"><div class="cart-line-main"><b>'+escapeHtml(itemTitle(item,p))+'</b><small>'+escapeHtml((p.color?'Ваза: '+p.color+' · ':'')+item.sku)+' · '+money(p.price_uah)+'</small><div class="cart-qty"><button type="button" data-cart-dec="'+escapeHtml(item.sku)+'">−</button><span>'+escapeHtml(item.qty)+'</span><button type="button" data-cart-inc="'+escapeHtml(item.sku)+'">+</button></div></div><div class="cart-line-side"><b>'+money(Number(p.price_uah||0)*item.qty)+'</b><button type="button" data-cart-remove="'+escapeHtml(item.sku)+'">×</button></div></div>';
    }).join('');
    host.innerHTML=rows+'<div class="cart-total"><span>Разом</span><b>'+money(total)+'</b></div><a class="btn dark wide cart-checkout" href="/checkout.html">Оформити замовлення</a>';
    host.querySelectorAll('[data-cart-remove]').forEach(btn=>btn.onclick=()=>setQty(btn.dataset.cartRemove,0));
    host.querySelectorAll('[data-cart-dec]').forEach(btn=>btn.onclick=()=>{const item=getCart().find(x=>x.sku===btn.dataset.cartDec);if(item)setQty(item.sku,item.qty-1)});
    host.querySelectorAll('[data-cart-inc]').forEach(btn=>btn.onclick=()=>{const item=getCart().find(x=>x.sku===btn.dataset.cartInc);if(item)setQty(item.sku,item.qty+1)});
  }

  const variantPhotoLoads=new Map();
  function preloadVariantPhoto(src){
    if(!src)return Promise.resolve();
    if(!variantPhotoLoads.has(src)){
      variantPhotoLoads.set(src,new Promise(resolve=>{
        const image=new Image();
        image.onload=()=>resolve(true);
        image.onerror=()=>resolve(false);
        image.src=src;
        if(image.complete)resolve(true);
      }));
    }
    return variantPhotoLoads.get(src);
  }

  function renderDesignCard(card,code,temporary=false,forceSource=false){
    const color=COLORS[code]||COLORS.GRA;
    const photoColor=card.dataset.photoColor||'';
    const photoSrc=card.dataset.photoSrc||'';
    const stage=card.querySelector('.pilot-media-stage');
    const backLabel=card.querySelector('.pilot-media-back strong');
    const link=card.querySelector('.pilot-hero-link');
    const variantSrc=card.dataset['variant'+code[0]+code.slice(1).toLowerCase()]||'';
    const img=card.querySelector('.pilot-media-front img');
    const showPhoto=!!variantSrc || (!!photoSrc && ((!catalogModel?.enabled&&forceSource) || code===photoColor));
    const media=card.querySelector('.pilot-hero-media');
    const applyVisual=()=>{
      if(img){
        const targetSrc=variantSrc || (showPhoto ? photoSrc : '');
        if(targetSrc && img.getAttribute('src')!==targetSrc)img.src=targetSrc;
        img.hidden=!showPhoto;
      }
      if(backLabel)backLabel.textContent=color.label;
      if(stage)stage.classList.toggle('is-flipped',!showPhoto);
    };
    if(media){
      media._colorTurnToken=(media._colorTurnToken||0)+1;
      const token=media._colorTurnToken;
      const previous=media.dataset.previewColor;
      media.dataset.previewColor=code;
      media.getAnimations().forEach(a=>a.cancel());
      const ready=(variantSrc || (showPhoto ? photoSrc : '')) ? preloadVariantPhoto(variantSrc || photoSrc) : Promise.resolve();
      if(previous && previous!==code && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
        ready.then(()=>{
          if(media._colorTurnToken!==token)return;
          const first=media.animate([
            {transform:'perspective(950px) rotateY(0deg)',opacity:1},
            {transform:'perspective(950px) rotateY(-90deg)',opacity:.75}
          ],{duration:175,easing:'ease-in',fill:'forwards'});
          first.finished.then(()=>{
            if(media._colorTurnToken!==token)return;
            applyVisual();
            first.cancel();
            const second=media.animate([
              {transform:'perspective(950px) rotateY(-90deg)',opacity:.75},
              {transform:'perspective(950px) rotateY(-360deg)',opacity:1}
            ],{duration:475,easing:'ease-out'});
            second.finished.then(()=>{if(media._colorTurnToken===token)second.cancel()}).catch(()=>{});
          }).catch(()=>{});
        });
      }else{
        ready.then(()=>{if(media._colorTurnToken===token)applyVisual()});
      }
    }else applyVisual();
    if(!temporary){
      const sizeCode=card.dataset.sizeCode;
      const designCode=card.dataset.designCode;
      const family=familyCode(card);
      const variant=catalogModel?.enabled?catalogModel.products.find(p=>p.design_id===card.dataset.catalogDesignId&&p.color_code===code):null;
      const itemSku=variant?.sku||designSku(family,designCode,sizeCode,code);
      const baseSku=catalogModel?.enabled?itemSku:canonicalSku(family,sizeCode,code);
      card.dataset.color=code;
      card.dataset.sku=itemSku;
      card.dataset.baseSku=baseSku;
      card.querySelectorAll('.pilot-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));
      const label=card.querySelector('.pilot-selected-color');if(label)label.textContent=color.label;
      if(link){const url=new URL(card.dataset.pdpUrl||'#',location.origin);url.searchParams.set('color',code);link.href=url.href;}
      const p=activeProducts.get(itemSku)||(!catalogModel?.enabled?activeProducts.get(baseSku):null),price=card.querySelector('.product-meta>b');
      if(price){
        if(p&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.remove('price-pending')}
        else{price.textContent='Ціну уточнюємо';price.classList.add('price-pending')}
      }
    }
  }

  function initDesignCards(){
    document.querySelectorAll('.design-variant-card').forEach(card=>{
      let selected=card.dataset.defaultColor||'GRA';
      card.dataset.sourcePreview='1';
      Object.keys(card.dataset).filter(key=>key.startsWith('variant') && /^variant[A-Z][a-z]+$/.test(key)).forEach(key=>preloadVariantPhoto(card.dataset[key]));
      card.querySelectorAll('.pilot-color').forEach(btn=>{
        btn.addEventListener('mouseenter',()=>renderDesignCard(card,btn.dataset.variantColor,true,false));
        btn.addEventListener('mouseleave',()=>renderDesignCard(card,selected,true,card.dataset.sourcePreview==='1'));
        btn.addEventListener('focus',()=>renderDesignCard(card,btn.dataset.variantColor,true,false));
        btn.addEventListener('blur',()=>renderDesignCard(card,selected,true,card.dataset.sourcePreview==='1'));
        btn.addEventListener('click',e=>{
          e.preventDefault();e.stopPropagation();
          selected=btn.dataset.variantColor;
          card.dataset.sourcePreview='0';
          renderDesignCard(card,selected,false,false);
        });
      });
      renderDesignCard(card,selected,false,true);
    });
  }

  function applyPdpProduct(info,itemSku,baseSku){
    if(!info)return;
    const p=activeProducts.get(itemSku)||(!catalogModel?.enabled?activeProducts.get(baseSku):null);
    let price=info.querySelector('.price-placeholder');
    if(!price){
      price=document.createElement('div');
      price.className='price-placeholder';
      const anchor=info.querySelector('.sku-identity')||info.querySelector('.product-subtitle')||info.querySelector('h1');
      anchor?.after(price);
    }
    if(p?.price_uah!=null&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.add('real-price')}
    else{price.textContent='Ціну уточнюємо';price.classList.remove('real-price')}
    let badge=info.querySelector('.api-availability');
    if(!badge){badge=document.createElement('p');badge.className='api-availability';price.after(badge)}
    badge.textContent=p?.status==='stock'?'В наявності':(p?.status==='preorder'?'Під замовлення'+(p.lead_time_days?' · '+p.lead_time_days+' дн.':''):'Недоступно');
    const cta=info.querySelector('.disabled-buy,[data-add-sku]');
    if(cta){
      if(p?.price_uah>0&&['stock','preorder'].includes(p.status)){
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

  // Use the exact Admin 2.0 SKU, image, stock and price in Google Product/Offer.
  function updateExactSchema(p,code,info){
    const existing=document.getElementById('magelle-product-schema');
    document.querySelectorAll('script[type="application/ld+json"]').forEach(n=>{
      if(n.id==='magelle-product-schema')return;
      try{if(JSON.parse(n.textContent)['@type']==='Product')n.remove()}catch(_){}
    });
    const images=(p?.photo_urls||[]).filter(u=>/^https:\/\/api\.magelle\.com\.ua\/(media|uploads)\//.test(u));
    if(!p||!images.length||!(Number(p.price_uah)>0)){existing?.remove();return;}
    const url=new URL(location.pathname,location.origin);
    if(code!==info.dataset.defaultColor)url.searchParams.set('color',code);
    const data={'@context':'https://schema.org','@type':'Product',
      name:'MaGelle '+p.title_ua,sku:p.sku,
      description:p.description_ua||'Інтер’єрна композиція MaGelle з сухоцвітів та стабілізованих рослин.',
      image:images,brand:{'@type':'Brand',name:'MaGelle'},color:p.color,url:url.href};
    if(p.status==='stock')data.offers={'@type':'Offer',price:p.price_uah,priceCurrency:'UAH',
      availability:'https://schema.org/InStock',itemCondition:'https://schema.org/NewCondition',url:url.href};
    else if(p.status==='hidden')data.offers={'@type':'Offer',price:p.price_uah,priceCurrency:'UAH',
      availability:'https://schema.org/OutOfStock',itemCondition:'https://schema.org/NewCondition',url:url.href};
    const node=existing||document.createElement('script');
    node.id='magelle-product-schema';node.type='application/ld+json';
    node.textContent=JSON.stringify(data);
    if(!existing)document.head.appendChild(node);
    const canonical=document.querySelector('link[rel="canonical"]');
    if(canonical)canonical.href=url.href;
  }

  function selectDesignPdp(code,updateUrl=true,forceSource=false){
    const info=document.querySelector('.design-variant-pdp');
    if(!info)return;
    const color=COLORS[code]||COLORS.GRA;
    const sizeCode=info.dataset.sizeCode;
    const designCode=info.dataset.designCode;
    const family=familyCode(info);
    const variant=catalogModel?.enabled?catalogModel.products.find(p=>p.design_id===info.dataset.catalogDesignId&&p.color_code===code):null;
    const itemSku=variant?.sku||designSku(family,designCode,sizeCode,code);
    const baseSku=catalogModel?.enabled?itemSku:canonicalSku(family,sizeCode,code);
    info.dataset.selectedSku=itemSku;
    info.dataset.selectedBaseSku=baseSku;
    info.dataset.selectedColor=color.label;

    const sku=document.getElementById('design-selected-sku');if(sku)sku.textContent=itemSku;
    const label=document.getElementById('design-pdp-color-label');if(label)label.textContent=color.label;
    const colorEl=document.getElementById('design-pdp-color');if(colorEl)colorEl.innerHTML='<i class="swatch swatch-'+escapeHtml(color.swatch)+'" '+(color.hex?'style="background:'+escapeHtml(color.hex)+'"':'')+'></i><span>'+escapeHtml(color.label)+'</span>';
    const spec=document.getElementById('design-spec-color');if(spec)spec.textContent=color.label;
    info.querySelectorAll('.design-pdp-color').forEach(b=>b.classList.toggle('active',b.dataset.variantColor===code));
    document.querySelectorAll('.mobile-photo-colors button').forEach(b=>{
      b.classList.toggle('active',b.dataset.mobileColor===code);
      b.setAttribute('aria-pressed',String(b.dataset.mobileColor===code));
    });

    const gallery=document.querySelector('[data-design-gallery]');
    if(gallery&&catalogModel?.enabled){
      const d=catalogModel.designs.find(d=>d.id===info.dataset.catalogDesignId);
      const staticVariantSrc=info.dataset['variant'+code[0]+code.slice(1).toLowerCase()]||'';
      const apiPhotos=variant?.photo_urls?.length?variant.photo_urls:(d?.source_color===code?d.source_photo_urls:[]);
      // Prefer the exact SKU's first-party media over stale static Drive previews.
      const photos=apiPhotos.length?[...apiPhotos,...(staticVariantSrc&&!apiPhotos.includes(staticVariantSrc)?[staticVariantSrc]:[])]:staticVariantSrc?[staticVariantSrc]:[];
      const main=document.getElementById('product-main-image'),ph=document.getElementById('design-photo-placeholder');
      if(main){main.hidden=!photos.length;if(photos.length)main.src=photos[0];}
      if(ph){ph.hidden=!!photos.length;const label=ph.querySelector('strong');if(label)label.textContent=color.label;}
      const thumbs=gallery.querySelector('.thumbs');
      if(thumbs){thumbs.hidden=false;thumbs.innerHTML=photos.map((src,i)=>`<button type="button" class="photo-thumb ${i===0?'active':''}" data-catalog-photo="${escapeHtml(src)}"><img src="${escapeHtml(src)}" alt="${escapeHtml(color.label)} · фото ${i+1}"></button>`).join('');thumbs.style.display=photos.length>1?'':'none';thumbs.querySelectorAll('[data-catalog-photo]').forEach(b=>b.onclick=()=>{if(main)main.src=b.dataset.catalogPhoto;});}
      const desc=info.querySelector('.product-description');if(desc)desc.textContent=variant?.description_ua||d?.description_ua||'';
      let specs=document.querySelector('.catalog2-specs');if(!specs){specs=document.createElement('div');specs.className='catalog2-specs';info.append(specs);}
      const values=[['Габарити',variant?.dimensions||d?.dimensions],['Склад',variant?.composition||d?.composition]];
      specs.innerHTML='<dl>'+values.filter(([,v])=>v).map(([k,v])=>`<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`).join('')+'</dl>';
      const oldSpecs=document.querySelector('.specs-section');if(oldSpecs)oldSpecs.hidden=true;
    }else if(gallery){
      const photoColor=gallery.dataset.photoColor||'';
      const main=document.getElementById('product-main-image');
      const ph=document.getElementById('design-photo-placeholder');
      const phLabel=document.getElementById('design-photo-placeholder-label');
      const thumbs=gallery.querySelector('.thumbs');
      const variantSrc=info.dataset['variant'+code[0]+code.slice(1).toLowerCase()]||'';
      const showPhoto=!!main && (!!variantSrc || (forceSource && code===photoColor) || code===photoColor);
      if(main && variantSrc)main.src=variantSrc;
      if(main)main.hidden=!showPhoto;
      if(ph){ph.hidden=showPhoto;if(phLabel)phLabel.textContent=color.label}
      if(thumbs)thumbs.style.display=(showPhoto&&code===photoColor)?'':'none';
    }

    if(updateUrl){
      const url=new URL(location.href);url.searchParams.set('color',code);history.replaceState({},'',url);
    }
    applyPdpProduct(info,itemSku,baseSku);
    trackViewItem(activeProducts.get(itemSku)||(!catalogModel?.enabled?activeProducts.get(baseSku):null));
    if(catalogModel?.enabled)updateExactSchema(variant,code,info);
  }

  function initDesignPdp(){
    const info=document.querySelector('.design-variant-pdp');if(!info)return;
    const requested=new URL(location.href).searchParams.get('color')||info.dataset.defaultColor||'GRA';
    const initial=COLORS[requested]?requested:(info.dataset.defaultColor||'GRA');
    info.dataset.sourcePreview='1';
    const gallery=document.querySelector('[data-design-gallery]');
    const mainPhoto=gallery?.querySelector('.product-main-photo');
    if(mainPhoto && !gallery.querySelector('.mobile-photo-colors')){
      const panel=document.createElement('div');
      panel.className='mobile-photo-colors';
      panel.setAttribute('aria-label','Колір вази');
      info.querySelectorAll('.design-pdp-color').forEach(original=>{
        const code=original.dataset.variantColor;
        const color=COLORS[code];if(!color)return;
        const btn=document.createElement('button');
        btn.type='button';btn.dataset.mobileColor=code;
        btn.setAttribute('aria-label',color.label);
        btn.title=color.label;
        btn.innerHTML='<i class="swatch swatch-'+color.swatch+'"></i><span>'+color.label+'</span>';
        btn.addEventListener('click',()=>original.click());
        panel.appendChild(btn);
      });
      gallery.appendChild(panel);
    }
    info.querySelectorAll('.design-pdp-color').forEach(btn=>btn.addEventListener('click',()=>{
      info.dataset.sourcePreview='0';
      selectDesignPdp(btn.dataset.variantColor,true,false);
    }));
    selectDesignPdp(initial,false,initial===(document.querySelector('[data-design-gallery]')?.dataset.photoColor||''));
  }

  function skuFromPdp(){
    const info=document.querySelector('.sku-pdp');
    if(info?.dataset.selectedBaseSku)return info.dataset.selectedBaseSku;
    const values=[...document.querySelectorAll('.sku-identity strong')];
    return values.map(x=>x.textContent.trim()).find(x=>/^MG-[A-Z0-9-]+$/.test(x))||'';
  }

  function applyProductData(products){
    activeProducts=new Map(products.map(p=>[p.sku,p]));
    products.forEach(p=>(p.aliases||[]).forEach(alias=>activeProducts.set(alias,p)));
    document.querySelectorAll('.sku-card:not(.design-variant-card)').forEach(card=>{
      const sku=card.dataset.sku||card.dataset.name?.match(/MG-[A-Z0-9-]+/)?.[0];
      const p=activeProducts.get(sku);
      const meta=card.querySelector('.product-meta');if(!meta)return;
      let price=meta.querySelector(':scope > b');if(!price){price=document.createElement('b');price.className='api-price';meta.append(price)}
      if(p&&Number(p.price_uah)>0){price.textContent=money(p.price_uah);price.classList.remove('price-pending');card.classList.add('api-active-product')}
      else{price.textContent='Ціну уточнюємо';price.classList.add('price-pending');card.classList.remove('api-active-product')}
    });
    document.querySelectorAll('.design-variant-card').forEach(card=>renderDesignCard(card,card.dataset.color||card.dataset.defaultColor||'GRA',false,card.dataset.sourcePreview==='1'));
    const designInfo=document.querySelector('.design-variant-pdp');
    if(designInfo){
      const code=new URL(location.href).searchParams.get('color')||designInfo.dataset.defaultColor||'GRA';
      selectDesignPdp(COLORS[code]?code:(designInfo.dataset.defaultColor||'GRA'),false,designInfo.dataset.sourcePreview==='1');
    }else{
      const info=document.querySelector('.sku-pdp'),sku=skuFromPdp();
      if(sku&&info){
        const p=activeProducts.get(sku);
        if(p){
          let price=info.querySelector('.price-placeholder');
          if(!price){price=document.createElement('div');price.className='price-placeholder';(info.querySelector('.sku-identity')||info.querySelector('.product-subtitle')||info.querySelector('h1'))?.after(price)}
          price.textContent=p.price_uah!=null?money(p.price_uah):'Ціну уточнюємо';
          trackViewItem(p);
        }
      }
    }
    renderCart();
    // Notify checkout when the public product API snapshot is available.
    document.dispatchEvent(new CustomEvent('magelle:cart-change'));
  }

  async function loadProducts(){
    try{
      const modelResponse=await fetch(API_BASE+'/api/catalog',{headers:{Accept:'application/json'}});
      if(modelResponse.ok){
        const model=await modelResponse.json();
        if(model.enabled){catalogModel=model;hydrateCatalog(model);applyProductData(model.products);document.dispatchEvent(new CustomEvent('magelle:cart-change'));return;}
      }
      const r=await fetch(API_BASE+'/api/products',{headers:{Accept:'application/json'}});
      if(!r.ok)return;
      applyProductData(await r.json());
    }catch(_){}
  }

  function variantButtons(variants,kind){
    return variants.map(p=>{const c=COLORS[p.color_code];if(!c)return '';return `<button type="button" class="${kind}" data-variant-color="${escapeHtml(p.color_code)}" aria-label="${escapeHtml(c.label)}"><i class="swatch" style="background:${escapeHtml(c.hex||'#777')}"></i><span>${escapeHtml(c.label)}</span></button>`;}).join('');
  }
  function hydrateCatalog(model){
    model.colors.forEach(c=>{COLORS[c.code]={label:c.title_ua,swatch:c.code.toLowerCase(),hex:c.hex};});
    // Approved storefront media is authoritative. The catalog API may lag behind
    // the reviewed 2 bouquets × 5 colors. Never recreate their hero/photo DOM
    // from that API response; use API data for pricing and SKU status only.
    if(document.querySelector('.design-variant-card'))return;
    const reviewedMedia=new Map([...document.querySelectorAll('.design-variant-card')].map(card=>{
      const key=[familyCode(card),card.dataset.designCode,card.dataset.sizeCode].join('|');
      const media={};
      for(const code of Object.keys(COLORS)){
        const value=card.dataset['variant'+code[0]+code.slice(1).toLowerCase()];
        if(value)media[code]=value;
      }
      if(card.dataset.photoColor&&card.dataset.photoSrc&&!media[card.dataset.photoColor])media[card.dataset.photoColor]=card.dataset.photoSrc;
      return [key,media];
    }));
    const variantsFor=d=>model.products.filter(p=>p.design_id===d.id);
    const cardFor=d=>{
      const variants=variantsFor(d),selected=variants.some(p=>p.color_code===d.default_color)?d.default_color:(variants[0]?.color_code||d.default_color||'GRA');
      const url=d.pdp_url||('/product.html?design='+encodeURIComponent(d.id));
      const link=url+(url.includes('?')?'&':'?')+'color='+selected;
      const fallback=reviewedMedia.get([d.family_code,d.code,d.size_code].join('|'))||{};
      const photos=Object.fromEntries(variants.map(p=>['data-variant-'+p.color_code.toLowerCase(),fallback[p.color_code]||p.photo_urls?.[0]||'']));
      const attr=Object.entries(photos).map(([k,v])=>k+'="'+escapeHtml(v)+'"').join(' ');
      const selectedVariant=variants.find(p=>p.color_code===selected);
      const src=fallback[selected]||selectedVariant?.photo_urls?.[0]||d.source_photo_urls?.[0]||'';
      return `<article class="product-card sku-card filter-item design-variant-card" data-catalog-design-id="${escapeHtml(d.id)}" data-size="${d.size_code==='DEL'?'S':d.size_code==='VYR'?'M':escapeHtml(d.size_code)}" data-size-code="${escapeHtml(d.size_code)}" data-collection="${escapeHtml(d.collection)}" data-name="${escapeHtml(d.series+' '+d.title_ua+' '+d.size_name+' '+variants.map(p=>p.color).join(' '))}" data-family="${escapeHtml(d.series)}" data-family-code="${escapeHtml(d.family_code)}" data-design="${escapeHtml(d.title_ua)}" data-design-code="${escapeHtml(d.code)}" data-variant-size="${escapeHtml(d.size_name)}" data-default-color="${escapeHtml(selected)}" data-photo-color="${escapeHtml(d.source_color)}" data-photo-src="${escapeHtml(d.source_photo_urls?.[0]||'')}" data-available-colors="${escapeHtml(variants.map(p=>p.color_code).join(','))}" data-pdp-url="${escapeHtml(url)}" ${attr}>
      <a href="${escapeHtml(link)}" class="product-photo sku-photo pilot-hero-link"><div class="pilot-hero-media"><div class="pilot-media-stage"><div class="pilot-media-face pilot-media-front"><img src="${escapeHtml(src)}" alt="${escapeHtml(d.series+' «'+d.title_ua+'»')}" loading="lazy" ${src?'':'hidden'}></div><div class="pilot-media-face pilot-media-back pilot-card-placeholder"><div><strong>${escapeHtml(COLORS[selected]?.label)}</strong><small>Фото готуємо</small></div></div></div></div></a>
      <div class="pilot-variant-picker" aria-label="Колір вази">${variantButtons(variants,'pilot-color')}</div><div class="product-meta"><div><small>${escapeHtml(d.size_name)}</small><h3><span class="catalog-title-name">${escapeHtml(d.series)} «${escapeHtml(d.title_ua)}» —</span><span class="catalog-title-size">${escapeHtml(d.size_name)}</span></h3><span class="pilot-selected-color"></span></div><b class="api-price price-pending">Ціну уточнюємо</b></div></article>`;
    };
    const catalogMain=document.querySelector('.catalog-main');
    if(catalogMain){
      catalogMain.querySelectorAll('.family-block').forEach(n=>n.remove());
      let section=null,last=null;
      model.designs.forEach(d=>{if(last!==d.collection){section=document.createElement('section');section.className='family-block';section.innerHTML=`<div class="family-heading"><h2>${escapeHtml(d.series)}</h2></div><div class="product-grid catalog-grid paired-grid"></div>`;catalogMain.append(section);last=d.collection;}section.querySelector('.product-grid').insertAdjacentHTML('beforeend',cardFor(d));});
    }else{
      const cards=document.querySelectorAll('.design-variant-card');
      if(cards.length){const collection=cards[0].dataset.collection,grid=cards[0].parentElement;grid.innerHTML=model.designs.filter(d=>d.collection===collection).map(cardFor).join('');}
    }
    initDesignCards();
    const colors=document.getElementById('filter-color');if(colors)colors.innerHTML='<option value="">Усі</option>'+model.colors.map(c=>`<option value="${escapeHtml(c.code)}">${escapeHtml(c.title_ua)}</option>`).join('');
    const collections=document.getElementById('filter-collection');if(collections){const seen=new Map(model.designs.map(d=>[d.collection,d.series]));collections.innerHTML='<option value="">Усі</option>'+[...seen].map(([k,v])=>`<option value="${escapeHtml(k)}">${escapeHtml(v)}</option>`).join('');}
    const sizes=document.getElementById('filter-size');if(sizes){const seen=new Map(model.designs.map(d=>[d.size_code==='DEL'?'S':d.size_code==='VYR'?'M':d.size_code,d.size_name]));sizes.innerHTML='<option value="">Усі</option>'+[...seen].map(([k,v])=>`<option value="${escapeHtml(k)}">${escapeHtml(v)}</option>`).join('');}
    const info=document.querySelector('.design-variant-pdp');
    if(info){
      const requested=new URL(location.href).searchParams.get('design');
      const d=model.designs.find(d=>requested?d.id===requested:d.code===info.dataset.designCode&&d.family_code===familyCode(info)&&d.size_code===info.dataset.sizeCode);
      if(d){
        Object.assign(info.dataset,{catalogDesignId:d.id,family:d.series,familyCode:d.family_code,design:d.title_ua,designCode:d.code,sizeCode:d.size_code,variantSize:d.size_name,defaultColor:d.default_color});
        const h1=info.querySelector('h1');if(h1)h1.textContent=d.series+' «'+d.title_ua+'» — '+d.size_name;
        document.title=d.series+' «'+d.title_ua+'» — MaGelle';
        const picker=info.querySelector('.design-pdp-colors .color-options');if(picker)picker.innerHTML=variantButtons(variantsFor(d),'color-option design-pdp-color');
        document.querySelector('.mobile-photo-colors')?.remove();initDesignPdp();
      }
    }
    document.dispatchEvent(new CustomEvent('magelle:catalog-refresh'));
  }

  window.MaGelleStore={getCart,saveCart,setQty,money,API_BASE,escapeHtml,productForItem,getProducts:()=>activeProducts,trackBeginCheckout,trackOrderRequest,getAnalyticsClientId};
  initDesignCards();
  initDesignPdp();
  updateCartCount();
  renderCart();
  loadProducts();
})();
