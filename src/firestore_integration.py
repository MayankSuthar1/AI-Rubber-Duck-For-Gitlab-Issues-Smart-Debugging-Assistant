"""
Firestore integration for storing project metadata and tracking project state.
"""
import logging
from google.cloud import firestore
from google.oauth2 import service_account
import os
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FirestoreManager:
    def __init__(self, service_account_path=None):
        """
        Initialize Firestore client
        
        Args:
            service_account_path: Path to service account JSON file
        """
        try:
            # Default service account path
            if not service_account_path:
                service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH', 'hackathon-service-account-key.json')
            
            if service_account_path and os.path.exists(service_account_path):
                logger.info(f"Using service account file: {service_account_path}")
                credentials = service_account.Credentials.from_service_account_file(service_account_path)
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
                if not project_id:
                    # Extract project ID from service account file
                    with open(service_account_path, 'r') as f:
                        service_account_info = json.load(f)
                        project_id = service_account_info.get('project_id')
                
                self.db = firestore.Client(credentials=credentials, project=project_id)
                logger.info(f"Firestore client initialized with service account for project: {project_id}")
            else:
                logger.warning(f"Service account file not found at: {service_account_path}")
                # Use default credentials (for Cloud Run or ADC)
                self.db = firestore.Client()
                logger.info("Firestore client initialized with default credentials")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            raise

    def store_project_metadata(self, project_id, project_data, repo_content=None):
        """
        Store project metadata and repository content in Firestore
        
        Args:
            project_id: GitLab project ID
            project_data: Dictionary containing project information
            repo_content: Repository content dictionary (optional)
        """
        try:
            doc_ref = self.db.collection('projects').document(str(project_id))
            
            metadata = {
                'project_id': project_id,
                'name': project_data.get('name', ''),
                'description': project_data.get('description', ''),
                'web_url': project_data.get('web_url', ''),
                'default_branch': project_data.get('default_branch', 'main'),
                'created_at': project_data.get('created_at', ''),
                'last_activity_at': project_data.get('last_activity_at', ''),
                'namespace': project_data.get('namespace', {}),
                'path_with_namespace': project_data.get('path_with_namespace', ''),
                'repo_content_stored': repo_content is not None,
                'last_repo_update': datetime.utcnow(),
                'webhook_registered': datetime.utcnow()
            }
            
            doc_ref.set(metadata, merge=True)
            
            # Store repository content if provided
            if repo_content:
                repo_doc_ref = self.db.collection('projects').document(str(project_id)).collection('repository').document('content')
                repo_doc_ref.set({
                    'content': repo_content,
                    'updated_at': datetime.utcnow(),
                    'project_id': project_id
                }, merge=True)
                logger.info(f"Stored repository content for project {project_id}")
            
            logger.info(f"Stored metadata for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store project metadata for {project_id}: {e}")
            return False

    def get_project_metadata(self, project_id):
        """
        Retrieve project metadata from Firestore
        
        Args:
            project_id: GitLab project ID
            
        Returns:
            Dictionary with project metadata or None if not found
        """
        try:
            doc_ref = self.db.collection('projects').document(str(project_id))
            doc = doc_ref.get()
            
            if doc.exists:
                logger.info(f"Retrieved metadata for project {project_id}")
                return doc.to_dict()
            else:
                logger.info(f"No metadata found for project {project_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve project metadata for {project_id}: {e}")
            return None

    def is_project_registered(self, project_id):
        """
        Check if project is already registered in the system
        
        Args:
            project_id: GitLab project ID
            
        Returns:
            Boolean indicating if project exists
        """
        metadata = self.get_project_metadata(project_id)
        return metadata is not None

    def update_vector_db_timestamp(self, project_id):
        """
        Update the last repository update timestamp
        
        Args:
            project_id: GitLab project ID
        """
        try:
            doc_ref = self.db.collection('projects').document(str(project_id))
            doc_ref.update({
                'last_repo_update': datetime.utcnow()
            })
            logger.info(f"Updated repository timestamp for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update repository timestamp for {project_id}: {e}")
            return False

    def store_issue_metadata(self, project_id, issue_iid, issue_data):
        """
        Store issue metadata for tracking
        
        Args:
            project_id: GitLab project ID
            issue_iid: Issue internal ID
            issue_data: Dictionary containing issue information
        """
        try:
            doc_ref = self.db.collection('projects').document(str(project_id)).collection('issues').document(str(issue_iid))
            
            metadata = {
                'issue_iid': issue_iid,
                'project_id': project_id,
                'title': issue_data.get('title', ''),
                'description': issue_data.get('description', ''),
                'state': issue_data.get('state', ''),
                'created_at': issue_data.get('created_at', ''),
                'updated_at': issue_data.get('updated_at', ''),
                'author': issue_data.get('author', {}),
                'labels': issue_data.get('labels', []),
                'is_rubber_duck_session': True,
                'last_ai_response': datetime.utcnow()
            }
            
            doc_ref.set(metadata, merge=True)
            logger.info(f"Stored issue metadata for project {project_id}, issue {issue_iid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store issue metadata for {project_id}/{issue_iid}: {e}")
            return False

    def get_repository_content(self, project_id):
        """
        Retrieve repository content from Firestore
        
        Args:
            project_id: GitLab project ID
            
        Returns:
            Dictionary with repository content or None if not found
        """
        try:
            repo_doc_ref = self.db.collection('projects').document(str(project_id)).collection('repository').document('content')
            doc = repo_doc_ref.get()
            
            if doc.exists:
                logger.info(f"Retrieved repository content for project {project_id}")
                return doc.to_dict().get('content', {})
            else:
                logger.info(f"No repository content found for project {project_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve repository content for {project_id}: {e}")
            return None

    def update_repository_content(self, project_id, repo_content):
        """
        Update repository content in Firestore
        
        Args:
            project_id: GitLab project ID
            repo_content: Updated repository content
        """
        try:
            repo_doc_ref = self.db.collection('projects').document(str(project_id)).collection('repository').document('content')
            repo_doc_ref.set({
                'content': repo_content,
                'updated_at': datetime.utcnow(),
                'project_id': project_id
            }, merge=True)
            
            # Update project metadata timestamp
            project_doc_ref = self.db.collection('projects').document(str(project_id))
            project_doc_ref.update({
                'last_repo_update': datetime.utcnow()
            })
            
            logger.info(f"Updated repository content for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update repository content for {project_id}: {e}")
            return False

    def get_project_context(self, project_id, issue_content, max_files=10):
        """
        Get relevant project context for an issue from stored repository content
        
        Args:
            project_id: GitLab project ID
            issue_content: Issue title and description
            max_files: Maximum number of files to include in context
            
        Returns:
            Formatted context string for the LLM
        """
        try:
            # Get project metadata
            project_metadata = self.get_project_metadata(project_id)
            if not project_metadata:
                return "No project metadata found."
            
            # Get repository content
            repo_content = self.get_repository_content(project_id)
            if not repo_content:
                return "No repository content found."
            
            # Build context string
            context_parts = []
            
            # Add project information
            context_parts.append("=== PROJECT INFORMATION ===")
            context_parts.append(f"Project: {project_metadata.get('name', 'Unknown')}")
            context_parts.append(f"Description: {project_metadata.get('description', 'No description')}")
            context_parts.append(f"Language: {repo_content.get('project_metadata', {}).get('programming_language', 'Unknown')}")
            context_parts.append(f"Default Branch: {project_metadata.get('default_branch', 'main')}")
            
            # Add README content if available
            readme_content = repo_content.get('readme_content', '')
            if readme_content:
                context_parts.append("\n=== README ===")
                context_parts.append(readme_content[:1000] + ("..." if len(readme_content) > 1000 else ""))
            
            # Add important files
            important_files = repo_content.get('important_files', {})
            if important_files:
                context_parts.append("\n=== IMPORTANT FILES ===")
                file_count = 0
                for file_path, file_info in list(important_files.items())[:max_files]:
                    if file_count >= max_files:
                        break
                    context_parts.append(f"\n--- {file_path} ---")
                    file_content = file_info.get('content', '')
                    # Limit content length
                    if len(file_content) > 800:
                        file_content = file_content[:800] + "... (truncated)"
                    context_parts.append(file_content)
                    file_count += 1
            
            # Add file structure overview
            file_structure = repo_content.get('file_structure', {})
            if file_structure:
                context_parts.append("\n=== PROJECT STRUCTURE ===")
                context_parts.append(f"Total files: {len(file_structure.get('files', []))}")
                context_parts.append(f"Directories: {len(file_structure.get('directories', []))}")
                file_types = file_structure.get('file_types', {})
                if file_types:
                    context_parts.append("File types: " + ", ".join([f"{ext}: {count}" for ext, count in list(file_types.items())[:5]]))
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to get project context for {project_id}: {e}")
            return "Error retrieving project context."
