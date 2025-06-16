"""
GitLab repository handler for fetching repository content and handling repository operations.
"""
import logging
import base64
import os
from typing import Dict, List, Optional
import gitlab

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitLabRepoHandler:
    def __init__(self, gitlab_instance):
        """
        Initialize GitLab repository handler
        
        Args:
            gitlab_instance: Initialized GitLab instance from python-gitlab
        """
        self.gl = gitlab_instance

    def get_repository_content(self, project_id: int, branch: str = None) -> Dict:
        """
        Fetch repository content including files, structure, and metadata
        
        Args:
            project_id: GitLab project ID
            branch: Branch to fetch from (default: project's default branch)
            
        Returns:
            Dictionary containing repository content and metadata
        """
        try:
            project = self.gl.projects.get(project_id)
            
            if not branch:
                branch = project.default_branch
            
            logger.info(f"Fetching repository content for project {project_id}, branch {branch}")
            
            # Get repository tree
            tree = project.repository_tree(recursive=True, ref=branch, all=True)
            
            # Get important files content
            important_files = self._get_important_files_content(project, tree, branch)
            
            # Get project metadata
            project_metadata = self._extract_project_metadata(project)
            
            # Compile repository content
            repo_content = {
                "project_metadata": project_metadata,
                "file_structure": self._build_file_structure(tree),
                "important_files": important_files,
                "readme_content": self._get_readme_content(project, branch),
                "package_files": self._get_package_files_content(project, branch),
                "total_files": len(tree),
                "branch": branch,
                "last_commit": self._get_last_commit_info(project, branch)
            }
            
            logger.info(f"Successfully fetched repository content for project {project_id}")
            return repo_content
            
        except Exception as e:
            logger.error(f"Failed to fetch repository content for project {project_id}: {e}")
            return {}

    def _extract_project_metadata(self, project) -> Dict:
        """
        Extract relevant project metadata
        
        Args:
            project: GitLab project object
            
        Returns:
            Dictionary with project metadata
        """
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description or "",
            "web_url": project.web_url,
            "default_branch": project.default_branch,
            "created_at": project.created_at,
            "last_activity_at": project.last_activity_at,
            "path_with_namespace": project.path_with_namespace,
            "namespace": {
                "name": project.namespace.get("name", ""),
                "path": project.namespace.get("path", ""),
                "kind": project.namespace.get("kind", "")
            },
            "topics": getattr(project, 'topics', []),
            "programming_language": getattr(project, 'programming_language', ''),
            "visibility": project.visibility
        }

    def _build_file_structure(self, tree: List) -> Dict:
        """
        Build a structured representation of the file tree
        
        Args:
            tree: Repository tree from GitLab API
            
        Returns:
            Dictionary representing file structure
        """
        structure = {
            "directories": [],
            "files": [],
            "file_types": {},
            "max_depth": 0
        }
        
        for item in tree:
            path_parts = item["path"].split("/")
            depth = len(path_parts) - 1
            structure["max_depth"] = max(structure["max_depth"], depth)
            
            if item["type"] == "tree":
                structure["directories"].append(item["path"])
            else:
                structure["files"].append({
                    "path": item["path"],
                    "name": item["name"],
                    "size": item.get("size", 0)
                })
                
                # Track file types
                file_ext = os.path.splitext(item["name"])[1].lower()
                if file_ext:
                    structure["file_types"][file_ext] = structure["file_types"].get(file_ext, 0) + 1
        
        return structure

    def _get_important_files_content(self, project, tree: List, branch: str) -> Dict:
        """
        Get content of important files (code files, configs, etc.)
        
        Args:
            project: GitLab project object
            tree: Repository tree
            branch: Branch name
            
        Returns:
            Dictionary with important files content
        """
        important_files = {}
        
        # Define important file patterns
        important_patterns = [
            # Configuration files
            "requirements.txt", "package.json", "Dockerfile", "docker-compose.yml",
            "Makefile", "CMakeLists.txt", "pom.xml", "build.gradle",
            # Source code files (limit to avoid too much content)
            "main.py", "app.py", "index.js", "main.js", "App.js",
            "main.java", "main.cpp", "main.c", "main.go",
            # Documentation
            "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
            # CI/CD
            ".gitlab-ci.yml", ".github/workflows/", "Jenkinsfile"
        ]
        
        for item in tree:
            if item["type"] == "blob":  # It's a file
                file_path = item["path"]
                file_name = item["name"]
                
                # Check if it's an important file
                should_include = any(
                    pattern in file_path.lower() or pattern == file_name.lower()
                    for pattern in important_patterns
                )
                
                # Also include Python, JavaScript, Java files from main directories
                if not should_include and len(file_path.split("/")) <= 3:
                    file_ext = os.path.splitext(file_name)[1].lower()
                    if file_ext in [".py", ".js", ".java", ".cpp", ".c", ".go", ".rs", ".php"]:
                        should_include = True
                
                if should_include:
                    try:
                        file_content = self._get_file_content(project, file_path, branch)
                        if file_content:
                            important_files[file_path] = {
                                "content": file_content,
                                "size": item.get("size", 0),
                                "type": os.path.splitext(file_name)[1].lower()
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get content for {file_path}: {e}")
        
        return important_files

    def _get_file_content(self, project, file_path: str, branch: str) -> Optional[str]:
        """
        Get content of a specific file
        
        Args:
            project: GitLab project object
            file_path: Path to the file
            branch: Branch name
            
        Returns:
            File content as string or None if failed
        """
        try:
            file_info = project.files.get(file_path=file_path, ref=branch)
            content = base64.b64decode(file_info.content).decode('utf-8')
            
            # Limit content size to avoid too large payloads
            if len(content) > 10000:  # 10KB limit
                content = content[:10000] + "\n... (content truncated)"
            
            return content
            
        except Exception as e:
            logger.warning(f"Failed to get file content for {file_path}: {e}")
            return None

    def _get_readme_content(self, project, branch: str) -> str:
        """
        Get README file content
        
        Args:
            project: GitLab project object
            branch: Branch name
            
        Returns:
            README content or empty string
        """
        readme_files = ["README.md", "README.rst", "README.txt", "README", "readme.md"]
        
        for readme_file in readme_files:
            content = self._get_file_content(project, readme_file, branch)
            if content:
                return content
        
        return ""

    def _get_package_files_content(self, project, branch: str) -> Dict:
        """
        Get package/dependency files content
        
        Args:
            project: GitLab project object
            branch: Branch name
            
        Returns:
            Dictionary with package files content
        """
        package_files = {}
        
        package_file_names = [
            "requirements.txt", "package.json", "Pipfile", "poetry.lock",
            "composer.json", "pom.xml", "build.gradle", "Cargo.toml"
        ]
        
        for file_name in package_file_names:
            content = self._get_file_content(project, file_name, branch)
            if content:
                package_files[file_name] = content
        
        return package_files

    def _get_last_commit_info(self, project, branch: str) -> Dict:
        """
        Get information about the last commit
        
        Args:
            project: GitLab project object
            branch: Branch name
            
        Returns:
            Dictionary with last commit information
        """
        try:
            commits = project.commits.list(ref_name=branch, per_page=1)
            if commits:
                commit = commits[0]
                return {
                    "id": commit.id,
                    "short_id": commit.short_id,
                    "title": commit.title,
                    "message": commit.message,
                    "author_name": commit.author_name,
                    "author_email": commit.author_email,
                    "created_at": commit.created_at,
                    "committed_date": commit.committed_date
                }
        except Exception as e:
            logger.warning(f"Failed to get last commit info: {e}")
        
        return {}

    def check_merge_to_main(self, webhook_payload: Dict) -> bool:
        """
        Check if the webhook event is a successful merge to main branch
        
        Args:
            webhook_payload: GitLab webhook payload
            
        Returns:
            Boolean indicating if it's a successful merge to main
        """
        try:
            object_kind = webhook_payload.get('object_kind')
            
            if object_kind == 'merge_request':
                merge_request = webhook_payload.get('object_attributes', {})
                action = merge_request.get('action')
                state = merge_request.get('state')
                target_branch = merge_request.get('target_branch')
                
                # Check if it's a successful merge to main/master branch
                is_merged = action == 'merge' and state == 'merged'
                is_main_branch = target_branch in ['main', 'master', 'develop']
                
                return is_merged and is_main_branch
            
            # Also handle push events to main branch
            elif object_kind == 'push':
                ref = webhook_payload.get('ref', '')
                branch_name = ref.replace('refs/heads/', '')
                
                return branch_name in ['main', 'master', 'develop']
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check merge to main: {e}")
            return False
