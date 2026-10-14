# ACLEDA exchange-rate fix — 2026-10-14

The previous parser required both USD and KHR in the first table cell. ACLEDA's compact widget puts USD in the first cell and KHR beside each Bid/Ask value, so a successful HTTP response still failed to parse. The fallback then returned a hard-coded 4,080 quote dated October 9, 2026 on every failure.

The new reader uses ACLEDA's official foreign-exchange page first and its compact widget second. It follows the Buy/Sell or Bid/Ask column headers, validates the currency pair and publication date, and selects the cash-note sell quote (the first labelled cash table), not the Super App or transfer rate. Unlabelled ticker rows and unrelated currency pairs are ignored.

Only quotes actually parsed from the bank are cached in a separate database table. A source publishing an older quote cannot overwrite a newer cached quote. If both sources fail, the endpoint returns the dated cache, or HTTP 503 if no verified quote has ever been fetched. There is no built-in numeric fallback.

The UI keeps displaying the saved conversion rate while loading or on error. A cached fallback is shown with its own amount and date, and does not overwrite the user's saved conversion rate. Successful current-source reads update the display conversion as before. The bank's source link is available in Settings. No transaction amounts or original currencies are changed.

Validation: 24 focused Python cases passed (FX/parser/cache and profile/budget regression checks), plus four Node checks of the actual refresh handler. The official live page was parsed successfully as a real-source integration check. No production personal data or secrets are used in tests. Existing unrelated test-suite failures remain documented in profile-budget-update.md.
