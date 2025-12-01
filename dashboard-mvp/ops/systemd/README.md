# Systemd РўР°Р№РјРµСЂС‹ РРЅС‚РµРіСЂР°С†РёР№

## РќР°Р·РЅР°С‡РµРЅРёРµ

РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёР№ Р·Р°РїСѓСЃРє Р·Р°РіСЂСѓР·С‡РёРєРѕРІ РґР°РЅРЅС‹С… РїРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ СЃ РїРѕРјРѕС‰СЊСЋ systemd С‚Р°Р№РјРµСЂРѕРІ.

## РЎС‚СЂСѓРєС‚СѓСЂР°

- `*.service` - С„Р°Р№Р»С‹ СЃРµСЂРІРёСЃРѕРІ systemd
- `*.timer` - С„Р°Р№Р»С‹ С‚Р°Р№РјРµСЂРѕРІ systemd
- `manage_timers.sh` - СЃРєСЂРёРїС‚ РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ С‚Р°Р№РјРµСЂР°РјРё
- `README.md` - РґРѕРєСѓРјРµРЅС‚Р°С†РёСЏ

## РЎРїРёСЃРѕРє С‚Р°Р№РјРµСЂРѕРІ

| РўР°Р№РјРµСЂ | Р Р°СЃРїРёСЃР°РЅРёРµ | РќР°Р·РЅР°С‡РµРЅРёРµ | РЎС‚Р°С‚СѓСЃ |
|--------|------------|------------|--------|
| qtickets | every 30 minutes | QTickets Sheets fallback | active |
| qtickets_api | every 30 minutes | Primary ingestion: QTickets REST API (Docker) | active |
| vk_ads | Р•Р¶РµРґРЅРµРІРЅРѕ РІ 00:00 MSK | Р—Р°РіСЂСѓР·РєР° СЃС‚Р°С‚РёСЃС‚РёРєРё VK Ads | Р’РєР»СЋС‡РµРЅ |
| direct | Р•Р¶РµРґРЅРµРІРЅРѕ РІ 00:10 MSK | Р—Р°РіСЂСѓР·РєР° СЃС‚Р°С‚РёСЃС‚РёРєРё РЇРЅРґРµРєСЃ.Р”РёСЂРµРєС‚ | Р’РєР»СЋС‡РµРЅ |
| gmail_ingest | РљР°Р¶РґС‹Рµ 4 С‡Р°СЃР° | Р РµР·РµСЂРІРЅС‹Р№ РєР°РЅР°Р» Gmail | РћС‚РєР»СЋС‡РµРЅ |
| alerts | РљР°Р¶РґС‹Рµ 2 С‡Р°СЃР° | РџСЂРѕРІРµСЂРєР° РѕС€РёР±РѕРє Рё Р°Р»РµСЂС‚РёРЅРі | Р’РєР»СЋС‡РµРЅ |

## РЈСЃС‚Р°РЅРѕРІРєР° Рё РЅР°СЃС‚СЂРѕР№РєР°

### 1. РљРѕРїРёСЂРѕРІР°РЅРёРµ С„Р°Р№Р»РѕРІ С‚Р°Р№РјРµСЂРѕРІ

```bash
# РЎРґРµР»Р°С‚СЊ СЃРєСЂРёРїС‚ СѓРїСЂР°РІР»РµРЅРёСЏ РёСЃРїРѕР»РЅСЏРµРјС‹Рј
chmod +x manage_timers.sh

# РЈСЃС‚Р°РЅРѕРІРёС‚СЊ РІСЃРµ С‚Р°Р№РјРµСЂС‹ РІ systemd (С‚СЂРµР±СѓРµС‚ РїСЂР°РІ root)
sudo ./manage_timers.sh install
```

### 2. Р’РєР»СЋС‡РµРЅРёРµ С‚Р°Р№РјРµСЂРѕРІ

```bash
# Р’РєР»СЋС‡РёС‚СЊ РІСЃРµ РѕСЃРЅРѕРІРЅС‹Рµ С‚Р°Р№РјРµСЂС‹
sudo ./manage_timers.sh enable qtickets
sudo ./manage_timers.sh enable qtickets_api
sudo ./manage_timers.sh enable vk_ads
sudo ./manage_timers.sh enable direct
sudo ./manage_timers.sh enable alerts

# Р”Р»СЏ QTickets API С‚СЂРµР±СѓРµС‚СЃСЏ СЃР±РѕСЂРєР° Docker РѕР±СЂР°Р·Р°:
cd /opt/zakaz_dashboard/dashboard-mvp
docker build -t qtickets_api:latest integrations/qtickets_api
```

