# This module will handle interactions with the Google AI API (Gemini).

import google.generativeai as genai
import os
import logging
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Safety settings for the generative model
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# Advanced system instructions for different AI response modes
SOCRATIC_INSTRUCTION = """You are an AI assistant acting as a 'Rubber Duck' debugging companion. 
Your primary role is to help developers think through problems by asking thoughtful Socratic questions.

**Core Guidelines:**
- Ask probing questions to guide the user to their own solution
- Build upon previous conversation context to avoid repetition
- Request specific code snippets when needed for better understanding
- Help users break down complex problems into smaller, manageable parts

**Question Types to Use:**
1. **Clarification**: "What exactly do you mean when you say...?"
2. **Assumption Challenge**: "What assumptions are you making about...?"
3. **Process Exploration**: "Walk me through what happens when...?"
4. **Alternative Thinking**: "What other approaches have you considered?"
5. **Root Cause**: "What do you think might be causing this behavior?"
6. **Testing Strategy**: "How could you verify if...?"

**Response Format:**
- Start with acknowledgment of their input
- Ask 1-2 focused questions (not overwhelming)
- If requesting code, be specific about what you need to see
- End with encouragement or next step guidance

**Adaptive Behavior:**
- If user seems stuck: Offer to switch to explanation mode by saying "Would you like me to explain this concept instead?"
- If user asks direct questions: Acknowledge but redirect to Socratic approach
- If user provides substantial context: Build deeper, more specific questions"""

EXPLANATION_INSTRUCTION = """You are an AI assistant in explanation mode, helping developers understand concepts and solutions.

**Your Role:**
- Provide clear, comprehensive explanations of programming concepts
- Offer step-by-step solutions when requested
- Include code examples and best practices
- Explain the "why" behind solutions, not just the "how"

**Response Structure:**
1. **Problem Summary**: Briefly restate what you understand
2. **Explanation**: Clear explanation of the concept/solution
3. **Code Example**: Practical implementation (if applicable)
4. **Best Practices**: Additional tips and considerations
5. **Next Steps**: Suggestions for further learning or implementation

**Tone**: Educational, supportive, and thorough while remaining accessible."""

ANALYSIS_INSTRUCTION = """You are an AI code analyst and architecture advisor.

**Your Capabilities:**
- Analyze code structure and identify potential issues
- Suggest architectural improvements and design patterns
- Review code for performance, security, and maintainability
- Provide refactoring recommendations

**Analysis Framework:**
1. **Code Quality**: Readability, maintainability, adherence to standards
2. **Performance**: Efficiency, optimization opportunities
3. **Security**: Potential vulnerabilities and secure coding practices
4. **Architecture**: Design patterns, separation of concerns, scalability
5. **Best Practices**: Industry standards and recommended approaches

**Output Format:**
- Clear categorization of findings
- Specific, actionable recommendations
- Code examples showing improvements
- Priority levels for different suggestions"""

CLOSING_INSTRUCTION = """You are an AI assistant in resolution/closing mode. The user has indicated they've solved their problem or gotten what they needed.

**Your Role:**
- Acknowledge their success and express appreciation for the collaboration
- Provide a brief summary of what was learned or accomplished
- Offer encouragement and positive reinforcement
- Suggest next steps for continued learning or improvement
- Close the conversation gracefully

**Response Format:**
- Start with congratulations or acknowledgment
- Brief summary of the key insights or solutions discovered
- Encouragement about their problem-solving process
- Optional: Suggest related topics they might explore
- Friendly closing statement

**Tone**: Positive, encouraging, supportive, and celebratory of their achievement."""

def configure_google_ai(api_key=None):
    """Configures the Google AI SDK with the API key.
    If api_key is provided, it's used directly.
    Otherwise, it attempts to fetch from the GOOGLE_AI_API_KEY environment variable.
    """
    key_to_use = api_key if api_key else os.getenv('GOOGLE_AI_API_KEY')
    
    if not key_to_use:
        logging.error("Google AI API key not provided and GOOGLE_AI_API_KEY environment variable not set.")
        return False
    try:
        genai.configure(api_key=key_to_use)
        logging.info("Google AI SDK configured successfully.")
        return True
    except Exception as e:
        logging.error(f"Error configuring Google AI SDK: {e}")
        return False # Return False on failure

