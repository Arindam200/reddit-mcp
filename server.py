import functools
import logging
import time
from datetime import datetime
from os import getenv
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar, cast

import praw  # type: ignore
from mcp.server.fastmcp import FastMCP

F = TypeVar("F", bound=Callable[..., Any])
if TYPE_CHECKING:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedditClientManager:
    """Manages the Reddit client and its state."""

    _instance = None
    _client = None
    _is_read_only = True

    def __new__(cls) -> "RedditClientManager":
        if cls._instance is None:
            cls._instance = super(RedditClientManager, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self) -> None:
        """Initialize the Reddit client with appropriate credentials."""
        client_id = getenv("REDDIT_CLIENT_ID")
        client_secret = getenv("REDDIT_CLIENT_SECRET")
        user_agent = getenv("REDDIT_USER_AGENT", "RedditMCPServer v1.0")
        username = getenv("REDDIT_USERNAME")
        password = getenv("REDDIT_PASSWORD")

        self._is_read_only = True

        try:
            # Try authenticated access first if credentials are provided
            if all([username, password, client_id, client_secret]):
                logger.info(
                    f"Attempting to initialize Reddit client with user authentication for u/{username}"
                )
                try:
                    self._client = praw.Reddit(
                        client_id=client_id,
                        client_secret=client_secret,
                        user_agent=user_agent,
                        username=username,
                        password=password,
                        check_for_updates=False,
                    )
                    # Test authentication
                    if self._client.user.me() is None:
                        raise ValueError(f"Failed to authenticate as u/{username}")

                    logger.info(f"Successfully authenticated as u/{username}")
                    self._is_read_only = False
                    return
                except Exception as auth_error:
                    logger.warning(f"Authentication failed: {auth_error}")
                    logger.info("Falling back to read-only access")

            # Fall back to read-only with client credentials
            if client_id and client_secret:
                logger.info("Initializing Reddit client with read-only access")
                self._client = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    check_for_updates=False,
                    read_only=True,
                )
                return

            # Last resort: read-only without credentials
            logger.info(
                "Initializing Reddit client in read-only mode without credentials"
            )
            self._client = praw.Reddit(
                user_agent=user_agent,
                check_for_updates=False,
                read_only=True,
            )
            # Test read-only access
            self._client.subreddit("popular").hot(limit=1)

        except Exception as e:
            logger.error(f"Error initializing Reddit client: {e}")
            self._client = None

    @property
    def client(self) -> Optional[praw.Reddit]:
        """Get the Reddit client instance."""
        return self._client

    @property
    def is_read_only(self) -> bool:
        """Check if the client is in read-only mode."""
        return self._is_read_only

    def check_user_auth(self) -> bool:
        """Check if user authentication is available for write operations."""
        if not self._client:
            logger.error("Reddit client not initialized")
            return False
        if self._is_read_only:
            logger.error("Reddit client is in read-only mode")
            return False
        return True


def require_write_access(func: F) -> F:
    """Decorator to ensure write access is available."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        reddit_manager = RedditClientManager()
        if reddit_manager.is_read_only:
            raise ValueError(
                "Write operation not allowed in read-only mode. Please provide valid credentials."
            )
        if not reddit_manager.check_user_auth():
            raise Exception(
                "Authentication required for write operations. "
                "Please provide valid REDDIT_USERNAME and REDDIT_PASSWORD environment variables."
            )
        return func(*args, **kwargs)

    return cast(F, wrapper)


mcp = FastMCP("Reddit MCP")
reddit_manager = RedditClientManager()


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


def _format_post(post: praw.models.Submission) -> str:
    """Format post information with AI-driven insights."""
    content_type = "Text Post" if post.is_self else "Link Post"
    content = post.selftext if post.is_self else post.url

    flags = []
    if post.over_18:
        flags.append("NSFW")
    if hasattr(post, "spoiler") and post.spoiler:
        flags.append("Spoiler")
    if post.edited:
        flags.append("Edited")

    # Add image URL section for non-self posts
    image_url_section = (
        f"""
        • Image URL: {post.url}"""
        if not post.is_self
        else ""
    )

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
        - Flags: {", ".join(flags) if flags else "None"}
        - Flair: {post.link_flair_text or "None"}
        • Links:
        - Full Post: https://reddit.com{post.permalink}
        - Short Link: https://redd.it/{post.id}

        📈 Engagement Analysis:
        - {_analyze_post_engagement(post.score, post.upvote_ratio, post.num_comments)}

        🎯 Best Time to Engage:
        - {_get_best_engagement_time(post.created_utc, post.score)}
        """


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


def _extract_reddit_id(reddit_id: str) -> str:
    """Extract the base ID from a Reddit URL or ID.

    Args:
        reddit_id: Either a Reddit ID or a URL containing the ID

    Returns:
        The extracted Reddit ID
    """
    if not reddit_id:
        raise ValueError("Empty ID provided")

    # If it's a URL, extract the ID part
    if "/" in reddit_id:
        # Handle both standard URLs and permalinks
        parts = [p for p in reddit_id.split("/") if p]
        # The ID is typically the last non-empty part
        reddit_id = parts[-1]
        logger.debug(f"Extracted ID {reddit_id} from URL")

    return reddit_id