# Gmail С‚Р°Р№РјРµСЂ РѕС‚РєР»СЋС‡РµРЅ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ (СЂРµР·РµСЂРІРЅС‹Р№ РєР°РЅР°Р»)
# sudo ./manage_timers.sh enable gmail

# Р’РєР»СЋС‡РёС‚СЊ healthcheck СЃРµСЂРІРµСЂ
sudo systemctl enable healthcheck.service
sudo systemctl start healthcheck.service
```

### 3. РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР°

```bash
# РџРѕРєР°Р·Р°С‚СЊ СЃС‚Р°С‚СѓСЃ РІСЃРµС… С‚Р°Р№РјРµСЂРѕРІ
./manage_timers.sh status

# РџРѕРєР°Р·Р°С‚СЊ СЃС‚Р°С‚СѓСЃ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ С‚Р°Р№РјРµСЂР°
./manage_timers.sh status qtickets
./manage_timers.sh status qtickets_api
```

## РЈРїСЂР°РІР»РµРЅРёРµ С‚Р°Р№РјРµСЂР°РјРё

### РћСЃРЅРѕРІРЅС‹Рµ РєРѕРјР°РЅРґС‹

```bash
# РџРѕРєР°Р·Р°С‚СЊ СЃРїСЂР°РІРєСѓ
./manage_timers.sh help

# РџРѕРєР°Р·Р°С‚СЊ СЂР°СЃРїРёСЃР°РЅРёРµ РІСЃРµС… С‚Р°Р№РјРµСЂРѕРІ
./manage_timers.sh schedule

# РџРѕРєР°Р·Р°С‚СЊ Р»РѕРіРё С‚Р°Р№РјРµСЂР°
./manage_timers.sh logs qtickets
./manage_timers.sh logs qtickets_api

# Р’РєР»СЋС‡РёС‚СЊ/РѕС‚РєР»СЋС‡РёС‚СЊ С‚Р°Р№РјРµСЂ
sudo ./manage_timers.sh enable qtickets
sudo ./manage_timers.sh enable qtickets_api
sudo ./manage_timers.sh disable qtickets
sudo ./manage_timers.sh disable qtickets_api

# Р—Р°РїСѓСЃС‚РёС‚СЊ/РѕСЃС‚Р°РЅРѕРІРёС‚СЊ/РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ С‚Р°Р№РјРµСЂ
sudo ./manage_timers.sh start qtickets
sudo ./manage_timers.sh start qtickets_api
sudo ./manage_timers.sh stop qtickets
sudo ./manage_timers.sh stop qtickets_api
sudo ./manage_timers.sh restart qtickets
sudo ./manage_timers.sh restart qtickets_api
```

### РџСЂСЏРјРѕРµ СѓРїСЂР°РІР»РµРЅРёРµ С‡РµСЂРµР· systemctl

```bash
# РЎС‚Р°С‚СѓСЃ С‚Р°Р№РјРµСЂР°
systemctl status qtickets.timer

# Р’РєР»СЋС‡РµРЅРёРµ С‚Р°Р№РјРµСЂР°
sudo systemctl enable qtickets.timer
sudo systemctl start qtickets.timer

# РћС‚РєР»СЋС‡РµРЅРёРµ С‚Р°Р№РјРµСЂР°
sudo systemctl stop qtickets.timer
sudo systemctl disable qtickets.timer

# РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ
journalctl -u qtickets.service -f
```

## Р Р°СЃРїРёСЃР°РЅРёРµ С‚Р°Р№РјРµСЂРѕРІ

### QTickets Sheets (fallback)
- **schedule**: `*:0/30` (every 30 minutes)
- **Р—Р°РґРµСЂР¶РєР°**: РґРѕ 60 СЃРµРєСѓРЅРґ (СЃР»СѓС‡Р°Р№РЅР°СЏ)
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: Р РµРіСѓР»СЏСЂРЅР°СЏ Р·Р°РіСЂСѓР·РєР° РґР°РЅРЅС‹С… Рѕ РїСЂРѕРґР°Р¶Р°С… Рё РјРµСЂРѕРїСЂРёСЏС‚РёСЏС…

### QTickets API (Docker)
- **schedule**: every 30 minutes (*:0/30)
- **timeout**: 600 seconds (10 РјРёРЅСѓС‚)
- **description**: Primary ingestion via Docker container `qtickets_api:latest`
- **prerequisites**: 
  - РЎРѕР±СЂР°С‚СЊ Docker РѕР±СЂР°Р·: `docker build -t qtickets_api:latest integrations/qtickets_api`
  - РќР°СЃС‚СЂРѕРёС‚СЊ `/opt/zakaz_dashboard/secrets/.env.qtickets_api` СЃ РїРµСЂРµРјРµРЅРЅС‹РјРё:
    - `QTICKETS_BASE_URL` (РёР»Рё `QTICKETS_API_BASE_URL` РґР»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё)
    - `QTICKETS_TOKEN` (РёР»Рё `QTICKETS_API_TOKEN` РґР»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё)
    - `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`
- **status**: Р’РєР»СЋС‡РµРЅ
- **execution**: docker run --rm --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api qtickets_api:latest (30-day bootstrap on first run, then QTICKETS_SINCE_HOURS for 30 min cadence)

### VK Ads
- **Р Р°СЃРїРёСЃР°РЅРёРµ**: `*-*-* 00:00:00` (РµР¶РµРґРЅРµРІРЅРѕ РІ РїРѕР»РЅРѕС‡СЊ)
- **Р—Р°РґРµСЂР¶РєР°**: РґРѕ 5 РјРёРЅСѓС‚ (СЃР»СѓС‡Р°Р№РЅР°СЏ)
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: Р—Р°РіСЂСѓР·РєР° СЃС‚Р°С‚РёСЃС‚РёРєРё Р·Р° РїСЂРµРґС‹РґСѓС‰РёР№ РґРµРЅСЊ

### РЇРЅРґРµРєСЃ.Р”РёСЂРµРєС‚
- **Р Р°СЃРїРёСЃР°РЅРёРµ**: `*-*-* 00:10:00` (РµР¶РµРґРЅРµРІРЅРѕ РІ 00:10)
- **Р—Р°РґРµСЂР¶РєР°**: РґРѕ 5 РјРёРЅСѓС‚ (СЃР»СѓС‡Р°Р№РЅР°СЏ)
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: Р—Р°РіСЂСѓР·РєР° СЃС‚Р°С‚РёСЃС‚РёРєРё Р·Р° РїСЂРµРґС‹РґСѓС‰РёР№ РґРµРЅСЊ

### Gmail (СЂРµР·РµСЂРІРЅС‹Р№ РєР°РЅР°Р»)
- **Р Р°СЃРїРёСЃР°РЅРёРµ**: `*-*-* 0,4,8,12,16,20:00:00` (РєР°Р¶РґС‹Рµ 4 С‡Р°СЃР°)
- **Р—Р°РґРµСЂР¶РєР°**: РґРѕ 5 РјРёРЅСѓС‚ (СЃР»СѓС‡Р°Р№РЅР°СЏ)
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: Р РµР·РµСЂРІРЅС‹Р№ РєР°РЅР°Р» РїСЂРё РЅРµРґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё QTickets API
- **РЎС‚Р°С‚СѓСЃ**: РћС‚РєР»СЋС‡РµРЅ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ

### Alerts
- **Р Р°СЃРїРёСЃР°РЅРёРµ**: `*-*-* */2:00:00` (РєР°Р¶РґС‹Рµ 2 С‡Р°СЃР°)
- **Р—Р°РґРµСЂР¶РєР°**: РґРѕ 5 РјРёРЅСѓС‚ (СЃР»СѓС‡Р°Р№РЅР°СЏ)
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: РџСЂРѕРІРµСЂРєР° РѕС€РёР±РѕРє Рё РѕС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёР№
- **РЎС‚Р°С‚СѓСЃ**: Р’РєР»СЋС‡РµРЅ

### Healthcheck
- **РўРёРї**: РЎРµСЂРІРёСЃ (РЅРµРїСЂРµСЂС‹РІРЅР°СЏ СЂР°Р±РѕС‚Р°)
- **РџРѕСЂС‚**: 8080
- **РќР°Р·РЅР°С‡РµРЅРёРµ**: HTTP СЌРЅРґРїРѕРёРЅС‚С‹ РґР»СЏ РјРѕРЅРёС‚РѕСЂРёРЅРіР°
- **РЎС‚Р°С‚СѓСЃ**: Р’РєР»СЋС‡РµРЅ

## Р›РѕРіРёСЂРѕРІР°РЅРёРµ

### Р–СѓСЂРЅР°Р»С‹ systemd

Р’СЃРµ Р»РѕРіРё РїРёС€СѓС‚СЃСЏ РІ systemd journal:

```bash
# РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ СЃРµСЂРІРёСЃР°
journalctl -u qtickets.service -n 100

