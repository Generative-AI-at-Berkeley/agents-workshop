from graph.m2.state import M2State

MAX_ATTEMPTS = 3


def should_retry(state: M2State) -> str:
	if state.get("review_passed", False):
		return "end"
	if state.get("attempts", 0) >= MAX_ATTEMPTS:
		return "end"
	return "retry"