def _format_comment(comment: praw.models.Comment) -> str:
    """Format comment information with AI-driven insights."""
    flags = []
    if comment.edited:
        flags.append("Edited")
    if hasattr(comment, "is_submitter") and comment.is_submitter:
        flags.append("OP")

    return f"""
        • Author: u/{str(comment.author)}
        • Content: {comment.body}
        • Stats:
        - Score: {comment.score:,}
        - Controversiality: {comment.controversiality if hasattr(comment, "controversiality") else "Unknown"}
        • Context:
        - Subreddit: r/{str(comment.subreddit)}
        - Thread: {comment.submission.title}
        • Metadata:
        - Posted: {_format_timestamp(comment.created_utc)}
        - Flags: {", ".join(flags) if flags else "None"}
        • Link: https://reddit.com{comment.permalink}

        💬 Comment Analysis:
        - {_analyze_comment_impact(comment.score, bool(comment.edited), hasattr(comment, "is_submitter"))}
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
def get_user_info(username: str) -> Dict[str, Any]:
    """Get information about a Reddit user.

    Args:
        username: The username of the Reddit user to get info for

    Returns:
        Dictionary containing user information with the following structure:
        {
            'username': str,  # User's username
            'created_utc': float,  # Account creation timestamp
            'comment_karma': int,  # User's comment karma
            'link_karma': int,  # User's post/link karma
            'has_verified_email': bool,  # Whether email is verified
            'is_mod': bool,  # Whether user is a moderator
            'is_gold': bool,  # Whether user has Reddit premium
            'has_subscribed': bool,  # Whether user has subscribed to premium
            'is_employee': bool,  # Whether user is a Reddit employee
            'over_18': bool,  # Whether user is marked as NSFW
            'is_suspended': bool,  # Whether account is suspended
            'suspension_expiration_utc': Optional[float],  # When suspension ends if suspended
            'total_karma': int,  # Total karma (comments + posts)
            'subreddit': Optional[Dict],  # User's profile subreddit info if exists
        }

    Raises:
        ValueError: If the username is invalid or not found
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not username or not isinstance(username, str) or username.startswith((" ", "/")):
        raise ValueError("Invalid username provided")

    # Clean up the username (remove u/ prefix if present)
    clean_username = username[2:] if username.startswith("u/") else username

    try:
        logger.info(f"Getting info for u/{clean_username}")
        user = manager.client.redditor(clean_username)
        # Force fetch user data to verify it exists
        _ = user.created_utc

        # Format the user info in a structured way
        return {
            "username": user.name,
            "created_utc": user.created_utc,
            "comment_karma": user.comment_karma,
            "link_karma": user.link_karma,
            "has_verified_email": getattr(user, "has_verified_email", False),
            "is_mod": getattr(user, "is_mod", False),
            "is_gold": getattr(user, "is_gold", False),
            "has_subscribed": getattr(user, "has_subscribed", False),
            "is_employee": getattr(user, "is_employee", False),
            "over_18": getattr(user, "over_18", False),
            "is_suspended": getattr(user, "is_suspended", False),
            "suspension_expiration_utc": getattr(
                user, "suspension_expiration_utc", None
            ),
            "total_karma": getattr(
                user, "total_karma", user.comment_karma + user.link_karma
            ),
            "subreddit": {
                "display_name": user.subreddit.display_name,
                "title": getattr(user.subreddit, "title", ""),
                "public_description": getattr(user.subreddit, "public_description", ""),
                "subscribers": getattr(user.subreddit, "subscribers", 0),
            }
            if hasattr(user, "subreddit") and user.subreddit
            else None,
        }
    except Exception as e:
        logger.error(f"Error getting user info for u/{clean_username}: {e}")
        if hasattr(e, "message") and "USER_DOESNT_EXIST" in str(e):
            raise ValueError(f"User u/{clean_username} not found") from e
        if "NOT_FOUND" in str(e):
            raise ValueError(f"User u/{clean_username} not found") from e
        raise RuntimeError(f"Failed to get user info: {e}") from e