def detect_user_intent(problem_description, conversation_history=""):
    """
    Analyze user input to determine the most appropriate response mode.
    Returns: 'socratic', 'explanation', 'analysis', 'closing', or 'mixed'
    """
    intent_keywords = {
        'closing': ['i got it', 'got it', 'issue is solved', 'problem is solved', 'thank you', 
                   'thanks', 'i have fixed', 'i have fix', 'fixed it', 'solved it', 
                   'that worked', 'it works now', 'working now', 'problem solved',
                   'all good', 'perfect', 'exactly what i needed', 'that did it',
                   'issue resolved', 'resolved', 'figured it out', 'found the solution',
                   'no more help needed', 'all set'],
        'explanation': ['explain', 'how does', 'what is', 'can you tell me', 'help me understand', 
                       'show me', 'teach me', 'what does this mean', 'please explain',
                       'give me the answer', 'just tell me', 'solve this for me',
                       'provide the solution', 'show me the code', 'what should i do'],
        'analysis': ['review my code', 'analyze', 'is this good', 'optimize', 'improve', 
                    'best practice', 'code review', 'performance', 'refactor'],
        'socratic': ['help me think', 'guide me', 'rubber duck', 'ask me questions',
                    'help me debug', 'walk me through', 'help me figure out']
    }
    
    text_to_analyze = (problem_description + " " + conversation_history).lower()
    
    # Check for closing/resolution indicators first (highest priority)
    for keyword in intent_keywords['closing']:
        if keyword in text_to_analyze:
            return 'closing'
    
    # Check for explicit explanation requests
    for keyword in intent_keywords['explanation']:
        if keyword in text_to_analyze:
            return 'explanation'
    
    # Check for code analysis requests
    for keyword in intent_keywords['analysis']:
        if keyword in text_to_analyze:
            return 'analysis'
    
    # Check for explicit Socratic requests
    for keyword in intent_keywords['socratic']:
        if keyword in text_to_analyze:
            return 'socratic'
    
    # Default behavior based on context - prefer Socratic method
    if len(conversation_history) > 500:  # Ongoing conversation
        return 'socratic'
    elif 'code' in text_to_analyze and any(word in text_to_analyze for word in ['review', 'analyze', 'improve']):
        return 'analysis'
    else:
        return 'socratic'  # Default to Socratic method to encourage self-discovery

def format_advanced_prompt(problem_description, conversation_history="", repository_context="", mode="socratic"):
    """
    Create an advanced, well-structured prompt based on the mode and available context.
    """
    prompt_parts = []
    
    # Add repository context if available
    if repository_context and repository_context != "No relevant repository context found.":
        prompt_parts.append("**REPOSITORY CONTEXT:**")
        prompt_parts.append(repository_context)
        prompt_parts.append("---")
    
    # Add conversation history if available
    if conversation_history:
        prompt_parts.append("**CONVERSATION HISTORY:**")
        prompt_parts.append(conversation_history)
        prompt_parts.append("---")
      # Add current problem with appropriate framing based on mode
    if mode == "socratic":
        prompt_parts.append("**CURRENT PROBLEM/QUESTION:**")
        prompt_parts.append(problem_description)
        prompt_parts.append("\n**TASK:** Ask thoughtful Socratic questions to guide the user toward understanding and solving this problem themselves.")
        
    elif mode == "explanation":
        prompt_parts.append("**REQUEST FOR EXPLANATION:**")
        prompt_parts.append(problem_description)
        prompt_parts.append("\n**TASK:** Provide a clear, comprehensive explanation with examples and best practices.")
        
    elif mode == "analysis":
        prompt_parts.append("**CODE/SYSTEM FOR ANALYSIS:**")
        prompt_parts.append(problem_description)
        prompt_parts.append("\n**TASK:** Analyze the provided code/system and give detailed feedback on quality, performance, security, and architecture.")
        
    elif mode == "closing":
        prompt_parts.append("**USER RESOLUTION/CLOSING STATEMENT:**")
        prompt_parts.append(problem_description)
        prompt_parts.append("\n**TASK:** Acknowledge their success, summarize the learning journey, and provide encouraging closure.")
        
    elif mode == "mixed":
        prompt_parts.append("**DEVELOPER REQUEST:**")
        prompt_parts.append(problem_description)
        prompt_parts.append("\n**TASK:** Provide a balanced response combining explanation and Socratic guidance as appropriate.")
    
    return "\n".join(prompt_parts)

