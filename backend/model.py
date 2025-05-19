from llama_cpp import Llama
import os
import asyncio
from typing import List, Dict, Any, AsyncIterator, Union, Optional
import utils
import re # Added for checking commands
import traceback # Added for detailed error logging

# Import configuration settings
from . import config

# Get model path from environment or use default
# MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3-8B-Q8_0.gguf")
# MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))

# Initialize model
llm = Llama(
    model_path=config.MODEL_PATH,
    n_ctx=config.N_CTX,
    n_threads=config.N_THREADS,
    n_batch=config.N_BATCH,
    main_gpu=config.MAIN_GPU,
    n_gpu_layers=config.N_GPU_LAYERS,
    flash_attn=config.FLASH_ATTN,
    use_mlock=config.USE_MLOCK,
    use_mmap=config.USE_MMAP,
    offload_kqv=config.OFFLOAD_KQV,
    verbose=config.LLAMA_VERBOSE
)

def _extract_and_clean_command(text: str) -> tuple[Optional[str], str]:
    """Detects /think or /no_think, returns the command and text with command removed."""
    text_lower = text.lower()
    command = None
    cleaned_text = text

    think_match = re.search(r"\s*/think\b|\A/think\b", text_lower)
    no_think_match = re.search(r"\s*/no_think\b|\A/no_think\b", text_lower)

    if no_think_match:
        command = "/no_think"
        # Remove the command and potentially surrounding spaces
        cleaned_text = re.sub(r"\s*/no_think\b|\A/no_think\b", "", text, flags=re.IGNORECASE).strip()
    elif think_match:
        command = "/think"
        cleaned_text = re.sub(r"\s*/think\b|\A/think\b", "", text, flags=re.IGNORECASE).strip()
    
    # Normalize multiple spaces to one if any remain after stripping
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return command, cleaned_text

async def generate_response(
    prompt: Union[str, List[Dict[str, str]]],
    max_tokens: int = config.MAX_TOKENS_GENERATION,
    system_prompt: Optional[str] = None
) -> str:
    final_prompt_str: str
    effective_system_prompt = system_prompt if system_prompt is not None else "You are a helpful assistant."
    user_command = None
    processed_prompt = prompt

    if isinstance(prompt, list):
        if prompt: # Ensure prompt list is not empty
            last_user_message_dict = None
            for i in range(len(prompt) - 1, -1, -1):
                if prompt[i].get("role") == "user":
                    last_user_message_dict = prompt[i]
                    break
            
            if last_user_message_dict:
                user_command, cleaned_content = _extract_and_clean_command(last_user_message_dict.get("content", ""))
                # Create a new list with the modified message to avoid changing original
                processed_prompt = list(prompt)
                # Find the index of the dictionary and update its content
                # This is a bit more complex if multiple user messages exist; for simplicity, assume last one is targeted
                # Or better, rebuild the message list if modification is needed
                # For now, let's assume we modify a copy of the last user message if command found
                # A truly robust way would be to rebuild the prompt list with the cleaned message
                temp_processed_prompt = []
                command_extracted_from_user_message = False
                for i in range(len(prompt)):
                    msg = prompt[i]
                    if msg.get("role") == "user" and i == (len(prompt) - (prompt[::-1].index(last_user_message_dict) +1) if last_user_message_dict in prompt else -1):
                        # This is the specific user message from which command was extracted
                        temp_processed_prompt.append({"role": "user", "content": cleaned_content})
                        command_extracted_from_user_message = True
                    else:
                        temp_processed_prompt.append(msg)
                if command_extracted_from_user_message:
                    processed_prompt = temp_processed_prompt

        if user_command: # Command found in user message
            effective_system_prompt = (effective_system_prompt or "").strip() + f" {user_command.strip()}" 
        # If no command from user, system_prompt remains as is (model default thinking)
        final_prompt_str = utils.format_chat_prompt(effective_system_prompt.strip(), processed_prompt)
    else:  # prompt is a string (raw user input)
        if prompt.strip().startswith("system"): # Pre-formatted prompt
            final_prompt_str = prompt 
            # We assume pre-formatted prompts handle their own thinking commands.
            effective_system_prompt = "<Pre-formatted prompt>" # Placeholder for logging
        else: # Raw user string
            user_command, cleaned_content = _extract_and_clean_command(prompt)
            processed_prompt = cleaned_content 
            
            current_base_system_p_for_string = system_prompt if system_prompt is not None else "You are a helpful assistant." # Different default for simple string
            
            if user_command == "/no_think":
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /no_think"
            elif user_command == "/think":
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /think"
            else: # No command from user string, or command was not /think or /no_think
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /think" # Default to thinking
            
            final_prompt_str = utils.format_simple_prompt(effective_system_prompt.strip(), processed_prompt)
    
    print(f"[MODEL_DEBUG] generate_response: Effective system prompt for model: '{effective_system_prompt}'")
    print(f"[MODEL_DEBUG] generate_response: Final prompt string to model (first 300 chars): {final_prompt_str[:300]}")

    response = llm(
        prompt=final_prompt_str,
        max_tokens=max_tokens,
        temperature=config.TEMPERATURE,
        top_k=config.TOP_K,
        top_p=config.TOP_P,
        min_p=config.MIN_P,
        repeat_penalty=config.REPEAT_PENALTY
    )
    return response["choices"][0]["text"]