@mcp.tool()
def get_top_posts(
    subreddit: str, time_filter: str = "week", limit: int = 10
) -> Dict[str, Any]:
    """Get top posts from a subreddit.

    Args:
        subreddit: Name of the subreddit (with or without 'r/' prefix)
        time_filter: Time period to filter posts (e.g. "day", "week", "month", "year", "all")
        limit: Number of posts to fetch (1-100)

    Returns:
        Dictionary containing structured post information with the following structure:
        {
            'subreddit': str,  # Subreddit name
            'time_filter': str,  # The time period used for filtering
            'posts': [  # List of posts, each with the following structure:
                {
                    'id': str,  # Post ID
                    'title': str,  # Post title
                    'author': str,  # Author's username
                    'score': int,  # Post score (upvotes - downvotes)
                    'upvote_ratio': float,  # Ratio of upvotes to total votes
                    'num_comments': int,  # Number of comments
                    'created_utc': float,  # Post creation timestamp
                    'url': str,  # URL to the post
                    'permalink': str,  # Relative URL to the post
                    'is_self': bool,  # Whether it's a self (text) post
                    'selftext': str,  # Content of self post (if any)
                    'link_url': str,  # URL for link posts (if any)
                    'over_18': bool,  # Whether marked as NSFW
                    'spoiler': bool,  # Whether marked as spoiler
                    'stickied': bool,  # Whether stickied in the subreddit
                    'locked': bool,  # Whether comments are locked
                    'distinguished': Optional[str],  # Distinguishing type (e.g., 'moderator')
                    'flair': Optional[Dict],  # Post flair information if any
                },
                ...
            ],
            'metadata': {
                'fetched_at': float,  # Timestamp when data was fetched
                'post_count': int,  # Number of posts returned
            }
        }

    Raises:
        ValueError: If subreddit is invalid or time_filter is not valid
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not subreddit or not isinstance(subreddit, str):
        raise ValueError("Subreddit name is required")

    valid_time_filters = ["hour", "day", "week", "month", "year", "all"]
    if time_filter not in valid_time_filters:
        raise ValueError(
            f"Invalid time filter. Must be one of: {', '.join(valid_time_filters)}"
        )

    limit = max(1, min(100, limit))  # Ensure limit is between 1 and 100

    # Clean up subreddit name (remove r/ prefix if present)
    clean_subreddit = subreddit[2:] if subreddit.startswith("r/") else subreddit

    try:
        logger.info(
            f"Getting top {limit} posts from r/{clean_subreddit} (time_filter={time_filter})"
        )

        # Get the subreddit
        sub = manager.client.subreddit(clean_subreddit)

        # Verify subreddit exists and is accessible
        _ = sub.display_name

        # Fetch posts
        posts = list(sub.top(time_filter=time_filter, limit=limit))

        if not posts:
            return {
                "subreddit": clean_subreddit,
                "time_filter": time_filter,
                "posts": [],
                "metadata": {"fetched_at": time.time(), "post_count": 0},
            }

        # Format posts into structured data
        formatted_posts = []
        for post in posts:
            try:
                # Get post data with error handling for each field
                post_data = {
                    "id": post.id,
                    "title": post.title,
                    "author": str(post.author)
                    if hasattr(post, "author") and post.author
                    else "[deleted]",
                    "score": getattr(post, "score", 0),
                    "upvote_ratio": getattr(post, "upvote_ratio", 0.0),
                    "num_comments": getattr(post, "num_comments", 0),
                    "created_utc": post.created_utc,
                    "url": f"https://www.reddit.com{post.permalink}"
                    if hasattr(post, "permalink")
                    else "",
                    "permalink": getattr(post, "permalink", ""),
                    "is_self": getattr(post, "is_self", False),
                    "selftext": getattr(post, "selftext", ""),
                    "link_url": getattr(post, "url", ""),
                    "over_18": getattr(post, "over_18", False),
                    "spoiler": getattr(post, "spoiler", False),
                    "stickied": getattr(post, "stickied", False),
                    "locked": getattr(post, "locked", False),
                    "distinguished": getattr(post, "distinguished", None),
                }

                # Add flair information if available
                if hasattr(post, "link_flair_text") and post.link_flair_text:
                    post_data["flair"] = {
                        "text": post.link_flair_text,
                        "css_class": getattr(post, "link_flair_css_class", ""),
                        "template_id": getattr(post, "link_flair_template_id", None),
                        "text_color": getattr(post, "link_flair_text_color", None),
                        "background_color": getattr(
                            post, "link_flair_background_color", None
                        ),
                    }
                else:
                    post_data["flair"] = None

                formatted_posts.append(post_data)

            except Exception as post_error:
                logger.error(
                    f"Error processing post {getattr(post, 'id', 'unknown')}: {post_error}"
                )
                continue

        return {
            "subreddit": clean_subreddit,
            "time_filter": time_filter,
            "posts": formatted_posts,
            "metadata": {"fetched_at": time.time(), "post_count": len(formatted_posts)},
        }

    except Exception as e:
        logger.error(f"Error getting top posts from r/{clean_subreddit}: {e}")
        if "private" in str(e).lower():
            raise ValueError(
                f"r/{clean_subreddit} is private or cannot be accessed"
            ) from e
        if "banned" in str(e).lower():
            raise ValueError(
                f"r/{clean_subreddit} has been banned or doesn't exist"
            ) from e
        if "not found" in str(e).lower():
            raise ValueError(f"r/{clean_subreddit} not found") from e
        raise RuntimeError(f"Failed to get top posts: {e}") from e


@mcp.tool()
def get_subreddit_info(subreddit_name: str) -> Dict[str, Any]:
    """Get information about a subreddit.

    Args:
        subreddit_name: Name of the subreddit (with or without 'r/' prefix)

    Returns:
        Dictionary containing subreddit information

    Raises:
        ValueError: If subreddit_name is invalid or subreddit not found
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not subreddit_name or not isinstance(subreddit_name, str):
        raise ValueError("Subreddit name is required")

    # Clean up subreddit name (remove r/ prefix if present)
    clean_name = (
        subreddit_name[2:] if subreddit_name.startswith("r/") else subreddit_name
    )

    try:
        logger.info(f"Getting info for r/{clean_name}")
        subreddit = manager.client.subreddit(clean_name)

        # Force fetch subreddit data to verify it exists
        _ = subreddit.display_name

        return {
            "display_name": subreddit.display_name,
            "title": subreddit.title,
            "description": subreddit.description,
            "subscribers": subreddit.subscribers,
            "created_utc": subreddit.created_utc,
            "over18": subreddit.over18,
            "public_description": subreddit.public_description,
            "url": subreddit.url,
            "active_user_count": getattr(subreddit, "active_user_count", None),
            "subreddit_type": getattr(subreddit, "subreddit_type", None),
            "submission_type": getattr(subreddit, "submission_type", None),
            "quarantine": getattr(subreddit, "quarantine", False),
        }
    except Exception as e:
        logger.error(f"Error getting info for r/{clean_name}: {e}")
        if "private" in str(e).lower():
            raise ValueError(f"r/{clean_name} is private or cannot be accessed") from e
        if "banned" in str(e).lower():
            raise ValueError(f"r/{clean_name} has been banned or doesn't exist") from e
        if "not found" in str(e).lower():
            raise ValueError(f"r/{clean_name} not found") from e
        raise RuntimeError(f"Failed to get subreddit info: {e}") from e


