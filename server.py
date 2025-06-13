import logging
import time
from datetime import datetime
from os import getenv
from typing import Dict, Optional

import praw  # type: ignore
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Reddit MCP")

# Global variable to track if Reddit client is in read-only mode
_reddit_client = None
_reddit_is_read_only = None

def get_reddit_client() -> Optional[praw.Reddit]:
    """Initialize and return Reddit client with or without credentials"""
    global _reddit_client, _reddit_is_read_only
    
    # Return cached client if already initialized
    if _reddit_client is not None:
        return _reddit_client
    
    """Initialize and return Reddit client with or without credentials"""
    client_id = getenv("REDDIT_CLIENT_ID")
    client_secret = getenv("REDDIT_CLIENT_SECRET")
    user_agent = getenv("REDDIT_USER_AGENT", "RedditMCPServer v1.0")
    username = getenv("REDDIT_USERNAME")
    password = getenv("REDDIT_PASSWORD")

    # Initialize with read-only mode flag
    _reddit_is_read_only = True

    try:
        # Check if we have credentials for authenticated access
        if username and password and client_id and client_secret:
            logger.info(f"Attempting to initialize Reddit client with user authentication for u/{username}")
            try:
                reddit_client = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    username=username,
                    password=password,
                    check_for_updates=False
                )
                # Test the authentication by making a simple API call
                reddit_client.user.me()
                logger.info(f"Successfully authenticated as u/{username}")
                _reddit_is_read_only = False
                return reddit_client
            except Exception as auth_error:
                logger.warning(f"Authentication failed for u/{username}: {auth_error}")
                logger.info("Falling back to read-only access")
                # Fall through to read-only initialization

        # Check if we have client credentials for read-only access
        if client_id and client_secret:
            logger.info("Initializing Reddit client with read-only access")
            return praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                check_for_updates=False,
                read_only=True
            )

        # Try to initialize in read-only mode without credentials
        logger.info("Initializing Reddit client in read-only mode without credentials")
        reddit_client = praw.Reddit(
            user_agent=user_agent,
            check_for_updates=False,
            read_only=True,
        )
        # Test read-only access by fetching a public subreddit
        try:
            reddit_client.subreddit("popular").hot(limit=1)
            return reddit_client
        except Exception as e:
            logger.error(f"Failed to initialize read-only client: {e}")
            return None

    except Exception as e:
        logger.error(f"Error initializing Reddit client: {e}")
        return None

# Initialize Reddit client
_reddit_client = get_reddit_client()

def require_write_access(func):
    """Decorator to ensure write access is available"""
    def wrapper(*args, **kwargs):
        if reddit_is_read_only:
            raise ValueError("Write operation not allowed in read-only mode. Please provide valid credentials.")
        if not _check_user_auth():
            raise Exception("Authentication required for write operations.")
        return func(*args, **kwargs)
    return wrapper

def _format_timestamp(timestamp: float) -> str:
    """Convert Unix timestamp to human readable format.

    Args:
        timestamp (float): Unix timestamp

    Returns:
        str: Formatted date string
    """
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(timestamp)

def _analyze_user_activity(karma_ratio: float, is_mod: bool, account_age_days: float) -> str:
    """Generate insights about user's Reddit activity and engagement."""
    insights = []

    # Analyze karma ratio
    if karma_ratio > 5:
        insights.append("Primarily a commenter, highly engaged in discussions")
    elif karma_ratio < 0.2:
        insights.append("Content creator, focuses on sharing posts")
    else:
        insights.append("Balanced participation in both posting and commenting")

    # Analyze account age and status
    if account_age_days < 30:
        insights.append("New user, still exploring Reddit")
    elif account_age_days > 365 * 5:
        insights.append("Long-time Redditor with extensive platform experience")

    if is_mod:
        insights.append("Community leader who helps maintain subreddit quality")

    return "\n  - ".join(insights)

