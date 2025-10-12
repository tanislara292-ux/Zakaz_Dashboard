#!/usr/bin/env python3
import os, requests, json, sys
BOT = os.environ.get("TG_BOT_TOKEN")
CHAT = os.environ.get("TG_CHAT_ID")
msg  = sys.argv[1] if len(sys.argv)>1 else "No message"
if BOT and CHAT:
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                  json={"chat_id": CHAT, "text": msg, "disable_web_page_preview": True})