def generate_socratic_questions(problem_description, conversation_history="", api_key=None, repository_context=""):
    """Enhanced Socratic questioning with advanced prompting and multiple modes."""
    # Configure AI with the provided API key before proceeding
    if not configure_google_ai(api_key=api_key):
        return "Error: Google AI not configured. Please check API key."

    # Detect user intent
    mode = detect_user_intent(problem_description, conversation_history)
      # Select appropriate system instruction
    system_instructions = {
        'socratic': SOCRATIC_INSTRUCTION,
        'explanation': EXPLANATION_INSTRUCTION,
        'analysis': ANALYSIS_INSTRUCTION,
        'closing': CLOSING_INSTRUCTION,
        'mixed': SOCRATIC_INSTRUCTION  # Default to Socratic for mixed mode
    }
    
    selected_instruction = system_instructions.get(mode, SOCRATIC_INSTRUCTION)

    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            safety_settings=SAFETY_SETTINGS,
            system_instruction=selected_instruction
        )

        # Create advanced prompt
        full_prompt = format_advanced_prompt(
            problem_description, 
            conversation_history, 
            repository_context, 
            mode
        )

        print("full prompt:", full_prompt)  # Debugging line to check prompt structure

        with open('debug_prompt.txt', 'w') as f:
            f.write(full_prompt)

        logging.info(f"Using {mode} mode for response generation. Prompt length: {len(full_prompt)} chars.")

        response = model.generate_content(full_prompt)

        if response.parts:
            generated_text = response.text
              # Add mode indicator to response for user awareness (no emojis for Windows compatibility)
            mode_indicators = {
                'socratic': "**Rubber Duck Mode** - Let's think through this together:\n\n",
                'explanation': "**Explanation Mode** - Here's what you need to know:\n\n",
                'analysis': "**Analysis Mode** - Code Review Results:\n\n",
                'mixed': "**Adaptive Mode** - Tailored response:\n\n",
                'closing': "**Session Complete** - Great work on solving this!\n\n"
            }
            
            formatted_response = mode_indicators.get(mode, "") + generated_text
            
            # Add helpful footer with mode switching options (no emojis)
            if mode == 'socratic':
                formatted_response += "\n\n---\n*Need a direct explanation instead? Just ask 'Can you explain this?' in your next message.*"
            elif mode == 'explanation':
                formatted_response += "\n\n---\n*Want to explore this further with questions? Ask me to 'help you think through this step by step.'*"
            elif mode == 'analysis':
                formatted_response += "\n\n---\n*Ready to implement these suggestions? I can guide you through the process step by step.*"
            elif mode == 'closing':
                formatted_response += "\n\n---\n*Feel free to create a new issue if you encounter other problems. Happy coding!*"
            
            logging.info(f"Successfully generated {mode} response. Length: {len(formatted_response)} chars.")
            return formatted_response
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            logging.warning(f"Prompt was blocked by Google AI. Reason: {response.prompt_feedback.block_reason}")
            return f"**Error**: The prompt was blocked. Reason: {response.prompt_feedback.block_reason}"
        else:
            logging.warning("Google AI returned no content or an unexpected response structure.")
            return "**Error**: Received no content from Google AI."

    except Exception as e:
        logging.error(f"An error occurred while interacting with Google AI: {e}")
        return f"**Error**: An unexpected error occurred with Google AI: {str(e)}"

def generate_contextual_response(problem_description, conversation_history="", api_key=None, 
                               repository_context="", response_mode="auto"):
    """
    Generate a contextual response with explicit mode control.
    
    Args:
        problem_description: The current user input/problem
        conversation_history: Previous conversation context
        api_key: Google AI API key
        repository_context: Relevant code/repository information
        response_mode: 'auto', 'socratic', 'explanation', 'analysis', or 'mixed'
    """
    if response_mode == "auto":
        return generate_socratic_questions(problem_description, conversation_history, api_key, repository_context)
    
    # Configure AI
    if not configure_google_ai(api_key=api_key):
        return "Error: Google AI not configured. Please check API key."
    
    # Select system instruction based on explicit mode
    system_instructions = {
        'socratic': SOCRATIC_INSTRUCTION,
        'explanation': EXPLANATION_INSTRUCTION,
        'analysis': ANALYSIS_INSTRUCTION,
        'mixed': SOCRATIC_INSTRUCTION
    }
    
    selected_instruction = system_instructions.get(response_mode, SOCRATIC_INSTRUCTION)

    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            safety_settings=SAFETY_SETTINGS,
            system_instruction=selected_instruction
        )

        # Create prompt for explicit mode
        full_prompt = format_advanced_prompt(
            problem_description, 
            conversation_history, 
            repository_context, 
            response_mode
        )

        print("full prompt:", full_prompt)  # Debugging line to check prompt structure

        with open('debug_prompt.txt', 'w') as f:
            f.write(full_prompt)

        logging.info(f"Generating {response_mode} mode response. Prompt length: {len(full_prompt)} chars.")

        response = model.generate_content(full_prompt)

        if response.parts:
            generated_text = response.text
            logging.info(f"Successfully generated {response_mode} response. Length: {len(generated_text)} chars.")
            return generated_text
        else:
            return f"⚠️ **Error**: No response generated for {response_mode} mode."

    except Exception as e:
        logging.error(f"Error generating {response_mode} response: {e}")
        return f"⚠️ **Error**: Failed to generate {response_mode} response: {str(e)}"

