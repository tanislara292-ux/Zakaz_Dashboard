## Quickstart: ClickHouse + QTickets end-to-end

1. **Bootstrap ClickHouse**
   ```bash
   cd dashboard-mvp/infra/clickhouse
   cp .env.example .env   # adjust only if you need custom ports/credentials
   ../scripts/bootstrap_clickhouse.sh
   ```
   The script waits for ch-zakaz to become healthy, applies bootstrap_schema.sql,
   and verifies that all QTickets tables (including meta_job_runs) are present.

2. **Run the dry-run smoke test**
   ```bash
   cd dashboard-mvp
   scripts/smoke_qtickets_dryrun.sh \
     --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api  # optional
   ```
   Without --env-file the helper copies configs/.env.qtickets_api.sample.
   It builds the Docker image, runs the loader, and fails if the container exits
   with a non-zero code or if zakaz.meta_job_runs receives new rows.

3. **Switch to production ingestion**
   - Edit the dotenv (DRY_RUN=false, real QTICKETS_TOKEN, ORG_NAME, ClickHouse credentials).
   - Re-run the container manually or schedule it:
     ```bash
     docker run --rm \
       --network clickhouse_default \
       --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
       qtickets_api:latest
     ```
   - Verify facts and meta_job_runs per integrations/qtickets_api/README.md.
# ¦Ð¦-¦-¦¬¦¬TÂ¦¬TÇ¦¦TÁ¦¦¦¬¦¦ ¦+¦-TÈ¦-¦-TÀ¦+ Zakaz (MVP) + ¦-¦-TÂ¦-¦-¦-TÂ¦¬¦¬¦-TÆ¦¬TÏ VK Ads

¦Õ¦+¦¬¦-TË¦¦ TÀ¦¦¦¬¦-¦¬¦¬TÂ¦-TÀ¦¬¦¦ ¦-TÀTÂ¦¦TÄ¦-¦¦TÂ¦-¦- ¦¬TÀ¦-¦¦¦¦TÂ¦-: ¦+¦-¦¦TÃ¦-¦¦¦-TÂ¦-TÆ¦¬TÏ, TÁTÅ¦¦¦-TË ¦+¦-¦-¦-TËTÅ, ¦¦¦-¦+ ¦¬¦-TÂ¦¦¦¦TÀ¦-TÆ¦¬¦¦ ¦¬ ¦-¦¬¦¦TÀ¦-TÆ¦¬¦-¦-¦-TË¦¦ TÈ¦-¦-¦¬¦-¦-TË. ¦æ¦¦¦¬TÌ òÀÔ ¦¬¦- 10òÀÓ14 ¦+¦-¦¦¦¦ TÁ¦-¦-TÀ¦-TÂTÌ TÃ¦¬TÀ¦-¦-¦¬TÏ¦¦¦-TË¦¦ MVP ¦-TÂTÇTÑTÂ¦-¦-TÁTÂ¦¬ ¦- Yandex DataLens ¦¬ ¦¬¦-¦+¦¦¦-TÂ¦-¦-¦¬TÂTÌ ¦¬¦-¦¬¦-¦-TÁTÂTÌTÎ ¦-¦-TÂ¦-¦-¦-TÂ¦¬¦¬¦¬TÀ¦-¦-¦-¦-¦-TÃTÎ ¦¬¦-¦¦TÀTÃ¦¬¦¦TÃ ¦-¦¦TÂTÀ¦¬¦¦ VK Ads.

