/**** QTickets API Ingest v2.0 (Apps Script)
 * Источник: REST API QTickets (Bearer TOKEN), без почты и без папок.
 * Документация (ключевые места):
 *  - База и авторизация: https://qtickets.ru/api/rest/v1/{method}, Authorization: Bearer TOKEN
 *  - Заказы:      GET /orders   (фильтр по payed, по дате, пагинация)
 *  - Мероприятия: GET /events,  GET /events/{id}
 *  - Места/показ: GET /shows/{show_id}/seats (max_quantity, free_quantity)
 *
 * Листы:
 *   QTickets:  date,event_id,city,order_id,tickets_sold,revenue,refunds,currency
 *   Inventory: date,event_id,tickets_total,tickets_left
 ****/

const CFG = {
  SPREADSHEET_ID: 'PASTE_SPREADSHEET_ID_HERE',  // <-- вставь ID BI_Central
  SHEET_SALES: 'QTickets',
  SHEET_INV: 'Inventory',
  SHEET_LOGS: 'Logs',
  TIMEZONE: 'Europe/Moscow',

  // Сколько дней подтягивать при каждом запуске (включая сегодня-1)
  LOOKBACK_DAYS: 7,

  // Адреса для алертов (через запятую). Необязательно; можно задать в Script Properties.
  ALERT_EMAILS_FALLBACK: '',

  // Триггер 00:00 МСК
  DAILY_TRIGGER_HOUR: 0
};

