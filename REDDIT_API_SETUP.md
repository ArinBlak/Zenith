# Reddit API Setup Guide

To enable sentiment analysis from Reddit, you need to create a Reddit app and obtain API credentials.

## Steps:

1. **Log in to Reddit**: Go to [reddit.com](https://reddit.com) and log in to your account

2. **Navigate to App Preferences**: Visit [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)

3. **Create a New App**:
   - Scroll to the bottom and click "create another app..."
   - Fill in the form:
     - **name**: Zenith Trading Bot (or any name you prefer)
     - **App type**: Select "script"
     - **description**: (optional)
     - **about url**: (optional)
     - **redirect uri**: http://localhost:8000 (required but not used)
   - Click "create app"

4. **Copy Credentials**:
   - After creating, you'll see your app listed
   - The **client_id** is the string directly under "personal use script"
   - The **secret** is shown as "secret"
   - Copy both values

5. **Update .env File**:
   ```bash
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_secret_here
   REDDIT_USER_AGENT=Zenith Trading Bot v1.0
   ```

6. **Restart the Web Server**:
   ```bash
   python web_api.py
   ```

That's it! The sentiment worker will now scrape Reddit posts from crypto subreddits.

## Troubleshooting

- **Invalid credentials**: Double-check you copied the full client_id and secret
- **Rate limits**: Reddit has rate limits. The worker polls every 30 minutes to stay within limits
- **No Reddit data**: Check the logs for any Reddit API errors: `tail -f binance_bot.log`
