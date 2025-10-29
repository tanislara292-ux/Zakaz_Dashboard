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

4. **Connect Yandex DataLens (Optional)**
   After ClickHouse is running, read-only DataLens users are automatically created:

   **Test connection:**
   ```bash
   curl -u datalens_reader:ChangeMe123! http://localhost:8123/?query=SELECT%201
   # Should return: 1

   # Verify table access:
   curl -u datalens_reader:ChangeMe123! http://localhost:8123/ --data "SELECT count() FROM system.tables WHERE database='zakaz'"
   # Should return: 31
   ```

   **DataLens Connection Parameters:**
   - **Host**: Your ClickHouse server address
   - **Port**: 8123 (HTTP interface)
   - **Database**: zakaz
   - **Username**: datalens_reader
   - **Password**: ChangeMe123!
   - **Rights**: Read-only access to zakaz.* tables

   ⚠️ **Production Security**: Change the default password before production deployment:
   ```bash
   ALTER USER datalens_reader IDENTIFIED WITH plaintext_password BY 'your_secure_password';
   ```

   📖 **Full Documentation**: See `dashboard-mvp/infra/clickhouse/README.md` for detailed setup instructions.
# �Ц-�-����T¦�TǦ�T������� �+�-TȦ-�-T��+ Zakaz (MVP) + �-�-T¦-�-�-T¦����-TƦ�T� VK Ads

�զ+���-T˦� T������-����T¦-T����� �-T�T¦�TĦ-��T¦-�- ��T��-����T¦-: �+�-��Tæ-���-T¦-TƦ�T�, T�TŦ��-T� �+�-�-�-T�T�, ���-�+ ���-T¦���T��-TƦ��� �� �-����T��-TƦ��-�-�-T˦� TȦ-�-���-�-T�. �榦��T� ��� ���- 10���14 �+�-���� T��-�-T��-T�T� Tæ�T��-�-��TϦ��-T˦� MVP �-T�T�T�T¦-�-T�T¦� �- Yandex DataLens �� ���-�+���-T¦-�-��T�T� ���-���-�-T�T�T�T� �-�-T¦-�-�-T¦�����T��-�-�-�-�-T�T� ���-��T�Tæ���T� �-��T�T����� VK Ads.

## ��T¦- T����-�������-�-�-�-�-
- �ߦ-T¦-�� A2: Apps Script `qtickets_api_ingest.gs` T����-T�T��-�-������T�Tæ�T� ���-���-��T� QTickets �� �-T�T¦-T¦��� ���- �-��T��-��T���T�T¦�TϦ- �- Google Sheets (`QTickets`, `Inventory`, `Logs`).
- �ߦ-T¦-�� B0���B3: Python-T���T��-��T� `vk-ads-pipeline` T��-�-��T��-��T� ���-T�T�T¦-TǦ-T�T� T�T¦-T¦�T�T¦���T� �-�-T�TϦ-�����-���� VK Ads, �-�-T��-�-������Tæ�T� UTM-�-��T¦��� �� ���-����T�T˦-�-��T� �+�-�-�-T˦� �- ����T�T� `VK_Ads`.
- �ئ-T�T��-T�T�T�Tæ�T�T�T��-T˦� T���T�����T�T� �+��T� �-T�T��-�-�-���-�-�-��T� T�T�T�Tæ�T�T�T�T� T¦-�-����T� (`tools/sheets_init.py`, `tools/sheets_validate.py`) ���- ���-���-��Ț-T˦- T�TŦ��-�-�- (`schemas/sheets/*.yaml`).
- �ߦ-���-T˦� ���-�-��������T� ��T��-����T¦-�-�� �+�-��Tæ-���-T¦-TƦ��� (`docs/`), �-����T�TǦ-T�Tɦ��� �����-�-T� ���-�-�-Tæ-�����-TƦ���, scope, T���T�����, DoR/DoD �� �-T�TŦ�T¦���T�T�T��-T�T� T�TŦ��-T�.

## ��T�TŦ�T¦���T�T�T��- ���-T¦-���-�-
1. **QTickets ��� Google Sheets** ��� Apps Script �-T˦��-���-TϦ�T�T�T� ���- �������+�-���-�-�-�-T� T�T���������T�T�, �-T˦�T�Tæ��-��T� ���-���-��T� �� �-T�T¦-T¦���, ���-����T�Tæ�T� T�T¦-T�T�T�T�.
2. **VK Ads ��� Google Sheets** ��� Python-���-�������-���- ���- T��-T�����T��-�-��T� (cron / GitHub Actions) �-�-T��-Tɦ-��T�T�T� �� VK API, �-�-�-���-Tɦ-��T� �-�-T�TϦ-�����-��T� UTM-�-��T¦��-�-��, ��T��-�-�-�+��T� �+���+Tæ��������-TƦ�T� �� ����TȦ�T� �+�-�-�-T˦� �- `VK_Ads`.
3. **Google Sheets ��� Yandex DataLens** ��� T¦-�-����TƦ- `BI_Central` �-T�T�T�Tæ��-��T� staging-T���T�T¦��-�-��; DataLens TǦ�T¦-��T� �+�-�-�-T˦� TǦ�T����� ���-�-�-����T¦-T� Google Sheets. �ܦ-�+������ �-����Tæ-�������-TƦ��� �-����T��-�-T� �- `docs/PROJECT_OVERVIEW.md`.

