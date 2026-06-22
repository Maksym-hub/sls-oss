# Deployment Drill

A **hands-on exercise**, not a command reference. Its job is to (a) prove the
deploy + recovery path actually works end-to-end and (b) transfer operational
knowledge so deploy is never a one-person dependency. Run it with the incoming
co-maintainer (Myroslav) driving and the current operator observing.

For the underlying commands see
[`getting-started/SETUP_FROM_SCRATCH.md`](../getting-started/SETUP_FROM_SCRATCH.md)
and [`getting-started/QUICKSTART.md`](../getting-started/QUICKSTART.md); for the
accounts/credentials see [`ACCESS_INVENTORY.md`](./ACCESS_INVENTORY.md); for
break-glass see [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

> **Setup:** do this against a **scratch/dev** stack (e.g. `slsflow-drill`), never
> the live `slsflow-dev`, so a mistake costs nothing. Tear it down at the end.

---

## Part A — Cold-start deploy (driver: co-maintainer)

The driver should reach a working console **from a clean machine** using only the
docs, while the observer notes anything missing or surprising.

- [ ] **Access confirmed** — driver has their own AWS profile, console login, and
      GitHub access per `ACCESS_INVENTORY.md` (not the observer's).
- [ ] **Clone** via the SSH alias: `git@github-maksym-hub:Maksym-hub/slsflow.git`.
      (Plain `git@github.com` picks the wrong identity — confirm the driver hit or
      avoided this.)
- [ ] **Restore the symlink** — after a fresh checkout confirm
      `sam/lambdas/console_api/slsflow` is a symlink to `../../../slsflow` (git mode
      `120000`). If a tool flattened it: `rm -f` then
      `ln -s ../../../slsflow sam/lambdas/console_api/slsflow`.
- [ ] **Toolchain** — Python 3.11+, Node 22+, AWS SAM CLI, AWS CLI v2 installed.
- [ ] **Configure** — `sam/samconfig.toml` profile + region (`slsflow-dev` /
      `us-east-1`), stack name overridden to the **drill** stack.
- [ ] **Deploy backend** — `sam build` (must work **without** `--use-container`;
      pure-Python deps only, ADR #65) then `sam deploy`. Stack reaches
      `CREATE_COMPLETE`.
- [ ] **Deploy UI** — `cd ui && npm ci && npm run build`, sync the static export to
      the UI S3 bucket, invalidate CloudFront. Point `.env.local`'s
      `API_GATEWAY_URL` at the drill API.
- [ ] **First pipeline** — `slsflow-init` a sample pipeline, `slsflow-deploy` it,
      trigger a run.

## Part B — Verify it actually works

- [ ] `GET /api/health` returns OK against the drill API Gateway URL.
- [ ] Console loads (CloudFront URL), lists the deployed pipeline.
- [ ] The sample run reaches success in Step Functions; the asset/run shows in the
      console.
- [ ] (If auth enabled) a Cognito test user can sign in.

## Part C — Recovery / break-glass (driver, observer prompts)

The point is to practise failure, not just happy-path.

- [ ] **Roll back a bad deploy** — make a trivial template change that fails to
      deploy, and recover (CFN rollback / redeploy the prior good revision). Driver
      narrates how they'd know it failed and where the logs are.
- [ ] **Find a failed execution** — open a failed Step Functions execution, read
      the error, locate the relevant CloudWatch logs. (This is the most common real
      incident — see `TROUBLESHOOTING.md`.)
- [ ] **Secret rotation dry-run** — talk through rotating one secret from
      `ACCESS_INVENTORY.md` §2 and where it's referenced.

## Part D — Sign-off

- [ ] Observer confirms the driver completed A–C **unaided** (docs + AWS console
      only).
- [ ] Every "missing or surprising" note from the observer is filed as a docs fix
      (update `SETUP_FROM_SCRATCH.md` / `TROUBLESHOOTING.md` / this drill).
- [ ] Driver added to the deploy roster in `ACCESS_INVENTORY.md` §5.
- [ ] **Drill stack torn down** (`sam delete` / delete the CFN stack + empty the
      drill S3 bucket).

| | Name | Date |
|---|---|---|
| Driver (co-maintainer) | | |
| Observer (operator) | | |

> Re-run this drill when the deploy path changes materially, or at least once
> before the public release so two people can deploy and recover independently.
