# TikTok upload setup (Content Posting API — Direct Post)

The factory publishes finished videos straight to your TikTok profile using
TikTok's official **Content Posting API**. This is the sanctioned route — no
browser automation, no ToS violations. It does require a one-time app setup and
TikTok's approval.

## 1. Create a TikTok developer app

1. Go to <https://developers.tiktok.com> and log in with your TikTok account.
2. **Manage apps → Connect an app** (create a new app). Give it a name and
   description that honestly reflect what it does (e.g. "publishes my own
   short-form story videos to my TikTok account").
3. Open the app and **add products**:
   - **Login Kit** (for OAuth sign-in)
   - **Content Posting API** — and under its configuration, turn on
     **Direct Post**.
4. Request the scopes: `user.info.basic` and `video.publish`.
5. Under **Login Kit → Redirect URI**, add exactly:

   ```
   http://localhost:53682/callback
   ```

   This must match `tiktok.redirect_uri` in your config verbatim.
6. Copy the app's **Client Key** and **Client Secret**.

## 2. Put the keys in the app

Open **Settings → Upload** and paste the Client Key and Client Secret, or edit
`settings/config.json` directly:

```json
"tiktok": {
  "client_key": "YOUR_CLIENT_KEY",
  "client_secret": "YOUR_CLIENT_SECRET",
  "redirect_uri": "http://localhost:53682/callback",
  "scopes": "user.info.basic,video.publish",
  "label_ai_generated": true,
  "disable_comment": false,
  "disable_duet": false,
  "disable_stitch": false,
  "cover_timestamp_ms": 1000
}
```

## 3. Connect your account

On the **Uploads** page click **Connect TikTok**. A browser window opens; sign
in and approve. The app catches the redirect on `localhost:53682`, exchanges the
code for an access token, and stores it in `data/tiktok_token.json`. The token
auto-refreshes; if it ever fails, just click Connect again.

## 4. Post

Click **Post rendered videos** (or run the full pipeline). Each rendered video
is direct-posted with a caption built from its SEO title, description and
hashtags, labelled as AI-generated.

## Important limitations (read this)

- **Audit gate on public posts.** Until your app passes TikTok's content-posting
  **audit**, every post is forced to **private (`SELF_ONLY`)** no matter what
  visibility you choose. Your uploads will succeed and appear on your own profile
  privately. Submit the audit from your app's Content Posting API page once your
  integration works; after approval, `PUBLIC_TO_EVERYONE` takes effect.
- **Visibility mapping.** `public → PUBLIC_TO_EVERYONE`, `private → SELF_ONLY`,
  `friends → MUTUAL_FOLLOW_FRIENDS`, `followers → FOLLOWER_OF_CREATOR`. If the
  connected account doesn't allow the level you picked, the app automatically
  falls back to the safest available option rather than failing the post.
- **Rate limit.** `video.publish` allows 6 upload initiations per minute per
  user, plus a daily post cap enforced by TikTok.
- **Video format.** MP4 (H.264) works out of the box — that's what the renderer
  produces. Files are uploaded in 5 MB chunks; small files go in a single chunk.
- **No public watch URL.** TikTok returns a `publish_id`, not a shareable video
  URL. The Uploads page shows the `publish_id` and status; double-click a row to
  open your TikTok profile.
- **No analytics via this API.** The Content Posting API does not return
  view/like counts, so the Analytics stage's stats pass stays idle unless a
  separate stats source (e.g. YouTube) is connected. Posting itself is
  unaffected.
