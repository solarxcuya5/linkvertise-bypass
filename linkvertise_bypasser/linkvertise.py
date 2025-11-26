from typing import Optional
import urllib.parse as urllib
from importlib import resources

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

LINKVERTISE_HOSTS = [
	"linkvertise.com",
	"link-target.net",
	"link-center.net",
	"link-hub.net",
	"direct-link.net",
]

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
	if "errors" in obj:
		for error in obj["errors"]:
			raise ValueError("error: " + error["message"])

def gen_user_token() -> str:
	"""Generates a random Linkvertise user token. 
	Not used in the bypasser, but may be useful for other purposes.

	Returns:
		str: 64 character long alphanumeric user token
	"""
	return ''.join(random.choice(
		string.ascii_uppercase + string.ascii_lowercase + string.digits)
				   for _ in range(64))

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
		   "Origin":"https://linkvertise.com","Referer":"https://linkvertise.com"}

GRAPHQL_ENDPOINT = "https://publisher.linkvertise.com/graphql"

def request_access_token(session: requests.Session, post: Post) -> str:
	"""Requests an access token from the Linkvertise GraphQL API.
	This is the first step to request a post URL

	Note that the cookie session must be passed to all requests related to the same post.
	"""
	acctok_res = session.post(GRAPHQL_ENDPOINT, json=access_token_request(post), headers=headers)
	logger.debug("acctok status: %d", acctok_res.status_code)
 
	acctok_res.raise_for_status()
 
	acctok = acctok_res.json()
	__process_errors(acctok)
 
	return acctok["data"]["getDetailPageContent"]["access_token"]

def request_post_token(session: requests.Session, access_token: str, post: Post) -> str:
	"""Requests a post token from the Linkvertise GraphQL API.
 
	Requires an access token obtained from request_access_token, and the cookie session.
	"""
	posttok_res = session.post(GRAPHQL_ENDPOINT, json=post_access_token_request(access_token, post), headers=headers)
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
	detail_res = session.post(GRAPHQL_ENDPOINT, json=post_detail_request(post_token, post), headers=headers)
	logger.debug("detail status: %d", detail_res.status_code)
 
	detail_res.raise_for_status()
 
	detail = detail_res.json()
	__process_errors(detail)
 
	return detail["data"]["getDetailPageTarget"]["url"]

def get_url(post: Post, session: Optional[requests.Session] = None) -> str:
	"""Processes a Linkvertise post and returns the final URL.

	A new session is created if none is provided.
	"""
	session = session or requests.Session()
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
	"""
	session = session or requests.Session()
	return get_url(parse_link(link, check_domain=check_domain), session=session)