## ¦çTÂ¦- TÀ¦¦¦-¦¬¦¬¦¬¦-¦-¦-¦-¦-
- ¦ß¦-TÂ¦-¦¦ A2: Apps Script `qtickets_api_ingest.gs` TÁ¦¬¦-TÅTÀ¦-¦-¦¬¦¬¦¬TÀTÃ¦¦TÂ ¦¬¦-¦¦¦-¦¬TË QTickets ¦¬ ¦-TÁTÂ¦-TÂ¦¦¦¬ ¦¬¦- ¦-¦¦TÀ¦-¦¬TÀ¦¬TÏTÂ¦¬TÏ¦- ¦- Google Sheets (`QTickets`, `Inventory`, `Logs`).
- ¦ß¦-TÂ¦-¦¦ B0òÀÓB3: Python-TÁ¦¦TÀ¦-¦¬TÁ `vk-ads-pipeline` TÁ¦-¦-¦¬TÀ¦-¦¦TÂ ¦¬¦-TÁTÃTÂ¦-TÇ¦-TÃTÎ TÁTÂ¦-TÂ¦¬TÁTÂ¦¬¦¦TÃ ¦-¦-TÊTÏ¦-¦¬¦¦¦-¦¬¦¦ VK Ads, ¦-¦-TÀ¦-¦-¦¬¦¬¦¬TÃ¦¦TÂ UTM-¦-¦¦TÂ¦¦¦¬ ¦¬ ¦¬¦-¦¬¦¬TÁTË¦-¦-¦¦TÂ ¦+¦-¦-¦-TË¦¦ ¦- ¦¬¦¬TÁTÂ `VK_Ads`.
- ¦Ø¦-TÄTÀ¦-TÁTÂTÀTÃ¦¦TÂTÃTÀ¦-TË¦¦ TÁ¦¦TÀ¦¬¦¬TÂTË ¦+¦¬TÏ ¦-TËTÀ¦-¦-¦-¦¬¦-¦-¦-¦¬TÏ TÁTÂTÀTÃ¦¦TÂTÃTÀTË TÂ¦-¦-¦¬¦¬TÆ (`tools/sheets_init.py`, `tools/sheets_validate.py`) ¦¬¦- ¦¬¦-¦¦¦-¦¬TÌ¦-TË¦- TÁTÅ¦¦¦-¦-¦- (`schemas/sheets/*.yaml`).
- ¦ß¦-¦¬¦-TË¦¦ ¦¦¦-¦-¦¬¦¬¦¦¦¦TÂ ¦¬TÀ¦-¦¦¦¦TÂ¦-¦-¦¦ ¦+¦-¦¦TÃ¦-¦¦¦-TÂ¦-TÆ¦¬¦¬ (`docs/`), ¦-¦¦¦¬TÎTÇ¦-TÎTÉ¦¬¦¦ ¦¬¦¬¦-¦-TË ¦¦¦-¦-¦-TÃ¦-¦¬¦¦¦-TÆ¦¬¦¦, scope, TÀ¦¬TÁ¦¦¦¬, DoR/DoD ¦¬ ¦-TÀTÅ¦¬TÂ¦¦¦¦TÂTÃTÀ¦-TÃTÎ TÁTÅ¦¦¦-TÃ.

## ¦ÐTÀTÅ¦¬TÂ¦¦¦¦TÂTÃTÀ¦- ¦¬¦-TÂ¦-¦¦¦-¦-
1. **QTickets òÆÒ Google Sheets** òÀÔ Apps Script ¦-TË¦¬¦-¦¬¦-TÏ¦¦TÂTÁTÏ ¦¬¦- ¦¦¦¦¦¦¦+¦-¦¦¦-¦-¦-¦-TÃ TÂTÀ¦¬¦¦¦¦¦¦TÀTÃ, ¦-TË¦¦TÀTÃ¦¦¦-¦¦TÂ ¦¬¦-¦¦¦-¦¬TË ¦¬ ¦-TÁTÂ¦-TÂ¦¦¦¬, ¦¬¦-¦¦¦¬TÀTÃ¦¦TÂ TÁTÂ¦-TÂTÃTÁTË.
2. **VK Ads òÆÒ Google Sheets** òÀÔ Python-¦¬¦-¦¦¦¬¦¬¦-¦¦¦- ¦¬¦- TÀ¦-TÁ¦¬¦¬TÁ¦-¦-¦¬TÎ (cron / GitHub Actions) ¦-¦-TÀ¦-TÉ¦-¦¦TÂTÁTÏ ¦¦ VK API, ¦-¦-¦-¦¦¦-TÉ¦-¦¦TÂ ¦-¦-TÊTÏ¦-¦¬¦¦¦-¦¬TÏ UTM-¦-¦¦TÂ¦¦¦-¦-¦¬, ¦¬TÀ¦-¦-¦-¦+¦¬TÂ ¦+¦¦¦+TÃ¦¬¦¬¦¬¦¦¦-TÆ¦¬TÎ ¦¬ ¦¬¦¬TÈ¦¦TÂ ¦+¦-¦-¦-TË¦¦ ¦- `VK_Ads`.
3. **Google Sheets òÆÒ Yandex DataLens** òÀÔ TÂ¦-¦-¦¬¦¬TÆ¦- `BI_Central` ¦-TËTÁTÂTÃ¦¬¦-¦¦TÂ staging-TÁ¦¬TÁTÂ¦¦¦-¦-¦¦; DataLens TÇ¦¬TÂ¦-¦¦TÂ ¦+¦-¦-¦-TË¦¦ TÇ¦¦TÀ¦¦¦¬ ¦¦¦-¦-¦-¦¦¦¦TÂ¦-TÀ Google Sheets. ¦Ü¦-¦+¦¦¦¬¦¬ ¦-¦¬¦¬TÃ¦-¦¬¦¬¦¬¦-TÆ¦¬¦¬ ¦-¦¬¦¬TÁ¦-¦-TË ¦- `docs/PROJECT_OVERVIEW.md`.