def _analyze_post_engagement(score: int, ratio: float, num_comments: int) -> str:
    """Generate insights about post engagement and performance."""
    insights = []

    # Analyze score and ratio
    if score > 1000 and ratio > 0.95:
        insights.append("Highly successful post with strong community approval")
    elif score > 100 and ratio > 0.8:
        insights.append("Well-received post with good engagement")
    elif ratio < 0.5:
        insights.append("Controversial post that sparked debate")

    # Analyze comment activity
    if num_comments > 100:
        insights.append("Generated significant discussion")
    elif num_comments > score * 0.5:
        insights.append("Highly discussable content with active comment section")
    elif num_comments == 0:
        insights.append("Yet to receive community interaction")

    return "\n  - ".join(insights)

def _analyze_subreddit_health(subscribers: int, active_users: int, age_days: float) -> str:
    """Generate insights about subreddit health and activity."""
    insights = []

    # Analyze size and activity
    if subscribers > 1000000:
        insights.append("Major subreddit with massive following")
    elif subscribers > 100000:
        insights.append("Well-established community")
    elif subscribers < 1000:
        insights.append("Niche community, potential for growth")

    if active_users:  # If we have active users data
        activity_ratio = active_users / subscribers if subscribers > 0 else 0
        if activity_ratio > 0.1:
            insights.append("Highly active community with strong engagement")
        elif activity_ratio < 0.01:
            insights.append("Could benefit from more community engagement initiatives")

    # Analyze age and maturity
    if age_days > 365 * 5:
        insights.append("Mature subreddit with established culture")
    elif age_days < 90:
        insights.append("New subreddit still forming its community")

    return "\n  - ".join(insights)

def _format_user_info(user: praw.models.Redditor) -> str:
    """Format user information with AI-driven insights."""
    status = []
    if user.is_mod: status.append("Moderator")
    if user.is_gold: status.append("Reddit Gold Member")
    if user.is_employee: status.append("Reddit Employee")

    account_age = (time.time() - user.created_utc) / (24 * 3600)  # age in days
    karma_ratio = user.comment_karma / user.link_karma if user.link_karma > 0 else float('inf')

    return f"""
        • Username: u/{user.name}
        • Karma:
        - Comment Karma: {user.comment_karma:,}
        - Post Karma: {user.link_karma:,}
        - Total Karma: {user.comment_karma + user.link_karma:,}
        • Account Status: {', '.join(status) if status else 'Regular User'}
        • Account Created: {_format_timestamp(user.created_utc)}
        • Profile URL: https://reddit.com/user/{user.name}

        📊 Activity Analysis:
        - {_analyze_user_activity(karma_ratio, user.is_mod, account_age)}

        💡 Recommendations:
        - {_get_user_recommendations(karma_ratio, user.is_mod, account_age)}
        """

def _format_post(post: praw.models.Submission) -> str:
    """Format post information with AI-driven insights."""
    content_type = "Text Post" if post.is_self else "Link Post"
    content = post.selftext if post.is_self else post.url

    flags = []
    if post.over_18: flags.append("NSFW")
    if hasattr(post, 'spoiler') and post.spoiler: flags.append("Spoiler")
    if post.edited: flags.append("Edited")

    # Add image URL section for non-self posts
    image_url_section = f"""
        • Image URL: {post.url}""" if not post.is_self else ""

    return f"""
        • Title: {post.title}
        • Type: {content_type}
        • Content: {content}
        • Author: u/{str(post.author)}
        • Subreddit: r/{str(post.subreddit)}{image_url_section}
        • Stats:
        - Score: {post.score:,}
        - Upvote Ratio: {post.upvote_ratio * 100:.1f}%
        - Comments: {post.num_comments:,}
        • Metadata:
        - Posted: {_format_timestamp(post.created_utc)}
        - Flags: {', '.join(flags) if flags else 'None'}
        - Flair: {post.link_flair_text or 'None'}
        • Links:
        - Full Post: https://reddit.com{post.permalink}
        - Short Link: https://redd.it/{post.id}

        📈 Engagement Analysis:
        - {_analyze_post_engagement(post.score, post.upvote_ratio, post.num_comments)}

        🎯 Best Time to Engage:
        - {_get_best_engagement_time(post.created_utc, post.score)}
        """