@mcp.tool()
def get_trending_subreddits(limit: int = 5) -> "Dict[str, List[Dict[str, Any]]]":
    """Get currently trending subreddits.

    Args:
        limit: Maximum number of trending subreddits to return (1-50)

    Returns:
        Dictionary containing list of trending subreddits with their basic info

    Raises:
        ValueError: If limit is invalid
        RuntimeError: For errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    limit = max(1, min(50, limit))  # Ensure limit is between 1 and 50

    try:
        logger.info(f"Getting top {limit} trending subreddits")
        popular_subreddits = manager.client.subreddits.popular(limit=limit)

        trending = []
        for sub in popular_subreddits:
            try:
                trending.append(
                    {
                        "display_name": sub.display_name,
                        "subscribers": sub.subscribers,
                        "public_description": sub.public_description,
                        "over18": sub.over18,
                        "url": sub.url,
                    }
                )
            except Exception as sub_error:
                logger.warning(
                    f"Error processing subreddit {getattr(sub, 'display_name', 'unknown')}: {sub_error}"
                )
                continue

        if not trending:
            logger.warning("No trending subreddits found")

        return {"trending_subreddits": trending}

    except Exception as e:
        logger.error(f"Error getting trending subreddits: {e}")
        raise RuntimeError(f"Failed to get trending subreddits: {e}") from e


@mcp.tool()
def get_subreddit_stats(subreddit: str) -> Dict[str, Any]:
    """Get statistics and information about a subreddit.

    Args:
        subreddit: Name of the subreddit (with or without 'r/' prefix)

    Returns:
        Dictionary containing structured subreddit information with the following structure:
        {
            'id': str,  # Subreddit ID (e.g., '2qgzt')
            'display_name': str,  # Subreddit display name (without r/ prefix)
            'title': str,  # Subreddit title
            'public_description': str,  # Public description
            'description': str,  # Full description (can include markdown)
            'subscribers': int,  # Number of subscribers
            'active_user_count': Optional[int],  # Currently active users if available
            'created_utc': float,  # Creation timestamp (UTC)
            'over18': bool,  # Whether marked as NSFW
            'submission_type': str,  # Allowed submission types (any, link, self)
            'allow_images': bool,  # Whether image uploads are allowed
            'allow_videos': bool,  # Whether video uploads are allowed
            'allow_polls': bool,  # Whether polls are allowed
            'spoilers_enabled': bool,  # Whether spoiler tags are enabled
            'wikienabled': bool,  # Whether wiki is enabled
            'user_is_banned': bool,  # Whether current user is banned
            'user_is_moderator': bool,  # Whether current user is a moderator
            'user_is_subscriber': bool,  # Whether current user is a subscriber
            'mod_permissions': List[str],  # Moderator permissions if applicable
            'metadata': {
                'fetched_at': float,  # Timestamp when data was fetched
                'url': str,  # Full URL to the subreddit
                'moderators_count': int,  # Number of moderators
                'rules': List[Dict],  # Subreddit rules if available
                'features': Dict[str, bool],  # Enabled subreddit features
            }
        }

    Raises:
        ValueError: If subreddit is invalid or not found
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not subreddit or not isinstance(subreddit, str):
        raise ValueError("Subreddit name is required")

    # Clean up subreddit name (remove r/ prefix if present)
    clean_name = subreddit[2:] if subreddit.startswith("r/") else subreddit

    try:
        logger.info(f"Getting stats for r/{clean_name}")
        sub = manager.client.subreddit(clean_name)

        # Force fetch subreddit data to verify it exists and load all attributes
        sub._fetch()

        # Get moderator count (requires mod permissions)
        mod_count = 0
        try:
            if hasattr(sub, "moderator"):
                mod_count = len(list(sub.moderator()))
        except Exception as mod_error:
            logger.debug(f"Could not fetch moderator count: {mod_error}")

        # Get rules if available
        rules = []
        try:
            if hasattr(sub, "rules"):
                rules = [
                    {
                        "short_name": rule.short_name,
                        "description": rule.description,
                        "violation_reason": rule.violation_reason,
                        "created_utc": rule.created_utc,
                        "priority": rule.priority,
                    }
                    for rule in sub.rules()
                ]
        except Exception as rules_error:
            logger.debug(f"Could not fetch rules: {rules_error}")

        # Build features dictionary
        features = {
            "wiki": getattr(sub, "wikienabled", False),
            "spoilers": getattr(sub, "spoilers_enabled", False),
            "polls": getattr(sub, "allow_polls", False),
            "images": getattr(sub, "allow_images", False),
            "videos": getattr(sub, "allow_videos", False),
            "crossposts": getattr(sub, "allow_crossposts", True),
            "chat": getattr(sub, "allow_chat_post_creation", False),
            "gallery": getattr(sub, "allow_galleries", False),
            "original_content": getattr(sub, "original_content_tag_enabled", False),
        }

        # Build the response
        subreddit_data = {
            "id": getattr(sub, "id", ""),
            "display_name": getattr(sub, "display_name", clean_name),
            "title": getattr(sub, "title", ""),
            "public_description": getattr(sub, "public_description", ""),
            "description": getattr(sub, "description", ""),
            "subscribers": getattr(sub, "subscribers", 0),
            "active_user_count": getattr(sub, "active_user_count", None),
            "created_utc": getattr(sub, "created_utc", 0),
            "over18": getattr(sub, "over18", False),
            "submission_type": getattr(sub, "submission_type", "any"),
            "allow_images": getattr(sub, "allow_images", False),
            "allow_videos": getattr(sub, "allow_videos", False),
            "allow_polls": getattr(sub, "allow_polls", False),
            "spoilers_enabled": getattr(sub, "spoilers_enabled", False),
            "wikienabled": getattr(sub, "wikienabled", False),
            "user_is_banned": getattr(sub, "user_is_banned", False),
            "user_is_moderator": getattr(sub, "user_is_moderator", False),
            "user_is_subscriber": getattr(sub, "user_is_subscriber", False),
            "mod_permissions": getattr(sub, "mod_permissions", []),
            "metadata": {
                "fetched_at": time.time(),
                "url": f"https://www.reddit.com/r/{clean_name}",
                "moderators_count": mod_count,
                "rules": rules,
                "features": features,
            },
        }

        return subreddit_data

    except Exception as e:
        logger.error(f"Error getting stats for r/{clean_name}: {e}")
        if "private" in str(e).lower():
            raise ValueError(f"r/{clean_name} is private or cannot be accessed") from e
        if "banned" in str(e).lower():
            raise ValueError(f"r/{clean_name} has been banned or doesn't exist") from e
        if "not found" in str(e).lower():
            raise ValueError(f"r/{clean_name} not found") from e
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to get subreddit stats: {e}") from e


