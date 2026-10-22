#!/usr/bin/env node
'use strict';

// Exercise the actual browser functions against every reviewed product page.
// Optional first argument: a saved /api/catalog JSON response for live-data QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const unescape = value => value.replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const clone = value => JSON.parse(JSON.stringify(value));
const attrs = tag => Object.fromEntries([...tag.matchAll(/data-([a-z-]+)="([^"]*)"/g)].map(([, name, value]) => [name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()), unescape(value)]));

function functionsBetween(first, next) {
  const begin = app.indexOf('  function ' + first + '(');
  const end = app.indexOf('  function ' + next + '(', begin);
  assert(begin >= 0 && end > begin, 'Actual app.js runtime functions must exist');
  return app.slice(begin, end);
}

const pages = [];
for (const file of fs.readdirSync(root).filter(file => file.endsWith('.html'))) {
  const raw = fs.readFileSync(path.join(root, file), 'utf8');
  if (/<meta name="robots" content="[^"]*noindex/.test(raw)) continue;
  const tag = raw.match(/<div class="product-info[^>]*design-variant-pdp[^>]*>/)?.[0];
  if (!tag) continue;
  const groups = [...raw.matchAll(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/g)]
    .map(match => JSON.parse(match[1])).filter(data => data['@type'] === 'ProductGroup');
  assert.equal(groups.length, 1, file + ': one reviewed ProductGroup');
  const canonical = raw.match(/<link rel="canonical" href="([^"]+)">/)?.[1];
  assert(canonical, file + ': canonical required');
  pages.push({ file, dataset: attrs(tag), group: groups[0], canonical });
}
assert.equal(pages.length, 16, 'Every public design must be covered');
assert.equal(pages.reduce((sum, page) => sum + page.group.hasVariant.length, 0), 64, 'All 64 admitted SKU fixtures must be covered');

const statusFromSchema = { InStock: 'stock', PreOrder: 'preorder', OutOfStock: 'hidden' };
const fixture = {
  enabled: true,
  products: pages.flatMap(page => page.group.hasVariant.map(product => ({
    design_id: page.group.productGroupID, sku: product.sku, color_code: product.sku.split('-').at(-1),
    title_ua: product.name.replace(/^MaGelle /, ''), description_ua: product.description,
    color: product.color, photo_urls: /design-(?:OF-KAR|SF-BUR)-/.test(page.group.productGroupID) ? [] : product.image, price_uah: product.offers.price,
    status: statusFromSchema[product.offers.availability.split('/').at(-1)],
  }))),
};
const catalog = process.argv[2] ? JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), 'utf8')) : fixture;
assert.equal(catalog.enabled, true, 'Catalog must be enabled');

function harness(page, products = catalog.products, requested = page.dataset.defaultColor) {
  const buttons = page.group.hasVariant.map(product => ({
    dataset: { variantColor: product.sku.split('-').at(-1) }, classList: { toggle() {} },
  }));
  const info = {
    dataset: clone(page.dataset),
    querySelectorAll(selector) { return selector === '.design-pdp-color' ? buttons : []; },
    querySelector(selector) { return selector === '.product-description' ? { textContent: page.group.description } : null; },
  };
  const canonical = { href: page.canonical };
  const schema = { id: 'merchant-static-schema', type: 'application/ld+json', textContent: JSON.stringify(page.group) };
  const duplicate = { textContent: JSON.stringify({ '@type': 'Product', sku: 'STALE' }), removed: false, remove() { this.removed = true; } };
  const organization = { textContent: JSON.stringify({ '@type': 'Organization', name: 'MaGelle' }), removed: false, remove() { this.removed = true; } };
  const document = {
    getElementById(id) { return id === 'merchant-static-schema' ? schema : null; },
    querySelector(selector) { return selector === 'link[rel="canonical"]' ? canonical : selector === '.design-variant-pdp' ? info : null; },
    querySelectorAll(selector) { return selector === 'script[type="application/ld+json"]' ? [schema, duplicate, organization] : []; },
  };
  const colors = Object.fromEntries(['GRA', 'MLK', 'WHT', 'SND', 'CHO'].map(code => [code, { label: code, swatch: code.toLowerCase() }]));
  const context = vm.createContext({
    URL, document, location: { origin: 'https://magelle.com.ua', pathname: new URL(page.canonical).pathname, href: page.canonical + '?color=' + requested },
    catalogModel: { enabled: true, products: clone(products) }, COLORS: colors, activeProducts: new Map(),
    familyCode: () => info.dataset.familyCode || page.group.productGroupID.split('-')[1],
    designSku: (family, design, size, code) => ['MG', family, design, size, code].join('-'),
    canonicalSku: () => { throw new Error('Managed SKU must not fall through to a legacy SKU'); },
    applyPdpProduct() {}, trackViewItem() {},
  });
  vm.runInContext(functionsBetween('pdpColor', 'pdpImageSizes') + functionsBetween('selectDesignPdp', 'initDesignPdp'), context);
  return { context, info, canonical, schema, duplicate, organization, run(code = requested) {
    context.selectDesignPdp(code, false, false);
    return JSON.parse(schema.textContent);
  } };
}

