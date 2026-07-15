"""
Meta (Facebook / Instagram / Threads) API Tester
--------------------------------------------------
A single-file Streamlit app for verifying API credentials and testing
post uploads to:
  - Facebook Page (via Graph API)
  - Instagram Business/Creator account linked to a Facebook Page (via Graph API)
  - Threads (via the Threads Graph API)

Deploy on streamlit.io Community Cloud:
  1. Push this file to a GitHub repo (e.g. as `app.py` or `meta_api_tester.py`).
  2. Go to https://share.streamlit.io -> "New app" -> point it at the repo/file.
  3. No extra secrets are required to deploy — all tokens/IDs are entered
     in the app UI at runtime (nothing is hardcoded or stored server-side).

Requirements (requirements.txt):
  streamlit
  requests

Notes on tokens:
  - Facebook Page posting requires a PAGE access token (not a user token),
    with pages_manage_posts / pages_read_engagement permissions.
  - Instagram posting requires the Instagram Business/Creator account ID
    (linked to the Facebook Page) and a Page/User token with
    instagram_basic + instagram_content_publish permissions. Instagram
    publishing is a two-step process: create a media container, then
    publish it.
  - Threads posting uses https://graph.threads.net and a Threads-specific
    long-lived access token plus the Threads user ID. It is also a
    two-step create-then-publish flow.
  - This tool never stores your keys anywhere — they live only in the
    Streamlit session for the duration of your browser session.
"""

import json
import time
import requests
import streamlit as st

GRAPH_BASE = "https://graph.facebook.com"
THREADS_BASE = "https://graph.threads.net"
DEFAULT_GRAPH_VERSION = "v20.0"
DEFAULT_THREADS_VERSION = "v1.0"

