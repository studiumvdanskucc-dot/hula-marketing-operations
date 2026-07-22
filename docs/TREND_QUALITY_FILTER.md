# Trend label quality filter

The dashboard must surface a usable fashion idea rather than a product
department. The filter therefore removes a label when it contains only generic
fashion/category words, is a vague word with no object, or names a platform
instead of a trend.

Examples removed: `bags`, `trousers`, `garments`, `designer bags`, `mini`,
`silhouette`, `chic`, `eBay`.

Examples kept: `black bags`, `red trousers`, `mini bags`, `raffia bags`,
`east–west bags`, `butter yellow`, `knitwear`, `polka dots`.

The rule runs at X phrase extraction, semantic clustering, Google candidate
selection, Google-series scoring and stored-snapshot loading. This prevents an
older snapshot from showing a generic term before the next live refresh.

**Data & Setup → Trend quality filter** displays both the complete permanent
single-term blocklist and the exact de-duplicated audit from the latest refresh,
including where each rejected label was found.
