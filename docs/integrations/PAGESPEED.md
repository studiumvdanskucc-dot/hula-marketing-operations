# PageSpeed Insights — read-only setup

Build pin: **PageSpeed Insights API v5**. See the
[official getting-started guide](https://developers.google.com/speed/docs/insights/v5/get-started).

This release contains a configuration/health shell and fixture template results.

## HULA owner actions

1. Approve HULA hosts and priority URLs for homepage, collection, product,
   journal and campaign templates.
2. Create an API key restricted to PageSpeed Insights API and, where practical,
   approved server egress.
3. Install the key directly in worker secrets.

```dotenv
PAGESPEED_API_KEY=
PAGESPEED_STRATEGIES=mobile,desktop
```

Future worker results must store URL, date, strategy, field/lab context,
metrics, diagnostics and API/source version. Run weekly and after material theme
deployments; do not spend quota on every URL from a Streamlit request.