## ¦áTÂTÀTÃ¦¦TÂTÃTÀ¦- TÀ¦¦¦¬¦-¦¬¦¬TÂ¦-TÀ¦¬TÏ
```
òÔÜòÔÀòÔÀ appscript/             # Google Apps Script (¦¬¦-TÂ¦-¦¦ QTickets)
òÔÜòÔÀòÔÀ docs/                  # ¦ßTÀ¦-¦¦¦¦TÂ¦-¦-TÏ ¦+¦-¦¦TÃ¦-¦¦¦-TÂ¦-TÆ¦¬TÏ ¦¬ TÈ¦-¦-¦¬¦-¦-TË
òÔÜòÔÀòÔÀ ops/                   # ¦Þ¦¬¦¦TÀ¦-TÆ¦¬¦-¦-¦-TË¦¦ TÇ¦¦¦¦-¦¬¦¬TÁTÂTË ¦¬ TÈ¦-¦-¦¬¦-¦-TË ¦¬¦¬TÁ¦¦¦-
òÔÜòÔÀòÔÀ schemas/sheets/        # YAML-TÁTÅ¦¦¦-TË ¦¬¦¬TÁTÂ¦-¦- Google Sheets
òÔÜòÔÀòÔÀ tools/                 # CLI-TÃTÂ¦¬¦¬¦¬TÂTË ¦+¦¬TÏ Sheets ¦¬ TÈ¦-¦-¦¬¦-¦-TË ¦¬TÀ¦-¦¦¦¦TÂ¦-
òÔÔòÔÀòÔÀ vk-python/             # Python-TÁ¦¦TÀ¦-¦¬TÁ TÁ¦-¦-TÀ¦- TÁTÂ¦-TÂ¦¬TÁTÂ¦¬¦¦¦¬ VK Ads
```

## ¦ÑTËTÁTÂTÀTË¦¦ TÁTÂ¦-TÀTÂ
1. ¦á¦¦¦-¦¬¦¬TÀTÃ¦¦TÂ¦¦ `.env.sample` ¦- `.env`, ¦¬¦-¦¬¦-¦¬¦-¦¬TÂ¦¦ ¦+¦-TÁTÂTÃ¦¬TË Google ¦¬ ¦¬¦-TÀ¦-¦-¦¦TÂTÀTË VK Ads.
2. ¦Ø¦-¦¬TÆ¦¬¦-¦¬¦¬¦¬¦¬TÀTÃ¦¦TÂ¦¦ ¦-¦¬TÀTÂTÃ¦-¦¬TÌ¦-¦-¦¦ ¦-¦¦TÀTÃ¦¦¦¦¦-¦¬¦¦ ¦¬ pre-commit:
   ```bash
   bash tools/init.sh
   ```
3. ¦ÒTËTÀ¦-¦-¦-¦¬¦-¦-¦¦TÂ¦¦ TÁTÂTÀTÃ¦¦TÂTÃTÀTÃ TÂ¦-¦-¦¬¦¬TÆ ¦¬¦- TÁTÅ¦¦¦-¦-¦-:
   ```bash
   python tools/sheets_init.py
   ```
4. ¦ßTÀ¦-¦-¦¦TÀTÌTÂ¦¦ ¦+¦-¦-¦-TË¦¦ ¦-¦- TÁ¦-¦-TÂ¦-¦¦TÂTÁTÂ¦-¦¬¦¦ TÁTÅ¦¦¦-¦-¦-:
   ```bash
   python tools/sheets_validate.py
   ```
5. ¦×¦-¦¬TÃTÁTÂ¦¬TÂ¦¦ ¦¬¦-¦¦¦¬¦¬¦-¦¦¦- VK Ads:
   ```bash
   cd vk-python
   python -m vk_ads_pipeline.main --dry-run --verbose
   ```

