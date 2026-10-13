# MAG-022 — MaGelle Google Merchant Center Readiness
Аудит 04 · 13.10.2026. Источник актуальности: публичный magelle.com.ua, API Admin 2.0 version 11, GitHub CI и живой browser QA.

## Таблица аудита

| Требование | До 13.10 | Сделано / проверено | Итог |
|---|---|---|---|
| Доставка/оплата | Нет утверждённых публичных сроков и способа оплаты, адрес выдачи оговаривался абстрактно | /delivery.html: Нова пошта, доставка за тарифом перевозчика за счёт покупателя, подготовка 0–1 рабочий день для наличия, транзит ориентировочно 1–5 дней, отправка после подтверждения банковской оплаты; самовывоз по согласованию с адресом | Live PASS |
| Повернення | Возвратный адрес, перевозка и сроки выплат не конкретизированы | /returns.html: 14-дневное право где применимо, возвраты по Днепру, распределение расходов, 3 банковских дня после приёма/проверки (в пределах законодательства), законные исключения без автоматического отказа из-за сухоцветов | Live PASS |
| Контакты и продавец | Базовые страницы имелись | /contacts.html, /seller.html: телефон, email, ФОП, РНОКПП и адрес; футер со ссылками | Live PASS |
| Privacy и checkout | Согласие имелось; сроки и способ оплаты не разъяснены на форме | /privacy.html; /checkout.html: обязательный способ получения и адрес, пояснение «заявка — не онлайн-оплата», банковская оплата после подтверждения, ссылки на политики | Browser PASS |
| Checkout stock race | На stock SKU возникало устаревшее сообщение «позиція недоступна» после начальной загрузки | checkout ждёт API, повторно валидирует после загрузки, убирает ложное предупреждение; app.js отправляет cart-change по готовности | Live regression PASS (Олива/Шоколад) |
| Управляемый каталог | 16 дизайнов ожидаются как 64 variants | GET /api/catalog version 11: 16 designs, 58 управляемых variants, дополнительно 14 legacy products; 6 SF variants отсутствуют; 17 из 58 managed имеют photo_urls | BLOCKER для полной матрицы |
| Стартовый фид | Первичный 3-SKU RSS существовал | /merchant.xml: 3 approved SKU, цены/наличие из /api/products; изображения только first-party /media/ или /uploads/, не Drive; автообновление hourly через GitHub Action | Feed CI PASS; 3-SKU pilot |
| Schema + Offer | На трёх pilot PDP внедрены статические Product/Offer | scripts/verify_merchant_feed.py проверяет SKU, canonical, price, UAH, availability, image_link MIME + magic bytes на GET, URL, brand и condition | Merchant sync SUCCESS |
| Индексация | Индексируемые landing и политики | /robots.txt открывает обход; /sitemap.xml включает 13 индексируемых URL, в том числе 3 pilot PDP; checkout noindex | PASS по коду/публикации |
| Buyer flow | Cart и checkout существовали | Живой browser: Олива (MG-OF-OLI-DEL-CHO), выбранный Шоколад, фото, 2600 UAH, stock, add cart, cart total, checkout, поля + согласие, политика. После исправления 6/6 regression PASS | PASS до отправки заявки; live submit не выполнялся |
| Mobile QA / полный ассортимент | Есть выполненные отдельные mobile QA, не все 64 SKU подтверждены | Для pilot checkout регрессия проверена в браузере; общая проверка всех 64 вариаций, mobile 390/430 и пост-submit receipt до финальной приёмки не завершена | OPEN |

## Обязательные публичные страницы
- https://magelle.com.ua/delivery.html
- https://magelle.com.ua/returns.html
- https://magelle.com.ua/contacts.html
- https://magelle.com.ua/seller.html
- https://magelle.com.ua/privacy.html
- https://magelle.com.ua/catalog.html
- https://magelle.com.ua/checkout.html
- https://magelle.com.ua/robots.txt
- https://magelle.com.ua/sitemap.xml
- **Фид**: https://magelle.com.ua/merchant.xml

## Pilot Merchant SKU
| SKU | Название | Price UAH | PDP |
|---|---|---:|---|
| MG-OF-MED-VYR-GRA | Organic Flare «Мед» — Виразний, Графіт | 4200 | /organic-flare-vyraznyi-pisochnyi.html (legacy filename, фактический default GRA) |
| MG-OF-PER-VYR-MLK | Organic Flare «Перлина» — Виразний, Молочний | 4200 | /organic-flare-vyraznyi-molochnyi.html |
| MG-OF-OLI-DEL-CHO | Organic Flare «Олива» — Делікатний, Шоколад | 2600 | /organic-flare-delikatnyi-shokolad.html |

Данные выше — snapshot 13.10, не ручные ограничения: скрипт заново читает API при синхронизации. Не добавлять SKU с неподтверждёнными exact media.

## Открытые действия и ответственность
1. **04 + владелец Admin 2.0 + 00**: выяснить и восстановить 6 отсутствующих управляемых вариантов Sculptural Fold, без выдуманных цен и наличия.
2. **07 + 00**: утвердить/загрузить exact фото для недостающих SKU, не использовать model-reference или чужие букеты в GMC.
3. **04 + 00**: QA desktop/mobile переключения конкретных цветов/цен/фото для расширения feed, живой checkout confirmation через контролируемый тест без ложных коммерческих заказов.
4. **05**: подключение/настройка Google Merchant Center (включая shipping/return settings и проверку после fetch). **Не запускать Ads до отдельного решения.**

## Факт-чек CI / изменения
- Merchant feed: scripts/build_merchant_feed.py, scripts/verify_merchant_feed.py; workflow .github/workflows/merchant-feed.yml hourly.
- Static approved Product/Offer на трёх pilot PDP, проверка единства XML/HTML в CI.
- POLICY: delivery b12bf037, returns 4c7800be, checkout notice 082d94c6.
- Checkout stock race: 3309b35c, app.js update 7e1ae75a, checkout cache 8a5ad07e.
- Live browser Олива/Шоколад: первая проверка выявила transient false-warning; после правки регрессия 6/6 PASS, submit enabled, message absent, total 2600.
- **Ни одного test-order в production не создано; подтверждение post-submit не проверено.**
- Google Merchant approval в рамках 04 не заявляется.

**Вердикт 04:** политики/SEO/3-SKU feed/live pre-submit buyer-flow готовы к предварительной проверке 05; весь MAG-022 и 64-SKU catalogue audit пока NOT DONE. Финальный 04→05 HANDOFF делать после закрытия оставшихся технических блокеров.