/** ====== ВХОДНАЯ ТОЧКА ====== */
function qticketsSync() {
  const lock = LockService.getScriptLock();
  try {
    lock.tryLock(30000);
    if (!lock.hasLock()) {
      log_('WARN', 'Sync', 'Уже идет выполнение, пропускаю');
      return;
    }
    const tz = CFG.TIMEZONE || Session.getScriptTimeZone();
    const end = new Date();
    const start = new Date(end.getTime() - CFG.LOOKBACK_DAYS * 86400 * 1000);

    const sales = fetchPaidOrders_(start, end);
    const mappedRows = mapOrdersToRows_(sales);
    upsertSales_(mappedRows);

    const invRows = fetchInventorySnapshot_(sales);
    upsertInventory_(invRows);

    log_('INFO', 'Sync', `Готово: orders=${sales.length}, sales_rows=${mappedRows.length}, inv_events=${invRows.length}`);
  } catch (e) {
    const msg = formatError_(e);
    log_('ERROR', 'Sync', 'Сбой', msg);
    alert_(msg);
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

/** ====== API HELPERS ====== */
function getToken_() {
  const p = PropertiesService.getScriptProperties().getProperty('QTICKETS_API_TOKEN');
  if (!p) throw new Error('Не задан QTICKETS_API_TOKEN в Script Properties');
  return p;
}
function getAlertEmails_() {
  return PropertiesService.getScriptProperties().getProperty('ALERT_EMAILS') || CFG.ALERT_EMAILS_FALLBACK || '';
}

const API_BASE = 'https://qtickets.ru/api/rest/v1';

function fetchJson_(path, bodyOrNull, page) {
  const token = getToken_();
  const url = `${API_BASE}/${path}`;
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache'
  };
  const payload = bodyOrNull ? JSON.stringify(bodyOrNull) : null;
  const params = {
    method: 'post',
    headers,
    muteHttpExceptions: true,
    payload
  };
  const res = UrlFetchApp.fetch(url, params);
  const code = res.getResponseCode();
  if (code !== 200) {
    throw new Error(`API ${path} HTTP ${code}: ${res.getContentText()}`);
  }
  const data = JSON.parse(res.getContentText() || '{}');
  return data;
}

/** ====== БИЗНЕС-ЛОГИКА: ЗАКАЗЫ ====== */
function fetchPaidOrders_(startDate, endDate) {
  const out = [];
  let page = 1;
  while (true) {
    const body = {
      where: [
        { column: 'payed', value: 1 },
        { column: 'payed_at', operator: '>=', value: toIso_(startDate) },
        { column: 'payed_at', operator: '<=', value: toIso_(endDate) }
      ],
      orderBy: { id: 'asc' },
      page
    };
    const resp = fetchJson_('orders', body);
    const chunk = (resp && (resp.data || resp.orders || resp.items)) || [];
    if (chunk.length === 0) break;
    out.push.apply(out, chunk);

    const pg = resp.paging || {};
    const per = Number(pg.perPage || chunk.length);
    const cur = Number(pg.currentPage || page);
    const total = Number(pg.total || chunk.length);
    if (!pg || !pg.perPage) {
      break;
    }
    if (cur * per >= total) break;
    page++;
  }
  return out;
}

function mapOrdersToRows_(orders) {
  const cityCache = {};
  const rows = [];
  for (const o of orders) {
    const eventId = o.event_id || (o.data && o.data.event_id);
    const orderId = o.id || (o.data && o.data.id);
    if (!eventId || !orderId) continue;

    const payedAt = o.payed_at || (o.data && o.data.payed_at) || o.created_at;
    const date = toYmd_(payedAt);
    const currency = o.currency_id || (o.data && o.data.currency_id) || 'RUB';
    const price = Number(o.price || (o.data && o.data.price) || 0);

    const baskets = o.baskets || (o.data && o.data.baskets) || [];
    let qty = 0;
    let refunded = 0;
    let showIds = new Set();
    for (const b of baskets) {
      qty += Number(b.quantity || 0);
      refunded += Number(b.refunded_amount || 0);
      if (b.show_id) showIds.add(b.show_id);
    }

    const city = getCityByEventId_(eventId, cityCache);

    rows.push({
      date,
      event_id: String(eventId),
      city,
      order_id: String(orderId),
      tickets_sold: qty,
      revenue: price,
      refunds: refunded,
      currency
    });
  }
  return rows;
}

function getCityByEventId_(eventId, cache) {
  if (cache[eventId] !== undefined) return cache[eventId];
  try {
    const resp = fetchJson_(`events/${eventId}`, null);
    const ev = resp.data || resp.event || resp;
    let city = '';
    if (ev && typeof ev === 'object') {
      city = ev.city_name || ev.city || (ev.city_id ? `city_${ev.city_id}` : '');
    }
    cache[eventId] = city || '';
    return cache[eventId];
  } catch (e) {
    cache[eventId] = '';
    return '';
  }
}

/** ====== ИНВЕНТАРЬ ====== */
function fetchInventorySnapshot_(orders) {
  const events = new Map();
  for (const o of orders) {
    const eventId = String(o.event_id || (o.data && o.data.event_id) || '');
    if (!eventId) continue;
    const baskets = o.baskets || (o.data && o.data.baskets) || [];
    for (const b of baskets) {
      if (!b.show_id) continue;
      if (!events.has(eventId)) events.set(eventId, new Set());
      events.get(eventId).add(b.show_id);
    }
  }

  const today = toYmd_(new Date());
  const out = [];
  for (const [eventId, showSet] of events.entries()) {
    let total = 0;
    let left = 0;
    for (const showId of showSet.values()) {
      try {
        const body = { select: ['max_quantity','free_quantity'], flat: true };
        const resp = fetchJson_(`shows/${showId}/seats`, body);
        const seats = (resp && (resp.data || resp.items)) || resp || {};
        const values = Array.isArray(seats) ? seats : Object.values(seats || {});
        for (const seat of values) {
          total += Number(seat.max_quantity || 0);
          left += Number(seat.free_quantity || 0);
        }
      } catch (e) {
        log_('WARN', 'Inventory', `Ошибка по show_id=${showId}`, formatError_(e));
      }
    }
    out.push({ date: today, event_id, tickets_total: total, tickets_left: left });
  }
  return out;
}

/** ====== ЗАПИСЬ ====== */
function ensureHeader_(sheet, header) {
  const rng = sheet.getRange(1,1,1,header.length);
  const now = rng.getValues()[0].map(v => String(v||'').trim());
  const same = (now.length === header.length) && now.every((v,i)=>v===header[i]);
  if (!same) rng.setValues([header]);
}
function getSheet_(name) {
  const ss = SpreadsheetApp.openById(CFG.SPREADSHEET_ID);
  return ss.getSheetByName(name) || ss.insertSheet(name);
}
function salesHeader_() { return ['date','event_id','city','order_id','tickets_sold','revenue','refunds','currency']; }
function invHeader_() { return ['date','event_id','tickets_total','tickets_left']; }

function upsertSales_(objects) {
  const sh = getSheet_(CFG.SHEET_SALES);
  ensureHeader_(sh, salesHeader_());
  const keyCols = ['date','event_id','order_id'];
  const existing = loadKeySet_(sh, keyCols);
  const rows = [];
  for (const o of objects) {
    const key = keyCols.map(k => String(o[k]||'').trim()).join('||');
    if (existing.has(key)) continue;
    rows.push(salesHeader_().map(h => o[h] ?? ''));
    existing.add(key);
  }
  if (rows.length) {
    sh.getRange(sh.getLastRow()+1, 1, rows.length, rows[0].length).setValues(rows);
  }
}

function upsertInventory_(objects) {
  const sh = getSheet_(CFG.SHEET_INV);
  ensureHeader_(sh, invHeader_());
  const keyCols = ['date','event_id'];
  const existing = loadKeySet_(sh, keyCols);
  const rows = [];
  for (const o of objects) {
    const key = keyCols.map(k => String(o[k]||'').trim()).join('||');
    if (existing.has(key)) continue;
    rows.push(invHeader_().map(h => o[h] ?? ''));
    existing.add(key);
  }
  if (rows.length) {
    sh.getRange(sh.getLastRow()+1, 1, rows.length, rows[0].length).setValues(rows);
  }
}

function loadKeySet_(sheet, keyCols) {
  const set = new Set();
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 2) return set;
  const header = sheet.getRange(1,1,1,lastCol).getValues()[0];
  const data = sheet.getRange(2,1,lastRow-1,lastCol).getValues();
  const idx = keyCols.map(k => header.indexOf(k));
  for (const r of data) {
    const parts = idx.map(i => String((i>=0 && i<r.length) ? r[i] : '').trim());
    set.add(parts.join('||'));
  }
  return set;
}