def _format_subreddit(subreddit: praw.models.Subreddit) -> str:
    """Format subreddit information with AI-driven insights."""
    flags = []
    if subreddit.over18: flags.append("NSFW")
    if hasattr(subreddit, 'subreddit_type'): flags.append(f"Type: {subreddit.subreddit_type}")

    age_days = (time.time() - subreddit.created_utc) / (24 * 3600)

    return f"""
        • Name: r/{subreddit.display_name}
        • Title: {subreddit.title}
        • Stats:
        - Subscribers: {subreddit.subscribers:,}
        - Active Users: {subreddit.active_user_count if hasattr(subreddit, 'active_user_count') else 'Unknown'}
        • Description:
        - Short: {subreddit.public_description}
        - Full: {subreddit.description}
        • Metadata:
        - Created: {_format_timestamp(subreddit.created_utc)}
        - Flags: {', '.join(flags) if flags else 'None'}
        • Links:
        - Subreddit: https://reddit.com{subreddit.url}
        - Wiki: https://reddit.com/r/{subreddit.display_name}/wiki

        🔍 Community Analysis:
        - {_analyze_subreddit_health(subreddit.subscribers, getattr(subreddit, 'active_user_count', 0), age_days)}

        📱 Engagement Tips:
        - {_get_subreddit_engagement_tips(subreddit)}
        """

def _get_user_recommendations(karma_ratio: float, is_mod: bool, account_age_days: float) -> str:
    """Generate personalized recommendations for user engagement."""
    recommendations = []

    if karma_ratio > 5:
        recommendations.append("Consider creating more posts to share your expertise")
    elif karma_ratio < 0.2:
        recommendations.append("Engage more in discussions to build community connections")

    if account_age_days < 30:
        recommendations.append("Explore popular subreddits in your areas of interest")
        recommendations.append("Read community guidelines before posting")

    if is_mod:
        recommendations.append("Share moderation insights with other community leaders")

    if not recommendations:
        recommendations.append("Maintain your balanced engagement across Reddit")

    return "\n  - ".join(recommendations)

def _get_best_engagement_time(created_utc: float, score: int) -> str:
    """Analyze and suggest optimal posting times based on post performance."""
    post_hour = datetime.fromtimestamp(created_utc).hour

    # Simple time zone analysis
    if 14 <= post_hour <= 18:  # Peak Reddit hours
        return "Posted during peak engagement hours (2 PM - 6 PM), good timing!"
    elif 23 <= post_hour or post_hour <= 5:
        return "Consider posting during more active hours (morning to evening)"
    else:
        return "Posted during moderate activity hours, timing could be optimized"

def _get_subreddit_engagement_tips(subreddit: praw.models.Subreddit) -> str:
    """Generate engagement tips based on subreddit characteristics."""
    tips = []

    if subreddit.subscribers > 1000000:
        tips.append("Post during peak hours for maximum visibility")
        tips.append("Ensure content is highly polished due to high competition")
    elif subreddit.subscribers < 1000:
        tips.append("Engage actively to help grow the community")
        tips.append("Consider cross-posting to related larger subreddits")

    if hasattr(subreddit, 'active_user_count') and subreddit.active_user_count:
        activity_ratio = subreddit.active_user_count / subreddit.subscribers
        if activity_ratio > 0.1:
            tips.append("Quick responses recommended due to high activity")

    return "\n  - ".join(tips or ["Regular engagement recommended to maintain community presence"])

def _check_post_exists(post_id: str) -> bool:
    """Verify that a post exists and is accessible.

    Args:
        post_id (str): The ID of the post to check

    Returns:
        bool: True if post exists and is accessible, False otherwise
    """
    if not reddit:
        return False

    try:
        submission = reddit.submission(id=post_id)
        # Try to access some attributes to verify the post exists
        _ = submission.title
        _ = submission.author
        return True
    except Exception as e:
        logger.error(f"Error checking post existence: {str(e)}")
        return False


def _check_user_auth() -> bool:
    """Check if user authentication is available for write operations"""
    if not reddit:
        logger.error("Reddit client not initialized")
        return False
    
    if _reddit_is_read_only:
        logger.error("Reddit client is in read-only mode")
        return False
    
    # Optional: Keep the try/except only for first-time verification
    # or remove it entirely since we already verified during init
    return True


