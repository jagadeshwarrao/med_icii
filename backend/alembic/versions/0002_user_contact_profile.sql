-- Adds editable customer contact details. Run after 0001_initial.sql.
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone varchar;
ALTER TABLE users ADD COLUMN IF NOT EXISTS address jsonb;
