# Production and HIPAA technical-readiness

## What this application provides

The repository provides technical building blocks: Argon2id password hashes, bearer-session support (adapt to HttpOnly secure cookies in the web BFF), server-side RBAC/ownership checks, immutable order price snapshots, state transition validation, audit-event records, PDF signature/type/size validation, private-object storage keys, and webhook idempotency.

It is **not automatically HIPAA compliant**. Compliance depends on the full deployed system, operations, jurisdictions, policies, risk analysis, workforce training, and signed agreements. Never use real PHI in development or test environments.

## Required before production

- Replace development startup schema creation with reviewed Alembic migrations and CI migration checks.
- Use a HIPAA-eligible cloud architecture only after executing appropriate BAAs. Configure private S3, SSE-KMS, block public access, VPC endpoints, bucket access logging, least-privilege IAM, object retention/lifecycle policy, and a malware scanning pipeline before records become available.
- Put the API behind TLS, WAF/rate limiting, centralized secrets management, network segmentation, database encryption/backups, monitored audit-log retention, and tested incident response.
- Configure a vetted transactional email service under the required agreement; no PHI or medicine detail in subjects or notification bodies.
- Set strong JWT/session secrets, key rotation, secure HttpOnly/SameSite cookies, CSRF protection, email verification and password-reset token storage, MFA (mandatory for admins), user lockout/risk controls, and admin provisioning outside public registration.
- Configure `stripe.checkout.Session.create` with a rotated restricted secret key; verify `Stripe-Signature` using the raw request body and `stripe.Webhook.construct_event`. Store Stripe IDs only—never payment cards or raw payment data.
- Add third-party penetration testing, dependency/SAST/secret scanning, backup restoration tests, accessibility review, audit reviews, data retention/deletion procedures, legal/regulatory review for every fulfilment destination, pharmacy licensing verification, and operational clinical/compliance review.

## Security notes

Document bytes are deliberately not persisted to PostgreSQL. The current development endpoint validates PDF magic bytes and creates only metadata; install a `PrivateStorage` adapter that streams the bytes to a private encrypted bucket and queues an antivirus scan. Do not issue a public URL: authorized server code may request a short-lived signed download URL after writing a document-access audit event.

All monetary calculation happens on the API from accepted quote snapshots. The client never decides checkout totals or payment confirmation. Webhooks are the payment source of truth and event IDs prevent duplicate processing.