let testedSelections = 0;
for (const page of pages) {
  const admitted = new Set(page.group.hasVariant.map(product => product.sku));
  for (const selected of page.group.hasVariant) {
    const code = selected.sku.split('-').at(-1);
    const test = harness(page, catalog.products, code);
    const result = test.run();
    assert.equal(test.info.dataset.selectedSku, selected.sku, page.file + ': selected SKU');
    assert.equal(test.canonical.href, page.canonical, selected.sku + ': canonical must stay clean');
    assert.equal(result['@type'], 'ProductGroup');
    assert.equal(result.productGroupID, page.group.productGroupID);
    assert.equal(result['@id'], page.canonical + '#product-group');
    assert.equal(result.url, page.canonical);
    assert.deepEqual(result.variesBy, ['https://schema.org/color']);
    assert.deepEqual(new Set(result.hasVariant.map(product => product.sku)), admitted, selected.sku + ': all real variants remain represented');
    for (const product of result.hasVariant) {
      const live = catalog.products.find(item => item.sku === product.sku);
      assert(live, product.sku + ': no fabricated SKU');
      assert.equal(product.isVariantOf['@id'], result['@id']);
      assert.equal(product.offers.price, live.price_uah);
      assert.equal(product.offers.priceCurrency, 'UAH');
      assert.equal(product.offers.url, product.url);
      assert.equal(product.offers.availability, 'https://schema.org/' + { stock: 'InStock', preorder: 'PreOrder', hidden: 'OutOfStock' }[live.status]);
      assert(product.image.length > 0 && product.image.every(url => /^https:\/\/(?:api\.)?magelle\.com\.ua\/(?:media|uploads)\//.test(url)), product.sku + ': first-party images');
      const expected = page.canonical + (product.sku.endsWith('-' + page.dataset.defaultColor) ? '' : '?color=' + live.color_code);
      assert.equal(product.url, expected, product.sku + ': base URL or exact color landing');
    }
    assert(test.duplicate.removed, 'Stale duplicate Product must be removed');
    assert.equal(test.organization.removed, false, 'Non-product schema must survive');
    const again = test.run(page.dataset.defaultColor);
    assert.deepEqual(new Set(again.hasVariant.map(item => item.sku)), admitted, 'Switching color must preserve all group variants');
    testedSelections++;
  }
  for (const requested of ['NOT_A_COLOR', ...['GRA', 'MLK', 'WHT', 'SND', 'CHO'].filter(code => !page.group.hasVariant.some(product => product.sku.endsWith('-' + code)))]) {
    const test = harness(page, catalog.products, requested);
    test.run();
    assert.equal(test.info.dataset.selectedSku, page.group.hasVariant.find(product => product.sku.endsWith('-' + page.dataset.defaultColor)).sku, 'Unsupported color must resolve to the real base SKU');
  }
}

// Commerce changes must hydrate independently of the reviewed static snapshot.
const page = pages[0];
const first = page.group.hasVariant[0].sku;
for (const [status, expected] of Object.entries({ stock: 'InStock', preorder: 'PreOrder', hidden: 'OutOfStock' })) {
  const products = clone(catalog.products);
  Object.assign(products.find(product => product.sku === first), { status, price_uah: 1234 });
  const test = harness(page, products);
  const product = test.run().hasVariant.find(product => product.sku === first);
  assert.equal(product.offers.availability, 'https://schema.org/' + expected);
  assert.equal(product.offers.price, 1234);
}
for (const change of [{ price_uah: 0 }, { status: 'draft' }]) {
  const products = clone(catalog.products);
  Object.assign(products.find(product => product.sku === first), change);
  assert(!harness(page, products).run().hasVariant.some(product => product.sku === first), 'Invalid offer must not be emitted');
}
console.log(`Product SEO runtime PASS: ${pages.length} groups, ${testedSelections} exact SKU selections, canonical stability, unsupported colors, duplicate cleanup, and stock/preorder/hidden offers.`);
