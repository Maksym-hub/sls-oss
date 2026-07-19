# Security Policy

## Supported Versions

Polyris is pre-1.0 software. Security fixes are applied to the latest released
version only. We recommend always running the most recent release.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < latest | :x:               |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, report them privately through one of the following channels:

<!-- TODO(release): replace with your real security contact before publishing -->
- **GitHub Security Advisories** (preferred): use the
  ["Report a vulnerability"](https://github.com/polyris/polyris/security/advisories/new)
  button on the repository's *Security* tab.
- **Email**: security@polyris.example  <!-- TODO(release): replace with a real, monitored address -->

Please include as much of the following as you can:

- The type of issue (e.g. injection, privilege escalation, secret exposure, SSRF).
- The affected component (SDK, Console API, generated CloudFormation/Step Functions, UI).
- Step-by-step instructions to reproduce, and a proof-of-concept if possible.
- The impact, including how an attacker might exploit it.

## What to Expect

- **Acknowledgement** within 3 business days.
- An initial assessment and severity classification within 10 business days.
- Coordinated disclosure: we will work with you on a fix and a public advisory,
  and credit you in the release notes unless you prefer to remain anonymous.

Please give us a reasonable window to remediate before any public disclosure.

## Scope

In scope:

- The Polyris SDK (`polyris/`) and its generated Step Functions / CloudFormation output.
- The Console API Lambda (`sam/lambdas/console_api/`) and supporting Lambdas.
- The Console UI (`ui/`).
- Deployment tooling and example infrastructure in this repository.

Out of scope:

- Vulnerabilities in third-party dependencies (report those upstream; we will
  update once a fix is available).
- Issues that require physical access to a user's machine or a compromised AWS
  account.
- Misconfigurations in a user's own AWS environment that are not caused by
  Polyris's defaults.

## `npm audit` findings — dev/build toolchain only

The Console UI ships as a **static export** (Next.js): the deployed site is plain HTML,
CSS, and JavaScript served from S3/CloudFront, with no server and no build or test
toolchain running in production.

The advisories currently reported by `npm audit` are therefore confined to
**development and build dependencies** — `vitest`, `vite`, `esbuild`, and the `postcss`
copy bundled inside `next`. These run only during local development, testing, and the
build step; **none are part of the shipped bundle**, so they do not affect deployed
instances or their users. Several advisories are additionally scoped to a local dev
server or to Windows-only paths, neither of which applies to the deployed artifact.

We treat these as **low-priority, non-runtime** issues. Clearing them fully requires a
major version bump of the test runner (`vitest`), which is a deliberate migration rather
than a patch; it is tracked as routine maintenance. A vulnerability in a **runtime**
dependency — anything that reaches the deployed bundle or the backend Lambdas — is
treated with priority and should be reported as above.