@mcp.tool()
@require_write_access
def create_post(
    subreddit: str,
    title: str,
    content: str,
    flair: Optional[str] = None,
    is_self: bool = True,
) -> Dict[str, Any]:
    """Create a new post in a subreddit.

    Args:
        subreddit: Name of the subreddit to post in (with or without 'r/' prefix)
        title: Title of the post (max 300 characters)
        content: Content of the post (text for self posts, URL for link posts)
        flair: Flair to add to the post. Must be an available flair in the subreddit
        is_self: Whether this is a self (text) post (True) or link post (False)

    Returns:
        Dictionary containing information about the created post

    Raises:
        ValueError: If input validation fails or flair is invalid
        RuntimeError: For other errors during post creation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    # Input validation
    if not subreddit or not isinstance(subreddit, str):
        raise ValueError("Subreddit name is required")
    if not title or not isinstance(title, str):
        raise ValueError("Post title is required")
    if len(title) > 300:
        raise ValueError("Title must be 300 characters or less")
    if not content or not isinstance(content, str):
        raise ValueError("Post content/URL is required")

    # Clean up subreddit name (remove r/ prefix if present)
    clean_subreddit = subreddit[2:] if subreddit.startswith("r/") else subreddit

    try:
        logger.info(f"Creating post in r/{clean_subreddit}")
        subreddit_obj = manager.client.subreddit(clean_subreddit)

        # Verify subreddit exists and is postable
        _ = subreddit_obj.display_name

        # Check if flair is valid if provided
        if flair:
            try:
                available_flairs = [
                    f["text"] for f in subreddit_obj.flair.link_templates
                ]
                if flair not in available_flairs:
                    raise ValueError(
                        f"Invalid flair. Available flairs: {', '.join(available_flairs)}"
                    )
            except Exception as flair_error:
                logger.warning(f"Error checking flairs: {flair_error}")
                raise ValueError(
                    "Failed to verify flair. The subreddit may not allow link flairs."
                ) from flair_error

        # Create the post
        try:
            if is_self:
                submission = subreddit_obj.submit(
                    title=title[:300],  # Ensure title is within limit
                    selftext=content,
                    flair_id=flair,
                    send_replies=True,
                )
            else:
                # Validate URL for link posts
                if not content.startswith(("http://", "https://")):
                    content = f"https://{content}"
                submission = subreddit_obj.submit(
                    title=title[:300],  # Ensure title is within limit
                    url=content,
                    flair_id=flair,
                    send_replies=True,
                )

            logger.info(f"Post created successfully: {submission.permalink}")

            return {
                "post": _format_post(submission),
                "metadata": {
                    "created_at": _format_timestamp(time.time()),
                    "subreddit": clean_subreddit,
                    "is_self_post": is_self,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "id": submission.id,
                },
            }

        except Exception as post_error:
            logger.error(f"Failed to create post in r/{clean_subreddit}: {post_error}")
            if "RATELIMIT" in str(post_error).upper():
                raise RuntimeError(
                    "You're doing that too much. Please wait before posting again."
                ) from post_error
            if "TOO_OLD" in str(post_error):
                raise RuntimeError(
                    "This subreddit only allows posts from accounts with a minimum age or karma."
                ) from post_error
            if "SUBREDDIT_NOEXIST" in str(post_error):
                raise ValueError(f"r/{clean_subreddit} does not exist") from post_error
            raise RuntimeError(f"Failed to create post: {post_error}") from post_error

    except Exception as e:
        logger.error(f"Error in create_post for r/{clean_subreddit}: {e}")
        if "private" in str(e).lower():
            raise ValueError(
                f"r/{clean_subreddit} is private or cannot be accessed"
            ) from e
        if "banned" in str(e).lower():
            raise ValueError(
                f"r/{clean_subreddit} has been banned or doesn't exist"
            ) from e
        if "not found" in str(e).lower():
            raise ValueError(f"r/{clean_subreddit} not found") from e
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to create post: {e}") from e


@mcp.tool()
@require_write_access
def reply_to_post(
    post_id: str, content: str, subreddit: Optional[str] = None
) -> Dict[str, Any]:
    """Post a reply to an existing Reddit post.

    Args:
        post_id: The ID of the post to reply to (can be full URL, permalink, or just ID)
        content: The content of the reply (1-10000 characters)
        subreddit: The subreddit name if known (for validation, with or without 'r/' prefix)

    Returns:
        Dictionary containing information about the created reply and parent post

    Raises:
        ValueError: If input validation fails or post is not found
        RuntimeError: For other errors during reply creation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    # Input validation
    if not post_id or not isinstance(post_id, str):
        raise ValueError("Post ID is required")
    if not content or not isinstance(content, str):
        raise ValueError("Reply content is required")
    if len(content) < 1 or len(content) > 10000:
        raise ValueError("Reply must be between 1 and 10000 characters")

    # Clean up subreddit name if provided
    clean_subreddit = None
    if subreddit:
        if not isinstance(subreddit, str):
            raise ValueError("Subreddit name must be a string")
        clean_subreddit = subreddit[2:] if subreddit.startswith("r/") else subreddit

    try:
        # Clean up the post_id if it's a full URL or permalink
        clean_post_id = _extract_reddit_id(post_id)
        logger.info(f"Creating reply to post ID: {clean_post_id}")

        # Get the submission object
        submission = manager.client.submission(id=clean_post_id)

        # Verify the post exists by accessing its attributes
        try:
            post_title = submission.title
            post_author = getattr(submission, "author", None)
            post_subreddit = submission.subreddit

            logger.info(
                f"Replying to post: "
                f"Title: {post_title}, "
                f"Author: {post_author}, "
                f"Subreddit: r/{post_subreddit.display_name}"
            )

        except Exception as e:
            logger.error(f"Failed to access post {clean_post_id}: {e}")
            raise ValueError(f"Post {clean_post_id} not found or inaccessible") from e

        # If subreddit was provided, verify we're in the right place
        if (
            clean_subreddit
            and post_subreddit.display_name.lower() != clean_subreddit.lower()
        ):
            raise ValueError(
                f"Post ID {clean_post_id} belongs to r/{post_subreddit.display_name}, "
                f"not r/{clean_subreddit}"
            )

        # Check if the post is archived or locked
        if getattr(submission, "archived", False):
            raise ValueError("Cannot reply to an archived post")
        if getattr(submission, "locked", False):
            raise ValueError("Cannot reply to a locked post")

        # Create the reply
        logger.info(f"Posting reply with content length: {len(content)} characters")
        try:
            reply = submission.reply(body=content)
            logger.info(f"Reply created successfully: {reply.id}")

            return {
                "reply": _format_comment(reply),
                "parent_post": _format_post(submission),
                "metadata": {
                    "created_at": _format_timestamp(time.time()),
                    "reply_id": reply.id,
                    "parent_id": clean_post_id,
                    "subreddit": post_subreddit.display_name,
                },
            }

        except Exception as reply_error:
            logger.error(f"Failed to create reply: {reply_error}")
            if "RATELIMIT" in str(reply_error).upper():
                raise RuntimeError(
                    "You're doing that too much. Please wait before replying again."
                ) from reply_error
            if "TOO_OLD" in str(reply_error):
                raise RuntimeError(
                    "This thread is archived and cannot be replied to"
                ) from reply_error
            raise RuntimeError(f"Failed to post reply: {reply_error}") from reply_error

    except Exception as e:
        logger.error(f"Error in reply_to_post for ID {post_id}: {e}")
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to create comment reply: {e}") from e


