# queuer

A Discord bot for queueing questions to be sent on an interval.

## Setup

1. Copy `.env.example` to `.env` and fill in the Discord values.
2. Install dependencies:

```bash
make install
```

For editable development installs:

```bash
make dev
```

## Run

The bot reads configuration from `.env` and initializes the SQLite database automatically on startup.

```bash
make run
```

## Check

Run a basic Python compilation check:

```bash
make check
```