# РћС‚СЃР»РµР¶РёРІР°РЅРёРµ Р»РѕРіРѕРІ РІ СЂРµР°Р»СЊРЅРѕРј РІСЂРµРјРµРЅРё
journalctl -u qtickets.service -f

# РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ РІСЃРµС… С‚Р°Р№РјРµСЂРѕРІ
journalctl -u "*timer" --since "1 hour ago"
```

### Р¤Р°Р№Р»РѕРІС‹Рµ Р»РѕРіРё

Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ Р»РѕРіРё РїРёС€СѓС‚СЃСЏ РІ С„Р°Р№Р»С‹ (РµСЃР»Рё РЅР°СЃС‚СЂРѕРµРЅРѕ РІ РїРµСЂРµРјРµРЅРЅС‹С… РѕРєСЂСѓР¶РµРЅРёСЏ):

- `logs/qtickets.log`
- `logs/vk_ads.log`
- `logs/direct.log`
- `logs/gmail.log`

## РњРѕРЅРёС‚РѕСЂРёРЅРі

### РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР°

```bash
# РџСЂРѕРІРµСЂРёС‚СЊ Р°РєС‚РёРІРЅС‹Рµ С‚Р°Р№РјРµСЂС‹
systemctl list-timers

# РџСЂРѕРІРµСЂРёС‚СЊ СЃС‚Р°С‚СѓСЃ РІСЃРµС… СЃРµСЂРІРёСЃРѕРІ
systemctl status qtickets.service vk_ads.service direct.service
```

### РњРµС‚Р°РґР°РЅРЅС‹Рµ РІ ClickHouse

РРЅС„РѕСЂРјР°С†РёСЏ Рѕ Р·Р°РїСѓСЃРєР°С… Р·Р°РїРёСЃС‹РІР°РµС‚СЃСЏ РІ С‚Р°Р±Р»РёС†Сѓ `zakaz.meta_job_runs`:

```sql
-- РџРѕСЃР»РµРґРЅРёРµ Р·Р°РїСѓСЃРєРё
SELECT * FROM zakaz.meta_job_runs
ORDER BY started_at DESC
LIMIT 10;

-- РЎС‚Р°С‚РёСЃС‚РёРєР° РїРѕ Р·Р°РґР°С‡Р°Рј
SELECT
    job,
    status,
    count() as runs,
    max(started_at) as last_run
FROM zakaz.meta_job_runs
GROUP BY job, status
ORDER BY job, status;
```

### РђР»РµСЂС‚С‹

РРЅС„РѕСЂРјР°С†РёСЏ РѕР± Р°Р»РµСЂС‚Р°С… СЃРѕС…СЂР°РЅСЏРµС‚СЃСЏ РІ С‚Р°Р±Р»РёС†Сѓ `zakaz.alerts`:

```sql
-- РџРѕСЃР»РµРґРЅРёРµ Р°Р»РµСЂС‚С‹
SELECT * FROM zakaz.alerts
ORDER BY created_at DESC
LIMIT 10;

-- РЎС‚Р°С‚РёСЃС‚РёРєР° РїРѕ Р°Р»РµСЂС‚Р°Рј
SELECT
    alert_type,
    count() as alerts_count,
    max(created_at) as last_alert
FROM zakaz.alerts
WHERE created_at >= today() - 7
GROUP BY alert_type
ORDER BY alerts_count DESC;
```

### Healthcheck СЌРЅРґРїРѕРёРЅС‚С‹

HTTP СЃРµСЂРІРµСЂ РїСЂРµРґРѕСЃС‚Р°РІР»СЏРµС‚ СЃР»РµРґСѓСЋС‰РёРµ СЌРЅРґРїРѕРёРЅС‚С‹:
- `GET /healthz` - Р±Р°Р·РѕРІР°СЏ РїСЂРѕРІРµСЂРєР° Р·РґРѕСЂРѕРІСЊСЏ
- `GET /healthz/detailed` - РґРµС‚Р°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° СЃ РјРµС‚СЂРёРєР°РјРё
- `GET /healthz/freshness` - РїСЂРѕРІРµСЂРєР° СЃРІРµР¶РµСЃС‚Рё РґР°РЅРЅС‹С…

```bash
# РџСЂРѕРІРµСЂРєР° Р·РґРѕСЂРѕРІСЊСЏ
curl http://localhost:8080/healthz

