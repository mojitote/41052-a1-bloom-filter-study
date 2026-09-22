# AI use and actual review record

OpenAI Codex generated most implementation, test, benchmark, analysis and report content in this session. It ran local tools and uploaded the repository at the user's request. These are agent actions; the log does not attribute debugging, measurements or understanding to the student when the student did not perform them.

## 1 Reference tests were less independent than they looked

Initial commit `93063ae` builds a `vector<bool>` oracle using `f.position(y, i)`. That is a useful bit-packing check, but an incorrect position helper could affect both the implementation and its oracle. Review added fixed mixer/index known-answer vectors and per-key filtered-set equality. The limitation is not concealed: known-answer examples still do not prove statistical independence of the hash family.

The initial benchmark also validates total returned counts, not individual outcomes. The later per-key exact-pipeline test strengthens that evidence without falsely claiming that aggregate counts alone prove equivalence.

Evidence: initial commit and the subsequent test diff; `results/tests.log` records 343,406 passing checks in optimized and sanitizer builds.

## 2 Analysis imports assumed unavailable packages

The first execution of `scripts/analyze.py` failed at:

```text
from scipy.stats import t
ModuleNotFoundError: No module named 'scipy'
```

After eliminating that dependency, the next attempt exposed:

```text
import matplotlib
ModuleNotFoundError: No module named 'matplotlib'
```

Both errors were observed in this session. They were one underlying mistake: assuming plotting/statistical packages were present without checking the environment. The final implementation uses documented two-sided t critical values for 2/4/8 seeded trials and installs Matplotlib in the project-local environment. `requirements.txt`, `results/python-versions.json` and `results/analysis.log` make the setup reproducible. No CSV values were changed to fix these setup errors.

## What is not an AI mistake

The `|=` to `=` example was constructed deliberately to demonstrate the no-false-negative invariant. It is not a discovered production bug. The early-exit hypothesis was investigated with a post-hoc ablation; an unexpected measurement is not automatically an AI error. Neither example is misrepresented as an accidental mistake for the disclosure requirement.

## Human understanding boundary

The student selected the topic and requested extensive AI assistance. The session does not establish that the student can already explain every line. `walkthrough.md` supplies a route for learning and demonstrating the code. Before submission the author should review the reflection and disclose any remaining uncertainty honestly. The video must use the author's own explanation; no synthetic personal walkthrough has been created.

## September 22 revision

At the user's request, Codex tightened the central conclusion and storage wording,
added contains_full_scan with the same storage/mapping, expanded equivalence tests,
and ran a separate exact-pipeline experiment plus analysis. Codex generated the
new figure, updated the template-based report and performed rendering QA. These
are agent-performed steps, not a claim that the student independently implemented
or measured them. The experiment tests pipeline impact, not hardware causation.

Codex also rewrote the report in clear student English at the user's request, preserving numerical results and references, and visually checked all 18 rendered pages.

Codex clarified mathematical notation and added six editable Word equation blocks, then checked their rendering and preserved experimental table values.
