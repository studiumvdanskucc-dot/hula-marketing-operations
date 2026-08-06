# Trend label quality filter

The dashboard must surface a usable fashion idea rather than a product
department or an unrelated topic mentioned by a fashion source. The filter
therefore removes a label when it contains only generic fashion/category words,
is vague, names a platform, or has no clear fashion product, material,
silhouette or style signal.

Examples removed: `bags`, `pants`, `skirt`, `flats`, `polka`, `trousers`,
`outfit ideas`, `dress`, `pretty dress`, `elegant shoes`, `Interior Design`,
`Kindness`, `wellness`, `mini`, `silhouette`, `chic`, `eBay`.

Examples kept: `jeans`, `loafers`, `sandals`, `designer bags`, `black bags`,
`red trousers`, `mini dress`, `mini bags`, `raffia bags`, `east–west bags`,
`puff sleeves`, `butter yellow`, `polka dots`, `Mary Janes`.

The rule runs at publisher title/heading extraction, GPT article extraction,
semantic alias clustering, Google-series scoring and stored-snapshot loading.
This prevents an older snapshot from showing a generic term before the next
live refresh.

**Data & Setup → Trend quality filter** displays both the complete permanent
single-term blocklist and the exact de-duplicated audit from the latest refresh,
including where each rejected label was found.