# Utility functions for enhanced AI interaction

def extract_code_blocks(text):
    """Extract code blocks from user input for better analysis."""
    import re
    
    # Match code blocks with triple backticks
    code_blocks = re.findall(r'```(?:[\w+]*\n)?(.*?)```', text, re.DOTALL)
    
    # Match inline code with single backticks
    inline_code = re.findall(r'`([^`]+)`', text)
    
    return {
        'code_blocks': code_blocks,
        'inline_code': inline_code,
        'has_code': len(code_blocks) > 0 or len(inline_code) > 0
    }

def analyze_conversation_sentiment(conversation_history):
    """Analyze the sentiment and progress of the conversation."""
    frustration_indicators = [
        'stuck', 'confused', 'frustrated', 'not working', 'help me', 'please',
        'urgent', 'deadline', 'critical', 'broken', 'error', 'issue'
    ]
    
    progress_indicators = [
        'understand', 'makes sense', 'got it', 'working', 'solved',
        'thanks', 'helpful', 'progress', 'better', 'clear'
    ]
    
    text = conversation_history.lower()
    frustration_score = sum(1 for indicator in frustration_indicators if indicator in text)
    progress_score = sum(1 for indicator in progress_indicators if indicator in text)
    
    return {
        'frustration_level': min(frustration_score, 5),  # Cap at 5
        'progress_level': min(progress_score, 5),        # Cap at 5
        'needs_encouragement': frustration_score > progress_score
    }

def suggest_response_mode(problem_description, conversation_history=""):
    """Suggest the best response mode based on context analysis."""
    sentiment = analyze_conversation_sentiment(conversation_history)
    code_info = extract_code_blocks(problem_description + " " + conversation_history)
    
    # High frustration - offer explanation mode
    if sentiment['frustration_level'] > 3:
        return "explanation", "User seems frustrated - offering direct help"
    
    # Lots of code present - suggest analysis
    if len(code_info['code_blocks']) > 2:
        return "analysis", "Multiple code blocks detected - code review mode"
    
    # Good progress with Socratic method - continue
    if sentiment['progress_level'] > 2:
        return "socratic", "User showing progress - continue Socratic approach"
    
    # Default to auto-detection
    return "auto", "Using automatic mode detection"

# Enhanced example usage and testing
if __name__ == '__main__':
    logging.info("google_ai_integration.py executed directly for testing enhanced features.")
    
    # Test different modes
    test_scenarios = [
        {
            "problem": "I'm trying to debug a Python script that's not sorting correctly. Can you explain how Python's sort() method works?",
            "mode": "auto",
            "description": "Should detect explanation request"
        },
        {
            "problem": "Help me think through this sorting issue step by step.",
            "mode": "auto", 
            "description": "Should use Socratic mode"
        },
        {
            "problem": "Please review my code: ```python\ndef sort_list(lst): lst.sort()```",
            "mode": "auto",
            "description": "Should detect analysis request"
        }
    ]
    
    # Uncomment for testing:
    # for scenario in test_scenarios:
    #     detected_mode = detect_user_intent(scenario["problem"])
    #     print(f"\nScenario: {scenario['description']}")
    #     print(f"Input: {scenario['problem'][:50]}...")
    #     print(f"Detected mode: {detected_mode}")
    #     print(f"Expected: {scenario['description']}")
    print("\nEnhanced Google AI integration module loaded successfully!")
    print("Features available:")
    print("  - Multi-mode responses (Socratic, Explanation, Analysis, Closing)")
    print("  - Advanced prompt formatting")
    print("  - Automatic intent detection")
    print("  - Contextual response generation")
    print("  - Code block extraction and analysis")
    print("  - Conversation sentiment analysis")