@mcp.tool()
def get_submission_by_url(url: str) -> Dict[str, Any]:
    """Get a Reddit submission by its URL.

    Args:
        url: The URL of the Reddit submission to retrieve

    Returns:
        Dictionary containing structured submission information with the following structure:
        {
            'id': str,  # Submission ID (e.g., 'abc123')
            'title': str,  # Submission title
            'author': str,  # Author's username or '[deleted]' if deleted
            'subreddit': str,  # Subreddit name
            'score': int,  # Post score (upvotes - downvotes)
            'upvote_ratio': float,  # Ratio of upvotes to total votes
            'num_comments': int,  # Number of comments
            'created_utc': float,  # Post creation timestamp (UTC)
            'url': str,  # Full URL to the post
            'permalink': str,  # Relative URL to the post
            'is_self': bool,  # Whether it's a self (text) post
            'selftext': str,  # Content of self post (if any)
            'selftext_html': Optional[str],  # HTML formatted content
            'link_url': str,  # URL for link posts (if any)
            'domain': str,  # Domain of the linked content
            'over_18': bool,  # Whether marked as NSFW
            'spoiler': bool,  # Whether marked as spoiler
            'stickied': bool,  # Whether stickied in the subreddit
            'locked': bool,  # Whether comments are locked
            'archived': bool,  # Whether the post is archived
            'distinguished': Optional[str],  # Distinguishing type (e.g., 'moderator')
            'flair': Optional[Dict],  # Post flair information if any
            'media': Optional[Dict],  # Media information if any
            'preview': Optional[Dict],  # Preview information if available
            'awards': List[Dict],  # List of awards received
            'metadata': {
                'fetched_at': float,  # Timestamp when data was fetched
                'subreddit_id': str,  # Subreddit full ID
                'author_id': str,  # Author's full ID if available
                'is_original_content': bool,  # Whether marked as OC
                'is_meta': bool,  # Whether marked as meta
                'is_crosspostable': bool,  # Whether can be crossposted
                'is_reddit_media_domain': bool,  # Whether media is hosted on Reddit
                'is_robot_indexable': bool,  # Whether search engines should index
                'is_created_from_ads_ui': bool,  # Whether created via ads UI
                'is_video': bool,  # Whether the post is a video
                'pinned': bool,  # Whether the post is pinned in the subreddit
                'gilded': int,  # Number of times gilded
                'total_awards_received': int,  # Total number of awards received
                'view_count': Optional[int],  # View count if available
                'visited': bool,  # Whether the current user has visited
            }
        }

    Raises:
        ValueError: If URL is invalid or submission not found
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not url or not isinstance(url, str):
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    try:
        logger.info(f"Getting submission from URL: {url}")

        # Create submission from URL
        submission = manager.client.submission(url=url)

        # Force fetch submission data to verify it exists and get all attributes
        submission.title  # This will raise if submission doesn't exist

        # Get basic submission data with error handling
        submission_data = {
            "id": submission.id,
            "title": submission.title,
            "author": str(submission.author)
            if hasattr(submission, "author") and submission.author
            else "[deleted]",
            "subreddit": submission.subreddit.display_name
            if hasattr(submission, "subreddit")
            else "unknown",
            "score": getattr(submission, "score", 0),
            "upvote_ratio": getattr(submission, "upvote_ratio", 0.0),
            "num_comments": getattr(submission, "num_comments", 0),
            "created_utc": submission.created_utc,
            "url": f"https://www.reddit.com{submission.permalink}"
            if hasattr(submission, "permalink")
            else url,
            "permalink": getattr(submission, "permalink", f"/comments/{submission.id}"),
            "is_self": getattr(submission, "is_self", False),
            "selftext": getattr(submission, "selftext", ""),
            "selftext_html": getattr(submission, "selftext_html", None),
            "link_url": getattr(submission, "url", ""),
            "domain": getattr(submission, "domain", ""),
            "over_18": getattr(submission, "over_18", False),
            "spoiler": getattr(submission, "spoiler", False),
            "stickied": getattr(submission, "stickied", False),
            "locked": getattr(submission, "locked", False),
            "archived": getattr(submission, "archived", False),
            "distinguished": getattr(submission, "distinguished", None),
            "flair": None,
            "media": getattr(submission, "media", None),
            "preview": getattr(submission, "preview", None),
            "awards": [],
        }

        # Add flair information if available
        if hasattr(submission, "link_flair_text") and submission.link_flair_text:
            submission_data["flair"] = {
                "text": submission.link_flair_text,
                "css_class": getattr(submission, "link_flair_css_class", ""),
                "template_id": getattr(submission, "link_flair_template_id", None),
                "text_color": getattr(submission, "link_flair_text_color", None),
                "background_color": getattr(
                    submission, "link_flair_background_color", None
                ),
            }

        # Add awards information if available
        if hasattr(submission, "all_awardings"):
            submission_data["awards"] = [
                {
                    "id": award.get("id"),
                    "name": award.get("name"),
                    "description": award.get("description"),
                    "coin_price": award.get("coin_price", 0),
                    "coin_reward": award.get("coin_reward", 0),
                    "icon_url": award.get("icon_url"),
                    "count": award.get("count", 1),
                }
                for award in submission.all_awardings
            ]

        # Add metadata
        submission_data["metadata"] = {
            "fetched_at": time.time(),
            "subreddit_id": getattr(submission.subreddit, "id", "")
            if hasattr(submission, "subreddit")
            else "",
            "author_id": f"t2_{submission.author.id}"
            if hasattr(submission, "author")
            and submission.author
            and hasattr(submission.author, "id")
            else None,
            "is_original_content": getattr(submission, "is_original_content", False),
            "is_meta": getattr(submission, "is_meta", False),
            "is_crosspostable": getattr(submission, "is_crosspostable", False),
            "is_reddit_media_domain": getattr(
                submission, "is_reddit_media_domain", False
            ),
            "is_robot_indexable": getattr(submission, "is_robot_indexable", True),
            "is_created_from_ads_ui": getattr(
                submission, "is_created_from_ads_ui", False
            ),
            "is_video": getattr(submission, "is_video", False),
            "pinned": getattr(submission, "pinned", False),
            "gilded": getattr(submission, "gilded", 0),
            "total_awards_received": getattr(submission, "total_awards_received", 0),
            "view_count": getattr(submission, "view_count", None),
            "visited": getattr(submission, "visited", False),
        }

        return submission_data

    except Exception as e:
        logger.error(f"Error in get_submission_by_url: {e}")
        if "404" in str(e) or "not found" in str(e).lower():
            raise ValueError(f"Submission not found at URL: {url}") from e
        if "403" in str(e) or "forbidden" in str(e).lower():
            raise ValueError(
                f"Not authorized to access submission at URL: {url}"
            ) from e
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to get submission by URL: {e}") from e


@mcp.tool()
def get_submission_by_id(submission_id: str) -> Dict[str, Any]:
    """Get a Reddit submission by its ID.

    Args:
        submission_id: The ID of the Reddit submission to retrieve (can be full URL or just ID)

    Returns:
        Dictionary containing structured submission information with the following structure:
        {
            'id': str,  # Submission ID (e.g., 'abc123')
            'title': str,  # Submission title
            'author': str,  # Author's username or '[deleted]' if deleted
            'subreddit': str,  # Subreddit name
            'score': int,  # Post score (upvotes - downvotes)
            'upvote_ratio': float,  # Ratio of upvotes to total votes
            'num_comments': int,  # Number of comments
            'created_utc': float,  # Post creation timestamp (UTC)
            'url': str,  # Full URL to the post
            'permalink': str,  # Relative URL to the post
            'is_self': bool,  # Whether it's a self (text) post
            'selftext': str,  # Content of self post (if any)
            'selftext_html': Optional[str],  # HTML formatted content
            'link_url': str,  # URL for link posts (if any)
            'domain': str,  # Domain of the linked content
            'over_18': bool,  # Whether marked as NSFW
            'spoiler': bool,  # Whether marked as spoiler
            'stickied': bool,  # Whether stickied in the subreddit
            'locked': bool,  # Whether comments are locked
            'archived': bool,  # Whether the post is archived
            'distinguished': Optional[str],  # Distinguishing type (e.g., 'moderator')
            'flair': Optional[Dict],  # Post flair information if any
            'media': Optional[Dict],  # Media information if any
            'preview': Optional[Dict],  # Preview information if available
            'awards': List[Dict],  # List of awards received
            'metadata': {
                'fetched_at': float,  # Timestamp when data was fetched
                'subreddit_id': str,  # Subreddit full ID
                'author_id': str,  # Author's full ID if available
                'is_original_content': bool,  # Whether marked as OC
                'is_meta': bool,  # Whether marked as meta
                'is_crosspostable': bool,  # Whether can be crossposted
                'is_reddit_media_domain': bool,  # Whether media is hosted on Reddit
                'is_robot_indexable': bool,  # Whether search engines should index
                'is_created_from_ads_ui': bool,  # Whether created via ads UI
                'is_video': bool,  # Whether the post is a video
                'pinned': bool,  # Whether the post is pinned in the subreddit
                'gilded': int,  # Number of times gilded
                'total_awards_received': int,  # Total number of awards received
                'view_count': Optional[int],  # View count if available
                'visited': bool,  # Whether the current user has visited
            }
        }

    Raises:
        ValueError: If submission_id is invalid or submission not found
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    if not submission_id or not isinstance(submission_id, str):
        raise ValueError("Submission ID is required")

    try:
        # Clean up the submission_id if it's a full URL or permalink
        clean_submission_id = _extract_reddit_id(submission_id)
        logger.info(f"Getting submission with ID: {clean_submission_id}")

        # Create submission from ID
        submission = manager.client.submission(id=clean_submission_id)

        # Force fetch submission data to verify it exists and get all attributes
        submission.title  # This will raise if submission doesn't exist

        # Get basic submission data with error handling
        submission_data = {
            "id": submission.id,
            "title": submission.title,
            "author": str(submission.author)
            if hasattr(submission, "author") and submission.author
            else "[deleted]",
            "subreddit": submission.subreddit.display_name
            if hasattr(submission, "subreddit")
            else "unknown",
            "score": getattr(submission, "score", 0),
            "upvote_ratio": getattr(submission, "upvote_ratio", 0.0),
            "num_comments": getattr(submission, "num_comments", 0),
            "created_utc": submission.created_utc,
            "url": f"https://www.reddit.com{submission.permalink}"
            if hasattr(submission, "permalink")
            else f"t3_{clean_submission_id}",
            "permalink": getattr(
                submission, "permalink", f"/comments/{clean_submission_id}"
            ),
            "is_self": getattr(submission, "is_self", False),
            "selftext": getattr(submission, "selftext", ""),
            "selftext_html": getattr(submission, "selftext_html", None),
            "link_url": getattr(submission, "url", ""),
            "domain": getattr(submission, "domain", ""),
            "over_18": getattr(submission, "over_18", False),
            "spoiler": getattr(submission, "spoiler", False),
            "stickied": getattr(submission, "stickied", False),
            "locked": getattr(submission, "locked", False),
            "archived": getattr(submission, "archived", False),
            "distinguished": getattr(submission, "distinguished", None),
            "flair": None,
            "media": getattr(submission, "media", None),
            "preview": getattr(submission, "preview", None),
            "awards": [],
        }

        # Add flair information if available
        if hasattr(submission, "link_flair_text") and submission.link_flair_text:
            submission_data["flair"] = {
                "text": submission.link_flair_text,
                "css_class": getattr(submission, "link_flair_css_class", ""),
                "template_id": getattr(submission, "link_flair_template_id", None),
                "text_color": getattr(submission, "link_flair_text_color", None),
                "background_color": getattr(
                    submission, "link_flair_background_color", None
                ),
            }

        # Add awards information if available
        if hasattr(submission, "all_awardings"):
            submission_data["awards"] = [
                {
                    "id": award.get("id"),
                    "name": award.get("name"),
                    "description": award.get("description"),
                    "coin_price": award.get("coin_price", 0),
                    "coin_reward": award.get("coin_reward", 0),
                    "icon_url": award.get("icon_url"),
                    "count": award.get("count", 1),
                }
                for award in submission.all_awardings
            ]

        # Add metadata
        submission_data["metadata"] = {
            "fetched_at": time.time(),
            "subreddit_id": getattr(submission.subreddit, "id", "")
            if hasattr(submission, "subreddit")
            else "",
            "author_id": f"t2_{submission.author.id}"
            if hasattr(submission, "author")
            and submission.author
            and hasattr(submission.author, "id")
            else None,
            "is_original_content": getattr(submission, "is_original_content", False),
            "is_meta": getattr(submission, "is_meta", False),
            "is_crosspostable": getattr(submission, "is_crosspostable", False),
            "is_reddit_media_domain": getattr(
                submission, "is_reddit_media_domain", False
            ),
            "is_robot_indexable": getattr(submission, "is_robot_indexable", True),
            "is_created_from_ads_ui": getattr(
                submission, "is_created_from_ads_ui", False
            ),
            "is_video": getattr(submission, "is_video", False),
            "pinned": getattr(submission, "pinned", False),
            "gilded": getattr(submission, "gilded", 0),
            "total_awards_received": getattr(submission, "total_awards_received", 0),
            "view_count": getattr(submission, "view_count", None),
            "visited": getattr(submission, "visited", False),
        }

        return submission_data

    except Exception as e:
        logger.error(f"Error in get_submission_by_id: {e}")
        if "404" in str(e) or "not found" in str(e).lower():
            raise ValueError(
                f"Submission with ID {clean_submission_id} not found"
            ) from e
        if "403" in str(e) or "forbidden" in str(e).lower():
            raise ValueError(
                f"Not authorized to access submission with ID {clean_submission_id}"
            ) from e
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to get submission by ID: {e}") from e


