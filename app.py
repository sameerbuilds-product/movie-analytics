import os, hashlib, re
from datetime import datetime, timezone
from urllib.parse import quote_plus
from html import unescape

import pandas as pd
import requests
import feedparser
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Indian Cinema Pulse", page_icon="🎬", layout="wide")
st.title("🎬 Indian Cinema Pulse")
st.caption("Indian movie news, trailers, reviews, OTT releases and box-office coverage — in one place.")
st.info("This app aggregates public headlines and snippets with links to original publishers. It does not host full articles or films.")

RSS_SOURCES = [
    ("India Cinema", "Indian cinema Bollywood Telugu Tamil Malayalam Kannada movie news"),
    ("Bollywood", "Bollywood Hindi film movie news"),
    ("Telugu Cinema", "Telugu cinema Tollywood movie news"),
    ("Tamil Cinema", "Tamil cinema Kollywood movie news"),
    ("Malayalam Cinema", "Malayalam cinema movie news"),
    ("Kannada Cinema", "Kannada cinema Sandalwood movie news"),
    ("Box Office", "Indian film box office collection"),
    ("Trailers & Releases", "Indian movie official trailer release date"),
    ("Reviews", "Indian movie film review"),
    ("OTT Releases", "Indian movie OTT release")
]
CATEGORIES = ["All Indian Cinema", "Bollywood", "Telugu Cinema", "Tamil Cinema", "Malayalam Cinema",
              "Kannada Cinema", "Box Office", "Trailers & Releases", "Reviews", "OTT Releases"]
TIMEOUT = 15

def get_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error("Supabase credentials are missing. Add SUPABASE_URL and SUPABASE_KEY in Streamlit app Secrets.")
        st.stop()
    return create_client(url, key)

def strip_html(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def fetch_rss(label, query):
    url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-IN&gl=IN&ceid=IN:en"
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "IndianCinemaPulse/1.0 RSS reader"})
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        title = strip_html(entry.get("title", "Untitled"))
        source_name = entry.get("source", {}).get("title", label)
        published = entry.get("published", entry.get("updated", ""))
        summary = strip_html(entry.get("summary", entry.get("description", "")))[:1000]
        rows.append({
            "article_id": hashlib.sha256(link.encode("utf-8")).hexdigest()[:32],
            "title": title,
            "link": link,
            "source": source_name,
            "published_at": published,
            "summary": summary,
            "category": label,
            "fetched_at": now
        })
    return rows

def sync_feeds(sb, selected_sources):
    progress = st.progress(0, text="Fetching public RSS feeds…")
    all_rows, errors = [], []
    for i, (label, query) in enumerate(selected_sources):
        try:
            all_rows.extend(fetch_rss(label, query))
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}: {e}")
        progress.progress((i + 1) / max(len(selected_sources), 1), text=f"Checked {label}")
    progress.empty()
    # Upsert in chunks to avoid request size limits
    inserted = 0
    for i in range(0, len(all_rows), 100):
        chunk = all_rows[i:i+100]
        if chunk:
            sb.table("articles").upsert(chunk, on_conflict="article_id").execute()
            inserted += len(chunk)
    return inserted, errors

def get_articles(sb, limit=500):
    result = sb.table("articles").select("*").order("published_at", desc=True).limit(limit).execute()
    return pd.DataFrame(result.data or [])

def get_saved_ids(sb):
    try:
        result = sb.table("saved_articles").select("article_id").execute()
        return {r["article_id"] for r in (result.data or [])}
    except Exception:
        return set()

def save_article(sb, article_id):
    sb.table("saved_articles").upsert({"article_id": article_id}, on_conflict="article_id").execute()

def unsave_article(sb, article_id):
    sb.table("saved_articles").delete().eq("article_id", article_id).execute()

sb = get_supabase()
with st.sidebar:
    st.header("Discover")
    category = st.selectbox("Category", CATEGORIES)
    query_text = st.text_input("Search headlines", placeholder="e.g. Rajinikanth, box office, trailer")
    st.divider()
    st.subheader("Feed refresh")
    selected_labels = st.multiselect("Sources", [x[0] for x in RSS_SOURCES], default=[x[0] for x in RSS_SOURCES])
    refresh_now = st.button("🔄 Fetch latest headlines", type="primary", use_container_width=True)
    st.caption("Refresh pulls the latest entries available in public RSS search feeds. Publisher updates and feed availability vary.")

