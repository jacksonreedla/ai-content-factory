# Prompt Templates

Every AI task reads its prompt from a `.txt` file in this folder.
Edit these files to change AI behaviour — no code changes needed.

Placeholders like `{title}` are filled in automatically at runtime.

| File | Used by | Placeholders |
|---|---|---|
| `score_story.txt` | Story Analyst agent | `{title}`, `{subreddit}`, `{upvotes}`, `{num_comments}`, `{text}` |
| `rewrite_story.txt` | Rewrite agent | `{title}`, `{text}`, `{style}`, `{target_words}`, `{target_seconds}` |
| `generate_metadata.txt` | SEO agent | `{title}`, `{narration}`, `{style}` |
| `thumbnail_text.txt` | Thumbnail agent | `{title}`, `{narration}` |
