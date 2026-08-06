# Shopify Admin GraphQL — read-only setup

Pinned API version: **2026-07**, the latest stable version observed on 6 August
2026. Recheck [Shopify's versioned API reference](https://shopify.dev/docs/api/admin-graphql/latest)
before release.

## HULA owner actions

1. Confirm the permanent `*.myshopify.com` domain, organization, store,
   locations, Markets/currencies and historical start date.
2. Create a HULA-owned custom app in the Shopify Dev Dashboard/Admin.
3. Request only required read scopes. Initial candidates are `read_products`,
   `read_inventory`, `read_locations` and `read_orders`. Add `read_all_orders`,
   `read_customers` or `read_reports` only after HULA approves the need and any
   protected-customer-data requirements.
4. Install the app and place its token directly into deployment secret storage.
   Do not send it in chat or commit it.

```dotenv
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_API_VERSION=2026-07
SHOPIFY_ADMIN_ACCESS_TOKEN=
SHOPIFY_READ_ONLY=true
```

The implemented client tests `shop` and reads orders, refunds and line-item
aggregates. It does not request customer names, email, phone or addresses. Run
**Settings → Connections → Shopify → Test connection**. A successful
test is still not a completed historical sync or reconciliation.

No Shopify mutation exists in this release.