# Р”РµС‚Р°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР°
curl http://localhost:8080/healthz/detailed

# РџСЂРѕРІРµСЂРєР° СЃРІРµР¶РµСЃС‚Рё РґР°РЅРЅС‹С…
curl http://localhost:8080/healthz/freshness
```

```sql
-- РџРѕСЃР»РµРґРЅРёРµ Р·Р°РїСѓСЃРєРё
SELECT * FROM zakaz.meta_job_runs 
ORDER BY started_at DESC 
LIMIT 10;

-- РЎС‚Р°С‚РёСЃС‚РёРєР° РїРѕ Р·Р°РґР°С‡Р°Рј
SELECT 
    job,
    status,
    count() as runs,
    max(started_at) as last_run
FROM zakaz.meta_job_runs
GROUP BY job, status
ORDER BY job, status;
```

## РћР±СЂР°Р±РѕС‚РєР° РѕС€РёР±РѕРє

### РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёР№ РїРµСЂРµР·Р°РїСѓСЃРє

Р’СЃРµ СЃРµСЂРІРёСЃС‹ РЅР°СЃС‚СЂРѕРµРЅС‹ РЅР° Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёР№ РїРµСЂРµР·Р°РїСѓСЃРє РїСЂРё РѕС€РёР±РєР°С…:
- `Restart=on-failure`
- `RestartSec=30` (Р·Р°РґРµСЂР¶РєР° 30 СЃРµРєСѓРЅРґ)

### РЈРІРµРґРѕРјР»РµРЅРёСЏ РѕР± РѕС€РёР±РєР°С…

РџСЂРё РѕС€РёР±РєР°С… Р·Р°РїСѓСЃРєР°:
1. Р—Р°РїРёСЃС‹РІР°РµС‚СЃСЏ РІ `zakaz.meta_job_runs` СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј 'error'
2. Р›РѕРіРёСЂСѓРµС‚СЃСЏ РІ systemd journal
3. РњРѕР¶РЅРѕ РЅР°СЃС‚СЂРѕРёС‚СЊ СѓРІРµРґРѕРјР»РµРЅРёСЏ С‡РµСЂРµР· `ops/alerts/notify.py`

### РўР°Р№РјР°СѓС‚С‹

РќР°СЃС‚СЂРѕРµРЅС‹ С‚Р°Р№РјР°СѓС‚С‹ РґР»СЏ РїСЂРµРґРѕС‚РІСЂР°С‰РµРЅРёСЏ Р·Р°РІРёСЃР°РЅРёСЏ:
- QTickets Sheets: 300 СЃРµРєСѓРЅРґ (5 РјРёРЅСѓС‚)
- QTickets API (Docker): 600 СЃРµРєСѓРЅРґ (10 РјРёРЅСѓС‚)
- VK Ads: 600 СЃРµРєСѓРЅРґ (10 РјРёРЅСѓС‚)
- Direct: 600 СЃРµРєСѓРЅРґ (10 РјРёРЅСѓС‚)
- Gmail: 300 СЃРµРєСѓРЅРґ (5 РјРёРЅСѓС‚)

## РћР±СЃР»СѓР¶РёРІР°РЅРёРµ

### Р СѓС‡РЅРѕР№ Р·Р°РїСѓСЃРє

```bash
# Р—Р°РїСѓСЃС‚РёС‚СЊ СЃРµСЂРІРёСЃ РІСЂСѓС‡РЅСѓСЋ
sudo systemctl start qtickets.service
sudo systemctl start qtickets_api.service

# Р—Р°РїСѓСЃС‚РёС‚СЊ СЃ РїР°СЂР°РјРµС‚СЂР°РјРё (РґР»СЏ QTickets API РЅСѓР¶РЅРѕ РёР·РјРµРЅРёС‚СЊ .env С„Р°Р№Р»)
sudo systemctl start qtickets_api.service
```

### РћС‚РєР»СЋС‡РµРЅРёРµ РЅР° РІСЂРµРјСЏ РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ

```bash
# РћС‚РєР»СЋС‡РёС‚СЊ РІСЃРµ С‚Р°Р№РјРµСЂС‹
sudo ./manage_timers.sh disable qtickets
sudo ./manage_timers.sh disable qtickets_api
sudo ./manage_timers.sh disable vk_ads
sudo ./manage_timers.sh disable direct

