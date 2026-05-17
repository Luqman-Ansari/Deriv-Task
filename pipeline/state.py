from enum import Enum


class Stage(str, Enum):
    INIT = "INIT"
    INPUTS_LOADED = "INPUTS_LOADED"
    TASKS_PARSED = "TASKS_PARSED"
    QUALITY_EVALUATED = "QUALITY_EVALUATED"
    SAFETY_REVIEWED = "SAFETY_REVIEWED"
    RETRY_INSTRUCTIONS_GENERATED = "RETRY_INSTRUCTIONS_GENERATED"
    FINAL_REPORT_COMPUTED = "FINAL_REPORT_COMPUTED"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"
    RESULTS_FINALISED = "RESULTS_FINALISED"


_ORDER = [
    Stage.INIT,
    Stage.INPUTS_LOADED,
    Stage.TASKS_PARSED,
    Stage.QUALITY_EVALUATED,
    Stage.SAFETY_REVIEWED,
    Stage.RETRY_INSTRUCTIONS_GENERATED,
    Stage.FINAL_REPORT_COMPUTED,
    Stage.VALIDATION_COMPLETE,
    Stage.RESULTS_FINALISED,
]


class PipelineState:
    def __init__(self) -> None:
        self.current = Stage.INIT

    def advance(self, to: Stage) -> None:
        idx = _ORDER.index(self.current)
        expected = _ORDER[idx + 1]
        if to != expected:
            raise ValueError(
                f"Illegal stage transition: {self.current} -> {to}. Expected: {expected}"
            )
        self.current = to
        print(f"  [STAGE] {self.current.value}")
