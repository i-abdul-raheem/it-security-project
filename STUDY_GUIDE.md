# SPN Differential Lab — Study Guide & Learning Roadmap

**Project:** `spn-dc` (IT Security — Differential Cryptanalysis)  
**Goal:** Pass the subject and finish the project without a deep dive into research-level cryptanalysis.

---

## 1. Topics covered by this project

### A. Crypto basics (minimum)

1. Block ciphers vs stream ciphers  
2. Confusion and diffusion (Shannon)  
3. Rounds, state, block size  
4. XOR as “difference” in binary ciphers  
5. Why we track **differences**, not full plaintext/ciphertext  

### B. SPN structure (core)

6. Substitution–Permutation Network (SPN) layout  
7. Parallel S-boxes (splitting the block into slices)  
8. S-box as a **permutation table** (lookup, bijective)  
9. Linear / permutation layer after S-boxes (**P-layer**)  
10. One round = S-box layer → P-layer (keys often ignored in difference analysis)  
11. Multi-round repetition  

### C. Differential cryptanalysis (exam-level)

12. Input difference Δx and output difference Δy  
13. Differential trail / characteristic (path through rounds)  
14. **DDT** (Difference Distribution Table)  
15. DDT formula: count pairs where S(x ⊕ a) ⊕ S(x) = b  
16. DDT probability ≈ count / 2^n for an n-bit S-box  
17. Forward propagation (input diff → possible output diffs)  
18. Backward / inverse view (fixed output → possible inputs)  
19. “Strong” vs “weak” differentials (high vs low DDT counts)  

### D. Linear layer math (just enough)

20. **GF(2)** / binary arithmetic (add = XOR)  
21. **Binary matrix** as bit mixer  
22. **Bijective** = invertible = full rank (no collapsing)  
23. Differences through P: same linear map as data (for XOR differences)  

### E. Constraints (project features)

24. Fixed difference at a position  
25. Abstract / nonzero-unknown difference  
26. Equality constraints (two S-box inputs must match)  
27. Conflict detection (empty possibility set = impossible)  

### F. Software / project (finish & demo)

28. Python package layout (`spn_dc/`)  
29. CLI commands (`spn-dc`, session file)  
30. Streamlit UI (tabs, propagate, animation, bit diagram)  
31. Running tests (`pytest`)  
32. Short report / demo for submission  

---

## 2. Learning roadmap (~1–2 weeks, shallow)

**Objective:** Understand enough to explain the project, run a demo, and answer viva questions.

### Phase 1 — Big picture (Day 1–2, ~3 hours)

| Learn | Stop when you can… |
|-------|---------------------|
| Block cipher + SPN diagram | Draw one round on paper: S-boxes → P |
| XOR difference | Say “difference = XOR of two related inputs” |
| What DDT is for | Say “DDT tells which output diffs are likely for a given input diff” |

**Skip:** full AES, Feistel details, key schedules, real attacks on ciphers.  
**Read:** `PROJECT_REPORT.md` sections 1–3.

### Phase 2 — S-box + DDT (Day 3–4, ~4 hours)

| Learn | Stop when you can… |
|-------|---------------------|
| S-box as permutation table | Give an example 4-bit table |
| Build / read one DDT row | For input diff a, list possible b with count > 0 |
| DDT probability | Compute prob = count/16 for 4-bit box |

**Practice:** UI → DDT tab; CLI: `compute_ddt --sbox 0`.

**Exam phrases:**

- Higher DDT count → more likely differential  
- Row for Δx = 0 is always concentrated at Δy = 0  

### Phase 3 — P-layer + bijective matrix (Day 5, ~2 hours)

| Learn | Stop when you can… |
|-------|---------------------|
| Binary matrix over GF(2) | “Each output bit is XOR of some input bits” |
| Bijective | “Invertible; every output pattern has one preimage” |
| Differences through P | “P acts linearly on differences the same way as on data” |

**Practice:** UI → S-boxes & P; Bit wiring tab for pins and P connections.  
**Skip:** Gaussian elimination proofs, optimal P design.

