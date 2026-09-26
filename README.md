# queuer

A Discord bot for queueing questions to be sent on an interval.

- `/qotd-set-channel` — choose the channel where scheduled QOTDs are posted.
- `/qotd-set-schedule` — set the daily posting time and timezone.
- `/qotd-disable-schedule` — disable the daily default schedule.
- `/qotd-config` — inspect the persisted bot configuration snapshot.
- `/qotd-confirm` — enqueue a draft and optionally provide a per-question `schedule_date`, `schedule_time`, and `timezone` override.

## Setup

1. Copy `.env.example` to `.env` and fill in the Discord values.
2. Install dependencies:

For container runs, prefer unquoted values in `.env` (for example, `GUILD_ID=1234567890`). The app now tolerates quoted values too, but plain `KEY=value` is the least surprising format across tools.

```bash
make install
```

For editable development installs:

```bash
make dev
```

### Run

The bot reads configuration from `.env` and initializes the SQLite database automatically on startup.

```bash
make run
```

### Docker

1. Copy `.env.example` to `.env` and fill in the Discord values.
1. Build the image:

```bash
make docker-build
```

`make docker-build` uses the local container engine directly, so it works with either Docker or Podman.

1. Start the bot container:

```bash
make docker-up
```

> [!NOTE]
>
> `make docker-up`, `make docker-down`, and `make docker-logs` use direct Podman or Docker container commands instead of Compose, which avoids Podman's Docker-compatible compose socket issues.
> 
> On Linux bind mounts, the container is started as your host UID/GID, and Podman uses `--userns keep-id`, so the SQLite file in `./data` stays writable.
> 
> SQLite data is persisted in `./data` on the host.

To follow logs:

```bash
make docker-logs
```

To stop the container:

```bash
make docker-down
```

### Check

Run a basic Python compilation check:

```bash
make check
```
