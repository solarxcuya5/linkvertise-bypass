from typing import Optional
import urllib.parse as urllib
from importlib import resources
import time

import requests, random, string, pathlib, logging
from . import templates

logger = logging.getLogger(__name__)
path = resources.files(templates)

with open(path / "gdpc_query_min.graphql") as f:
	GDPC_QUERY = f.read()
	
with open(path / "cdpc_query_min.graphql") as f:
	CDPC_QUERY = f.read()

with open(path / "gdpt_query_min.graphql") as f:
	GDPT_QUERY = f.read()

# Load user agents from a bundled CSV file (one UA per line).
# Lines starting with '#' or empty lines are ignored.
try:
	with open(path / "user_agents.csv", encoding="utf-8") as f:
		_USER_AGENTS = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
except FileNotFoundError:
	# Fallback single UA if the file is not present
	_USER_AGENTS = [
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
	]

def get_random_user_agent() -> str:
	"""Return a random User-Agent from the loaded list."""
	if not _USER_AGENTS:
		# safety fallback
		return "Mozilla/5.0 (compatible; LinkvertiseBypass/1.0; +https://example.com/bot)"
	return random.choice(_USER_AGENTS)

# Keep Origin and Referer here, but DO NOT include a static User-Agent.
default_headers = {
	"Origin": "https://linkvertise.com",
	"Referer": "https://linkvertise.com",
}

LINKVERTISE_HOSTS = [
	"linkvertise.com",
	"link-target.net",
	"link-center.net",
	"link-hub.net",
	"direct-link.net",
]

class RandomUserAgentSession(requests.Session):
	"""requests.Session that picks a random User-Agent at session creation and uses it for all requests.

	Behavior:
	- Picks one UA per session (so multiple requests in same session are consistent).
	- Merges default_headers with any headers provided to the request.
	"""
	def __init__(self, *, force_user_agent: Optional[str] = None):
		super().__init__()
		# choose one UA for the lifetime of this session (or use provided one)
		self._ua = force_user_agent if force_user_agent else get_random_user_agent()

	def request(self, method, url, **kwargs):
		# Get headers provided for this call (if any)
		req_headers = kwargs.pop("headers", {}) or {}
		# Start from module defaults, then update with per-call headers
		merged = dict(default_headers)
		merged.update({k: v for k, v in req_headers.items() if v is not None})

		# Use the session's fixed User-Agent
		merged["User-Agent"] = self._ua

		# Put merged headers back into kwargs and proceed
		kwargs["headers"] = merged
		# Optional: log UA for debugging
		logger.debug("Request %s %s with User-Agent: %s", method, url, self._ua)
		return super().request(method, url, **kwargs)

class Post:
	"""Represents a Linkvertise post, consisting of a user id and a post id"""
	POST_URL: str = "https://linkvertise.com"
 
	user: str
	id: str
	
	def __init__(self, user: str, id: str):
		if len(user) != 6:
			raise ValueError("user must be 6 characters long: " + user)
		self.user = user
		self.id = id

	def __str__(self) -> str:
		return f"{self.POST_URL}/{self.user}/{self.id}"

	def __repr__(self) -> str:
		return f"Post({self.user}, {self.id})"

def access_token_request(post: Post) -> dict:
	return {
		"operationName": "getDetailPageContent",
		"variables": {
			"linkIdentificationInput": {
				"userIdAndUrl": {
					"user_id": post.user,
					"url": post.id
				}
			},
			"origin": "sharing",
			"additional_data": {
				"taboola": {
					"user_id": "fallbackUserId",
					"url": str(post),
				}
			}
		},
		"query": GDPC_QUERY
	}

def post_access_token_request(access_token: str, post: Post) -> dict:
	return {
		"operationName": "completeDetailPageContent",
		"variables": {
			"linkIdentificationInput": {
				"userIdAndUrl": {
					"user_id": post.user,
					"url": post.id
				}
			},
			"completeDetailPageContentInput": {
				"access_token": access_token
			}
		},
		"query": CDPC_QUERY
	}

def post_detail_request(post_token: str, post: Post) -> dict:
	return {
		"operationName": "getDetailPageTarget",
		"variables": {
			"linkIdentificationInput": {
				"userIdAndUrl": {
					"user_id": post.user,
					"url": post.id
				}
			},
			"token": post_token
		},
		"query": GDPT_QUERY
	}

