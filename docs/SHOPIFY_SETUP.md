# Connect the HULA Shopify store

This is the live-catalogue option. The app uses Shopify's read-only Admin GraphQL API. It does not need Apify to read the catalogue, and it does not request customers, orders, payments, or permission to edit products. If the HULA-owned app cannot be installed yet, use the [CSV catalogue route](CSV_CATALOGUE.md) instead.

## Access you need

Ask the store owner to perform these steps or give your Shopify staff account the **App development** permission. Keep the client secret in password-protected company storage.

## Create the API-only app

1. Open the [Shopify Dev Dashboard](https://dev.shopify.com/dashboard). In Shopify Admin, it is also available from the store-name menu under **Dev Dashboard**.
2. Open **Apps**, choose **Create app**, then **Start from Dev Dashboard**.
3. Name it `HULA Trend Intelligence`.
4. Open **Versions** and create a version.
5. For the app URL, keep Shopify's default non-embedded URL. This Streamlit dashboard does not run inside Shopify Admin.
6. Add only these Admin API scopes:
   - `read_products`
   - `read_inventory`
7. Select the newest available webhook/API version and **Release** the version.
8. Return to **Home**, choose **Install app**, select the live HULA store, and approve the two read-only scopes.

Shopify does not apply later scope changes automatically. If you change the app version, HULA's store admin must approve the new scopes again.

## Copy the three settings

1. In the app's **Settings**, copy the **Client ID** and **Client secret**.
2. Find the permanent `*.myshopify.com` domain for the store. The app needs only the subdomain. If the domain is `hula-hk.myshopify.com`, use `hula-hk`.
3. Add these values to Streamlit secrets and GitHub Actions secrets:

```toml
SHOPIFY_SHOP = "hula-hk"
SHOPIFY_CLIENT_ID = "..."
SHOPIFY_CLIENT_SECRET = "..."
SHOPIFY_API_VERSION = "2026-07"
SHOPIFY_STOREFRONT_URL = "https://thehula.com"
```

Do not paste a secret into source code, a Git commit, Slack, or this chat.

## What happens to the token

Current Dev Dashboard apps use Shopify's client-credentials flow. The dashboard exchanges the client ID and secret for a short-lived access token, caches it in memory, and automatically asks for a new one before the 24-hour token expires.

Older custom apps may still have a long-lived Admin access token. The connector supports it through `SHOPIFY_ADMIN_ACCESS_TOKEN`, but the current client-credentials method above is preferred for a new HULA app.

## Test it

1. Open **Data & Setup** in the Streamlit dashboard.
2. Under **Product catalogue**, select **Shopify API**.
3. Select **Test Shopify API**. A successful result displays the connected Shopify shop name without displaying credentials.
4. Keep **Shopify API** selected.
5. Select **Refresh trends + Shopify catalogue**. Live product images, tags, prices, status, and total inventory should replace the CSV or demo catalogue.

## Common errors

- **`shop_not_permitted`**: the app is not installed on this store, it was created under the wrong organisation, or client credentials are not allowed for that shop.
- **Access denied for a product field**: release a version with `read_products` and `read_inventory`, then let the store admin approve it.
- **No products**: confirm products are `ACTIVE`; the connector deliberately excludes draft and archived products.
- **Incorrect product links**: set `SHOPIFY_STOREFRONT_URL` to the public HULA domain and `SHOPIFY_SHOP` to the permanent myshopify subdomain.

Official references: [Dev Dashboard app setup](https://shopify.dev/docs/apps/build/dev-dashboard/create-apps-using-dev-dashboard), [client-credentials access tokens](https://shopify.dev/docs/apps/build/dev-dashboard/get-api-access-tokens), and [Admin GraphQL products](https://shopify.dev/docs/api/admin-graphql/latest/queries/products).
