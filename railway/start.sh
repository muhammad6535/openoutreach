#!/bin/bash
set -euo pipefail

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1920x1080x24 &
sleep 1
export DISPLAY=:99

if [ "${ENABLE_VNC:-false}" = "true" ]; then
    x11vnc -display :99 -forever -shared -nopw &
    websockify --web /opt/noVNC 6080 localhost:5900 &
fi

cd /app

python manage.py migrate --no-input
python manage.py setup_crm
chown -R ubuntu:ubuntu /app/data 2>/dev/null || true

if [ -n "${RAILWAY_ADMIN_USER:-}" ] && [ -n "${RAILWAY_ADMIN_PASS:-}" ]; then
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='$RAILWAY_ADMIN_USER').exists():
    User.objects.create_superuser('$RAILWAY_ADMIN_USER', '${RAILWAY_ADMIN_EMAIL:-admin@example.com}', '$RAILWAY_ADMIN_PASS')
    print('Admin user created')
else:
    print('Admin user exists')
" 2>&1
fi

python manage.py shell -c "
from linkedin.models import SiteConfig, LinkedInProfile, Campaign, SearchKeyword
import os
# SiteConfig
cfg = SiteConfig.load()
changed = False
for env_key, cfg_key in [('RAILWAY_LLM_PROVIDER','llm_provider'),('RAILWAY_LLM_API_KEY','llm_api_key'),('RAILWAY_AI_MODEL','ai_model'),('RAILWAY_LLM_API_BASE','llm_api_base')]:
    val = os.environ.get(env_key)
    if val and getattr(cfg, cfg_key) != val:
        setattr(cfg, cfg_key, val)
        changed = True
if changed:
    cfg.save()
    print('SiteConfig updated from env')
else:
    print('SiteConfig unchanged')
# LinkedIn Profile from env
username = os.environ.get('RAILWAY_LINKEDIN_USERNAME')
password = os.environ.get('RAILWAY_LINKEDIN_PASSWORD')
if username and password:
    if not LinkedInProfile.objects.filter(username=username).exists():
        LinkedInProfile.objects.create(username=username, password=password, active=True)
        print('LinkedIn Profile created')
    else:
        print('LinkedIn Profile exists')
# Campaign
if not Campaign.objects.filter(is_freemium=False).exists():
    Campaign.objects.create(name='FAANG Outreach', is_freemium=False, daily_connect_limit=20, max_connections_per_campaign=300, active_hours_start='09:00', active_hours_end='17:00', active_timezone='America/New_York')
    print('Campaign created')
else:
    print('Campaign exists')
# Search Keywords
keywords = ['Google', 'Amazon', 'Apple', 'Netflix', 'Meta', 'Facebook', 'FAANG', 'HR', 'talent acquisition']
for kw in keywords:
    SearchKeyword.objects.get_or_create(keyword=kw)
print(f'{SearchKeyword.objects.count()} search keywords')
" 2>&1

DJANGO_SETTINGS_MODULE=linkedin.django_settings python manage.py collectstatic --no-input 2>&1

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/openoutreach.conf
