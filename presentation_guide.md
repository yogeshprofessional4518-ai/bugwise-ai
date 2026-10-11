# BugWise AI — Presentation Guide

## Problem

New programmers may know that Python reported an error but still struggle to locate the cause, understand the concept, choose a safe correction, and distinguish a syntax check from a behavioral test.

## Proposed solution

BugWise AI is a local-first debugging dashboard. It parses pasted Python, identifies a limited set of well-supported static issues, explains them in beginner-friendly terms, suggests only conservative edits, and clearly reports which checks ran.

## Architecture

`app.py` coordinates the Streamlit interface. `analyzer.py` validates and inspects source. `fixer.py` creates reviewable suggestions and a `difflib` patch. `explainer.py` maps findings to rule-based lessons. `verifier.py` compiles candidates and runs a small allowlist of trusted reference operations on fixture inputs, without executing candidate code. `examples.py` supplies ten educational examples and expected results.

## AST and compile()

`compile(source, ..., "exec")` checks whether Python can compile the submitted text; it does not execute it. `ast.parse()` turns valid source into structured syntax nodes. Those nodes let the analyzer inspect names, operators, and literal subscripts more carefully than plain text matching. Neither tool proves the program's intended logic is correct.

## Error detection and correction

The analyzer reports syntax and indentation errors with parser line numbers. A symbol-table check flags unresolved global references, and AST rules recognize a few literal hazards such as division by zero and out-of-range constant indexes. These are static checks: most runtime errors depend on values and control flow not known at analysis time. Fix suggestions are narrow (a unique spelling match, recognized missing block colon, or a clearly missing first indentation) and remain unverified until reviewed.

## Verification and test cases

The verifier checks compilation and computes expected-versus-actual outcomes using allowlisted trusted reference operations on fixed educational inputs. It never runs the submitted source or claims it was sandboxed. Fixture tests are enabled only when the editor contains an exact educational sample and its known correction; they demonstrate the sample's behavior, not arbitrary candidate behavior. A successful compile is a syntax result, not proof of logical correctness.

## Limitations

- Static analysis cannot reliably predict every runtime exception.
- Dynamic features, namespace mutation, external dependencies, and environment-specific behavior can evade simple rules.
- Trusted reference operations do not dynamically evaluate the submitted candidate.
- Some logical errors, including accumulation and arithmetic mistakes, are explained in the curated educational examples but cannot be inferred universally.

## Future improvements

Add an OS-enforced isolated execution service with strict CPU, memory, filesystem, and network limits; broaden static rules with precision tests; and allow instructors to add trusted, transparent test fixtures.

## Short demo script

1. Select **Undefined variable**, then analyze. Point out the static NameError finding and its line number.
2. Read the beginner explanation and show the uniquely suggested spelling correction plus the unified diff.
3. Explain that the correction remains unverified unless the relevant checks run; the app never executes the submitted code.
4. Select **Missing colon** and analyze to show a parser-based syntax finding and a conservative block-header suggestion.
5. Select **Incorrect loop logic**. Discuss why syntax passes while `total = number` retains only the final loop item.
6. Show the computed result of `10` from the trusted summation reference operation and read the verification warning aloud: the reference operation ran, not the pasted source.
7. Close by distinguishing compilation, static analysis, and behavioral testing.

## Likely viva questions

1. **What problem does BugWise AI solve?** It helps learners interpret selected Python errors, review conservative corrections, and understand what was actually verified.
2. **What is an AST?** An Abstract Syntax Tree is a structured representation of source code that tools can inspect without running it.
3. **Why use `compile()`?** It asks Python to validate/compile syntax, and in this app the resulting code object is discarded rather than executed.
4. **Does successful compilation mean the program is correct?** No. It only establishes syntax/compilability, not intended behavior.
5. **Does the app run pasted Python?** No. User source is never executed with `exec`, `eval`, or a subprocess.
6. **How does it find a misspelled name?** A symbol-table analysis identifies unresolved global references; the fixer only suggests a unique close match among visible names.
7. **Can static analysis find every NameError?** No. Dynamic globals, imports, and runtime state can change which names exist.
8. **How are corrections verified?** Candidates are compiled, and allowlisted trusted reference operations run on known fixture inputs; the candidate itself is not run.
9. **What is Learning Mode?** It gives a hint and concept explanation first, hiding the correction until the learner asks to reveal it.
10. **Why not just run code in Streamlit?** Arbitrary Python has access to process capabilities; running it in the web app would be unsafe without real OS isolation.
11. **What does the diff show?** A unified text diff between original input and a suggested copy; the original input remains unchanged.
12. **What is the next important improvement?** A separately isolated runner with OS-enforced resource and capability limits, plus trustworthy behavioral tests.
