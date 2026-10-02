#!/bin/sh
# Sign in to LinkedIn in the container's Chromium, viewed at http://localhost:6080/vnc.html
Xvfb :99 -screen 0 1472x828x24 &
export DISPLAY=:99
sleep 1
x11vnc -display :99 -forever -nopw -quiet -rfbport 5900 &
websockify --web /usr/share/novnc 6080 localhost:5900 &
echo "Open http://localhost:6080/vnc.html and sign in to LinkedIn (tick Keep me logged in)"
exec python -m linkedin_jobs_scraper login --chrome-user-data-dir /app/chrome-profile \
    --chrome-executable-path "$CHROMEDRIVER_PATH" --chrome-binary-location "$CHROME_BIN"
