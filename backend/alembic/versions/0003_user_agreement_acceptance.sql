-- Records the version and time of explicit User Agreement acceptance at registration.
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreement_version varchar;
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreement_accepted_at timestamp;
