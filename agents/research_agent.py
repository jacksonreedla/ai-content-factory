"""Research Agent: pulls stories from all enabled content sources into the DB.

Sources are configured via ``sources.enabled`` (any of reddit, rss, ai). Each
source runs independently: one failing (missing Reddit credentials, an
unreachable feed, an offline LLM) is logged and skipped rather than killing
the run - as long as at least one source is usable. The agent only reports a
hard failure when every enabled source failed to produce anything.
"""
from __future__ import annotations

import random
import time

from agents.base import Agent, AgentContext, AgentResult
from app.accounts import account_names
from api.reddit_archive import RedditArchiveClient
from api.reddit_client import (RedditClient, RedditConfigError, RedditFilters,
                               RedditJSONClient, passes_filters, reddit_rss_url)
from api.rss_client import RSSClient, RSSFilters, passes_rss_filters
from api.story_generator import StoryGenerator
from database.repositories import StoryRepo
from models.story import Story


class ResearchAgent(Agent):
    name = "research"
    stage = "research"

    def execute(self, ctx: AgentContext) -> AgentResult:
        repo = StoryRepo(ctx.db)
        enabled = ctx.data.get(
            "sources", ctx.config.get("sources.enabled", ["reddit"]))

        added = filtered = 0
        errors: list[str] = []
        ran_any = False

        runners = {
            "reddit": self._run_reddit,
            "rss": self._run_rss,
            "ai": self._run_ai,
        }
        active = [s for s in enabled if s in runners]

        for i, source in enumerate(active):
            ctx.report(self.stage, i / max(len(active), 1))
            try:
                a, f = runners[source](ctx, repo, errors)
                added += a
                filtered += f
                ran_any = True
            except _SourceSkipped as exc:
                errors.append(str(exc))
            except Exception as exc:  # a source blowing up shouldn't kill others
                self.log.warning("Source '%s' failed: %s", source, exc)
                errors.append(f"{source}: {exc}")

        # Safety net: if a thin run leaves fewer fresh stories than the
        # accounts need, top up with original AI stories so none run dry.
        topup = self._maybe_topup(ctx, repo, errors, added)
        if topup:
            added += topup
            ran_any = True

        ctx.data["stories_added"] = added

        # Fatal only when nothing worked at all (e.g. reddit-only + no creds),
        # so the GUI still surfaces the original helpful error message.
        if not ran_any:
            message = errors[0] if errors else "no content sources enabled"
            return AgentResult(ok=False, message=message,
                               data={"errors": errors})

        message = f"{added} new stories added, {filtered} filtered out"
        if topup:
            message += f" (incl. {topup} AI top-up)"
        if errors:
            message += f", {len(errors)} source warning(s)"
        return AgentResult(ok=True, message=message,
                           data={"added": added, "filtered": filtered,
                                 "topup": topup, "errors": errors})

    def _maybe_topup(self, ctx: AgentContext, repo: StoryRepo,
                     errors: list[str], added: int) -> int:
        """Generate AI stories to reach a minimum fresh supply for the run.

        The target defaults to (number of accounts x topup_per_account) so it
        scales with how many accounts you're feeding; set ai_stories.topup_target
        to pin an explicit number. Generation is capped by ai_stories.topup_max
        to bound LLM time/cost, and any failure is non-fatal (logged + recorded).
        """
        if not ctx.config.get("ai_stories.topup_enabled", True):
            return 0
        target = int(ctx.config.get("ai_stories.topup_target", 0) or 0)
        if target <= 0:
            n_accounts = len(account_names(ctx.config)) or 1
            per = int(ctx.config.get("ai_stories.topup_per_account", 3))
            target = n_accounts * per
        if added >= target:
            return 0
        need = min(target - added, int(ctx.config.get("ai_stories.topup_max", 12)))
        if need <= 0:
            return 0
        self.log.info("Only %d new story(ies) this run (target %d); generating "
                      "%d AI top-up story(ies) so no account runs dry",
                      added, target, need)
        try:
            generator = StoryGenerator(ctx.config, ctx.llm, ctx.prompts)
            stories = generator.generate(need)
            a, _ = self._store(ctx, repo, stories, lambda s: (bool(s.text), "empty"))
            return a
        except Exception as exc:
            self.log.warning("AI top-up failed: %s", exc)
            errors.append(f"ai top-up: {exc}")
            return 0

    # ------------------------------------------------------------------ sources
    def _store(self, ctx: AgentContext, repo: StoryRepo,
               stories: list[Story], passes) -> tuple[int, int]:
        """Filter, dedupe and persist a batch. Returns (added, filtered)."""
        added = filtered = 0
        for story in stories:
            ok, reason = passes(story)
            if not ok:
                filtered += 1
                self.log.debug("Filtered %s '%s': %s",
                               story.source, story.title[:50], reason)
                continue
            before = ctx.db.scalar(
                "SELECT COUNT(*) FROM stories WHERE source = ? AND source_id = ?",
                (story.source, story.source_id),
            )
            repo.upsert(story)
            if not before:
                added += 1
        return added, filtered

    def _run_reddit(self, ctx, repo, errors) -> tuple[int, int]:
        subreddits = ctx.data.get(
            "subreddits", ctx.config.get("reddit.subreddits", []))
        listing = ctx.config.get("reddit.listing", "top")
        time_filter = ctx.config.get("reddit.time_filter", "day")
        limit = ctx.config.get("reddit.limit_per_subreddit", 25)

        try:
            client = RedditClient(ctx.config)
        except RedditConfigError as exc:
            # No API credentials: fall back to Reddit's PUBLIC endpoints.
            # 'json' (default) gives full-quality data; 'rss' is the last resort.
            if not subreddits:
                raise _SourceSkipped(f"reddit: {exc}") from exc
            method = ctx.config.get("reddit.public_method", "auto")
            self.log.info("Reddit API not configured; using public %s", method)
            return self._run_reddit_public(
                ctx, repo, errors, subreddits, listing, time_filter, limit,
                method)

        filters = RedditFilters.from_config(ctx.config)

        added = filtered = 0
        for subreddit in subreddits:
            try:
                stories = client.fetch_stories(subreddit, listing, time_filter, limit)
            except Exception as exc:
                self.log.warning("r/%s failed: %s", subreddit, exc)
                errors.append(f"r/{subreddit}: {exc}")
                continue
            a, f = self._store(ctx, repo, stories,
                               lambda s: passes_filters(s, filters))
            added += a
            filtered += f
        return added, filtered

    def _run_reddit_public(self, ctx, repo, errors, subreddits, listing,
                           time_filter, limit, method="auto") -> tuple[int, int]:
        """Fetch subreddits without an API key.

        ``method`` selects the transport:
          * "json" / "auto" - Reddit's public ``.json`` listings. These carry
            full post text and real score/comment counts, so the normal
            upvote/comment RedditFilters apply. "auto" additionally falls back
            to RSS for any subreddit whose JSON fetch fails.
          * "rss" - Reddit's public RSS feeds only (no score/comment counts;
            word-count/age filters are used instead). Last-resort transport.

        Stories are labelled source='reddit' so analytics track them by
        subreddit either way. Text-story subreddits work best; image/video
        subs carry little body text and get filtered out.
        """
        method = method if method in ("archive", "json", "rss", "auto") else "auto"
        added = filtered = 0

        # Base pause between requests, with jitter, so we don't trip a 429.
        pace = float(ctx.config.get("reddit.request_delay_s", 3.0))
        rss_fallback: list[str] = []

        # Preferred credential-free path: the Reddit *archive* API. It carries
        # real (matured) score/comment counts, so the upvote/comment filters
        # apply just like the official API - no key required.
        if method in ("archive", "auto"):
            client = RedditArchiveClient(ctx.config)
            filters = RedditFilters.from_config(ctx.config)
            for idx, sub in enumerate(subreddits):
                if idx > 0 and pace > 0:
                    time.sleep(pace + random.uniform(0, pace))
                try:
                    stories = client.fetch_stories(sub, listing, time_filter, limit)
                except Exception as exc:
                    self.log.warning("archive r/%s failed: %s", sub, exc)
                    if method == "auto":
                        rss_fallback.append(sub)      # degrade to RSS for this sub
                    else:
                        errors.append(f"r/{sub} (archive): {exc}")
                    continue
                a, f = self._store(ctx, repo, stories,
                                   lambda s: passes_filters(s, filters))
                added += a
                filtered += f
            if not rss_fallback:
                return added, filtered
            subreddits = rss_fallback            # RSS carries the stragglers
            self.log.info("Falling back to RSS for %d subreddit(s)",
                          len(rss_fallback))

        elif method == "json":
            # Reddit usually hard-blocks unauthenticated .json now; kept for
            # completeness. 403 fails fast (see RedditJSONClient).
            client = RedditJSONClient(ctx.config)
            filters = RedditFilters.from_config(ctx.config)
            for idx, sub in enumerate(subreddits):
                if idx > 0 and pace > 0:
                    time.sleep(pace + random.uniform(0, pace))
                try:
                    stories = client.fetch_stories(sub, listing, time_filter, limit)
                except Exception as exc:
                    self.log.warning("public JSON r/%s failed: %s", sub, exc)
                    errors.append(f"r/{sub} (public JSON): {exc}")
                    continue
                a, f = self._store(ctx, repo, stories,
                                   lambda s: passes_filters(s, filters))
                added += a
                filtered += f
            return added, filtered

        # RSS transport (explicit 'rss', or the JSON auto-fallback remainder).
        from api.rss_client import RSSClient, RSSFilters, passes_rss_filters

        client = RSSClient(ctx.config)
        rss_filters = RSSFilters.from_config(ctx.config)
        delay = float(ctx.config.get("rss.request_delay_s", 2.5))

        for idx, sub in enumerate(subreddits):
            if idx > 0 and delay > 0:
                time.sleep(delay)   # pace requests so Reddit doesn't 429
            url = reddit_rss_url(sub, listing, time_filter)
            try:
                stories = self._fetch_feed(client, url, limit, delay)
            except Exception as exc:
                self.log.warning("public r/%s failed: %s", sub, exc)
                errors.append(f"r/{sub} (public RSS): {exc}")
                continue
            for story in stories:            # relabel rss -> reddit/<sub>
                story.source = "reddit"
                story.subreddit = sub
            a, f = self._store(ctx, repo, stories,
                               lambda s: passes_rss_filters(s, rss_filters))
            added += a
            filtered += f
        return added, filtered

    def _run_rss(self, ctx, repo, errors) -> tuple[int, int]:
        feeds = ctx.data.get("feeds", ctx.config.get("rss.feeds", []))
        if not feeds:
            raise _SourceSkipped("rss: no feeds configured")
        client = RSSClient(ctx.config)
        filters = RSSFilters.from_config(ctx.config)
        limit = ctx.config.get("rss.limit_per_feed", 25)
        delay = float(ctx.config.get("rss.request_delay_s", 2.5))

        added = filtered = 0
        for idx, feed in enumerate(feeds):
            if idx > 0 and delay > 0:
                time.sleep(delay)   # pace requests so rate-limited hosts don't 429
            try:
                stories = self._fetch_feed(client, feed, limit, delay)
            except Exception as exc:
                self.log.warning("feed %s failed: %s", feed, exc)
                errors.append(f"feed {feed}: {exc}")
                continue
            a, f = self._store(ctx, repo, stories,
                               lambda s: passes_rss_filters(s, filters))
            added += a
            filtered += f
        return added, filtered

    def _fetch_feed(self, client, feed, limit, delay):
        """Fetch one feed; on HTTP 429 wait once (longer) and retry."""
        from urllib.error import HTTPError
        try:
            return client.fetch_stories(feed, limit)
        except HTTPError as exc:
            if exc.code != 429:
                raise
            wait = max(delay * 2, 5.0)
            self.log.info("429 on %s; waiting %.0fs and retrying once", feed, wait)
            time.sleep(wait)
            return client.fetch_stories(feed, limit)

    def _run_ai(self, ctx, repo, errors) -> tuple[int, int]:
        generator = StoryGenerator(ctx.config, ctx.llm, ctx.prompts)
        count = ctx.data.get("ai_count", ctx.config.get("ai_stories.count", 3))
        stories = generator.generate(count)
        # Generated stories are original and pre-shaped; accept them all.
        return self._store(ctx, repo, stories, lambda s: (bool(s.text), "empty"))


class _SourceSkipped(RuntimeError):
    """A source is enabled but not usable right now (soft skip, recorded)."""
