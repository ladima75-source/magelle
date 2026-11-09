// Contract tests for protected Admin 2.0 messenger shortcuts (no external sends).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const s = fs.readFileSync('server/static/admin2.js', 'utf8');
function between(start, end) {
  const i=s.indexOf(start), j=s.indexOf(end,i+start.length);
  assert(i>=0 && j>i, 'Cannot locate '+start);
  return s.slice(i,j);
}
const normalize = between('function ukrainianPhone(v)', 'function paymentRequestText(o)');
const contact = between('function orderContactActions(o)', 'async function loadOrders()');
const sandbox={
  paymentRequestText:()=> 'Підтверджуємо замовлення №206: 1 700 грн',
  customerOrderNumber:()=>206,
  esc:(x)=>String(x).replaceAll('&','&amp;').replaceAll('"','&quot;'),
  encodeURIComponent,
  String,Number,
};
vm.createContext(sandbox);
vm.runInContext(normalize+'\n'+contact,sandbox);
assert.equal(sandbox.ukrainianPhone('0733335449'),'380733335449');
assert.equal(sandbox.ukrainianPhone('+380 73 333 54 49'),'380733335449');
assert.equal(sandbox.ukrainianPhone('bad'),'');
const order={id:6,phone:'0733335449',payment_status:'unpaid',status:'confirmed',items:[]};
const html=sandbox.orderContactActions(order);
assert(html.includes('https://wa.me/380733335449?text='));
assert(html.includes('https://t.me/+380733335449?text='));
assert(html.includes('viber://chat?number=%2B380733335449'));
assert(html.includes('Скопіювати повідомлення'));
assert(html.includes('>Telegram<') && html.includes('>Viber<'));
assert(html.includes('>SMS<'));
assert(!html.includes('sendMessage') && !html.includes('Автоматично надіслано'));
assert(!sandbox.orderContactActions({...order,payment_status:'paid'}).includes('https://t.me/'));
assert(!sandbox.orderContactActions({...order,status:'cancelled'}).includes('viber://'));
console.log('MaGelle order messenger links: PASS');