def _format_comment(comment: praw.models.Comment) -> str:
    """Format comment information with AI-driven insights."""
    flags = []
    if comment.edited: flags.append("Edited")
    if hasattr(comment, 'is_submitter') and comment.is_submitter: flags.append("OP")

    return f"""
        • Author: u/{str(comment.author)}
        • Content: {comment.body}
        • Stats:
        - Score: {comment.score:,}
        - Controversiality: {comment.controversiality if hasattr(comment, 'controversiality') else 'Unknown'}
        • Context:
        - Subreddit: r/{str(comment.subreddit)}
        - Thread: {comment.submission.title}
        • Metadata:
        - Posted: {_format_timestamp(comment.created_utc)}
        - Flags: {', '.join(flags) if flags else 'None'}
        • Link: https://reddit.com{comment.permalink}

        💬 Comment Analysis:
        - {_analyze_comment_impact(comment.score, bool(comment.edited), hasattr(comment, 'is_submitter'))}
        """

def _analyze_comment_impact(score: int, is_edited: bool, is_op: bool) -> str:
    """Analyze comment's impact and context."""
    insights = []

    if score > 100:
        insights.append("Highly upvoted comment with significant community agreement")
    elif score < 0:
        insights.append("Controversial or contested viewpoint")

    if is_edited:
        insights.append("Refined for clarity or accuracy")
    if is_op:
        insights.append("Author's perspective adds context to original post")

    return "\n  - ".join(insights or ["Standard engagement with discussion"])

@mcp.tool()
def get_user_info(username: str) -> Dict:
    """Get information about a Reddit user.

    Args:
        username (str): The username of the Reddit user to get info for

    Returns:
        Dict: Formatted user information as bullet points
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting info for u/{username}")
        user = reddit.redditor(username)
        return {"result": _format_user_info(user)}
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise

@mcp.tool()
def get_top_posts(subreddit: str, time_filter: str = "week", limit: int = 10) -> Dict:
    """Get top posts from a subreddit.

    Args:
        subreddit (str): Name of the subreddit
        time_filter (str): Time period to filter posts (e.g. "day", "week", "month", "year", "all")
        limit (int): Number of posts to fetch

    Returns:
        Dict: List of formatted top posts as bullet points
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting top posts from r/{subreddit}")
        posts = reddit.subreddit(subreddit).top(time_filter=time_filter, limit=limit)

        formatted_posts = [_format_post(post) for post in posts]
        summary = f"""
        Top {limit} Posts from r/{subreddit} ({time_filter}):
        Fetched at: {_format_timestamp(time.time())}

        {'=' * 50}
        """ + f"\n{'=' * 50}\n".join(formatted_posts)

        return {"result": summary}
    except Exception as e:
        logger.error(f"Error getting top posts: {e}")
        raise

@mcp.tool()
def get_subreddit_info(subreddit_name: str) -> Dict:
    """Get information about a subreddit.

    Args:
        subreddit_name (str): Name of the subreddit

    Returns:
        Dict: Subreddit information including description, subscribers, etc.
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting info for r/{subreddit_name}")
        subreddit = reddit.subreddit(subreddit_name)
        return {
            "display_name": subreddit.display_name,
            "title": subreddit.title,
            "description": subreddit.description,
            "subscribers": subreddit.subscribers,
            "created_utc": subreddit.created_utc,
            "over18": subreddit.over18,
            "public_description": subreddit.public_description,
            "url": subreddit.url,
        }
    except Exception as e:
        logger.error(f"Error getting subreddit info: {e}")
        raise

@mcp.tool()
def get_trending_subreddits() -> Dict:
    """Get currently trending subreddits.

    Returns:
        Dict: List of trending subreddit names
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info("Getting trending subreddits")
        popular_subreddits = reddit.subreddits.popular(limit=5)
        trending = [subreddit.display_name for subreddit in popular_subreddits]
        return {"trending_subreddits": trending}
    except Exception as e:
        logger.error(f"Error getting trending subreddits: {e}")
        raise