/** ====== ЛОГИ И АЛЕРТЫ ====== */
function log_(level, source, message, details) {
  try {
    const sh = getSheet_(CFG.SHEET_LOGS);
    const tz = CFG.TIMEZONE || 'Europe/Moscow';
    const now = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd'T'HH:mm:ssXXX");
    sh.appendRow([now, source||'QTickets', level||'INFO', String(message||''), details||'']);
  } catch (_) {}
}
function alert_(text) {
  const to = getAlertEmails_();
  if (!to) return;
  try {
    MailApp.sendEmail({ to, subject: 'QTickets API — ошибка', htmlBody: '<pre style="white-space:pre-wrap">'+safe_(text)+'</pre>' });
  } catch (_) {}
}
function safe_(s){ return String(s||'').replace(/[<>&]/g, c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])); }

/** ====== ДАТЫ ====== */
function toIso_(d){ const z = CFG.TIMEZONE || 'Europe/Moscow'; return Utilities.formatDate(new Date(d), z, "yyyy-MM-dd'T'HH:mm:ssXXX"); }
function toYmd_(d){ const z = CFG.TIMEZONE || 'Europe/Moscow'; return Utilities.formatDate(new Date(d), z, 'yyyy-MM-dd'); }

/** ====== ТРИГГЕР ====== */
function createDailyTrigger() {
  ScriptApp.newTrigger('qticketsSync')
    .timeBased()
    .everyDays(1)
    .atHour(CFG.DAILY_TRIGGER_HOUR)
    .create();
}
