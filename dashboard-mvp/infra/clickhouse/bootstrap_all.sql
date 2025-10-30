/*
  Deprecated wrapper.

  Use the two-step flow instead:
    1. bootstrap_schema.sql
    2. bootstrap_roles_grants.sql

  This file remains only to guide legacy automation that still invokes it.
*/

SELECT 'bootstrap_all.sql is deprecated. Run bootstrap_schema.sql and bootstrap_roles_grants.sql instead.' AS message;
