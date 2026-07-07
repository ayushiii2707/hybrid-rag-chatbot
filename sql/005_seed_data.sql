-- =============================================================================
-- 005_seed_data.sql
-- Seed Data Documentation
-- =============================================================================
--
-- Source: backend/main.py lines 74-89 (lifespan handler)
--
-- The application seeds default user accounts at startup for manual
-- validation and testing. These users are only created if they do not
-- already exist (checked by email).
--
-- Password hashing: bcrypt via backend/auth/password_service.py
--
-- ⚠️  SECURITY NOTE:
-- DO NOT store real passwords or hashes in this file.
-- The application generates bcrypt hashes at runtime via register_user().
-- Replace <BCRYPT_HASH> placeholders with actual hashes during deployment,
-- or rely on the application's automatic seeding in main.py.
-- =============================================================================


-- =============================================================================
-- SEED USERS
-- =============================================================================
--
-- These accounts are created by the lifespan handler in main.py using
-- the register_user() function, which bcrypt-hashes the password before
-- inserting. Below are the logical INSERT equivalents with placeholder
-- hashes since actual bcrypt output varies per invocation.
--
-- To generate a valid hash for deployment:
--   python -c "from bcrypt import hashpw, gensalt; print(hashpw(b'<PASSWORD>', gensalt()).decode())"
-- =============================================================================

-- Default vendor accounts
INSERT INTO users (id, email, hashed_password, role, status, created_at)
VALUES (
    gen_random_uuid(),
    'ayushir2707@gmail.com',
    '<BCRYPT_HASH>',  -- Replace with bcrypt hash at deployment time
    'vendor',
    'active',
    now()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, hashed_password, role, status, created_at)
VALUES (
    gen_random_uuid(),
    'swadha945@gmail.com',
    '<BCRYPT_HASH>',  -- Replace with bcrypt hash at deployment time
    'vendor',
    'active',
    now()
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, hashed_password, role, status, created_at)
VALUES (
    gen_random_uuid(),
    'ayushihihi7@gmail.com',
    '<BCRYPT_HASH>',  -- Replace with bcrypt hash at deployment time
    'vendor',
    'active',
    now()
) ON CONFLICT (email) DO NOTHING;

-- Default admin account
INSERT INTO users (id, email, hashed_password, role, status, created_at)
VALUES (
    gen_random_uuid(),
    'admin@ril.com',
    '<BCRYPT_HASH>',  -- Replace with bcrypt hash at deployment time
    'admin',
    'active',
    now()
) ON CONFLICT (email) DO NOTHING;


-- =============================================================================
-- SEED DATA SUMMARY
-- =============================================================================
--
-- Total seed records: 4 users
--
-- | Email                     | Role   | Notes                          |
-- |---------------------------|--------|--------------------------------|
-- | ayushir2707@gmail.com     | vendor | Default test account           |
-- | swadha945@gmail.com       | vendor | Default test account           |
-- | ayushihihi7@gmail.com     | vendor | Default test account           |
-- | admin@ril.com             | admin  | Default admin account          |
--
-- All passwords are bcrypt-hashed at runtime by the application.
-- See backend/main.py lifespan handler for the seeding logic.
--
-- No other seed data (roles, permissions, configuration, lookup tables)
-- was found in the codebase.
-- =============================================================================