st.set_page_config(page_title="Meta API Tester", page_icon="🧪", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def show_response(resp: requests.Response, label: str = "Response"):
    """Pretty-print a requests.Response, color coded by status."""
    try:
        data = resp.json()
    except ValueError:
        data = {"raw_text": resp.text}

    if resp.ok and "error" not in data:
        st.success(f"{label}: HTTP {resp.status_code}")
    else:
        st.error(f"{label}: HTTP {resp.status_code}")
    st.json(data)
    return data


def do_get(url, params):
    try:
        return requests.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        st.error(f"Request failed: {e}")
        return None


def do_post(url, params=None, data=None, files=None):
    try:
        return requests.post(url, params=params, data=data, files=files, timeout=60)
    except requests.RequestException as e:
        st.error(f"Request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Sidebar: shared credentials
# ---------------------------------------------------------------------------

st.sidebar.title("🔑 Credentials")
st.sidebar.caption("Nothing you enter here is stored — it only lives in this browser session.")

graph_version = st.sidebar.text_input("Graph API version", value=DEFAULT_GRAPH_VERSION)
threads_version = st.sidebar.text_input("Threads API version", value=DEFAULT_THREADS_VERSION)

st.sidebar.markdown("---")
st.sidebar.subheader("Facebook / Instagram")
fb_app_id = st.sidebar.text_input("App ID", key="fb_app_id")
fb_app_secret = st.sidebar.text_input("App Secret", key="fb_app_secret", type="password")
fb_user_token = st.sidebar.text_input("User Access Token", key="fb_user_token", type="password")
fb_page_id = st.sidebar.text_input("Page ID", key="fb_page_id")
fb_page_token = st.sidebar.text_input("Page Access Token (optional, else fetched)", key="fb_page_token", type="password")
ig_user_id = st.sidebar.text_input("Instagram Business Account ID", key="ig_user_id")

st.sidebar.markdown("---")
st.sidebar.subheader("Threads")
threads_user_id = st.sidebar.text_input("Threads User ID", key="threads_user_id")
threads_access_token = st.sidebar.text_input("Threads Access Token", key="threads_access_token", type="password")

st.title("🧪 Meta API Tester — Facebook, Instagram & Threads")
st.caption(
    "Validate credentials and test-post to a Facebook Page, an Instagram "
    "Business account, and Threads, all from one place."
)

tab_fb_auth, tab_fb_post, tab_ig, tab_threads = st.tabs(
    ["Facebook: Verify Key/ID", "Facebook: Page Post", "Instagram: Post", "Threads: Post"]
)

# ---------------------------------------------------------------------------
# Tab 1: Facebook token/id verification
# ---------------------------------------------------------------------------
with tab_fb_auth:
    st.subheader("Verify App ID / App Secret / Access Token")
    st.write(
        "Uses `GET /debug_token` to inspect a token, and `GET /me` to confirm "
        "the token identifies the expected user or page."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Debug Token (App Token method)"):
            if not (fb_app_id and fb_app_secret and fb_user_token):
                st.warning("App ID, App Secret, and a User Access Token are required.")
            else:
                app_access_token = f"{fb_app_id}|{fb_app_secret}"
                url = f"{GRAPH_BASE}/{graph_version}/debug_token"
                params = {"input_token": fb_user_token, "access_token": app_access_token}
                resp = do_get(url, params)
                if resp is not None:
                    show_response(resp, "debug_token")

    with col2:
        if st.button("Call /me with User Token"):
            if not fb_user_token:
                st.warning("Enter a User Access Token first.")
            else:
                url = f"{GRAPH_BASE}/{graph_version}/me"
                params = {"access_token": fb_user_token, "fields": "id,name"}
                resp = do_get(url, params)
                if resp is not None:
                    show_response(resp, "/me")

    st.markdown("---")
    st.subheader("List Pages this User Token manages")
    if st.button("Fetch /me/accounts"):
        if not fb_user_token:
            st.warning("Enter a User Access Token first.")
        else:
            url = f"{GRAPH_BASE}/{graph_version}/me/accounts"
            params = {"access_token": fb_user_token}
            resp = do_get(url, params)
            if resp is not None:
                data = show_response(resp, "/me/accounts")
                if resp.ok and "data" in data:
                    st.info("Copy a Page ID / Page Access Token above into the sidebar.")

    st.markdown("---")
    st.subheader("Verify Page ID directly")
    if st.button("Fetch Page Info"):
        if not fb_page_id:
            st.warning("Enter a Page ID in the sidebar first.")
        else:
            token_to_use = fb_page_token or fb_user_token
            if not token_to_use:
                st.warning("Enter a Page Access Token or User Access Token.")
            else:
                url = f"{GRAPH_BASE}/{graph_version}/{fb_page_id}"
                params = {"access_token": token_to_use, "fields": "id,name,category,link"}
                resp = do_get(url, params)
                if resp is not None:
                    show_response(resp, "Page info")

# ---------------------------------------------------------------------------
# Tab 2: Facebook Page post
# ---------------------------------------------------------------------------
with tab_fb_post:
    st.subheader("Post to a Facebook Page")
    st.write("Text post via `POST /{page-id}/feed`, or photo post via `POST /{page-id}/photos`.")

    post_type = st.radio("Post type", ["Text/Link post", "Photo post (by URL)"], horizontal=True)

    message = st.text_area("Message", placeholder="Hello from the Meta API Tester!")
    link = ""
    photo_url = ""
    if post_type == "Text/Link post":
        link = st.text_input("Optional link to attach")
    else:
        photo_url = st.text_input("Photo URL (publicly accessible)")

    published = st.checkbox("Publish immediately", value=True)

    if st.button("Submit Page Post"):
        token_to_use = fb_page_token or fb_user_token
        if not fb_page_id or not token_to_use:
            st.warning("Page ID and a Page/User Access Token are required (see sidebar).")
        else:
            if post_type == "Text/Link post":
                url = f"{GRAPH_BASE}/{graph_version}/{fb_page_id}/feed"
                params = {
                    "message": message,
                    "access_token": token_to_use,
                    "published": str(published).lower(),
                }
                if link:
                    params["link"] = link
            else:
                url = f"{GRAPH_BASE}/{graph_version}/{fb_page_id}/photos"
                params = {
                    "url": photo_url,
                    "caption": message,
                    "access_token": token_to_use,
                    "published": str(published).lower(),
                }
            resp = do_post(url, params=params)
            if resp is not None:
                show_response(resp, "Page post result")

# ---------------------------------------------------------------------------
# Tab 3: Instagram post
# ---------------------------------------------------------------------------
with tab_ig:
    st.subheader("Post to Instagram (Business/Creator account)")
    st.write(
        "Two-step flow: create a media container with "
        "`POST /{ig-user-id}/media`, then publish it with "
        "`POST /{ig-user-id}/media_publish`."
    )

    ig_media_type = st.radio("Media type", ["Image", "Video/Reel"], horizontal=True)
    ig_media_url = st.text_input("Media URL (publicly accessible image or video)")
    ig_caption = st.text_area("Caption", key="ig_caption")

    if st.button("Create + Publish Instagram Post"):
        token_to_use = fb_page_token or fb_user_token
        if not ig_user_id or not token_to_use:
            st.warning("Instagram Business Account ID and an access token are required.")
        elif not ig_media_url:
            st.warning("Enter a media URL.")
        else:
            # Step 1: create container
            create_url = f"{GRAPH_BASE}/{graph_version}/{ig_user_id}/media"
            create_params = {
                "caption": ig_caption,
                "access_token": token_to_use,
            }
            if ig_media_type == "Image":
                create_params["image_url"] = ig_media_url
            else:
                create_params["video_url"] = ig_media_url
                create_params["media_type"] = "REELS"

            st.write("**Step 1: creating media container...**")
            create_resp = do_post(create_url, params=create_params)
            create_data = show_response(create_resp, "media container") if create_resp is not None else None

            if create_data and create_resp.ok and "id" in create_data:
                container_id = create_data["id"]

                # For video, Instagram needs time to process before publishing.
                if ig_media_type == "Video/Reel":
                    st.write("Waiting for video container to finish processing...")
                    status_url = f"{GRAPH_BASE}/{graph_version}/{container_id}"
                    for attempt in range(10):
                        status_resp = do_get(status_url, {"fields": "status_code", "access_token": token_to_use})
                        if status_resp is not None and status_resp.ok:
                            status_code = status_resp.json().get("status_code")
                            st.caption(f"Attempt {attempt + 1}: status = {status_code}")
                            if status_code == "FINISHED":
                                break
                        time.sleep(5)

                st.write("**Step 2: publishing container...**")
                publish_url = f"{GRAPH_BASE}/{graph_version}/{ig_user_id}/media_publish"
                publish_params = {"creation_id": container_id, "access_token": token_to_use}
                publish_resp = do_post(publish_url, params=publish_params)
                if publish_resp is not None:
                    show_response(publish_resp, "publish result")

    st.markdown("---")
    st.subheader("Verify Instagram Account ID")
    if st.button("Fetch IG Account Info"):
        token_to_use = fb_page_token or fb_user_token
        if not ig_user_id or not token_to_use:
            st.warning("Enter Instagram Business Account ID and a token first.")
        else:
            url = f"{GRAPH_BASE}/{graph_version}/{ig_user_id}"
            params = {"fields": "id,username,name,biography", "access_token": token_to_use}
            resp = do_get(url, params)
            if resp is not None:
                show_response(resp, "IG account info")

# ---------------------------------------------------------------------------
# Tab 4: Threads post
# ---------------------------------------------------------------------------
with tab_threads:
    st.subheader("Post to Threads")
    st.write(
        "Two-step flow against the Threads Graph API: create a container "
        "with `POST /{threads-user-id}/threads`, then publish it with "
        "`POST /{threads-user-id}/threads_publish`."
    )

    threads_media_type = st.radio("Post type", ["Text only", "Image", "Video"], horizontal=True)
    threads_text = st.text_area("Text", key="threads_text")
    threads_media_url = ""
    if threads_media_type != "Text only":
        threads_media_url = st.text_input("Media URL (publicly accessible)")

    if st.button("Create + Publish Threads Post"):
        if not threads_user_id or not threads_access_token:
            st.warning("Threads User ID and Threads Access Token are required (see sidebar).")
        else:
            create_url = f"{THREADS_BASE}/{threads_version}/{threads_user_id}/threads"
            create_params = {
                "access_token": threads_access_token,
                "text": threads_text,
            }
            if threads_media_type == "Text only":
                create_params["media_type"] = "TEXT"
            elif threads_media_type == "Image":
                create_params["media_type"] = "IMAGE"
                create_params["image_url"] = threads_media_url
            else:
                create_params["media_type"] = "VIDEO"
                create_params["video_url"] = threads_media_url

            st.write("**Step 1: creating Threads container...**")
            create_resp = do_post(create_url, params=create_params)
            create_data = show_response(create_resp, "threads container") if create_resp is not None else None

            if create_data and create_resp.ok and "id" in create_data:
                container_id = create_data["id"]

                if threads_media_type == "Video":
                    st.write("Waiting for video container to finish processing...")
                    status_url = f"{THREADS_BASE}/{threads_version}/{container_id}"
                    for attempt in range(10):
                        status_resp = do_get(
                            status_url, {"fields": "status", "access_token": threads_access_token}
                        )
                        if status_resp is not None and status_resp.ok:
                            status_code = status_resp.json().get("status")
                            st.caption(f"Attempt {attempt + 1}: status = {status_code}")
                            if status_code == "FINISHED":
                                break
                        time.sleep(5)

                st.write("**Step 2: publishing container...**")
                publish_url = f"{THREADS_BASE}/{threads_version}/{threads_user_id}/threads_publish"
                publish_params = {"creation_id": container_id, "access_token": threads_access_token}
                publish_resp = do_post(publish_url, params=publish_params)
                if publish_resp is not None:
                    show_response(publish_resp, "publish result")

    st.markdown("---")
    st.subheader("Verify Threads User ID / Token")
    if st.button("Fetch Threads Profile"):
        if not threads_user_id or not threads_access_token:
            st.warning("Enter Threads User ID and Access Token first.")
        else:
            url = f"{THREADS_BASE}/{threads_version}/{threads_user_id}"
            params = {
                "fields": "id,username,threads_profile_picture_url,threads_biography",
                "access_token": threads_access_token,
            }
            resp = do_get(url, params)
            if resp is not None:
                show_response(resp, "Threads profile")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
with st.expander("ℹ️ Setup notes / troubleshooting"):
    st.markdown(
        """
- **Facebook Page token vs User token:** Page-level actions (posting, reading
  page-only fields) need a **Page access token**. Get one via `/me/accounts`
  after logging in with a User token that has `pages_show_list` and
  `pages_manage_posts` permissions.
- **Instagram** requires the IG account to be a **Business or Creator**
  account linked to the Facebook Page, and the token needs
  `instagram_basic` + `instagram_content_publish` scopes.
- **Threads** uses a separate app product ("Threads API") in the Meta
  Developer dashboard, its own OAuth flow, and the `graph.threads.net`
  host — a Facebook/Instagram token will **not** work here.
- **Common errors:**
  - `190` — invalid/expired access token → re-generate it.
  - `10` / `200` — missing permission → check the token's granted scopes
    with the "Debug Token" button.
  - `9007` (Instagram) — media not yet ready for publish → the app retries
    automatically for video, but very large files may need more time.
- Long-lived tokens: exchange short-lived tokens via
  `GET /oauth/access_token?grant_type=fb_exchange_token` before using this
  tool for anything beyond quick tests.
        """
    )

st.caption("Built for local testing before wiring these calls into your own backend.")
