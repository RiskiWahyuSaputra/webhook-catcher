#!/usr/bin/env fish
# Launch Webhook Catcher & Request Inspector

set SCRIPT_DIR (status dirname)
cd $SCRIPT_DIR

set PORT 4040
if test (count $argv) -ge 1
    set PORT $argv[1]
end

echo "⚡ Menjalankan Webhook Catcher pada port $PORT..."
python3 app.py $PORT
