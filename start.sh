#!/bin/bash
set -e


# Start both services in background, let PID 1 manage them directly
python web.py &
python api.py --host 0.0.0.0 --port 1218 --device cpu &

# Wait for both to exit
wait