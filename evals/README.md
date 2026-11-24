# Evaluation

Two layers.

## 1. Retrieval (automatic, in CI)

`cases.json` holds representative questions. For each, `tests/test_evals.py` checks the
part that is deterministic: the place is resolved correctly (or correctly reported as
ambiguous or unknown), and the sources the skill would consult include the ones a local
would expect and exclude the ones they would not. This runs offline on every pull request.

## 2. Answers (by hand, with any agent)

Each case also lists `answer_must` and `answer_must_not`: properties of a good answer
that need a reader (or a grading model) to judge. To run a case:

1. Install the `open-local` skill in the agent under test.
2. Ask the `question` exactly as written, in a new conversation.
3. Mark each `answer_must` / `answer_must_not` line as met or not. Every case also carries
   the common checks in `always`.

`examples/` holds a real answer produced this way, with its coverage report.

Answers depend on what the sources published that day, so there is no fixed expected
text. The checks are about behaviour: citing, separating proposals from decisions,
reporting gaps, refusing to guess.

Add a case when a real answer goes wrong. That is how this set should grow.