@mcp.tool()
def get_subreddit_stats(subreddit: str) -> Dict:
    """Get statistics about a subreddit.

    Args:
        subreddit (str): Name of the subreddit

    Returns:
        Dict: Formatted subreddit statistics and information
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting stats for r/{subreddit}")
        sub = reddit.subreddit(subreddit)
        return {"subreddit": _format_subreddit(sub)}
    except Exception as e:
        logger.error(f"Error getting subreddit stats: {e}")
        raise

@mcp.tool()
@require_write_access
def create_post(
    subreddit: str,
    title: str,
    content: str,
    flair: Optional[str] = None,
    is_self: bool = True,
) -> Dict:
    """Create a new post in a subreddit.

    Args:
        subreddit (str): Name of the subreddit to post in
        title (str): Title of the post
        content (str): Content of the post (text for self posts, URL for link posts)
        flair (Optional[str]): Flair to add to the post. Must be an available flair in the subreddit
        is_self (bool): Whether this is a self (text) post (True) or link post (False)

    Returns:
        Dict: Formatted information about the created post

    Raises:
        ValueError: If the client is in read-only mode
    """
    if _reddit_is_read_only:
        raise ValueError("Cannot create posts in read-only mode. Please provide valid credentials.")

    if not reddit:
        raise Exception("Reddit client not initialized")

    if not _check_user_auth():
        raise Exception("Authentication required for posting. Please provide valid REDDIT_USERNAME and REDDIT_PASSWORD environment variables.")

    try:
        logger.info(f"Creating post in r/{subreddit}")
        subreddit_obj = reddit.subreddit(subreddit)

        if flair:
            available_flairs = [f["text"] for f in subreddit_obj.flair.link_templates]
            if flair not in available_flairs:
                raise ValueError(f"Invalid flair. Available flairs: {', '.join(available_flairs)}")

        if is_self:
            submission = subreddit_obj.submit(
                title=title,
                selftext=content,
                flair_id=flair,
            )
        else:
            submission = subreddit_obj.submit(
                title=title,
                url=content,
                flair_id=flair,
            )
        logger.info(f"Post created: {submission.permalink}")

        return {
            "post": _format_post(submission),
            "metadata": {
                "created_at": _format_timestamp(time.time()),
                "subreddit": subreddit,
                "is_self_post": is_self
            }
        }

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise

@mcp.tool()
@require_write_access
def reply_to_post(post_id: str, content: str, subreddit: Optional[str] = None) -> Dict:
    """Post a reply to an existing Reddit post.

    Args:
        post_id (str): The ID of the post to reply to (can be full URL, permalink, or just ID)
        content (str): The content of the reply
        subreddit (Optional[str]): The subreddit name if known (for validation)

    Returns:
        Dict: Formatted information about the created reply

    Raises:
        ValueError: If the client is in read-only mode
    """
    if _reddit_is_read_only:
        raise ValueError("Cannot create replies in read-only mode. Please provide valid credentials.")

    if not reddit:
        raise Exception("Reddit client not initialized")

    if not _check_user_auth():
        raise Exception("Authentication required for replying to posts. Please provide valid REDDIT_USERNAME and REDDIT_PASSWORD environment variables.")

    try:
        logger.info(f"Creating reply to post {post_id}")

        # Clean up the post_id if it's a full URL or permalink
        if "/" in post_id:
            original_id = post_id
            post_id = post_id.split("/")[-1]
            logger.info(f"Extracted post ID {post_id} from {original_id}")

        # Verify post exists
        if not _check_post_exists(post_id):
            raise ValueError(f"Post with ID {post_id} does not exist or is not accessible")

        # Get the submission object
        submission = reddit.submission(id=post_id)

        logger.info(
            f"Post details: Title: {submission.title}, Author: {submission.author}, Subreddit: {submission.subreddit.display_name}"
        )

        # If subreddit was provided, verify we're in the right place
        if subreddit and submission.subreddit.display_name.lower() != subreddit.lower():
            raise ValueError(f"Post ID belongs to r/{submission.subreddit.display_name}, not r/{subreddit}")

        # Create the reply
        logger.info(f"Attempting to post reply with content length: {len(content)}")
        reply = submission.reply(body=content)

        return {
            "reply": _format_comment(reply),
            "parent_post": _format_post(submission),
            "metadata": {
                "created_at": _format_timestamp(time.time())
            }
        }

    except Exception as e:
        logger.error(f"Error creating reply: {e}")
        raise

@mcp.tool()
@require_write_access
def reply_to_comment(comment_id: str, content: str, subreddit: Optional[str] = None) -> Dict:
    """Post a reply to an existing Reddit comment.

    Args:
        comment_id (str): The ID of the comment to reply to (can be full URL, permalink, or just ID)
        content (str): The content of the reply
        subreddit (Optional[str]): The subreddit name if known (for validation)

    Returns:
        Dict: Formatted information about the created reply
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    # Check if client is in read-only mode
    if _reddit_is_read_only:
        raise ValueError("Cannot reply to comment: Reddit client is in read-only mode. Please provide valid credentials.")

    if not _check_user_auth():
        raise Exception("Authentication required for replying to comments. Please provide valid REDDIT_USERNAME and REDDIT_PASSWORD environment variables.")

    try:
        logger.info(f"Creating reply to comment {comment_id}")

        # Clean up the comment_id if it's a full URL or permalink
        if "/" in comment_id:
            original_id = comment_id
            comment_id = comment_id.split("/")[-1]
            logger.info(f"Extracted comment ID {comment_id} from {original_id}")

        # Get the comment object
        comment = reddit.comment(id=comment_id)

        logger.info(f"Comment details: Author: {comment.author}, Subreddit: {comment.subreddit.display_name}")

        # If subreddit was provided, verify we're in the right place
        if subreddit and comment.subreddit.display_name.lower() != subreddit.lower():
            raise ValueError(f"Comment ID belongs to r/{comment.subreddit.display_name}, not r/{subreddit}")

        # Create the reply
        logger.info(f"Attempting to post reply with content length: {len(content)}")
        reply = comment.reply(body=content)

        return {
            "reply": _format_comment(reply),
            "parent_comment": _format_comment(comment),
            "thread": _format_post(comment.submission),
            "metadata": {
                "created_at": _format_timestamp(time.time())
            }
        }

    except Exception as e:
        logger.error(f"Error creating reply: {e}")
        raise

