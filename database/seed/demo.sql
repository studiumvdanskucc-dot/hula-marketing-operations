-- Optional non-production seed. Never run in a production project.
-- Demo application records are normally generated in the local SQLite fallback.

insert into public.metric_definitions(
  technical_name, business_name, formula, source_system,
  refresh_cadence, owner, limitations
) values
  ('shopify_booked_commerce_revenue', 'Commerce revenue', 'Included Shopify/POS net sales under the signed refund, tax, shipping and exclusion rules', 'Shopify', 'Hourly incremental; nightly reconciliation', 'Finance / Ecommerce', 'Not a marketing attribution value'),
  ('platform_paid_roas', 'Blended paid ROAS', '(Google Ads platform conversion value + Meta platform purchase value) / paid-media spend', 'Google Ads + Meta Ads', 'Every 4–6 hours; daily finalization', 'Paid Media Specialist', 'Platforms can overlap and use different attribution windows'),
  ('marketing_efficiency_ratio', 'MER', 'Shopify net sales / included paid-media spend', 'Shopify + paid media', 'Daily', 'Marketing Operations', 'Inclusions must be versioned')
on conflict (technical_name) do nothing;
