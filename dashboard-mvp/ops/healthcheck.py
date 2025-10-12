#!/usr/bin/env python3
import os, sys
from clickhouse_connect import get_client
client = get_client(host=os.environ.get("CH_HOST","localhost"),
                    port=int(os.environ.get("CH_PORT","8123")),
                    username=os.environ.get("CH_USER","admin"),
                    password=os.environ.get("CH_PASSWORD",""),
                    database=os.environ.get("CH_DB","default"),
                    https=os.environ.get("CH_HTTPS","0")=="1")
q = client.query("SELECT * FROM meta.v_quality_last_day")
row = q.result_rows[0]
d, sales_rows, sales_rev, vk_rows, vk_spend = row
problems = []
if sales_rows == 0: problems.append("Sales vitrine is empty for yesterday")
if vk_rows == 0:    problems.append("VK vitrine is empty for yesterday")
if sales_rev < 0:   problems.append("Negative net_revenue")
if vk_spend < 0:    problems.append("Negative spend")
if problems:
    print(" ; ".join(problems))
    sys.exit(2)
print("OK")