def __process_errors(obj: dict):
	# Log full GraphQL response when there are errors to help debugging
	if "errors" in obj:
		logger.debug("GraphQL response with errors: %s", obj)
		for error in obj["errors"]:
			# raise with the provided message but keep the full object in DEBUG log
			raise ValueError("error: " + error.get("message", str(error)))

def gen_user_token() -> str:
	"""Generates a random Linkvertise user token. 
	Not used in the bypasser, but may be useful for other purposes.

	Returns:
		str: 64 character long alphanumeric user token
	"""
	return ''.join(random.choice(
		string.ascii_uppercase + string.ascii_lowercase + string.digits)
				   for _ in range(64))

GRAPHQL_ENDPOINT = "https://publisher.linkvertise.com/graphql"

def request_access_token(session: requests.Session, post: Post) -> str:
	"""Requests an access token from the Linkvertise GraphQL API.
	This is the first step to request a post URL

	Note that the cookie session must be passed to all requests related to the same post.
	"""
	acctok_res = session.post(GRAPHQL_ENDPOINT, json=access_token_request(post), headers=default_headers)
	logger.debug("acctok status: %d", acctok_res.status_code)
 
	acctok_res.raise_for_status()
 
	acctok = acctok_res.json()
	__process_errors(acctok)
 
	return acctok["data"]["getDetailPageContent"]["access_token"]

def request_post_token(session: requests.Session, access_token: str, post: Post) -> str:
	"""Requests a post token from the Linkvertise GraphQL API.
 
	Requires an access token obtained from request_access_token, and the cookie session.
	"""
	posttok_res = session.post(GRAPHQL_ENDPOINT, json=post_access_token_request(access_token, post), headers=default_headers)
	logger.debug("posttok status: %d", posttok_res.status_code)
 
	posttok_res.raise_for_status()
 
	posttok = posttok_res.json()
	__process_errors(posttok)
 
	return posttok["data"]["completeDetailPageContent"]["TARGET"]

def request_url(session: requests.Session, post_token: str, post: Post) -> str:
	"""Requests the final URL from the Linkvertise GraphQL API.

	Requires a post token obtained from request_post_token, and the cookie session.
 
	After this step, the cookie session can be discarded.
	"""
	detail_res = session.post(GRAPHQL_ENDPOINT, json=post_detail_request(post_token, post), headers=default_headers)
	logger.debug("detail status: %d", detail_res.status_code)
 
	detail_res.raise_for_status()
 
	detail = detail_res.json()
	__process_errors(detail)
 
	return detail["data"]["getDetailPageTarget"]["url"]

def get_url(post: Post, session: Optional[requests.Session] = None) -> str:
	"""Processes a Linkvertise post and returns the final URL.

	A new session is created if none is provided.
	"""
	session = session or RandomUserAgentSession()
	access_token = request_access_token(session, post)
	post_token = request_post_token(session, access_token, post)
	return request_url(session, post_token, post)

def parse_link(link: str, check_domain: bool = True) -> Post:
	"""Parse a Linkvertise link and return a `Post` object."""
	url = urllib.urlparse(link)
	
	if check_domain and url.netloc not in LINKVERTISE_HOSTS:
		raise ValueError("invalid linkvertise link: " + link)

	path = url.path.strip("/").split("/")
	if len(path) != 2:
		raise ValueError("invalid linkvertise link: " + link)

	return Post(path[0], path[1])

def bypass(link: str, check_domain: bool = True, session: Optional[requests.Session] = None) -> str:
	"""Bypasses a Linkvertise link and returns the final URL.

	A new session is created if none is provided.

	Important change: perform an initial GET on the original link to allow cookies / server-side state
	to be set the same way a browser would. This reduces the chance of Linkvertise treating the
	GraphQL calls as "early" or fraudulent.
	"""
	# Use the same session across the three GraphQL calls for consistency
	session = session or RandomUserAgentSession()

	# Try an initial GET to the original link (this populates cookies and other server-side state).
	# It's normal for the server to set cookies or perform redirects here.
	try:
		logger.debug("Initial GET to %s to populate cookies / session state", link)
		# We rely on RandomUserAgentSession to attach the UA and merge default headers.
		session.get(link, headers=default_headers, allow_redirects=True, timeout=10)
		# small pause to mimic a browser (helps reduce anti-bot heuristics)
		time.sleep(0.25)
	except Exception as e:
		# Don't fail hard here — we still attempt the GraphQL flow, but log for debugging.
		logger.debug("Initial GET failed or timed out: %s", e)

	return get_url(parse_link(link, check_domain=check_domain), session=session)