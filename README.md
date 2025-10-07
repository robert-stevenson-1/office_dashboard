# Office Dashboard

Both useful and Not

## How to run

```bash
# Install python
sudo apt install python3 python3-venv

# Create venv
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

# Install requirements
pip3 install -r requirements.txt

# Run tmux
tmux new-session -s dashboard

# Activate venv
source .venv/bin/activate

# Run webserver
python3 webserver.py

# New tmux pane
ctrl b c

# Activate venv
source .venv/bin/activate

# Run serial temperature sensor
python3 serial_reader.py
```