## ��T�T�Tæ�T�T�T��- T������-����T¦-T���T�
```
��������� appscript/             # Google Apps Script (���-T¦-�� QTickets)
��������� docs/                  # ��T��-����T¦-�-T� �+�-��Tæ-���-T¦-TƦ�T� �� TȦ-�-���-�-T�
��������� ops/                   # �ަ���T��-TƦ��-�-�-T˦� TǦ���-����T�T�T� �� TȦ-�-���-�-T� ����T����-
��������� schemas/sheets/        # YAML-T�TŦ��-T� ����T�T¦-�- Google Sheets
��������� tools/                 # CLI-T�T¦�����T�T� �+��T� Sheets �� TȦ-�-���-�-T� ��T��-����T¦-
��������� vk-python/             # Python-T���T��-��T� T��-�-T��- T�T¦-T¦�T�T¦����� VK Ads
```

## ��T�T�T�T�T˦� T�T¦-T�T�
1. �ᦦ�-����T�Tæ�T¦� `.env.sample` �- `.env`, ���-���-���-��T¦� �+�-T�T�Tæ�T� Google �� ���-T��-�-��T�T�T� VK Ads.
2. �ئ-��TƦ��-��������T�Tæ�T¦� �-��T�T�Tæ-��Ț-�-�� �-��T�Tæ����-���� �� pre-commit:
   ```bash
   bash tools/init.sh
   ```
3. ��T�T��-�-�-���-�-��T¦� T�T�T�Tæ�T�T�T�T� T¦-�-����T� ���- T�TŦ��-�-�-:
   ```bash
   python tools/sheets_init.py
   ```
4. ��T��-�-��T�T�T¦� �+�-�-�-T˦� �-�- T��-�-T¦-��T�T�T¦-���� T�TŦ��-�-�-:
   ```bash
   python tools/sheets_validate.py
   ```
5. �צ-��T�T�T¦�T¦� ���-�������-���- VK Ads:
   ```bash
   cd vk-python
   python -m vk_ads_pipeline.main --dry-run --verbose
   ```

## �Ԧ-��Tæ-���-T¦-TƦ�T�
- `docs/PROJECT_OVERVIEW.md` ��� TƦ�����, KPI, �-T�T¦�TĦ-��T�T� �� �+�-T��-���-�-T� ���-T�T¦-.
- `docs/COMMUNICATION_PLAN.md` ��� T��-T�����T��-�-���� T��-���-�-�-�-�-, SLA �� ���-�-T¦-��T�T�.
- `docs/ACCESS_HANDBOOK.md` ��� ���-T�TϦ+�-�� �-T˦+�-TǦ� �+�-T�T�Tæ��-�- �� T�T��-�-���-���� T�����T���T¦-�-.
- `docs/RISK_LOG.md` ��� Tæ�T��-�-�����-���� T���T����-�-�� �� T�T���������T�T� T�T����-���-TƦ���.
- `docs/ARCHITECTURE.md` ��� T�TŦ��-�- ���-T¦-���-�- �+�-�-�-T�T� �� T¦-TǦ��� �-�-T¦-�-�-T¦����-TƦ���.
- `ops/` ��� TǦ���-����T�T�T� ������-�-T�TĦ-, TȦ-�-���-�-T� ����T����-, DoR/DoD.

## �⦦T�T¦�T��-�-�-�-���� �� ���-�-T�T��-��T� ���-TǦ�T�T¦-�-
- �ߦ�T����-�� �����-���-���-���� TǦ�T����� pre-commit (`black`, `markdownlint`, �-�-���-�-T˦� ��T��-�-��T�����).
- `vk-python` T��-�+��T�����T� unit-T¦�T�T�T� (`pytest`) �-�- T��-���-�-T� ���-�-TĦ���T�T��-TƦ��� �� �-�-T��-�-�������-TƦ�T� T�T¦-T¦�T�T¦�����.
- �ۦ-���� ��T����-���-���-��T� ���-�������-���-�-�- �+�-T�T�Tæ��-T� �- ����T�T¦� `Logs`; ��T���T¦�TǦ�T������� �-TȦ��-���� �+Tæ-����T�T�T�T�T�T� �-�- ���-T�T�T� ���� Script Properties.

## �ߦ-�+�+��T������-
�ئ-T�T�T�Tæ�TƦ��� ���- ���-�-�-Tæ-�����-TƦ�TϦ- �� �-����T��-TƦ��-�-�-T˦� ���-�-T¦-��T�T� ��� �- `docs/COMMUNICATION_PLAN.md`. �Ц�T�Tæ-��Ț-T˦� T���T����� �� T�T����-���-TƦ��� ��� `docs/RISK_LOG.md`. �Ҧ-��T��-T�T� ���- ���-T�T��-T�T�T�Tæ�T�T�T���: smorozov@zakaz.example (T¦�TŦ����+), bkoroleva@zakaz.example (��T��-����T¦-T˦� �-���-���+����T�).

