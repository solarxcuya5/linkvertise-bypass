# Linkvertise Bypasser

Bypasses linkvertise links by accessing their internal GraphQL API,
without the need of a browser.

# Example Usage

## Basic single URL

```python
import linkvertise_bypasser as linkvertise

ad_url = "https://linkvertise.com/12345/example"
url = linkvertise.bypass(ad_url)
```

## From User ID and Post name

```python
import linkvertise_bypasser as linkvertise

post = linkvertise.Post(12345, "example")
url = linkvertise.get_url(post)
```

## Keeping session between requests

```python
import requests
import linkvertise_bypasser as linkvertise

session = requests.Session()
for ad_url in urls:
	url = linkvertise.bypass(ad_url, session=session)
```