### Phase 4 — Propagation & constraints (Day 6–7, ~3 hours)

| Learn | Stop when you can… |
|-------|---------------------|
| One-round flow | before S-box → after S-box → after P |
| Multi-round | Output of P becomes next round’s S-box input |
| Constraints | Fixed / abstract / equal; check = consistent or not |
| Explosion of possibilities | Why small examples only |

**Practice:**

1. Create cipher: 2 rounds, 2 S-boxes, 4-bit  
2. Propagate `0x11`  
3. Play animation + Bit wiring  
4. Add conflicting equality → Check constraints fails  

### Phase 5 — Trails & paths (Day 8, ~2 hours)

| Learn | Stop when you can… |
|-------|---------------------|
| Differential trail | One choice of output diff per S-box per round |
| Trail probability | Product of per-S-box DDT probabilities |
| generate_paths / filter | List likely trails above threshold |

**Practice:** Paths tab → generate → filter → animate one trail.

### Phase 6 — Finish for submission (Day 9–10, ~4 hours)

| Task | Deliverable |
|------|-------------|
| Pick one toy cipher | e.g. 2×4-bit S-boxes, 3 rounds |
| One worked example | Input Δ, 1–2 rounds propagation (screenshot) |
| One DDT screenshot | Comment on one “strong” cell |
| One constraint example | Equal or fixed diff that works / fails |
| Short write-up (1–2 pages) | Problem, design, DDT, propagation, demo, limits |
| Optional | `pytest` green + short demo video |

---

## 3. Viva cheat sheet

1. **SPN:** parallel S-boxes, then linear bit mixing, repeated for R rounds.  
2. **Difference:** XOR; we study how Δ propagates; keys simplified away.  
3. **DDT:** DDT[a][b] = number of x with S(x⊕a)⊕S(x) = b.  
4. **Bijective P:** invertible binary matrix; differences follow same map.  
5. **This tool:** configures SPN, DDT, propagates Δ, constraints, optional paths.  
6. **Limitation:** exponential blow-up; educational sizes only; not a full attack tool.

---

## 4. Must know vs can ignore

| Must know (pass) | Can ignore (for now) |
|------------------|----------------------|
| SPN round structure | Feistel, ARX ciphers |
| XOR difference | Modular addition differentials |
| DDT meaning + one example | Optimal S-box design theory |
| Binary matrix P-layer | MDS matrices, coding theory |
| Bijective = invertible | Formal attack proofs |
| CLI/UI demo flow | Attacks on real AES |
| Project limitations | Key schedule proofs |

---

## 5. Fastest study order

```
Day 1–2:  SPN + XOR differences
Day 3–4:  S-box + DDT (UI DDT tab)
Day 5:    P-layer + bijective matrix (Bit wiring tab)
Day 6–7:  Propagation + constraints
Day 8:    Paths (good for report)
Day 9–10: Write report + rehearse demo
```

---

## 6. Five-minute demo script

1. Sidebar: **2 rounds, 2 S-boxes, 4-bit** → Create cipher  
2. **DDT** tab: show S-box 0; mention one high-probability entry  
3. **Propagate** `0x11` → Play animation  
4. **Bit wiring:** scrub steps; point at S0, S1, P wires  
5. **Input & constraints:** fix one input diff → propagate again  
6. **Paths:** generate trails, filter, show strongest trail  
7. Close: “Tool models difference propagation; real ciphers need larger analysis and key handling.”

---

## 7. Key equations (exam)

**Difference (XOR):**

```
Δx = x ⊕ x'
```

**DDT entry:**

```
DDT[a][b] = |{ x : S(x ⊕ a) ⊕ S(x) = b }|
```

**DDT probability (n-bit S-box, 2^n inputs):**

```
P(b | a) ≈ DDT[a][b] / 2^n
```

**P-layer (linear over GF(2)):**

```
y = M · x   (addition = XOR, multiplication = AND)
```

**Bijective P:** matrix M is invertible (full rank over GF(2)).

---

*Generated for the `spn-dc` project — differential propagation lab for configurable SPNs.*
