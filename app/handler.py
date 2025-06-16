# This file will contain the main application logic for handling webhook events.
import os
import logging
# Assuming src.gitlab_integration and src.google_ai_integration are accessible
# This might require adjusting PYTHONPATH or the project structure if running app directly
# For a package structure, it might be: from ..src.gitlab_integration import ...
from src.gitlab_integration import get_gitlab_instance, get_issue_details, post_comment_to_issue, BOT_SIGNATURE
from src.google_ai_integration import configure_google_ai, generate_socratic_questions, generate_contextual_response, detect_user_intent
from src.firestore_integration import FirestoreManager
from src.gitlab_repo_handler import GitLabRepoHandler

# Logging configuration should ideally be done at the app level (e.g., in Flask app setup)
# For now, keeping it here for direct translation, but it might be removed if app handles it.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Trigger phrase for the AI Rubber Duck - this could become a configurable setting
RUBBER_DUCK_TRIGGER_PHRASE = "Rubber Duck Help Me"

# Initialize managers
service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH', 'hackathon-service-account-key.json')
firestore_manager = None

def get_managers():
    """Initialize and return managers"""
    global firestore_manager
    
    if firestore_manager is None:
        firestore_manager = FirestoreManager(service_account_path)
    
    return firestore_manager

def format_conversation_for_ai(issue_title, issue_description, comments):
    """Formats the issue title, description, and comments into a single string for the AI,
       separating AI responses from user responses for stateful conversation.
    """
    ai_conversation_history = []
    current_problem_statement = f"Issue Title: {issue_title}\nIssue Description:\n{issue_description}"
    temp_user_responses = []

    for comment in comments: # comment is a dict here
        comment_body = comment['body'] # Access 'body' using dictionary key
        is_ai_comment = comment_body.startswith(BOT_SIGNATURE) or comment_body.startswith("<!-- AI Rubber Duck -->") or comment_body.startswith("**Sended By AI Rubber Duck:**") or comment_body.startswith("Sended By AI Rubber Duck:") or comment_body.startswith("AI Rubber Duck:")
        # Ensure author is accessed correctly if it's a dict
        author_username = comment['author'] # Assuming author is already just the username string as per get_issue_details

        if is_ai_comment:
            if temp_user_responses:
                ai_conversation_history.append(f"User responses since last AI question:\n" + "\n".join(temp_user_responses))
                temp_user_responses = []
            
            ai_question = comment_body.replace(BOT_SIGNATURE, "").strip()
            ai_conversation_history.append(f"Previous AI Question: {ai_question}")
        else:
            temp_user_responses.append(f"User ({author_username}): {comment_body}")
    
    if temp_user_responses:
        current_problem_statement += "\n\nFurther comments/details from user:\n" + "\n".join(temp_user_responses)
    
    formatted_history = "\n---\n".join(ai_conversation_history) if ai_conversation_history else ""

    logging.info(f"Formatted current problem statement for AI: {current_problem_statement[:200]}...")
    if formatted_history:
        logging.info(f"Formatted conversation history for AI: {formatted_history[:200]}...")
    else:
        logging.info("No previous AI conversation history found for this issue.")

    return current_problem_statement, formatted_history

