from flask import Flask, request, jsonify, render_template
import os
import logging
from dotenv import load_dotenv
from app.handler import process_issue_event
from src.gitlab_integration import BOT_SIGNATURE

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

app = Flask(__name__)

# Configuration
APP_GITLAB_URL = os.getenv('APP_GITLAB_URL', 'https://gitlab.com')
APP_TARGET_GITLAB_TOKEN = os.getenv('APP_TARGET_GITLAB_TOKEN')
APP_GOOGLE_AI_API_KEY = os.getenv('APP_GOOGLE_AI_API_KEY')
GITLAB_WEBHOOK_SECRET = os.getenv('GITLAB_WEBHOOK_SECRET')

@app.route('/')
def home():
    """Serve the home page with webhook configuration instructions"""
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def gitlab_webhook():
    logging.info("Webhook received.")
    
    # Validate webhook secret if configured
    if GITLAB_WEBHOOK_SECRET:
        gitlab_token_header = request.headers.get('X-Gitlab-Token')
        if not gitlab_token_header or gitlab_token_header != GITLAB_WEBHOOK_SECRET:
            logging.warning("Invalid X-Gitlab-Token or token missing.")
            return jsonify({"status": "error", "message": "Invalid webhook secret"}), 403
        logging.info("Webhook secret validated successfully.")

    if not request.is_json:
        logging.warning("Webhook request not in JSON format.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    payload = request.get_json()
    
    object_kind = payload.get('object_kind')
    event_type_header = request.headers.get('X-Gitlab-Event')

    logging.info(f"Received event. Object Kind: '{object_kind}', X-Gitlab-Event Header: '{event_type_header}'")

    project_id = None
    issue_iid = None
    action = None
    project_data = None
    issue_title = None

    # Handle merge request events for vector DB updates
    if object_kind == 'merge_request':
        from src.gitlab_repo_handler import GitLabRepoHandler
        
        merge_request = payload.get('object_attributes', {})
        project_data = payload.get('project', {})
        project_id = project_data.get('id')
          # Check if it's a successful merge to main branch
        repo_handler = GitLabRepoHandler(None)
        if repo_handler.check_merge_to_main(payload):
            logging.info(f"Successful merge to main branch detected for project {project_id}")
            handler_input = {
                "gitlab_url": APP_GITLAB_URL,
                "gitlab_token": APP_TARGET_GITLAB_TOKEN,
                "project_id": project_id,
                "google_api_key": APP_GOOGLE_AI_API_KEY,
                "event_type": "merge_to_main",
                "action": "update_repo_content",
                "project_data": project_data
            }
            
            result = process_issue_event(handler_input)
            return jsonify(result)
        else:
            return jsonify({"status": "skipped", "message": "Not a merge to main branch"}), 200

    elif object_kind == 'issue' and payload.get('project') and payload.get('object_attributes'):
        logging.info("Processing an 'issue' event.")
        project_data = payload['project']
        issue_attributes = payload['object_attributes']
        project_id = project_data.get('id')
        issue_iid = issue_attributes.get('iid')
        issue_title = issue_attributes.get('title', '')
        action = issue_attributes.get('action')
        
        logging.info(f"Issue event details: project_id={project_id}, issue_iid={issue_iid}, action={action}")
        
        # Check if the issue title contains "Rubber Duck Help Me"
        if "Rubber Duck Help Me" not in issue_title:
            logging.info(f"Issue title '{issue_title}' does not contain 'Rubber Duck Help Me'. Skipping.")
            return jsonify({"status": "skipped", "message": "Not a Rubber Duck Help Me request"}), 200

    elif object_kind == 'note' and payload.get('project') and payload.get('issue') and payload.get('object_attributes'):
        logging.info("Processing a 'note' (comment) event.")
        project_data = payload['project']
        issue_data = payload['issue']
        note_attributes = payload['object_attributes']
        
        project_id = project_data.get('id')
        issue_iid = issue_data.get('iid')
        issue_title = issue_data.get('title', '')
        action = note_attributes.get('noteable_type')
        
        logging.info(f"Note event details: project_id={project_id}, issue_iid={issue_iid}, noteable_type={action}")

        # Check if the issue title contains "Rubber Duck Help Me"
        if "Rubber Duck Help Me" not in issue_title:
            logging.info(f"Issue title '{issue_title}' does not contain 'Rubber Duck Help Me'. Skipping.")
            return jsonify({"status": "skipped", "message": "Not a Rubber Duck Help Me request"}), 200

        if action != 'Issue':
            logging.info(f"Note is for '{action}', not an Issue. Skipping.")
            return jsonify({"status": "skipped", "message": f"Not a comment on an issue (type: {action})"}), 200
        
        # Prevent processing comments made by the bot itself
        note_body = note_attributes.get('note', '')
        print("note_body --------- start ---------")
        print(note_body)
        print("note_body --------- end ---------")
        if (note_body.startswith(BOT_SIGNATURE) or 
            note_body.startswith("<!-- AI Rubber Duck -->") or 
            note_body.startswith("**Sended By AI Rubber Duck:**") or 
            note_body.startswith("Sended By AI Rubber Duck:")):
            logging.info("Comment is from the bot itself (starts with BOT_SIGNATURE). Skipping.")
            return jsonify({"status": "skipped", "message": "Comment from bot"}), 200

    else:
        logging.warning(f"Webhook payload not for a supported event or malformed. Object kind: '{object_kind}'.")
        if object_kind == 'issue':
            logging.warning(f"For 'issue' event: 'project' present: {'project' in payload}, 'object_attributes' present: {'object_attributes' in payload}")
        elif object_kind == 'note':
            logging.warning(f"For 'note' event: 'project' present: {'project' in payload}, 'issue' present: {'issue' in payload}, 'object_attributes' present: {'object_attributes' in payload}")
        return jsonify({"status": "error", "message": "Invalid payload or not a supported event type"}), 400

    # Validate required fields based on event type
    if object_kind in ['issue', 'note'] and (not project_id or not issue_iid):
        logging.error(f"Missing or invalid project_id ('{project_id}') or issue_iid ('{issue_iid}') in webhook payload.")
        return jsonify({"status": "error", "message": "Missing or invalid project_id or issue_iid"}), 400
    elif object_kind == 'merge_request' and not project_id:
        logging.error(f"Missing or invalid project_id ('{project_id}') in merge request webhook payload.")
        return jsonify({"status": "error", "message": "Missing or invalid project_id"}), 400

    if not APP_TARGET_GITLAB_TOKEN:
        logging.error("APP_TARGET_GITLAB_TOKEN is not configured for the service.")
        return jsonify({"status": "error", "message": "Service token configuration error"}), 500
    if not APP_GOOGLE_AI_API_KEY:
        logging.error("APP_GOOGLE_AI_API_KEY is not configured for the service.")
        return jsonify({"status": "error", "message": "Service AI key configuration error"}), 500

    handler_input = {
        "gitlab_url": APP_GITLAB_URL,
        "gitlab_token": APP_TARGET_GITLAB_TOKEN,
        "project_id": project_id,
        "issue_iid": issue_iid,
        "google_api_key": APP_GOOGLE_AI_API_KEY,
        "event_type": object_kind,
        "action": action,
        "project_data": project_data
    }
    
    logging.info(f"Calling process_issue_event for project {project_id}, issue {issue_iid}, event_type {object_kind}, action {action}")
    result = process_issue_event(handler_input)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=False, port=os.getenv("PORT", 8080))
