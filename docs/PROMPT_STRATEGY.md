# Prompt Strategy & Architecture — InquiryBot Enterprise

Prompt engineering in InquiryBot is built upon a deterministic structure that optimizes context ingestion and restricts speculative behavior.

## 1. Prompt Layout Structure
The final system payload submitted to the LLM is structured systematically:

1.  **System Persona & Guidelines:** Declares the agent's professional identity and strict adherence to evidence-based answering.
2.  **Context Section:**
    *   **PDF Documents Context:** Dynamically loaded chunks extracted from uploaded PDFs, labeled with file names and chunk indices.
    *   **Admin FAQ Context:** Overriding knowledge chunks added by administrators via the training UI.
3.  **Governance Constraints:** Explicit instructions specifying the fallback refusal message.
4.  **User Question:** The validated query submitted by the current active user.

## 2. Prompt Priorities
Prompts are refined based on four key priorities:
1.  **Safety & Alignment:** The model is locked to prevent prompt injection and declines requests unrelated to the target business domain.
2.  **Evidence Fidelity:** The model must reference source documents exactly. Textual rewrites are permitted, but semantic facts must remain identical to the source.
3.  **Clarity & Structure:** Output format is structured with paragraph separation to enhance UI readability.
4.  **Conciseness:** Avoids conversational fluff (e.g. "I would be happy to help with that!"). It delivers factual content immediately.

## 3. Dynamic Prompt Assembly Code
Prompt assembly resides in `services/chat_service.py` under the `generate_response` method. The prompt dynamically binds:
*   The raw retrieved documents text context.
*   The configured global `REFUSAL_MESSAGE`.
*   The user's query.
This clean encapsulation isolates dynamic states, allowing the prompt structure to be tested using mock inputs.