def process_issue_event(webhook_data):
    """
    Processes an issue event received from a GitLab webhook.
    webhook_data is expected to be a dictionary parsed from the JSON payload.
    It should contain at least:
    - project_id
    - issue_iid (for issue/note events)
    - gitlab_url (URL of the GitLab instance)
    - gitlab_token (API token for accessing this project - this needs secure handling)
    - event_type (issue, note, merge_request, merge_to_main)
    - project_data (project information from webhook)
    """
    logging.info("Processing issue event via webhook handler.")

    # Extract necessary data from webhook_data
    gitlab_url = webhook_data.get('gitlab_url')
    gitlab_token = webhook_data.get('gitlab_token')
    project_id = webhook_data.get('project_id')
    issue_iid = webhook_data.get('issue_iid')
    event_type = webhook_data.get('event_type')
    action = webhook_data.get('action')
    project_data = webhook_data.get('project_data', {})
    google_api_key = webhook_data.get('google_api_key')

    if not all([gitlab_url, gitlab_token, project_id, google_api_key]):
        logging.error("Missing critical data in webhook_data for processing: gitlab_url, gitlab_token, project_id, google_api_key.")
        return {"status": "error", "message": "Missing critical configuration."}

    logging.info(f"Processing project {project_id}, event_type {event_type} on {gitlab_url}")

    try:
        gl = get_gitlab_instance(gitlab_url, gitlab_token)
        firestore_mgr = get_managers()
    except ValueError as e:
        logging.error(f"Failed to initialize services due to configuration: {e}")
        return {"status": "error", "message": f"Service configuration error: {e}"}
    except Exception as e:
        logging.error(f"Failed to initialize services: {e}")
        return {"status": "error", "message": f"Failed to initialize services: {e}"}
    
    # Handle merge to main branch - update repository content
    if event_type == "merge_to_main" or action == "update_repo_content":
        return handle_merge_to_main(gl, project_id, project_data, firestore_mgr)

    # For issue/note events, ensure we have issue_iid
    if not issue_iid:
        logging.error(f"Missing issue_iid for {event_type} event")
        return {"status": "error", "message": "Missing issue_iid for issue/note event"}
    
    # Check if this is a new project (first time seeing this project_id)
    is_new_project = not firestore_mgr.is_project_registered(project_id)
    
    if is_new_project:
        logging.info(f"New project detected: {project_id}. Storing repository content and metadata.")
        success = handle_new_project(gl, project_id, project_data, firestore_mgr)
        if not success:
            logging.error(f"Failed to process new project {project_id}")
            return {"status": "error", "message": "Failed to process new project"}

    # Fetch fresh issue details
    try:
        issue_data = get_issue_details(gl, project_id, issue_iid)
    except Exception as e:
        logging.error(f"Failed to fetch details for issue {issue_iid}: {e}")
        return {"status": "error", "message": f"Failed to fetch issue details: {e}"}
        
    if not issue_data:
        logging.error(f"Failed to fetch details for issue {issue_iid} (returned None).")
        return {"status": "error", "message": f"Failed to fetch details for issue {issue_iid}."}

    issue_title = issue_data['title']
    issue_description = issue_data['description'] if issue_data['description'] else "No description provided."
    comments = issue_data['comments'] 

    # Check if this is a rubber duck session
    is_rubber_duck_session = RUBBER_DUCK_TRIGGER_PHRASE.lower() in issue_title.lower()
    
    # If it's not initially a rubber duck session by title, check if any existing comment is from the bot
    if not is_rubber_duck_session:
        for comment in comments:
            if comment['body'].startswith(BOT_SIGNATURE):
                is_rubber_duck_session = True
                logging.info(f"Found existing AI bot comment. Continuing session for issue {issue_iid} based on comment history.")
                break

    if not is_rubber_duck_session:
        logging.info(f"Issue title '{issue_title}' does not trigger rubber duck, and no prior bot interaction found. Skipping event type '{event_type}'.")
        return {"status": "skipped", "message": "Not a rubber duck session."}

    logging.info(f"Rubber duck session active for issue: {issue_title} (event type: {event_type})")    # Prevent bot from replying to its own comments
    if comments and comments[0]['body'].startswith(BOT_SIGNATURE):
        logging.info(f"The last comment on issue {issue_iid} was already made by the AI Bot. Skipping to avoid loops.")
        return {"status": "skipped", "message": "Last comment by bot."}
    
    # Store issue metadata for tracking
    firestore_mgr.store_issue_metadata(project_id, issue_iid, issue_data)
    
    # Get repository context for better AI responses
    issue_content = f"{issue_title}\n{issue_description}"
    repo_context = firestore_mgr.get_project_context(project_id, issue_content)
    current_problem, conversation_history = format_conversation_for_ai(issue_title, issue_description, comments)    # Detect user intent to choose appropriate response mode
    user_intent = detect_user_intent(current_problem, conversation_history)
    logging.info(f"Detected user intent: {user_intent}")
    
    # If user is indicating closure/resolution, handle appropriately
    if user_intent == 'closing':
        logging.info("User indicated problem resolution. Generating closing response.")
        # Generate a closing/congratulatory response
        ai_response = generate_socratic_questions(
            problem_description=current_problem, 
            conversation_history=conversation_history,
            api_key=google_api_key,
            repository_context=""  # No need for repo context in closing
        )
        
        # Post closing response and return
        try:
            post_comment_to_issue(gl, project_id, issue_iid, ai_response)
            logging.info(f"Successfully posted closing response to issue {issue_iid}.")
            return {"status": "success", "message": "Closing response posted."}
        except Exception as e:
            logging.error(f"Failed to post closing comment to GitLab issue {issue_iid}: {e}")
            return {"status": "error", "message": f"Failed to post closing comment to GitLab: {e}"}

    logging.info("Generating AI response with enhanced prompting.")
    try:
        # Use the enhanced contextual response generation
        ai_response = generate_socratic_questions(
            problem_description=current_problem, 
            conversation_history=conversation_history,
            api_key=google_api_key,
            repository_context=repo_context
        )
    except Exception as e:
        logging.error(f"Error generating AI response: {e}")
        return {"status": "error", "message": f"Error generating AI response: {e}"}

    if not ai_response:
        logging.warning("Google AI did not return any response.")
        return {"status": "no_action", "message": "AI did not generate a response."}

    logging.info(f"Generated AI response (mode: {user_intent}): {ai_response[:100]}...")

    # Post the AI response back to the GitLab issue
    try:
        post_comment_to_issue(gl, project_id, issue_iid, ai_response)
        logging.info(f"Successfully posted AI response to issue {issue_iid}.")
        return {"status": "success", "message": "AI response posted."}
    except Exception as e:
        logging.error(f"Failed to post comment to GitLab issue {issue_iid}: {e}")
        return {"status": "error", "message": f"Failed to post comment to GitLab: {e}"}

