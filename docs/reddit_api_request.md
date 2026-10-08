# Reddit Data API — Access Request Draft

Since Reddit disabled self-serve app creation under the **Responsible Builder
Policy (2026)**, you now request Data API access through a support ticket and
wait for manual approval. This doc has the link, what to put in each field, and
the drafted text you can paste and adapt.

---

## Where to submit

**Developer (non-commercial) Data API request form:**
https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164&tf_42139884615700=api_request_type_developer_clone

Use this form if you're treating the project as a personal, non-commercial
build. If the channel is monetized, read the **"Read this first"** note below
before choosing — Reddit may route you to the commercial path instead.

---

## Read this first — the one thing to get right

Reddit's policy draws two lines that matter for this project:

1. **Commercialization.** Using Reddit data for commercial purposes needs
   explicit written approval via the *enterprise* form, not this one. A
   monetized YouTube channel that rebuilds Reddit posts into videos is
   reasonably seen as commercial. Be honest about whether you monetize — the
   policy explicitly prohibits misrepresenting *how or why* you access Reddit
   data, and getting caught understating it risks a ban later.

2. **AI training vs. AI rewriting.** The policy bans using Reddit data to
   *train* machine-learning models. This project does **not** train anything —
   it uses an existing LLM to rewrite individual posts into narration. That's a
   real and defensible distinction, and the draft below states it plainly so
   there's no ambiguity.

**Recommendation:** if the channel is (or will be) monetized, submit through the
commercial/enterprise form instead and describe it exactly as below. If it's
genuinely a hobby with no revenue, the developer form is appropriate. Either
way, describe it truthfully — approval built on an accurate description is the
only kind worth having.

Commercial/enterprise form:
https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164&tf_42139884615700=api_request_type_enterprise_clone

---

## Field-by-field

The form fields vary, but you'll typically be asked for the following. Fill in
the bracketed parts.

- **Name:** [your full name]
- **Email:** [your email]
- **Reddit username:** [u/your_username]
- **Organization / project name:** AI Content Factory (personal project)
- **Which API:** Reddit Data API (read-only)
- **Use case / description:** paste the block below
- **Expected request volume:** see the block below (keep it accurate and modest)
- **Will you store Reddit data:** yes — see the retention note below

---

## Use-case description (paste this)

> **Project:** AI Content Factory — a personal desktop application I built that
> assembles short narrated videos.
>
> **What it does with Reddit data:** With read-only access, it fetches the top
> public self-post ("text post") submissions from a small, fixed set of
> storytelling subreddits (e.g. r/tifu, r/TrueOffMyChest, r/MaliciousCompliance).
> For each post it reads the title and body text and basic public metadata
> (score, comment count, timestamp). It uses this only to (a) filter for posts
> that are long and popular enough to be worth adapting, and (b) pass the text
> to a general-purpose large language model that rewrites it into an original
> spoken narration script. The narration is then turned into a video.
>
> **What it does NOT do:** It does not train any machine-learning or AI model on
> Reddit data. It does not post, comment, vote, message, or take any write
> action — access is strictly read-only. It does not attempt to identify,
> de-anonymize, or infer sensitive characteristics about any user. It does not
> resell, license, or redistribute Reddit data.
>
> **Scale:** Single user, single machine. Roughly [1–3] research runs per day,
> each reading the top ~25 posts from ~7 subreddits — on the order of a few
> hundred read requests per day at most, well within standard rate limits.
>
> **Attribution / data handling:** Only the small set of posts selected for
> adaptation are stored locally, and only for as long as needed to produce the
> video. I will comply with the Data API Terms, the Responsible Builder Policy,
> and the Public Content Policy, and will register the app and set a descriptive
> User-Agent as required.
>
> **Commercial status:** [Choose one and delete the other:]
> [ • This is a non-commercial hobby project with no revenue. ]
> [ • The resulting videos may be monetized; I understand this may require the
>     commercial access path and am happy to proceed accordingly. ]

---

## After approval

Once Reddit grants access and you have a **client ID** and **client secret**,
put them into the app — no code changes needed:

```
python -c "from app.config import Config; c=Config.load(); c.set('reddit.client_id','YOUR_ID'); c.set('reddit.client_secret','YOUR_SECRET'); c.set('sources.enabled',['reddit','ai']); print('reddit source enabled')"
```

Then run `python main.py --stage research` and the built-in `reddit` source
takes over — full post text, real upvote/comment counts, and no RSS throttling.
You can drop the Reddit RSS feeds at that point and keep RSS for non-Reddit
sources (or turn RSS off entirely).

Set a real User-Agent too, e.g.:
`ai-content-factory/1.0 by u/your_username`
