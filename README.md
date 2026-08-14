# GIPPO Telegram Bot

A small private Telegram bot that signs in to the GIPPO loyalty cabinet and
shows:

- the current discount;
- purchases in the current month;
- the amount remaining until the next level.

The bot uses Telegram long polling, so it does not need a public HTTP endpoint.
Access is restricted to an explicit allow-list of Telegram user IDs.

## Commands

- `/start` — open the bot and show the current values;
- `/status` — refresh the values from the GIPPO cabinet.

The message also has an **Обновить** button.

## Local setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"  # Windows
cp .env.example .env
```

On Linux, activate `.venv/bin/activate` or invoke `.venv/bin/python` directly.
Load the variables from `.env`, then run:

```bash
gippo-check --json
gippo-bot
```

`gippo-check` verifies the cabinet integration without requiring a Telegram bot
token. Do not commit `.env`; it contains both the cabinet password and bot token.

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | bot only | Token issued by BotFather |
| `TELEGRAM_ALLOWED_USER_IDS` | bot only | Comma-separated Telegram numeric user IDs |
| `GIPPO_LOGIN` | yes | GIPPO cabinet login/phone |
| `GIPPO_PASSWORD` | yes | GIPPO cabinet password |
| `GIPPO_BASE_URL` | no | Defaults to `https://cabinet.gippo.by` |
| `GIPPO_TIMEOUT_SECONDS` | no | Request timeout, defaults to 20 seconds |
| `LOG_LEVEL` | no | Python log level, defaults to `INFO` |

The bot refuses to start if the allow-list is empty. Failed HTTP responses and
page bodies are not logged, avoiding accidental disclosure of cabinet data.

## Tests

```bash
python -m pytest
ruff check .
```

## Linux deployment

The included user-level systemd unit follows the deployment layout on the
target host: the checkout is `/srv/bots/gippo-bot/app`, the virtual environment
is `/srv/bots/gippo-bot/venv`, and secrets live in the owner-readable
`/srv/bots/gippo-bot/.env` file.

```bash
mkdir -p /srv/bots/gippo-bot
git clone https://github.com/Kabaye/gippo-bot.git /srv/bots/gippo-bot/app
python3 -m venv /srv/bots/gippo-bot/venv
/srv/bots/gippo-bot/venv/bin/python -m pip install /srv/bots/gippo-bot/app
chmod 600 /srv/bots/gippo-bot/.env
mkdir -p ~/.config/systemd/user
cp /srv/bots/gippo-bot/app/deploy/gippo-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gippo-bot.service
```

Check it with `systemctl --user status gippo-bot.service` and
`journalctl --user -u gippo-bot.service`. The service runs entirely as the
unprivileged `apps` user and restarts automatically after transient failures.
