-- Hotfix: align promo codes staging schema with loader (discount_value column)
-- Apply on existing environments where stg_qtickets_api_promo_codes_raw was created without discount_value.

ALTER TABLE zakaz.stg_qtickets_api_promo_codes_raw
    ADD COLUMN IF NOT EXISTS discount_value Nullable(Float64) AFTER discount_type;

-- Local/testing database
ALTER TABLE IF EXISTS zakaz_test.stg_qtickets_api_promo_codes_raw
    ADD COLUMN IF NOT EXISTS discount_value Nullable(Float64) AFTER discount_type;
