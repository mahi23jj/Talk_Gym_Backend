from typing import Any, Dict, List

from app.services.Ai_Transaltion import split_sentences


def sentence_structure_analysis(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    transcript_sentences = analysis.get("transcript_sentences", [])
    if transcript_sentences:
        sentences = [
            {
                "idx": int(item.get("idx", item.get("index", i))),
                "sentence": str(item.get("sentence", "")).strip(),
            }
            for i, item in enumerate(transcript_sentences)
            if str(item.get("sentence", "")).strip()
        ]
    else:
        transcript = analysis.get("transcript", "")
        raw_sentences = split_sentences(transcript)
        sentences = [{"idx": idx, "sentence": sentence} for idx, sentence in enumerate(raw_sentences)]

    feedback_map = {
        int(item.get("idx", item.get("sentence_index", item.get("index", -1)))): item
        for item in analysis.get("sentence_feedback", [])
        if isinstance(item, dict)
    }

    result = []

    for sentence_row in sentences:
        idx = sentence_row["idx"]
        sentence = sentence_row["sentence"]
        feedback = feedback_map.get(idx)

        result.append({
            "id": idx,
            "sentence": sentence,
            "issue": feedback.get("issue") if feedback else None,
            "improvement_type": feedback.get("improvement_type") if feedback else None,
            "improvement": feedback.get("improved_example") if feedback else None
        })

    return result






    
