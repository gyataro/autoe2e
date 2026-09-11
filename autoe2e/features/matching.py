import json
from typing import Any

from autoe2e.llm import LLMService
from autoe2e.llm.prompts import (
    SIMILARITY_SYSTEM_PROMPT,
    create_similarity_user_messages,
)
from autoe2e.storage import FunctionalityStore
from autoe2e.utils import extract_response_content, geometric_score


def index_functionalities(
    llm: LLMService,
    store: FunctionalityStore,
    functionalities: list[str],
) -> list[int]:
    embeddings = llm.embeddings.embed_documents(functionalities)
    return [
        _resolve_match(llm, store, rank, text, embedding, store.nearest(embedding))
        for rank, (text, embedding) in enumerate(zip(functionalities, embeddings))
    ]


def link_action(
    store: FunctionalityStore,
    functionality_ids: list[int],
    *,
    state_id: str,
    state_url: str,
    previous_state_id: str | None,
    action_id: str,
    previous_action_id: str | None,
    action_test_id: str | None,
    action_depth: int,
    action_type: str = "SINGLE",
) -> None:
    store.add_action_links(
        {
            "url": state_url,
            "state": state_id,
            "prev_state": previous_state_id,
            "action": action_id,
            "prev_action": previous_action_id,
            "test_id": action_test_id,
            "depth": action_depth,
            "type": action_type,
            "rank_score": geometric_score(rank),
            "func_pointer": str(functionality_id),
            "final": False,
            "should_execute": True,
        }
        for rank, functionality_id in enumerate(functionality_ids)
    )


def _resolve_match(
    llm: LLMService,
    store: FunctionalityStore,
    rank: int,
    text: str,
    embedding: list[float],
    candidates: list[dict[str, Any]],
) -> int:
    exact_indices = [
        index for index, candidate in enumerate(candidates) if candidate["text"] == text
    ]
    decision: dict[str, Any] = {
        "match": bool(exact_indices),
        "match_index": exact_indices,
        "combined_text": text,
    }
    if candidates:
        response = llm.invoke(
            SIMILARITY_SYSTEM_PROMPT,
            create_similarity_user_messages(
                text, "\n".join(candidate["text"] for candidate in candidates)
            ),
        )
        decision = json.loads(extract_response_content(response))
        if "match_index" in decision:
            indices = decision["match_index"]
            if isinstance(indices, int):
                indices = [indices]
            decision["match_index"] = list(dict.fromkeys([*indices, *exact_indices]))
        elif exact_indices:
            decision.update(match=True, match_index=exact_indices, combined_text=text)

    if not decision["match"]:
        return store.create(text, embedding, geometric_score(rank))

    match_ids = [candidates[index]["_id"] for index in decision["match_index"]]
    combined_text = decision.get("combined_text", text)
    store.merge(
        match_ids[0],
        match_ids[1:],
        combined_text,
        llm.embeddings.embed_query(combined_text),
    )
    return match_ids[0]