@mcp.tool()
@require_write_access
def who_am_i() -> Dict[str, Any]:
    """Get information about the currently authenticated user.

    Returns:
        Dictionary containing structured user information with the following structure:
        {
            'id': str,  # Full user ID (e.g., 't2_abc123')
            'name': str,  # Username
            'created_utc': float,  # Account creation timestamp
            'comment_karma': int,  # Comment karma
            'link_karma': int,  # Post/link karma
            'total_karma': int,  # Total karma (comments + posts)
            'awardee_karma': int,  # Karma from awards received
            'awarder_karma': int,  # Karma from awards given
            'has_verified_email': bool,  # Whether email is verified
            'is_employee': bool,  # Whether user is a Reddit employee
            'is_friend': bool,  # Whether user is a friend
            'is_gold': bool,  # Whether user has Reddit Premium
            'is_mod': bool,  # Whether user is a moderator
            'is_suspended': bool,  # Whether account is suspended
            'verified': bool,  # Whether account is verified
            'has_subscribed': bool,  # Whether user has subscribed to Premium
            'snoovatar_img': str,  # URL to snoovatar image
            'icon_img': str,  # URL to user's icon
            'pref_show_snoovatar': bool,  # Whether to show snoovatar
            'snoovatar_size': Optional[List[int]],  # Snoovatar dimensions
            'subreddit': Optional[Dict],  # User's profile subreddit info
            'metadata': {
                'fetched_at': float,  # Timestamp when data was fetched
                'is_authenticated': bool,  # Whether user is authenticated
                'is_moderator': bool,  # Whether user is a moderator
                'has_verified_email': bool,  # Whether email is verified
                'has_mail': bool,  # Whether user has unread messages
                'has_mod_mail': bool,  # Whether user has mod mail
                'has_subscribed': bool,  # Whether user has subscribed to Premium
                'in_chat': bool,  # Whether user is in chat
                'in_redesign_beta': bool,  # Whether user is in redesign beta
                'new_modmail_exists': bool,  # Whether user has new modmail
                'pref_no_profanity': bool,  # Whether to filter profanity
                'suspension_expiration_utc': Optional[float],  # When suspension ends if suspended
            }
        }

    Raises:
        ValueError: If user authentication is not available
        RuntimeError: For other errors during the operation
    """
    manager = RedditClientManager()
    if not manager.client:
        raise RuntimeError("Reddit client not initialized")

    try:
        logger.info("Getting information about the current authenticated user")

        # Check if user is authenticated
        if not manager.check_user_auth():
            raise ValueError(
                "User authentication required. Please provide valid credentials."
            )

        # Get the current user
        current_user = manager.client.user.me()
        if not current_user:
            raise ValueError("Failed to retrieve current user information")

        username = getattr(current_user, "name", "unknown")
        logger.info(f"Retrieved information for user: {username}")

        # Get user preferences and other attributes with safe defaults
        prefs = getattr(current_user, "prefs", {}) or {}
        subreddit = getattr(current_user, "subreddit", {}) or {}

        # Build the user info dictionary
        user_info = {
            "id": getattr(current_user, "id", ""),
            "name": username,
            "created_utc": getattr(current_user, "created_utc", 0),
            "comment_karma": getattr(current_user, "comment_karma", 0),
            "link_karma": getattr(current_user, "link_karma", 0),
            "total_karma": getattr(current_user, "total_karma", 0),
            "awardee_karma": getattr(current_user, "awardee_karma", 0),
            "awarder_karma": getattr(current_user, "awarder_karma", 0),
            "has_verified_email": getattr(current_user, "has_verified_email", False),
            "is_employee": getattr(current_user, "is_employee", False),
            "is_friend": getattr(current_user, "is_friend", False),
            "is_gold": getattr(current_user, "is_gold", False),
            "is_mod": getattr(current_user, "is_mod", False),
            "is_suspended": getattr(current_user, "is_suspended", False),
            "verified": getattr(current_user, "verified", False),
            "has_subscribed": getattr(current_user, "has_subscribed", False),
            "snoovatar_img": getattr(current_user, "snoovatar_img", ""),
            "icon_img": getattr(current_user, "icon_img", ""),
            "pref_show_snoovatar": prefs.get("show_snoovatar", False),
            "snoovatar_size": getattr(current_user, "snoovatar_size", None),
            "subreddit": {
                "display_name": subreddit.get("display_name", ""),
                "name": subreddit.get("display_name_prefixed", ""),
                "public_description": subreddit.get("public_description", ""),
                "subscribers": subreddit.get("subscribers", 0),
                "created_utc": subreddit.get("created_utc", 0),
                "over18": subreddit.get("over18", False),
                "suggested_comment_sort": subreddit.get(
                    "suggested_comment_sort", "best"
                ),
                "title": subreddit.get("title", ""),
                "url": subreddit.get("url", ""),
            }
            if subreddit
            else None,
            "metadata": {
                "fetched_at": time.time(),
                "is_authenticated": True,
                "is_moderator": getattr(current_user, "is_mod", False),
                "has_verified_email": getattr(
                    current_user, "has_verified_email", False
                ),
                "has_mail": getattr(current_user, "has_mail", False),
                "has_mod_mail": getattr(current_user, "has_mod_mail", False),
                "has_subscribed": getattr(current_user, "has_subscribed", False),
                "in_chat": getattr(current_user, "in_chat", False),
                "in_redesign_beta": prefs.get("in_redesign_beta", False),
                "new_modmail_exists": getattr(
                    current_user, "new_modmail_exists", False
                ),
                "pref_no_profanity": prefs.get("no_profanity", True),
                "suspension_expiration_utc": getattr(
                    current_user, "suspension_expiration_utc", None
                ),
            },
        }

        return user_info

    except Exception as e:
        logger.error(f"Error in who_am_i: {e}")
        if "401" in str(e) or "unauthorized" in str(e).lower():
            raise ValueError(
                "Authentication failed. Please check your credentials."
            ) from e
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Failed to retrieve user information: {e}") from e


if __name__ == "__main__":
    mcp.run()
