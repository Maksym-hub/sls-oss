# Alerts

Polyris tells you when a task fails. There are two layers:

1. **Browser notifications** — in-app, automatic, free. Nothing to configure.
2. **Slack / PagerDuty** — configured per-pipeline in the UI under
   **Settings → Alerts** (Team tier).

> **Note (ADR #103).** Alerts used to be declared in the DAG with an `alerts=`
> argument. That argument is **deprecated and ignored** — remove it. All alert
> delivery now lives in the UI, not in code.

## Browser notifications (free)

When a task fails, an in-app notification appears in the console. This is on by
default for every pipeline — there is no setup and no cost. It is the only alert
channel in the free tier.

## Slack & PagerDuty (Team)

Open **Settings → Alerts**, pick a pipeline, and enable the channels you want.

### Slack

| Field | What it does |
| --- | --- |
| **Webhook URL** | Your Slack Incoming Webhook. Stored as an encrypted SSM secret — only the parameter name is kept in the registry, never the URL itself. |
| **Channel mode** | *Default* posts to whatever channel the webhook is bound to. *Custom* overrides it with the channel you type. |
| **Channel** | The channel to post to when mode is *Custom* (e.g. `#data-alerts`). |
| **Mentions** | People or groups to tag on failure — a Slack user ID (`U…`), a user-group ID (`S…`), or `here` / `channel`. |

On a failure you get a message with the pipeline, task, and error, plus action
buttons: **Skip**, **Mark Success**, **Fail**, **Restart**. Clicking one resolves
the paused task directly — the same actions available in the console.

### PagerDuty

| Field | What it does |
| --- | --- |
| **Routing key** | Your PagerDuty Events API v2 routing key. Stored as an encrypted SSM secret — only the parameter name is kept in the registry. |
| **Severity** | One of `critical`, `error`, `warning`, `info`. |

A failure triggers a PagerDuty incident. If the task recovers (you mark it
success/skip), the incident is resolved automatically. A live failure and the
later terminal failure share one incident — you are paged once, not twice.

### Test button

Each channel has a **Test** button that sends a sample alert so you can confirm
the webhook / routing key works before relying on it.

## How a failure flows

When a task fails, it pauses and waits (default 5 hours) for a decision while the
alerts fire:

- Browser notification appears immediately.
- If Slack is enabled, the interactive message (with buttons) is posted.
- If PagerDuty is enabled, an incident is triggered so on-call can act during the
  wait window.

You (or on-call) then **Skip**, **Mark Success**, **Fail**, or **Restart** — from
the console, the browser notification, or the Slack buttons. The pipeline
continues based on that decision. If PagerDuty was triggered and the task is
resolved, the incident is closed.

## Where secrets live

The webhook URL and the PagerDuty routing key are **secrets**. They are written to
**SSM Parameter Store** (SecureString, encrypted). The pipeline's `alert_config`
in the registry stores only the *parameter name* (e.g.
`/polyris/alerts/<pipeline>/slack-webhook`) plus the non-secret settings (channel,
mentions, severity). Reading the registry never exposes a secret.
