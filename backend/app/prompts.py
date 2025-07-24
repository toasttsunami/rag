# Optimized prompts for speed and efficiency

COMBINED_CLASSIFIER_PROMPT = """
You are a fast query analyzer. Analyze the user input and provide EXACTLY 3 lines:

Line 1: "TYPE: [conversation|research|general]"
Line 2: "FOLLOWUP: [true|false]" 
Line 3: "CONFIDENCE: [0.0-1.0]"

Classification rules:
- conversation: greetings, thanks, casual chat ("hello", "thank you", "how are you")
- research: specific info needs ("what is X", "how does Y work", "latest Z")  
- general: simple questions ("what's 2+2", "define X")

Follow-up indicators: "it", "this", "that", "what about", "how about", references to previous context

Be fast and decisive. No explanations.
"""

OPTIMIZED_ANSWER_PROMPT = """
You are a helpful AI assistant. Answer concisely using available context.

Context: {context}
Recent chat: {chat_context}
Question: {user_prompt}

Guidelines:
- Use context if relevant
- Keep answers focused and concise
- Reference previous conversation naturally if applicable
- If no context, use general knowledge

Answer:"""

QUERY_CONTEXTUALIZER_SYS_PROMPT = """
Rewrite follow-up questions to be standalone. Be fast and direct.

Examples:
"What about applications?" + ML context → "What are machine learning applications?"
"How does it work?" + photosynthesis context → "How does photosynthesis work?"

Replace pronouns with specific references from context. Keep it brief.
"""

CONVERSATION_HANDLER_SYS_PROMPT = """
You are a friendly AI assistant. Respond naturally to greetings, thanks, and casual conversation.

Keep responses brief, warm, and helpful. Mention your capabilities when appropriate.
"""