# 3. System Design

SE-Blackboard is a modular multi-agent framework designed to isolate the effect of communication architecture on software engineering task performance. The system comprises four components: (1) a structured SE state schema, (2) three pluggable communication modes, (3) four specialized agents, and (4) a pipeline topology that orchestrates agent execution.

## 3.1 SE State Schema

The foundation of the framework is a domain-specific state schema implemented as Pydantic models. The schema captures the key artifacts produced during a multi-agent bug-fixing pipeline:

- **IssueInfo**: Contains the original issue description, repository name, base commit, and any hints or error traces extracted from the issue body.
- **Analysis**: Stores the Planner agent's output, including root cause analysis, affected files, a proposed fix strategy, and relevant source code context.
- **Patch**: Represents the Coder agent's output as a unified diff, along with a natural language description of the changes made.
- **Review**: Contains the Reviewer agent's assessment, including an accept/reject decision, identified issues, and specific feedback for revision.
- **TestResult**: Records the Tester agent's evaluation, including pass/fail status, test output, and diagnostic information.

A critical design principle is **field ownership**: each agent writes only to its designated state fields while having read access to upstream fields. The Planner writes to Analysis, the Coder to Patch, the Reviewer to Review, and the Tester to TestResult. This ownership model prevents agents from inadvertently overwriting each other's contributions and ensures a clear audit trail.

Crucially, the original issue description (`IssueInfo`) is always preserved in the shared state and remains directly accessible to all agents. This design choice is the architectural mechanism by which the Blackboard prevents knowledge drift: downstream agents such as the Coder can reference the verbatim issue text rather than relying solely on the Planner's summarization.

## 3.2 Communication Modes

The framework supports three communication modes, each providing a different mechanism for inter-agent information transfer:

**Message-Passing (MP)**: In this mode, each agent receives only the output of its immediate predecessor as natural language input. The Coder receives the Planner's analysis text; the Reviewer receives the Coder's patch description. No structured state is shared between agents. This mirrors the communication pattern used by most existing multi-agent SE systems.

**Blackboard (BB)**: All agents read from and write to a shared `SEBlackboardState` instance. When an agent is invoked, it receives a view of the shared state tailored to its role via `get_state_for_agent(role)`. This view includes all upstream state fields plus the original issue description. The agent's output is written back to the shared state. Importantly, the Coder agent in BB mode receives both the Planner's structured analysis *and* the original issue text, enabling it to cross-reference the Planner's interpretation against the source.

**Hybrid**: This mode combines both communication channels. Agents receive the message-passing context (predecessor output) alongside access to the blackboard state. The intent is to provide the richness of shared state while preserving the focused, curated context that message-passing provides.

The three modes share identical agent implementations and prompt templates (with mode-specific variants for context formatting). This design ensures that observed differences are attributable to the communication architecture rather than to agent behavior or prompt engineering.

## 3.3 Agent Design

The pipeline employs four specialized agents, each implemented as a subclass of a base `Agent` class:

**Planner**: Analyzes the issue description and available code context to produce a structured analysis. The analysis includes root cause identification, affected files and functions, and a step-by-step fix strategy. In BB mode, the Planner writes its analysis to the shared state; in MP mode, its output is forwarded as text to the Coder.

**Coder**: Generates a unified diff patch based on the analysis and available source code. The Coder receives code context retrieved from the target repository via git checkout of the base commit. In BB mode, the Coder can access both the Planner's analysis and the original issue from the shared state; in MP mode, it receives only the Planner's text output. The Coder uses structured JSON output to separate the patch diff from its explanation.

**Reviewer**: Evaluates the generated patch for correctness, completeness, and adherence to the fix strategy. The Reviewer produces an accept/reject decision with detailed feedback. On rejection, the pipeline returns to the Coder with the review feedback for revision, a feedback-driven iteration mechanism analogous to the verbal reinforcement learning approach in Reflexion [Shinn et al., 2023].

**Tester**: Evaluates the final patch using the SWE-bench Docker evaluation harness. The Tester receives the patch diff and applies it against the target repository's test suite to determine whether the patch resolves the failing tests specified in the issue.

Each agent has two prompt variants: one for message-passing mode and one for blackboard mode. The blackboard prompt instructs the agent to consult the shared state fields, while the message-passing prompt focuses on processing the received message. This dual-prompt design ensures that agents are appropriately guided to use the available information sources.

## 3.4 Pipeline Topology

The framework currently implements a **Sequential Pipeline** topology:

```
Planner → Coder → Reviewer → [accept?] → Tester
                      ↑          |
                      └── [reject] ──┘
```

The pipeline executes as follows:

1. The **Planner** analyzes the issue and produces a fix strategy.
2. The **Coder** generates a patch based on the analysis and code context.
3. The **Reviewer** evaluates the patch and either accepts or rejects it.
4. On rejection, the pipeline returns to the Coder with reviewer feedback (up to `max_iterations` total cycles, default 3).
5. On acceptance or when the maximum iteration count is reached, the **Tester** evaluates the final patch.

A key design decision is that the Tester always executes on the final iteration, regardless of the Reviewer's decision. This ensures that every experiment run produces a test result, enabling fair comparison across configurations.

The framework also supports a **Debate Pipeline** topology with multiple Coders generating competing patches and a Reviewer selecting the best candidate, though this topology is not evaluated in the current study.
