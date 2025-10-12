#!/usr/bin/env python3
import argparse, os, subprocess

p = argparse.ArgumentParser()
p.add_argument("--from", dest="from_", required=True, help="YYYY-MM-DD")
p.add_argument("--to",   dest="to",    required=True, help="YYYY-MM-DD")
args = p.parse_args()

env = os.environ.copy()
subprocess.check_call(["python","-m","vk_ads_pipeline.main","--from",args.from_,"--to",args.to,"--sink","clickhouse"], env=env, cwd="vk-python")
subprocess.check_call(["python","ch-python/cli.py","build-dm-vk","--from",args.from_,"--to",args.to], env=env)
subprocess.check_call(["python","ch-python/cli.py","build-dm-sales","--from",args.from_,"--to",args.to], env=env)