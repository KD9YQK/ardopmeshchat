# chat_daemon.py

Headless ARDOP mesh chat **daemon** entrypoint.

This script runs the existing mesh chat backend without any GUI and without any user input.

## What it does

When running, the daemon:

- Participates as a normal mesh node (OGMs, forwarding, dedup, ordering)
- Receives and stores chat messages in the existing SQLite database
- Performs gap detection and recovery (including targeted/range sync if enabled in config)
- Responds to sync requests from peers
- Logs activity to **stdout**
- Runs indefinitely until terminated (SIGINT/SIGTERM), then shuts down cleanly

## Requirements

- Python 3.x (same version you use for the rest of the project)
- Project dependencies already used by the system (e.g., PyYAML via `config_loader.py`)
- A valid `config.yaml` (or `--config <path>`)

## Usage

```bash
python3 chat_daemon.py [--config PATH] [--callsign CALLSIGN] [--db-path PATH] [-v|-vv]
```

### Command-line options

- `--config PATH`  
  Path to `config.yaml`. Default: `config.yaml`

- `--callsign CALLSIGN`  
  Overrides `mesh.callsign` from the YAML **at runtime** (does not modify the YAML).

- `--db-path PATH`  
  Overrides `chat.db_path` from the YAML **at runtime**.
  - If the path is relative, it is resolved relative to the config file directory.
  - If the path is absolute, it is used as-is.

- `-v`, `-vv`  
  Logging verbosity:
  - `-v` (default) → INFO
  - `-vv` → DEBUG
  - `-v` omitted / verbosity lower → WARNING

## Examples

### 1) Run using default `config.yaml`

```bash
python3 chat_daemon.py
```

### 2) Run with an explicit config path

```bash
python3 chat_daemon.py --config /opt/mesh/config.yaml
```

### 3) Override callsign (runtime only)

```bash
python3 chat_daemon.py --callsign N0CALL-7
```

### 4) Override database path (relative to config directory)

```bash
python3 chat_daemon.py --db-path ./data/chat.sqlite
```

### 5) Override database path (absolute)

```bash
python3 chat_daemon.py --db-path /var/lib/mesh/chat.sqlite
```

### 6) Override both callsign and DB path

```bash
python3 chat_daemon.py --callsign GATE-VHF --db-path ./vhf.sqlite
```

### 7) Increase log verbosity

```bash
python3 chat_daemon.py -vv
```

## Running multiple instances (same host)

If you run multiple daemons on the same machine, use **different callsigns** and **different DB paths** to avoid collisions:

```bash
python3 chat_daemon.py --callsign GATE-VHF --db-path ./vhf.sqlite --config ./vhf.yaml
python3 chat_daemon.py --callsign GATE-HF  --db-path ./hf.sqlite  --config ./hf.yaml
```

Each instance will behave as a distinct mesh node.

## Output format

The daemon drains the backend UI event queue and prints:

- Status events:
  ```
  [STATUS] ...
  ```
- Chat events:
  ```
  [YYYY-MM-DD HH:MM:SS] #channel <NICK> message text
  ```
- Node list updates:
  ```
  [NODES] N: ...
  ```
- Channel list updates:
  ```
  [CHANNELS] N: ...
  ```
- History snapshots (minimal):
  ```
  [HISTORY] <channel>: <count> message(s)
  ```

## Shutdown

The daemon exits cleanly on:

- `SIGINT` (Ctrl+C)
- `SIGTERM` (service stop / kill)

On shutdown it calls `backend.shutdown()` and allows a short delay for threads to wind down.

## Notes

- This daemon is intentionally **non-interactive**: no stdin, no REPL, no commands.
- It is designed to reuse the same backend stack used by the GUI.
- Sending chat messages is not supported by this entrypoint (by design).
