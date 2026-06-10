#!/usr/bin/env python3
"""Wait for LinkedIn profile to be configured, then start the daemon."""

import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkedin.django_settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from linkedin.models import LinkedInProfile, SiteConfig, Campaign


def is_ready():
    if not SiteConfig.objects.filter(pk=1).exists():
        return False
    cfg = SiteConfig.objects.get(pk=1)
    if not cfg.llm_api_key:
        return False
    if not LinkedInProfile.objects.filter(active=True).exists():
        return False
    if not Campaign.objects.filter(is_freemium=False).exists():
        return False
    return True


if __name__ == "__main__":
    wait_count = 0
    while not is_ready():
        wait_count += 1
        if wait_count == 1:
            print("[wait_for_setup] Waiting for setup via admin...", flush=True)
            print("   1. Create a Campaign (non-freemium) at /admin/linkedin/campaign/", flush=True)
            print("   2. Create a LinkedIn Profile at /admin/linkedin/linkedinprofile/", flush=True)
            print("   3. Ensure SiteConfig has LLM API key at /admin/linkedin/siteconfig/1/change/", flush=True)
        if wait_count % 10 == 0:
            print(f"[wait_for_setup] Still waiting... ({wait_count * 30}s elapsed)", flush=True)
        time.sleep(30)

    print("[wait_for_setup] ✅ Setup found — starting daemon")
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "rundaemon"])