## ¦Ô¦-¦¦TÃ¦-¦¦¦-TÂ¦-TÆ¦¬TÏ
- `docs/PROJECT_OVERVIEW.md` òÀÔ TÆ¦¦¦¬¦¬, KPI, ¦-TÀTÂ¦¦TÄ¦-¦¦TÂTË ¦¬ ¦+¦-TÀ¦-¦¦¦-¦-TÏ ¦¦¦-TÀTÂ¦-.
- `docs/COMMUNICATION_PLAN.md` òÀÔ TÀ¦-TÁ¦¬¦¬TÁ¦-¦-¦¬¦¦ TÁ¦-¦¬¦-¦-¦-¦-¦-, SLA ¦¬ ¦¦¦-¦-TÂ¦-¦¦TÂTË.
- `docs/ACCESS_HANDBOOK.md` òÀÔ ¦¬¦-TÀTÏ¦+¦-¦¦ ¦-TË¦+¦-TÇ¦¬ ¦+¦-TÁTÂTÃ¦¬¦-¦- ¦¬ TÅTÀ¦-¦-¦¦¦-¦¬¦¦ TÁ¦¦¦¦TÀ¦¦TÂ¦-¦-.
- `docs/RISK_LOG.md` òÀÔ TÃ¦¬TÀ¦-¦-¦¬¦¦¦-¦¬¦¦ TÀ¦¬TÁ¦¦¦-¦-¦¬ ¦¬ TÂTÀ¦¬¦¦¦¦¦¦TÀTË TÍTÁ¦¦¦-¦¬¦-TÆ¦¬¦¬.
- `docs/ARCHITECTURE.md` òÀÔ TÁTÅ¦¦¦-¦- ¦¬¦-TÂ¦-¦¦¦-¦- ¦+¦-¦-¦-TËTÅ ¦¬ TÂ¦-TÇ¦¦¦¬ ¦-¦-TÂ¦-¦-¦-TÂ¦¬¦¬¦-TÆ¦¬¦¬.
- `ops/` òÀÔ TÇ¦¦¦¦-¦¬¦¬TÁTÂTË ¦¦¦¬¦¦-¦-TÄTÄ¦-, TÈ¦-¦-¦¬¦-¦-TË ¦¬¦¬TÁ¦¦¦-, DoR/DoD.

## ¦â¦¦TÁTÂ¦¬TÀ¦-¦-¦-¦-¦¬¦¦ ¦¬ ¦¦¦-¦-TÂTÀ¦-¦¬TÌ ¦¦¦-TÇ¦¦TÁTÂ¦-¦-
- ¦ß¦¬TÀ¦¬¦-¦¦ ¦¬¦¬¦-¦¦¦-¦¦¦-¦¬¦¦ TÇ¦¦TÀ¦¦¦¬ pre-commit (`black`, `markdownlint`, ¦-¦-¦¬¦-¦-TË¦¦ ¦¬TÀ¦-¦-¦¦TÀ¦¦¦¬).
- `vk-python` TÁ¦-¦+¦¦TÀ¦¦¦¬TÂ unit-TÂ¦¦TÁTÂTË (`pytest`) ¦-¦- TÀ¦-¦¬¦-¦-TÀ ¦¦¦-¦-TÄ¦¬¦¦TÃTÀ¦-TÆ¦¬¦¬ ¦¬ ¦-¦-TÀ¦-¦-¦¬¦¬¦¬¦-TÆ¦¬TÎ TÁTÂ¦-TÂ¦¬TÁTÂ¦¬¦¦¦¬.
- ¦Û¦-¦¦¦¬ ¦¬TÁ¦¬¦-¦¬¦-¦¦¦-¦¬TÏ ¦¬¦-¦¦¦¬¦¬¦-¦¦¦-¦-¦- ¦+¦-TÁTÂTÃ¦¬¦-TË ¦- ¦¬¦¬TÁTÂ¦¦ `Logs`; ¦¦TÀ¦¬TÂ¦¬TÇ¦¦TÁ¦¦¦¬¦¦ ¦-TÈ¦¬¦-¦¦¦¬ ¦+TÃ¦-¦¬¦¬TÀTÃTÎTÂTÁTÏ ¦-¦- ¦¬¦-TÇTÂTÃ ¦¬¦¬ Script Properties.

## ¦ß¦-¦+¦+¦¦TÀ¦¦¦¦¦-
¦Ø¦-TÁTÂTÀTÃ¦¦TÆ¦¬¦¬ ¦¬¦- ¦¦¦-¦-¦-TÃ¦-¦¬¦¦¦-TÆ¦¬TÏ¦- ¦¬ ¦-¦¬¦¦TÀ¦-TÆ¦¬¦-¦-¦-TË¦¦ ¦¦¦-¦-TÂ¦-¦¦TÂTË òÀÔ ¦- `docs/COMMUNICATION_PLAN.md`. ¦Ð¦¦TÂTÃ¦-¦¬TÌ¦-TË¦¦ TÀ¦¬TÁ¦¦¦¬ ¦¬ TÍTÁ¦¦¦-¦¬¦-TÆ¦¬¦¬ òÀÔ `docs/RISK_LOG.md`. ¦Ò¦-¦¬TÀ¦-TÁTË ¦¬¦- ¦¬¦-TÄTÀ¦-TÁTÂTÀTÃ¦¦TÂTÃTÀ¦¦: smorozov@zakaz.example (TÂ¦¦TÅ¦¬¦¬¦+), bkoroleva@zakaz.example (¦¬TÀ¦-¦¦¦¦TÂ¦-TË¦¦ ¦-¦¦¦-¦¦¦+¦¦¦¦TÀ).