if refresh_now or "did_initial_refresh" not in st.session_state:
    selected = [x for x in RSS_SOURCES if x[0] in selected_labels]
    if selected:
        with st.spinner("Checking public feeds and saving new headlines to Supabase…"):
            try:
                count, errors = sync_feeds(sb, selected)
                st.session_state.did_initial_refresh = True
                st.session_state.last_refresh = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
                st.success(f"Processed {count} feed entries. Supabase has been updated.")
                if errors:
                    with st.expander(f"{len(errors)} feed(s) could not be fetched"):
                        st.write("\n".join(errors))
            except Exception as e:
                st.error(f"Supabase sync failed: {type(e).__name__}: {e}")

try:
    articles = get_articles(sb)
except Exception as e:
    st.error(f"Could not read articles from Supabase: {type(e).__name__}: {e}")
    st.stop()

saved_ids = get_saved_ids(sb)
if articles.empty:
    st.warning("Your Supabase articles table is empty. Click Fetch latest headlines to populate it.")
else:
    articles["search_blob"] = (articles["title"].fillna("") + " " + articles["summary"].fillna("") + " " + articles["source"].fillna("") + " " + articles["category"].fillna("")).str.lower()
    if category != "All Indian Cinema":
        category_term = category.lower().replace(" & ", " ")
        if category == "Bollywood":
            category_term = "bollywood"
        articles = articles[articles["search_blob"].str.contains(category_term, regex=False, na=False)]
    if query_text.strip():
        articles = articles[articles["search_blob"].str.contains(query_text.strip().lower(), regex=False, na=False)]

m1, m2, m3 = st.columns(3)
m1.metric("Headlines in results", f"{len(articles):,}")
m2.metric("Watchlist items", f"{len(saved_ids):,}")
m3.metric("Last refresh", st.session_state.get("last_refresh", "Not refreshed this session"))

tab_feed, tab_watchlist, tab_info = st.tabs(["📰 Headlines", "🔖 Watchlist", "⚙️ About & setup"])

def display_rows(frame):
    if frame.empty:
        st.info("No headlines found. Change your filters or fetch the latest headlines.")
        return
    for _, row in frame.head(100).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row.get('title','Untitled')}**")
            st.caption(f"{row.get('source','Source')} · {row.get('published_at','')}")
            summary = row.get("summary", "")
            if summary:
                st.write(str(summary)[:350] + ("…" if len(str(summary)) > 350 else ""))
            c1, c2 = st.columns([1, 5])
            with c1:
                article_id = row["article_id"]
                if article_id in saved_ids:
                    if st.button("✓ Saved", key=f"unsave_{article_id}"):
                        try:
                            unsave_article(sb, article_id)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not remove bookmark: {e}")
                else:
                    if st.button("🔖 Save", key=f"save_{article_id}"):
                        try:
                            save_article(sb, article_id)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not save bookmark: {e}")
            with c2:
                st.markdown(f"[Read original publisher ↗]({row.get('link','#')})")

with tab_feed:
    display_rows(articles.sort_values("published_at", ascending=False, na_position="last") if not articles.empty else articles)

with tab_watchlist:
    try:
        saved = sb.table("saved_articles").select("article_id, saved_at, articles(*)").execute()
        saved_rows = []
        for row in (saved.data or []):
            article = row.get("articles")
            if article:
                saved_rows.append(article)
        display_rows(pd.DataFrame(saved_rows))
    except Exception as e:
        st.warning("Watchlist could not be loaded. Check the saved_articles table and its foreign-key relationship.")
        st.caption(str(e))

with tab_info:
    st.subheader("What 'realtime' means in this version")
    st.markdown("""
- When you click **Fetch latest headlines**, the app checks multiple public RSS search feeds and stores/updates entries in Supabase.
- Supabase provides a persistent shared database across app restarts and deployments.
- This is near-real-time on refresh, not a guaranteed live news wire. Google News and publishers determine when items appear.
- The app does not run a permanent background job on every visitor page load. A scheduled worker can be added later, but free hosting and quotas must be respected.
- Article headlines, summaries, and links are displayed; the full article remains on the publisher's site.
    """)
    st.subheader("Privacy note")
    st.write("This starter version has a shared watchlist for all app visitors. Before making it public for multiple users, add Supabase Auth and user_id-based row-level security so bookmarks are private.")
    st.subheader("Troubleshooting")
    st.markdown("""
1. If tables are missing, run `schema.sql` in Supabase SQL Editor.
2. In Streamlit Community Cloud, add `SUPABASE_URL` and `SUPABASE_KEY` under App settings → Secrets.
3. Use a Supabase publishable/anon key with appropriate RLS policies. Never put the `service_role` key in a public app or commit secrets to GitHub.
4. If feeds fail temporarily, try again later; public RSS availability can vary.
    """)

st.divider()
st.caption("Indian Cinema Pulse · Free-first public-feed aggregator · Data persists in Supabase")