@mcp.tool()
def get_submission_by_url(url: str) -> Dict:
    """Get a Reddit submission by its URL.

    Args:
        url (str): The URL of the Reddit submission to retrieve

    Returns:
        Dict: Formatted information about the submission
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting submission from URL: {url}")

        # Create submission from URL
        submission = reddit.submission(url=url)

        # Verify the submission exists by accessing its attributes
        _ = submission.title
        _ = submission.author

        return {
            "submission": _format_post(submission),
            "metadata": {
                "retrieved_at": _format_timestamp(time.time())
            }
        }
    except Exception as e:
        logger.error(f"Error getting submission by URL: {e}")
        raise

@mcp.tool()
def get_submission_by_id(submission_id: str) -> Dict:
    """Get a Reddit submission by its ID.

    Args:
        submission_id (str): The ID of the Reddit submission to retrieve

    Returns:
        Dict: Formatted information about the submission
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    try:
        logger.info(f"Getting submission with ID: {submission_id}")

        # Clean up the submission_id if it's a full URL or permalink
        if "/" in submission_id:
            original_id = submission_id
            submission_id = submission_id.split("/")[-1]
            logger.info(f"Extracted submission ID {submission_id} from {original_id}")

        # Create submission from ID
        submission = reddit.submission(id=submission_id)

        # Verify the submission exists by accessing its attributes
        _ = submission.title
        _ = submission.author

        return {
            "submission": _format_post(submission),
            "metadata": {
                "retrieved_at": _format_timestamp(time.time())
            }
        }
    except Exception as e:
        logger.error(f"Error getting submission by ID: {e}")
        raise

@mcp.tool()
@require_write_access
def who_am_i() -> Dict:
    """Get information about the currently authenticated user.

    Returns:
        Dict: Formatted information about the current user
    """
    if not reddit:
        raise Exception("Reddit client not initialized")

    if not _check_user_auth():
        raise Exception("User authentication required. Please provide username and password.")

    try:
        logger.info("Getting information about the current user")
        current_user = reddit.user.me()
        return {"result": _format_user_info(current_user)}
    except Exception as e:
        logger.error(f"Error getting current user info: {e}")
        raise

if __name__ == "__main__":
    mcp.run()