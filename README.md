# Reddit MCP Server

This repository contains a Model Context Protocol server implementation for Reddit that allows AI assistants to access and interact with Reddit content through PRAW (Python Reddit API Wrapper).

<a href="https://glama.ai/mcp/servers/@Arindam200/reddit-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@Arindam200/reddit-mcp/badge" alt="Reddit Server MCP server" />
</a>

![image](./Demo.png)

## What is MCP?

The Model Context Protocol (MCP) is a standard for enabling AI assistants to interface with external services, tools, and data sources. This server implements the MCP specification to provide access to Reddit content. 

To know more about MCP, Check this [video](https://www.youtube.com/watch?v=BwB1Jcw8Z-8)

## Features

- Get detailed user information with engagement analysis
- Retrieve user comment and post history with flexible filtering
- Fetch and analyze top posts from any subreddit
- Search for posts across all of Reddit or within specific subreddits using search terms
- Get comprehensive subreddit statistics and health metrics
- View trending subreddits with growth patterns
- Create strategic posts with timing recommendations
- Reply to posts and comments with engagement optimization
- AI-driven insights and recommendations
- Smart response formatting with engagement metrics

## Installation

1. Clone this repository

```bash
git clone https://github.com/Arindam200/reddit-mcp.git
cd reddit-mcp
```

2. **Connect to the MCP server**

   Copy the below json with the appropriate {{PATH}} values:

   ```json
   {
     "mcpServers": {
       "reddit": {
         "command": "{{PATH_TO_UV}}", // Run `which uv` and place the output here
         "args": [
           "--directory",
           "{{PATH_TO_SRC}}", // cd into the repo, run `pwd` and enter the output here
           "run",
           "server.py"
         ],
         "env": {
           "REDDIT_CLIENT_ID": "your_client_id",
           "REDDIT_CLIENT_SECRET": "your_client_secret",
           "REDDIT_USERNAME": "your_username", // Optional for authenticated operations
           "REDDIT_PASSWORD": "your_password" // Optional for authenticated operations
         }
       }
     }
   }
   ```

   You can obtain Reddit API credentials by creating an app at [Reddit's app preferences page](https://www.reddit.com/prefs/apps).

   For **Claude**, save this as `claude_desktop_config.json` in your Claude Desktop configuration directory at:

   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   For **Cursor**, save this as `mcp.json` in your Cursor configuration directory at:

   ```
   ~/.cursor/mcp.json
   ```

3. **Restart Claude Desktop / Cursor**

   Open Claude Desktop and you should now see Reddit as an available integration.

   Or restart Cursor.

### Available Tools

The server provides the following tools:

#### Read-only Tools (require only client credentials):

- `get_user_info(username)` - Get detailed user analysis with engagement insights
- `get_user_comments(username, sort, time_filter, limit)` - Get a user's comment history with filtering options
- `get_user_posts(username, sort, time_filter, limit)` - Get a user's post/submission history with filtering options
- `get_top_posts(subreddit, time_filter, limit)` - Get and analyze top posts
- `search_posts(query, subreddit, sort, time_filter, limit)` - Search for posts across Reddit or within a specific subreddit
- `get_subreddit_stats(subreddit)` - Get comprehensive subreddit analysis
- `get_trending_subreddits()` - Get list of trending subreddits
- `get_submission_by_url(url)` - Get a Reddit submission by its URL
- `get_submission_by_id(submission_id)` - Get a Reddit submission by its ID

#### Authenticated Tools (require user credentials):

- `who_am_i()` - Get information about the currently authenticated user
- `create_post(subreddit, title, content, flair, is_self)` - Create an optimized post
- `reply_to_post(post_id, content, subreddit)` - Add a reply with engagement insights
- `reply_to_comment(comment_id, content, subreddit)` - Add a strategic reply
- `send_message(username, subject, message)` - Send a private message to a user.
  Subject is capped at 100 characters by Reddit, body at 10000. The recipient is
  verified before sending, so a typo fails locally instead of silently at Reddit.
  Note that Reddit returns no message id on success and refuses messages to the
  authenticated account itself.
- `join_subreddit(subreddit_name, unsubscribe)` - Subscribe or unsubscribe

## Example Queries

Here are some examples of what you can ask an AI assistant connected to this server:

- "Who am I on Reddit?" or "Show my Reddit profile"
- "Analyze u/spez's Reddit activity"
- "Show me u/spez's recent comments"
- "Get the top posts by u/poem_for_your_sprog from the past year"
- "Show me the most controversial comments by u/username"
- "Show me the top posts from r/Python this week"
- "Search for posts about 'machine learning' across all of Reddit"
- "Find posts about 'beginner tutorials' in r/learnprogramming from this month"
- "Get statistics about r/AskReddit"
- "What are the trending subreddits right now?"
- "Create a post in r/Python about a new project"
- "Reply to this post with an insightful comment"
- "What's the best time to post in this subreddit?"

## Advanced Features

### AI-Driven Analysis

The server provides intelligent analysis in several areas:

1. **User Analysis**

   - Engagement patterns
   - Activity trends
   - Community influence
   - Personalized recommendations

2. **Post Analysis**

   - Performance metrics
   - Engagement quality
   - Timing optimization
   - Content impact assessment

3. **Community Analysis**
   - Health indicators
   - Growth patterns
   - Activity metrics
   - Engagement opportunities

### Smart Response Formatting

- Organized bullet points
- Engagement statistics
- AI-driven insights
- Strategic recommendations
- Performance metrics

## Authentication

The server supports two levels of authentication:

1. **Read-only Access**

   - Requires: `client_id` and `client_secret`
   - Allows: Fetching public data, reading posts/comments

2. **Authenticated Access**
   - Requires: All read-only credentials PLUS `username` and `password`
   - Allows: All read-only operations PLUS posting and commenting

## Deployment to Google Cloud Run

Deploy this MCP server to Google Cloud Run for remote access via streamable-http transport - **no Dockerfile needed!**

### Prerequisites

- **Google Cloud Account**: Create at [cloud.google.com](https://cloud.google.com)
- **gcloud CLI**: Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- **Reddit API Credentials**: Your `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`

### Quick Deployment (Source-Based)

**Basic deployment (without authentication):**

```bash
# 1. Authenticate with Google Cloud
gcloud auth login

# 2. Set your project ID
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# 3. Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# 4. Deploy directly from source
gcloud run deploy reddit-mcp \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=streamable-http,REDDIT_CLIENT_ID=your_client_id,REDDIT_CLIENT_SECRET=your_client_secret,REDDIT_USER_AGENT=RedditMCPServer/1.0

# 5. Get your service URL
gcloud run services describe reddit-mcp --region us-central1 --format 'value(status.url)'
```

**Secure deployment (with Bearer Token authentication):**

```bash
# Generate a secure bearer token
export BEARER_TOKEN=$(openssl rand -base64 32)
echo "Your Bearer Token: $BEARER_TOKEN"
# ⚠️ Save this token securely!

# Deploy with Bearer Token
gcloud run deploy reddit-mcp \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=streamable-http,MCP_BEARER_TOKEN=$BEARER_TOKEN,REDDIT_CLIENT_ID=your_client_id,REDDIT_CLIENT_SECRET=your_client_secret,REDDIT_USER_AGENT=RedditMCPServer/1.0
```

Google Cloud Buildpacks automatically detects your Python app, installs dependencies, and builds the container.

### MCP Client Configuration

**Without authentication:**

```json
{
  "mcpServers": {
    "reddit": {
      "transport": "streamable-http",
      "url": "https://reddit-mcp-xxxxx.run.app/mcp"
    }
  }
}
```

**With Bearer Token authentication:**

```json
{
  "mcpServers": {
    "reddit": {
      "transport": "streamable-http",
      "url": "https://reddit-mcp-xxxxx.run.app/mcp",
      "headers": {
        "Authorization": "Bearer your_generated_token_here"
      }
    }
  }
}
```

### Local Testing

**Stdio mode (default, for local MCP clients):**

```bash
# Install dependencies
uv pip install -e .

# Set environment variables
export REDDIT_CLIENT_ID=your_client_id
export REDDIT_CLIENT_SECRET=your_client_secret
export REDDIT_USER_AGENT=RedditMCPServer/1.0

# Run with stdio (default)
python server.py
```

**HTTP mode (for testing Cloud Run setup locally):**

```bash
# Install with auth support
uv pip install -e ".[auth]"

# Without Bearer Token
export MCP_TRANSPORT=streamable-http
export PORT=8080
export REDDIT_CLIENT_ID=your_client_id
export REDDIT_CLIENT_SECRET=your_client_secret
export REDDIT_USER_AGENT=RedditMCPServer/1.0

python server.py
curl http://localhost:8080/mcp

# With Bearer Token
export MCP_BEARER_TOKEN=test-token-123
python server.py
curl -H "Authorization: Bearer test-token-123" http://localhost:8080/mcp
```

### Monitoring and Logs

**View real-time logs:**

```bash
# Stream live logs from your deployed service
gcloud run services logs tail reddit-mcp --region us-central1

# View logs in Cloud Console
# https://console.cloud.google.com/run/detail/us-central1/reddit-mcp/logs
```

**View logs for a specific time period:**

```bash
# Last 10 log entries
gcloud run services logs read reddit-mcp --region us-central1 --limit 10

# Logs from the last hour
gcloud run services logs read reddit-mcp --region us-central1 --filter="timestamp>=\"$(date -u -d '1 hour ago' --rfc-3339=seconds)\""
```

**Check service status:**

```bash
# Get service details
gcloud run services describe reddit-mcp --region us-central1

# List all revisions
gcloud run revisions list --service reddit-mcp --region us-central1
```

**Update environment variables:**

```bash
# Update a single environment variable
gcloud run services update reddit-mcp --region us-central1 \
  --update-env-vars MCP_BEARER_TOKEN=new_token_here

# View current environment variables
gcloud run services describe reddit-mcp --region us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.