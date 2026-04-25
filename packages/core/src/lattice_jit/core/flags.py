from dataclasses import dataclass


@dataclass(slots=True)
class FeatureFlags:
    enable_litellm: bool = False
    enable_opa_http: bool = False
    enable_phase_b: bool = True
