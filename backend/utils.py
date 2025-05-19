from typing import List, Dict

def format_chat_prompt(system_prompt: str, conversation_history: List[Dict[str, str]]) -> str:
    """
    Formats the system prompt and conversation history according to the specified template.

    Args:
        system_prompt: The system message.
        conversation_history: A list of message objects, where each object has a 'role' and 'content'.

    Returns:
        A formatted string ready for the model.
    """
    prompt_parts = []

    # Modify system prompt to include instructions for the response format
    enhanced_system_prompt = system_prompt

    # Add system prompt
    prompt_parts.append(f"<|im_start|>system\n{enhanced_system_prompt}<|im_end|>")

    # Add conversation history
    for message in conversation_history:
        if isinstance(message, dict):
            role = message.get("role", "user") # Default to user if role is missing, though it shouldn't be
            content = message.get("content", "")
            prompt_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        # Optionally, else: handle or log malformed message

    # Add the final assistant prompt
    prompt_parts.append(f"<|im_start|>assistant") # Note: No newline after assistant per original request

    return "\n".join(prompt_parts)

def format_simple_prompt(system_prompt: str, user_prompt: str) -> str:
    """
    Formats a simple system and user prompt according to the specified template.

    Args:
        system_prompt: The system message.
        user_prompt: The user message.

    Returns:
        A formatted string ready for the model.
    """
    return f"""<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{user_prompt}<|im_end|>
<|im_start|>assistant
"""

# Example usage (can be removed or kept for testing):
if __name__ == '__main__':
    sys_prompt = "You are a helpful AI assistant. Your role is to provide concise and accurate answers."
    history = [
        {"role": "user", "content": "Hello, who are you?"},
        {"role": "assistant", "content": "I am an AI assistant. How can I help you today?"},
        {"role": "user", "content": "What is the capital of France?"}
    ]
    formatted = format_chat_prompt(sys_prompt, history)
    print(formatted)
