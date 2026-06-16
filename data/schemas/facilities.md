# Raw facilities dataset — schema notes

10,000 records, 51 columns. Coverage of evidence fields (from hackathon brief):

| Field | Coverage |
| --- | --- |
| description | 100% |
| capability | 99.7% |
| procedure | 92.5% |
| equipment | 77.0% |
| numberDoctors | 36.4% |
| capacity | 25.2% |
| yearEstablished | 47.8% |

Always-present columns: facility name, state, city, latitude, longitude,
controlled specialties, description, source URLs. 9,996 of 10,000 also have a
postcode.

These are *claims*, not ground truth — the trust-weighting logic in `silver/`
treats them as evidence to score, not facts to trust.
