import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Import the shared LLM model instance and generation functions
from . import model 
# Import configuration settings
from . import config

logger = logging.getLogger(__name__)

# Constants for routes
ROUTE_GENERAL = "GENERAL"
ROUTE_WEB = "WEB"

async def classify_query(query: str, conv_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Classifies the user query to determine the appropriate route (WEB or GENERAL)."""
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    # Use the system prompt from config
    system_prompt = config.CLASSIFIER_SYSTEM_PROMPT.format(current_date=current_date_str)

    # Construct messages for the LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    logger.info(f"Classifying query for conv_id='{conv_id}', user_id='{user_id}': '{query}'")
    logger.debug(f"Classifier system prompt: {system_prompt}")

    try:
        # Use the shared LLM instance for classification
        # Ensure max_tokens is appropriate for a short classification (WEB/GENERAL)
        response_text = await model.generate_response(
            prompt=messages, 
            max_tokens=config.CLASSIFIER_MAX_TOKENS, # Use max_tokens from config
            system_prompt=None # System prompt is already part of 'messages'
        )
        response_text = response_text.strip().upper()
        logger.info(f"Classifier raw response: '{response_text}' for query: '{query}'")

        if "WEB" in response_text:
            reason = "Query classified as requiring web search based on LLM response."
            logger.info(f"Route: WEB. Reason: {reason}")
            return {"route": ROUTE_WEB, "confidence": 0.9, "reasoning": reason, "classified_by": "llm"}
        elif "GENERAL" in response_text:
            reason = "Query classified as general knowledge based on LLM response."
            logger.info(f"Route: GENERAL. Reason: {reason}")
            return {"route": ROUTE_GENERAL, "confidence": 0.9, "reasoning": reason, "classified_by": "llm"}
        else:
            # Fallback or further analysis if response is unclear
            reason = f"LLM classification unclear ('{response_text}'). Defaulting to GENERAL."
            logger.warning(reason)
            return {"route": ROUTE_GENERAL, "confidence": 0.5, "reasoning": reason, "classified_by": "llm_fallback"}

    except Exception as e:
        logger.error(f"Error during query classification: {e}")
        return {"route": ROUTE_GENERAL, "confidence": 0.0, "reasoning": f"Error in LLM classification: {e}", "classified_by": "error"}

async def optimize_query_for_search(query: str, conv_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Optimizes the user query for web search using an LLM prompt."""
    # Use the system prompt from config
    system_prompt = config.QUERY_OPTIMIZER_SYSTEM_PROMPT

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]

    logger.info(f"Optimizing query for conv_id='{conv_id}', user_id='{user_id}': '{query}'")
    logger.debug(f"Optimizer system prompt: {system_prompt}")

    try:
        # Use the shared LLM instance
        optimized_query = await model.generate_response(
            prompt=messages,
            max_tokens=config.OPTIMIZER_MAX_TOKENS, # Use max_tokens from config
            system_prompt=None # System prompt is already part of 'messages'
        )
        optimized_query = optimized_query.strip()
        # Remove potential quotes if the model wraps the query in them
        if optimized_query.startswith('"') and optimized_query.endswith('"'):
            optimized_query = optimized_query[1:-1]
        if optimized_query.startswith("'") and optimized_query.endswith("'"):
            optimized_query = optimized_query[1:-1]
            
        logger.info(f"Original query: '{query}' -> Optimized query: '{optimized_query}'")
        return optimized_query
    except Exception as e:
        logger.error(f"Error optimizing query: {e}. Returning original query.")
        return query # Fallback to original query on error

# Example usage (optional, for testing)
async def main_test():
    # Configure logging for testing
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    test_queries = [
        "What's the weather like in London today?",
        "Who won the last Super Bowl?",
        "Explain the theory of relativity.",
        "What is the capital of France?",
        "latest news on stock market",
        "How to bake a chocolate cake?",
        "/no_think tell me a joke"
    ]

    print("\n--- Testing Query Classification ---")
    for tq in test_queries:
        classification_result = await classify_query(tq, "test_conv", "test_user")
        print(f"Query: '{tq}' -> Route: {classification_result['route']}, Reasoning: {classification_result['reasoning']}")

    print("\n--- Testing Query Optimization ---")
    search_queries = [
        "Can you tell me what the current weather forecast is for San Francisco, California?",
        "I'd like to know who the current president of the United States is, please.",
        "what are the recent developments in ai ethics"
    ]
    for sq in search_queries:
        optimized_q = await optimize_query_for_search(sq, "test_conv", "test_user")
        print(f"Original: '{sq}' -> Optimized: '{optimized_q}'")

if __name__ == "__main__":
    asyncio.run(main_test())