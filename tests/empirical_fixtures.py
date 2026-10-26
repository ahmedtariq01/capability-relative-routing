"""Invented routing fixture, not LAB-Bench text or empirical outcomes."""
from crr.empirical import Observation, Question


def fixture():
    questions, observations, entries = [], [], []
    for subset in ("LitQA2", "ProtocolQA", "SeqQA"):
        for i in range(20):
            item = f"synthetic-{subset}-{i}"
            text = "Synthetic task " + "word " * (i + 1) + (" ACGTACGT 1234" if i % 2 else "")
            questions.append(Question(item, subset, f"group-{subset}-{i}", text,
                                      ("short", "a longer synthetic option", "not enough information")))
            entries.append({"original_id": item, "subset": subset, "source_group": questions[-1].source_group,
                            "split": "development"})
            for j in range(4):
                failed = i == 19 and j == 0
                solved = not failed and (i % 5 <= j or (i >= 15 and j == 0))
                observations.append(Observation(item, f"model_{j+1}", solved,
                                                "failed" if failed else "answered", (j+1) * .01))
        for i in range(40):
            entries.append({"original_id": f"never-load-{subset}-{i}", "subset": subset,
                            "source_group": f"held-{subset}-{i}", "split": "held_out"})
    manifest = {"selection": {"items": entries}, "models": [{"slot": f"model_{i}"} for i in range(1, 5)],
                "method": {"held_out_outcomes_seen": False}}
    return manifest, tuple(questions), tuple(observations)