def handle_new_project(gl, project_id, project_data, firestore_mgr):
    """
    Handle a new project by fetching repository content and storing metadata
    
    Args:
        gl: GitLab instance
        project_id: GitLab project ID
        project_data: Project data from webhook
        firestore_mgr: Firestore manager instance
    
    Returns:
        Boolean indicating success
    """
    try:
        logging.info(f"Processing new project {project_id}")
        
        # Get repository content
        repo_handler = GitLabRepoHandler(gl)
        repo_content = repo_handler.get_repository_content(project_id)
        
        if not repo_content:
            logging.error(f"Failed to fetch repository content for project {project_id}")
            return False
        
        # Store project metadata and repository content in Firestore
        success = firestore_mgr.store_project_metadata(project_id, project_data, repo_content)
        if not success:
            logging.error(f"Failed to store project data for project {project_id}")
            return False
        
        logging.info(f"Successfully processed new project {project_id}")
        return True
        
    except Exception as e:
        logging.error(f"Error handling new project {project_id}: {e}")
        return False

def handle_merge_to_main(gl, project_id, project_data, firestore_mgr):
    """
    Handle merge to main branch by updating repository content
    
    Args:
        gl: GitLab instance
        project_id: GitLab project ID
        project_data: Project data from webhook
        firestore_mgr: Firestore manager instance
    
    Returns:
        Response dictionary
    """
    try:
        logging.info(f"Handling merge to main for project {project_id}")
        
        # Check if project is registered
        if not firestore_mgr.is_project_registered(project_id):
            logging.info(f"Project {project_id} not registered, treating as new project")
            success = handle_new_project(gl, project_id, project_data, firestore_mgr)
            if not success:
                return {"status": "error", "message": "Failed to process new project"}
            return {"status": "success", "message": "New project processed and repository content stored"}
        
        # Get updated repository content
        repo_handler = GitLabRepoHandler(gl)
        repo_content = repo_handler.get_repository_content(project_id)
        
        if not repo_content:
            logging.error(f"Failed to fetch repository content for project {project_id}")
            return {"status": "error", "message": "Failed to fetch repository content"}
        
        # Update repository content in Firestore
        success = firestore_mgr.update_repository_content(project_id, repo_content)
        if not success:
            logging.error(f"Failed to update repository content for project {project_id}")
            return {"status": "error", "message": "Failed to update repository content"}
        
        logging.info(f"Successfully updated repository content for project {project_id}")
        return {"status": "success", "message": "Repository content updated"}
        
    except Exception as e:
        logging.error(f"Error handling merge to main for project {project_id}: {e}")
        return {"status": "error", "message": f"Error handling merge: {e}"}

# Note: The old `if __name__ == '__main__':` block from scripts/main.py is not directly applicable here
# as this module is intended to be imported and its functions called by the Flask app.
# Local testing of process_issue_event would involve mocking webhook_data and calling it directly.