async def generate_stream(
    prompt: Union[str, List[Dict[str, str]]],
    max_tokens: int = config.MAX_TOKENS_GENERATION,
    system_prompt: Optional[str] = None
) -> AsyncIterator[str]:
    print(f"[MODEL_DEBUG] generate_stream: Called with prompt type: {type(prompt)}, max_tokens: {max_tokens}, system_prompt (initial): '{system_prompt}'")
    if isinstance(prompt, list):
        # Only log first 2 items for brevity if it's a list
        print(f"[MODEL_DEBUG] generate_stream: Prompt content (list, first 2 items): {prompt[:2]}")
    else:
        # Log first 100 chars for string prompts
        print(f"[MODEL_DEBUG] generate_stream: Prompt content (str, first 100 chars): {prompt[:100]}")

    final_prompt_str: str
    # Ensure base_system_prompt is defined correctly based on input system_prompt or a default
    base_system_prompt = system_prompt if system_prompt is not None else "You are a reasoning assistant. You always reason your way through tasks and employ a step by step approach to your methods to solve problems. You only return responses that are well thought out, logical, and honest."
    user_command_from_message: Optional[str] = None
    processed_prompt = prompt 

    if isinstance(prompt, list):
        effective_system_prompt = base_system_prompt # Start with base or provided system prompt
        if prompt: 
            temp_prompt_list = []
            last_user_msg_idx = -1
            for i in range(len(prompt) -1, -1, -1):
                if prompt[i].get("role") == "user":
                    last_user_msg_idx = i
                    break
            
            if last_user_msg_idx != -1:
                original_content = prompt[last_user_msg_idx].get("content", "")
                extracted_cmd, cleaned_content = _extract_and_clean_command(original_content)
                if extracted_cmd:
                    user_command_from_message = extracted_cmd
                    for i_msg in range(len(prompt)):
                        if i_msg == last_user_msg_idx:
                            temp_prompt_list.append({"role": "user", "content": cleaned_content})
                        else:
                            temp_prompt_list.append(prompt[i_msg])
                    processed_prompt = temp_prompt_list
                else:
                    processed_prompt = list(prompt) # Use a copy if no command extracted but ensure it's the original list content
            else: # No user messages in the list
                processed_prompt = list(prompt)

        if user_command_from_message == "/no_think":
            effective_system_prompt = (base_system_prompt or "").strip() + " /no_think"
        elif user_command_from_message == "/think":
             effective_system_prompt = (base_system_prompt or "").strip() + " /think"
        else: 
            effective_system_prompt = (base_system_prompt or "").strip() + " /think" # Default to thinking

        final_prompt_str = utils.format_chat_prompt(effective_system_prompt.strip(), processed_prompt)
    else:  # prompt is a string (raw user input)
        # This path is less common for chat streams but handled for completeness
        if prompt.strip().startswith("system"): # Pre-formatted prompt
            final_prompt_str = prompt 
            # We assume pre-formatted prompts handle their own thinking commands.
            effective_system_prompt = "<Pre-formatted prompt>" # Placeholder for logging
        else: # Raw user string
            user_command_from_message, cleaned_content = _extract_and_clean_command(prompt)
            processed_prompt = cleaned_content 
            
            current_base_system_p_for_string = system_prompt if system_prompt is not None else "You are a helpful assistant." # Different default for simple string
            
            if user_command_from_message == "/no_think":
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /no_think"
            elif user_command_from_message == "/think":
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /think"
            else: # No command from user string, or command was not /think or /no_think
                effective_system_prompt = (current_base_system_p_for_string or "").strip() + " /think" # Default to thinking
            
            final_prompt_str = utils.format_simple_prompt(effective_system_prompt.strip(), processed_prompt)
    
    print(f"[MODEL_DEBUG] generate_stream: Effective system prompt for model: '{effective_system_prompt}'")
    print(f"[MODEL_DEBUG] generate_stream: Final prompt string to model (first 300 chars): {final_prompt_str[:300]}")

    stream = llm(
        prompt=final_prompt_str,
        max_tokens=max_tokens,
        temperature=config.TEMPERATURE,
        top_k=config.TOP_K,
        top_p=config.TOP_P,
        min_p=config.MIN_P,
        repeat_penalty=config.REPEAT_PENALTY,
        stream=True
    )

    try:
        for chunk_idx, chunk in enumerate(stream):
            chunk_str_repr = str(chunk)
            print(f"[MODEL_DEBUG] generate_stream: Received chunk {chunk_idx}: {chunk_str_repr[:200]}{'...' if len(chunk_str_repr) > 200 else ''}")
            try:
                token = chunk["choices"][0]["text"]
                print(f"[MODEL_TOKEN_DEBUG] Raw token from llama-cpp: '{token.encode('unicode_escape').decode('utf-8')}'")
                yield token
            except (KeyError, IndexError) as e_chunk:
                print(f"[MODEL_ERROR] generate_stream: Error accessing token in chunk {chunk_idx}: {e_chunk}. Chunk: {chunk_str_repr}")
    except Exception as e_stream:
        print(f"[MODEL_ERROR] generate_stream: Exception during llm streaming: {e_stream}")
        print(f"[MODEL_ERROR] generate_stream: Traceback:\n{traceback.format_exc()}")
        # Put the exception itself or a marker onto the queue if needed, or re-raise.
        # For now, re-raising will propagate it to the task.
        raise e_stream # Send error sentinel