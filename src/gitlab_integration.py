# This module will handle interactions with the GitLab API.

import gitlab
import os
import logging # Import logging

# Configure basic logging for the module
# This will inherit the root logger's configuration if set by the main script,
# or use a default basicConfig if no other logging is configured.
logger = logging.getLogger(__name__)

# Signature to identify comments made by the AI bot.
# Making it more explicit for AI processing in conversation history and for UI visibility.
BOT_SIGNATURE = "**Sended By AI Rubber Duck:**\n"

def get_gitlab_instance(gitlab_url, private_token):
    """Creates and returns a GitLab API instance based on provided URL and token."""
    if not private_token:
        logger.error("GitLab private token not provided to get_gitlab_instance.")
        raise ValueError("GitLab private token is required.")
    if not gitlab_url:
        logger.error("GitLab URL not provided to get_gitlab_instance.")
        raise ValueError("GitLab URL is required.")
    
    logger.debug(f"Attempting to connect to GitLab instance at {gitlab_url}")
    # Use the provided gitlab_url and private_token
    gl = gitlab.Gitlab(gitlab_url, private_token=private_token, timeout=10)

    try:
        gl.auth()  # Verify authentication
        logger.info(f"Successfully authenticated to GitLab instance at {gitlab_url} as {gl.user.username}")
        return gl
    except gitlab.exceptions.GitlabAuthenticationError as e:
        logger.error(f"GitLab authentication failed: {e}")
        raise
    except gitlab.exceptions.GitlabHttpError as e: # Catch other HTTP errors during auth
        logger.error(f"GitLab HTTP error during authentication: {e.status_code} - {e.error_message}")
        raise
    except Exception as e: # Catch any other unexpected errors (e.g., network issues)
        logger.error(f"An unexpected error occurred during GitLab authentication: {e}")
        raise

def get_issue_details(gl, project_id, issue_iid):
    """Fetches an issue and its comments using a pre-initialized GitLab instance."""
    if not gl:
        logger.error("GitLab instance (gl) not provided to get_issue_details.")
        raise ValueError("GitLab instance (gl) is required.")

    logger.info(f"Fetching details for issue IID {issue_iid} in project ID {project_id}")
    try:
        # gl is already initialized and passed as an argument
        project = gl.projects.get(project_id)
        logger.debug(f"Successfully fetched project: {project.name_with_namespace}")
        issue = project.issues.get(issue_iid)
        logger.debug(f"Successfully fetched issue: {issue.title}")
        
        comments = []
        # Iterate using iterator=True for potentially large number of notes to handle pagination
        for note in issue.notes.list(all=True, iterator=True):
            comments.append({
                'id': note.id,
                'body': note.body,
                'author': note.author['username'],
                'created_at': note.created_at,
                'system': note.system
            })
        logger.info(f"Fetched {len(comments)} comments for issue {issue_iid}.")
            
        return {
            'title': issue.title,
            'description': issue.description,
            'author': issue.author['username'],
            'created_at': issue.created_at,
            'comments': comments
        }
    except gitlab.exceptions.GitlabGetError as e:
        logger.error(f"Failed to get GitLab resource (project/issue/notes): {e.status_code} - {e.error_message}")
        # Distinguish between 404 (not found) and other errors
        if e.response_code == 404:
            logger.error(f"Resource not found (Project ID: {project_id}, Issue IID: {issue_iid}). Please check IDs.")
        # Consider re-raising a custom exception or the original one
        raise
    except gitlab.exceptions.GitlabHttpError as e:
        logger.error(f"GitLab HTTP error while fetching issue details: {e.status_code} - {e.error_message}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching issue details: {e}")
        raise

def post_comment_to_issue(gl, project_id, issue_iid, comment_body):
    """Posts a new comment to a specific GitLab issue using a pre-initialized GitLab instance."""
    if not gl:
        logger.error("GitLab instance (gl) not provided to post_comment_to_issue.")
        raise ValueError("GitLab instance (gl) is required.")

    logger.info(f"Attempting to post comment to issue IID {issue_iid} in project ID {project_id}")
    try:
        # gl is already initialized and passed as an argument
        project = gl.projects.get(project_id)
        issue = project.issues.get(issue_iid)
        
        # Prepend signature to the comment body
        full_comment = f"{BOT_SIGNATURE}\n{comment_body}"
        
        note = issue.notes.create({'body': full_comment})
        logger.info(f"Successfully posted comment (Note ID: {note.id}) to issue {issue_iid} in project {project_id}")
        return note
    except gitlab.exceptions.GitlabCreateError as e:
        logger.error(f"Failed to create GitLab comment: {e.status_code} - {e.error_message}")
        # Specific handling for common errors like 401 (unauthorized), 403 (forbidden), 422 (unprocessable)
        if e.response_code == 401:
            logger.error("Unauthorized to post comment. Check API token permissions.")
        elif e.response_code == 403:
            logger.error("Forbidden to post comment. Check project permissions for the token.")
        raise
    except gitlab.exceptions.GitlabHttpError as e:
        logger.error(f"GitLab HTTP error while posting comment: {e.status_code} - {e.error_message}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting comment: {e}")
        raise

# Example Usage (for testing purposes - remove or comment out for production):
if __name__ == '__main__':
    # Basic logging config for direct script execution
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("gitlab_integration.py executed directly for testing.")
    # Ensure GITLAB_URL and GITLAB_PRIVATE_TOKEN are set as environment variables
    # And that PROJECT_ID and ISSUE_IID point to a valid test issue
    test_project_id = os.getenv('TEST_GITLAB_PROJECT_ID')
    test_issue_iid = os.getenv('TEST_GITLAB_ISSUE_IID')

    if not all([test_project_id, test_issue_iid]):
        logger.warning("Please set TEST_GITLAB_PROJECT_ID and TEST_GITLAB_ISSUE_IID env vars for testing.")
    else:
        try:
            gitlab_url = os.getenv('GITLAB_URL')
            logger.info(f"Attempting to connect to GitLab at: {gitlab_url}")
            # Test authentication
            # gl_instance = get_gitlab_instance()
            # logger.info(f"Authenticated as: {gl_instance.user.username}")

            # Test fetching issue details
            logger.info(f"\nFetching details for issue {test_issue_iid} in project {test_project_id}...")
            # Explicitly pass the GitLab URL and private token from environment variables
            gl_instance = get_gitlab_instance(os.getenv('GITLAB_URL'), os.getenv('GITLAB_PRIVATE_TOKEN'))
            issue_data = get_issue_details(gl_instance, test_project_id, test_issue_iid)
            logger.info(f"Issue Title: {issue_data['title']}")
            logger.info(f"Issue Author: {issue_data['author']}")
            logger.info(f"Issue Description: {issue_data['description']}")
            logger.info("Comments:")
            for c in issue_data['comments']:
                logger.info(f"  - [{c['author']} at {c['created_at']}]: {c['body'][:50]}...")

            # Test posting a comment
            # logger.info("\nPosting a test comment...")
            # new_comment = post_comment_to_issue(test_project_id, test_issue_iid, "This is a test comment from the AI Rubber Duck script! (v2 with logging)")
            # logger.info(f"Posted comment ID: {new_comment.id}")

        except ValueError as ve:
            logger.error(f"Configuration Error: {ve}")
        except gitlab.exceptions.GitlabError as ge:
            logger.error(f"GitLab API Error: {ge}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
