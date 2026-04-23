from graph.m4.state import M4State

MAX_ATTEMPTS = 3


def should_retry(state: M4State) -> str:
	if state.get("review_passed", False):
		return "end"
	if state.get("attempts", 0) >= MAX_ATTEMPTS:
		return "end"
	return "retry"
