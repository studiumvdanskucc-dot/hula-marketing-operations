# Connect the rolling X fashion listener

The app is designed for the Apify Actor **X Tweet Scraper by ScrapeBadger**:

```text
scrape.badger/twitter-tweets-scraper
```

This Actor accepts X Advanced Search syntax through `query`, returns post dates,
authors and engagement fields, and supports API-driven Task runs. Actor pricing,
availability and terms can change, so confirm them in Apify before each major
increase in collection volume.

## 1. Create the saved Task

1. Open <https://apify.com/scrape.badger/twitter-tweets-scraper>.
2. Choose **Try for free**.
3. Set **Mode** to `Advanced Search`.
4. Use a harmless test query such as:

   ```text
   "fashion trend" lang:en -filter:replies -filter:nativeretweets
   ```

5. Set **Query type** to `Latest` and **Max results** to `10`.
6. Run it once and confirm the Dataset contains tweet text, creation time and
   author/engagement fields.
7. Save the input as a Task named `hula-weekly-fashion-x`.
8. Open the Task's **Settings** and copy the actual **Task ID**. Do not use the
   Apify user ID.
9. Open **Settings → Integrations → API tokens** and copy a token for this app.

The Task supplies the Actor and any stable extra settings. During a refresh,
the app overrides only `mode`, `query`, `query_type` and `max_results` for each
planned search.

## 2. Add the settings

For `.streamlit/secrets.toml`:

```toml
APIFY_TOKEN = "YOUR_COMPLETE_TOKEN"
APIFY_X_TASK_ID = "YOUR_REAL_TASK_ID"
APIFY_X_TASK_INPUT_JSON = "{}"
APIFY_TIMEOUT_SECONDS = "480"
APIFY_X_MEMORY_MB = "512"

APIFY_X_LISTENING_MODE = "topic_plan"
APIFY_RESULTS_PER_QUERY = "50"
APIFY_EXPERT_RESULTS_PER_QUERY = "35"
APIFY_MAX_TOTAL_CHARGE_USD = "0.25"
X_LANGUAGE = "en"
X_PRIORITY_ACCOUNTS = "WhoWhatWear,WhoWhatWearUK,Lyst"
X_EXPERT_ACCOUNTS = "VogueRunway,VogueBusiness,BoF,WGSN,HYPEBEAST,Highsnobiety,Fashionista_com,Dazed,i_D,BritishVogue,VogueHongKong,TatlerAsia,VestiaireCo,therealreal"
```

`APIFY_MAX_TOTAL_CHARGE_USD` is a ceiling for each individual Actor run, while
`max_results` is the tighter practical limit for this pay-per-result Actor.
The default weekly plan requests no more than 710 returned posts across all
searches before duplicates are removed.

## 3. What the app searches

The plan avoids relying on only hashtags or only profiles. It contains:

| Layer | Purpose | Windows |
| --- | --- | --- |
| Products | Bags, shoes, dresses, jewellery and accessories | Current 7 days + previous 7 days |
| Colours & materials | Open-ended colour, fabric, print and texture language | Current + previous |
| Shapes & silhouettes | Open-ended bag, shoe, dress, skirt, trouser and denim proportions | Current + previous |
| Aesthetics | Emerging aesthetic, runway, street-style and vintage language | Current + previous |
| Fresh publisher validation | Up to 12 current names discovered from the approved publisher panel | Current + previous |
| Commercial priority | Who What Wear, Who What Wear UK and Lyst at 3× evidence weight | Current + previous |
| Supporting panel | A configurable set of fashion/editorial and resale sources at 1× | Current + previous |

When the publisher panel yields no usable names, the fifth open family falls
back to general styling/resale discovery. The dynamic family replaces that
fallback rather than adding paid runs, so the governed run count is unchanged.

Each date window is an independent Advanced Search. This prevents a single
`Latest` result set from filling almost entirely with the newest posts and makes
week-on-week growth measurable.

## 4. Test before a paid refresh

1. Restart Streamlit after saving the settings.
2. Open **Data & Setup → X listening design** and review the planned searches.
3. Click **Test Apify task**.
4. The green result should identify:

   ```text
   scrape.badger/twitter-tweets-scraper
   ```

5. Run one refresh.
6. In Apify, inspect the runs, total returned items and actual USD usage.
7. Reduce `APIFY_RESULTS_PER_QUERY` before increasing refresh frequency.

The default configuration is intentionally small. At the Actor's advertised
price of roughly USD 0.15 per 1,000 returned tweets, 710 results represent about
USD 0.11 in result fees, although Apify platform usage and future pricing can
change. The app preserves successful searches if one query window fails and
reports the precise failed window in **Refresh notes**.

Every X run explicitly requests 512 MB and receives a server-side timeout. If
the app stops waiting or a polling request fails, it attempts to abort that run
so its memory is released. A 402 capacity response stops the rest of the plan
immediately; it is shown once rather than repeated for every remaining query.

After a 402 memory error, open **Data & Setup → Apify X run capacity**. Check the
active HULA runs, stop them if no other HULA refresh is intentionally running,
wait about 15 seconds, and check again. Jobs outside the configured HULA task
must be handled from Apify Console.

## 5. Privacy and noise controls

Raw post text is used only in memory for topic detection. Raw author IDs and
handles are one-way hashed in memory so the system can measure independent
author breadth and dominance. The saved snapshot contains aggregate topic
metrics only—no raw posts, handles or author hashes.

The pipeline also:

- removes the same post returned by several searches;
- measures unique authors, not only post volume;
- uses engagement per view when view counts exist;
- scores the commercial-priority and supporting panels separately from open discovery;
- penalises promotional, duplicate and author-dominated evidence;
- compares the current seven days with a non-overlapping previous seven days.

Official references: <https://apify.com/scrape.badger/twitter-tweets-scraper>
and <https://docs.apify.com/api/v2/actor-task-runs-post>.
