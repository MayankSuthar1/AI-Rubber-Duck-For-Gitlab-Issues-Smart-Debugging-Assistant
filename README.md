# AI Rubber Duck For Gitlab's Issues - Smart Debugging Assistant

**🏆 Google AI in Action Hackathon 2025 - GitLab Challenge**

An AI-powered debugging assistant that helps developers solve problems through interactive questioning directly within GitLab issues. Built with Google Cloud AI and GitLab webhooks to accelerate software development.

## Table of Contents
1. [About](#about)
2. [Getting Started](#getting-started)
3. [Setup](#setup)
4. [How It Works in the Backend](#how-it-works-in-the-backend)
5. [Examples](#examples)
6. [Future Work](#future-work)

---

## About

### What is AI Rubber Duck?
AI Rubber Duck is an intelligent debugging companion that integrates directly into your GitLab workflow. When developers get stuck, they create an issue with "Rubber Duck Help Me" in the title, and our AI assistant provides contextual guidance through Socratic questioning.

### Key Features
- **🤖 AI-Powered Assistance**: Uses Google Gemini AI for intelligent responses
- **🔗 GitLab Integration**: Seamless webhook integration with GitLab issues
- **📚 Context-Aware**: Understands your entire project structure
- **💬 Interactive Conversations**: Supports multi-turn debugging sessions
- **⚡ Real-Time**: Instant responses to issue creation and comments

### Technologies Used
- **Google Cloud**: Firestore (database), Gemini AI (language model)
- **GitLab**: Webhooks API, Issues API, Repository API
- **Backend**: Python Flask, python-gitlab library
- **Platform**: Web-based service


### Demo & Links
**🎬 Demo Video**: [YouTube Link] (< 3 minutes)  
**🌐 Live Demo**: [Hosted Application URL]


---
## Getting Started

### Configure GitLab Webhook

To enable the AI Rubber Duck functionality in your GitLab project:

1. **Access Webhook Settings**
   - Go to your GitLab project → **Settings** → **Webhooks**

2. **Configure Webhook Details**
   - **URL**: `https://your-domain.com/webhook` (or ngrok URL for testing)
   - **Secret Token**: Use same value as `GITLAB_WEBHOOK_SECRET` should be `nkcuxx7uvUsywxT`
   - **Trigger Events**: Enable the following:
     - ✅ Issues events
     - ✅ Comments (Note events)
     - ✅ Merge request events

3. **Save It**
   - Click **Add webhook** to save

### Using the AI Rubber Duck

Once configured, simply create an issue with "Rubber Duck Help Me" in the title or description, and the AI will analyze your project context and provide helpful assistance!


---

## Setup

### Prerequisites
- Python 3.8+
- GitLab account with project
- Google Cloud account
- Public URL (ngrok for testing)

### Installation and Configuration

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd version_2
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Google Cloud Setup**
   - Enable Firestore API and Google AI API
   - Create service account with Firestore Admin role
   - Download key as `account-key.json`

4. **Environment Configuration**
   ```bash
   # Create .env file
   FLASK_APP=app/app.py
   APP_GITLAB_URL=https://gitlab.com
   APP_TARGET_GITLAB_TOKEN=your_gitlab_token
   APP_GOOGLE_AI_API_KEY=your_google_ai_key
   GITLAB_WEBHOOK_SECRET=your_webhook_secret
   GOOGLE_CLOUD_PROJECT=your_project_id
   GOOGLE_SERVICE_ACCOUNT_PATH=account-key.json
   ```

5. **Run Application**
   ```bash
   flask run -p 5000
   ```

---


## How It Works in the Backend

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitLab        │    │   Flask Web      │    │  Google Cloud   │
│   Platform      │    │   Application    │    │   Services      │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │   Issues    │◄├────┤►│   Webhook    │ │    │ │  Firestore  │ │
│ │   Comments  │ │    │ │   Handler    │◄├────┤►│  Database   │ │
│ │   Merges    │ │    │ │              │ │    │ │             │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
│                 │    │         │        │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │ Repository  │◄├────┤►│   Business   │ │    │ │   Gemini    │ │
│ │   Content   │ │    │ │    Logic     │◄├────┤►│     AI      │ │
│ │     API     │ │    │ │   Handler    │ │    │ │   Models    │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────┘

Data Flow:
1. Developer creates issue with "Rubber Duck Help Me"
2. GitLab sends webhook to Flask app
3. Handler fetches project context from Firestore
4. AI processes issue + context → generates response
5. Response posted back to GitLab issue
```

### Core Components

1. **Webhook Handler** (`app/app.py`)
   - Receives GitLab webhooks
   - Validates secret tokens
   - Routes events to appropriate handlers

2. **Business Logic** (`app/handler.py`)
   - Processes issue events
   - Manages project registration
   - Orchestrates AI responses

3. **GitLab Integration** (`src/gitlab_integration.py`)
   - Fetches issue details and comments
   - Posts AI responses back to issues
   - Retrieves repository content

4. **AI Integration** (`src/google_ai_integration.py`)
   - Configures Google Gemini AI
   - Generates contextual responses
   - Supports Socratic questioning mode

5. **Data Storage** (`src/firestore_integration.py`)
   - Stores project metadata
   - Caches repository content
   - Tracks conversation history

### Data Flow

1. **Project Registration**: First webhook triggers repository content fetch and Firestore storage
2. **Issue Processing**: AI receives issue + full project context to generate relevant questions
3. **Response Generation**: Gemini AI creates Socratic questions based on problem and codebase
4. **Content Updates**: Merge events automatically refresh repository context

### AI Context Generation
The AI receives comprehensive context including:
- Project metadata and structure
- README and configuration files
- Relevant source code files
- Issue history and previous responses

---

## Examples

### Example 1: JavaScript Error
**Issue Title**: `Rubber Duck Help Me - ReferenceError in Node.js server`

**User Problem**:
```
Getting error: ReferenceError: ten is not defined
Line: ten(port, () => {
```

**AI Response**:
```
Looking at your error "ReferenceError: ten is not defined", I can see this is on the line where 
you're trying to start a server.

Can you tell me what you intended to write instead of "ten"? 
What function do you typically use to start a server listening on a port?
```

### Example 2: Authentication Issue
**Issue Title**: `Rubber Duck Help Me - User login keeps failing`

**User Problem**:
```
My authentication endpoint returns 401 even with correct credentials
```

**AI Response** (with project context):
```
I can see you're using bcrypt for password hashing in your auth.js file. 

Let's think through this step by step:
1. Are you comparing the plain text password with the hashed password correctly?
2. Can you show me how you're calling bcrypt.compare()?
3. What does your user lookup query return - does it find the user?
```

### Example 3: Database Connection
**Issue Title**: `Rubber Duck Help Me - Database connection timeout`

**AI Response** (after analyzing config files):
```
I notice you're using MongoDB connection pooling in your config. 

When you say "timeout", let's narrow this down:
1. Is this happening on the initial connection or during queries?
2. Have you checked if your connection string includes the correct timeout parameters?
3. Looking at your .env.example, are all required environment variables set?
```

### Conversation Flow
```
Developer creates issue → AI asks clarifying questions → Developer responds → 
AI provides deeper analysis → Solution discovered → AI congratulates and summarizes
```

---

## Future Work

### Immediate Enhancements
- **Multi-Language Support**: Expand beyond Python/JavaScript to Java, C++, Go
- **IDE Integration**: VS Code extension for direct AI assistance
- **Enhanced Context**: Include test files and documentation in AI analysis
- **Performance Optimization**: Faster response times and better caching

### Advanced Features
- **Custom AI Training**: Project-specific models trained on team's coding patterns
- **Team Analytics**: Insights into common debugging patterns and knowledge gaps
- **Smart Suggestions**: Proactive issue detection based on code changes
- **Integration Expansion**: GitHub, Bitbucket, Azure DevOps support

### Enterprise Features
- **Multi-Tenant Support**: Organization-level management and analytics
- **Advanced Security**: SSO integration and audit logging
- **API Rate Limiting**: Usage controls and quota management
- **Custom Deployment**: On-premises and private cloud options

### Research Directions
- **Code Understanding**: Better static analysis integration
- **Learning from Interactions**: AI improvement from successful debugging sessions
- **Predictive Assistance**: Anticipate issues before they occur
- **Knowledge Graph**: Build connections between common problems and solutions

---

## Submission Links

**📂 Source Code**: [GitHub Repository URL]  
**📋 Devpost**: [Hackathon Submission URL]

---



**Built for Google AI in Action Hackathon 2025 - Accelerating Software Development with AI**
