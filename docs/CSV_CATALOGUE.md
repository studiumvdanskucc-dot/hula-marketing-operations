# Use a product CSV catalogue

This is the fastest route when the Shopify API app is not installed yet. Uploading a CSV does not change Shopify or the original file.

## Shopify export

1. In Shopify, open **Products**.
2. Select the products or current page and choose **Export**.
3. Export as **CSV for Excel, Numbers, or another spreadsheet program**.
4. In the dashboard, open **Data & Setup → Product catalogue**.
5. Select **Upload CSV**, choose the file and review the normalised preview.
6. Select **Use this CSV catalogue**.

The importer recognises Shopify fields such as `Handle`, `Title`, `Body (HTML)`, `Vendor`, `Type`, `Tags`, `Status`, `Variant Inventory Qty`, `Variant Price`, `Image Src` and `Image Alt Text`. Multiple variant rows with the same handle become one product. Inventory is summed and the lowest listed variant price is used.

## Simple CSV

Select **Download simple CSV template** in the dashboard. The recommended columns are:

| Column | Purpose |
| --- | --- |
| `title` | Required product name |
| `vendor` | Designer or brand |
| `product_type` | Bag, dress, shoes, accessory and so on |
| `status` | `ACTIVE`, `DRAFT` or `ARCHIVED`; defaults to `ACTIVE` |
| `inventory` | Available quantity; if omitted, the preview clearly warns that 1 is assumed |
| `price` / `currency` | Display price and currency, such as `HKD` |
| `tags` | Comma-, semicolon- or pipe-separated attributes |
| `description` | Product copy used for relevance matching |
| `image_url` | Public product image URL |
| `product_url` | Public storefront link |
| `handle` | Stable slug; generated from the title if omitted |
| `created_at` | Optional ISO date for the freshness component |

Friendly alternatives such as `Product Name`, `Brand`, `Category`, `Quantity`, `Stock`, `Keywords` and `Image URL` are also recognised.

## What is saved

The app saves only the normalised product fields inside `data/latest_snapshot.json`; it does not keep a second copy of the raw uploaded CSV. Future Wednesday refreshes reuse that catalogue until a replacement CSV is applied or the team switches to the Shopify API.

The importer accepts files up to 150 MB and 400,000 source rows. Large Shopify
exports are read using only the catalogue columns the dashboard needs, which
keeps memory usage manageable. Review warnings before applying the catalogue,
especially missing inventory, images or created dates.