# РР»Рё РѕСЃС‚Р°РЅРѕРІРёС‚СЊ Р±РµР· РѕС‚РєР»СЋС‡РµРЅРёСЏ
sudo ./manage_timers.sh stop qtickets
sudo ./manage_timers.sh stop qtickets_api
sudo ./manage_timers.sh stop vk_ads
sudo ./manage_timers.sh stop direct

# РћСЃС‚Р°РЅРѕРІРёС‚СЊ Рё СѓРґР°Р»РёС‚СЊ Docker РєРѕРЅС‚РµР№РЅРµСЂС‹ QTickets API РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё
docker stop $(docker ps -q --filter "name=qtickets_api_") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=qtickets_api_") 2>/dev/null || true
```

### РџСЂРѕРІРµСЂРєР° РїРѕСЃР»Рµ РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ

```bash
# РџСЂРѕРІРµСЂРёС‚СЊ СЃС‚Р°С‚СѓСЃ
./manage_timers.sh status

# Р—Р°РїСѓСЃС‚РёС‚СЊ РІСЂСѓС‡РЅСѓСЋ РґР»СЏ РїСЂРѕРІРµСЂРєРё
sudo ./manage_timers.sh start qtickets
sudo ./manage_timers.sh start qtickets_api

# РџСЂРѕСЃРјРѕС‚СЂРµС‚СЊ Р»РѕРіРё
./manage_timers.sh logs qtickets
./manage_timers.sh logs qtickets_api

# Р”Р»СЏ QTickets API С‚Р°РєР¶Рµ РјРѕР¶РЅРѕ РїСЂРѕРІРµСЂРёС‚СЊ Docker Р»РѕРіРё:
docker logs $(docker ps -aq --filter "name=qtickets_api_" --latest)
```

## Р‘РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ

### РџСЂР°РІР° РґРѕСЃС‚СѓРїР°

- РЎРµСЂРІРёСЃС‹ Р·Р°РїСѓСЃРєР°СЋС‚СЃСЏ РѕС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ `etl`
- РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ Р·Р°РіСЂСѓР¶Р°СЋС‚СЃСЏ РёР· Р·Р°С‰РёС‰РµРЅРЅС‹С… С„Р°Р№Р»РѕРІ РІ `secrets/`
- Р›РѕРіРё РЅРµ СЃРѕРґРµСЂР¶Р°С‚ РєРѕРЅС„РёРґРµРЅС†РёР°Р»СЊРЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРё
- QTickets API Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ РІ Docker РєРѕРЅС‚РµР№РЅРµСЂРµ РѕС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ `etl` С…РѕСЃС‚Р°
- РЎРµРєСЂРµС‚С‹ РїРµСЂРµРґР°СЋС‚СЃСЏ С‡РµСЂРµР· `--env-file` Рё РїРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ Docker

### РР·РѕР»СЏС†РёСЏ

- Р Р°Р±РѕС‡Р°СЏ РґРёСЂРµРєС‚РѕСЂРёСЏ: `/opt/zakaz_dashboard`
- РџРµСЂРµРјРµРЅРЅР°СЏ `PYTHONPATH` РѕРіСЂР°РЅРёС‡РµРЅР° РґРёСЂРµРєС‚РѕСЂРёРµР№ РїСЂРѕРµРєС‚Р°
- РћРіСЂР°РЅРёС‡РµРЅРЅС‹Рµ РїСЂР°РІР° РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ `etl`

## Р РµР·РµСЂРІРЅРѕРµ РєРѕРїРёСЂРѕРІР°РЅРёРµ РєРѕРЅС„РёРіСѓСЂР°С†РёРё

```bash
# РЎРѕР·РґР°С‚СЊ Р±СЌРєР°Рї С„Р°Р№Р»РѕРІ systemd
sudo cp -r /etc/systemd/system/*timer* /backup/systemd/
sudo cp -r /etc/systemd/system/*service* /backup/systemd/

# Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РёР· Р±СЌРєР°РїР°
sudo cp /backup/systemd/*timer* /etc/systemd/system/
sudo cp /backup/systemd/*service* /etc/systemd/system/
sudo systemctl daemon-reload
