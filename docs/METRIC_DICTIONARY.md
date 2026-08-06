# HULA Marketing Operations metric dictionary

Default timezone: **Asia/Hong_Kong**. Default reporting currency: **HKD**.
Source currency, amount, conversion date and conversion-rate source must be
retained when conversion is required.

| Business metric | Technical name | Formula | Source of truth | Attribution | Refresh | Important limitation |
|---|---|---|---|---|---|---|
| Commerce revenue | `shopify_booked_commerce_revenue` | Included Shopify/POS commerce amount under the signed gross/discount/refund/tax/shipping/exclusion rules | Shopify/POS | None; booked commerce | Hourly + nightly reconciliation | Definition must state treatment of refunds, gift cards, tests, staff, exchange and cancelled orders |
| Net revenue | `shopify_net_revenue` | Gross sales − included discounts − included returns/refunds, with tax/shipping treatment stated | Shopify/POS | None | Hourly + nightly | Not interchangeable with provider-attributed revenue |
| Orders | `shopify_included_orders` | Count of distinct included order IDs | Shopify/POS | None | Hourly | The agency fixture has five orders not allocated to displayed locations |
| AOV | `shopify_aov` | Commerce revenue / included orders | Shopify/POS | None | Daily | Median order value is reported separately |
| Median order value | `shopify_median_order_value` | Median included order amount | Shopify/POS | None | Daily | Requires order-level values; cannot be derived from total/AOV |
| New customers | `shopify_new_customers` | Customers whose first included order is in the period | Shopify | None | Daily | Protected customer access and identity rules may apply |
| Repeat revenue share | `shopify_repeat_revenue_share` | Revenue from returning customers / included commerce revenue | Shopify | None | Daily | Depends on the signed new/returning definition |
| Historical realized CLV | `historical_realized_customer_value` | Historical included revenue / included customers for the stated observation window | Shopify | None | Monthly | Not predictive CLV; not contribution margin unless cost data exists |
| Paid spend | `paid_media_spend` | Included Google Ads cost + Meta Ads spend | Google Ads + Meta | None | 4–6 hourly + daily final | Agency fees and creative production are excluded unless separately configured |
| Platform paid revenue | `platform_paid_conversion_value` | Google Ads conversion value + Meta purchase value, shown with each platform's window | Google Ads + Meta | Provider-specific | 4–6 hourly + daily final | Platforms can overlap; never compare as booked revenue without a reconciliation view |
| Blended paid ROAS | `platform_paid_roas` | Platform paid revenue / paid spend | Google Ads + Meta | Provider-specific | Daily | Email revenue is excluded; window differences remain visible |
| MER | `marketing_efficiency_ratio` | Included Shopify/POS commerce revenue / included paid-media spend | Shopify + paid media | Blended efficiency, not attribution | Daily | Revenue and spend inclusions must be versioned |
| Spend per all new customer | `spend_per_all_new_customer` | Included paid-media spend / all Shopify new customers | Shopify + paid media | Efficiency proxy | Daily/monthly | Not CAC; includes in-store and potentially organic new customers |
| True paid CAC | `paid_new_customer_cac` | Included paid-media spend / deduplicated new customers attributable to paid media | Governed identity + attribution layer | Agreed paid attribution | Daily/monthly | Unavailable until paid-acquired customer identity is reliable |
| Google Ads ROAS | `google_ads_platform_roas` | Google Ads conversion value / Google Ads cost | Google Ads | Account conversion actions/window | 4–6 hourly | Conversion-action set and currency/timezone must be captured |
| Meta ROAS | `meta_platform_roas` | Meta purchase value / Meta spend | Meta | Actual account attribution setting | 4–6 hourly | View-through attribution may overlap other channels |
| Klaviyo attributed revenue | `klaviyo_attributed_revenue` | Revenue returned by the selected Klaviyo reporting metric | Klaviyo | Configured Klaviyo window | 6–12 hourly + daily | Campaign/flow attribution can overlap commerce and other channels |
| Organic-search revenue | `ga4_organic_attributed_revenue` | GA4 purchase revenue assigned to Organic Search under the selected reporting attribution | GA4 | GA4 reporting identity/model | Daily | Search Console has no revenue and is not substituted |
| Search CTR | `gsc_weighted_ctr` | Sum clicks / sum impressions | Search Console | None | Daily after lag | Weighted calculation; average of row CTRs is wrong |
| Search position | `gsc_weighted_position` | Sum(position × impressions) / sum impressions | Search Console | None | Daily after lag | Grouping by property/page can change interpretation |
| Email revenue per recipient | `klaviyo_revenue_per_recipient` | Attributed conversion value / delivered recipients | Klaviyo | Configured window | Daily | Small targeted sends need sample-size context |
| AI-referral sessions | `ga4_ai_referral_sessions` | GA4 sessions matching a versioned source/referrer classifier | GA4 | Session attribution | Daily | Does not expose prompts, citations or dark/direct traffic |
| GBP direction requests | `gbp_direction_requests` | Provider-reported direction actions | Google Business Profile | None | Daily | Not verified physical-store visits |

## Fixture reconciliation facts

The bundled July 2026 fixture intentionally preserves report defects as a
quality-control example:

- executive revenue: HK$2,490,383.00;
- displayed location sum: HK$2,520,529.56;
- unexplained difference: HK$30,146.56;
- headline orders: 409;
- displayed store-order sum: 404.

These are not normalized away. The reconciliation screen requires a reviewer
reason and source/filter evidence.

The corrected fixture also records that the four displayed channel rows total
HK$1,337,083.87, only 53.69% of headline commerce revenue, while Klaviyo uses a
90-day attribution window and Meta uses seven days. These rows are separate,
overlapping attribution views—not a complete channel split.

The supplied report's analytics page states 57,585 session starts, 56,127 page
views, 35,081 view-item events and 851 add-to-cart events. Shopify separately
states 1,459 add-to-carts and 84 online orders. The platform does not invent a
347-checkout count or join these sources into a complete funnel.
