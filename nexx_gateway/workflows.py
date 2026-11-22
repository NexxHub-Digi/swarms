"""Bounded, read-only workflow definitions. Never register arbitrary user tools."""

from typing import Final

WORKFLOWS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "research": (
        ("Research Analyst", "Organize the task into known facts, unknowns, and verification steps. Do not invent citations or imply that browsing occurred."),
        ("Research Reviewer", "Identify unverified assertions, alternative explanations, and evidence requirements. Produce a useful, clearly qualified answer."),
    ),
    "creative": (
        ("Creative Strategist", "Develop an audience-specific brief with creative direction, messaging, format, and accessibility requirements."),
        ("Creative Reviewer", "Turn the brief into implementable creative instructions. Do not claim to have rendered imagery, video, or audio."),
    ),
    "software": (
        ("Software Architect", "Describe architecture, interfaces, data boundaries, acceptance criteria, and security threats."),
        ("Engineering Reviewer", "Develop an implementation and testing plan. Do not claim code was committed, deployed, or tested without evidence."),
    ),
    "operations": (
        ("Operations Analyst", "Analyze the provided operational information, constraints, bottlenecks, and possible improvements. Mark assumptions."),
        ("Operations Reviewer", "Create an actionable operational checklist and metrics. Do not fabricate records or take external actions."),
    ),
    "support": (
        ("Support Assistant", "Draft a clear, respectful support response using only the context supplied in the task."),
        ("Support Reviewer", "Check clarity, privacy, accuracy, and whether escalation or human approval is needed."),
    ),
    "commerce": (
        ("Commerce Analyst", "Assess catalogue, fulfilment, customer experience, and merchant operations from provided facts only."),
        ("Commerce Reviewer", "Recommend measurable, practical actions. Never create orders, alter inventory, or promise availability."),
    ),
    "finance_readonly": (
        ("Finance Analyst", "Summarize user-provided financial records and assumptions for review. Do not initiate transfers, advise bypassing regulation, or invent balances."),
        ("Finance Reviewer", "Check arithmetic assumptions, verification needs, risks, and required human or compliance review. No transaction execution."),
    ),
}
