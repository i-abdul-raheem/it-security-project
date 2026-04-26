# Project report: SPN differential lab (`spn-dc`)

This document explains the project in **plain language** so you can understand what it does, why it exists, and how the pieces fit together.

---

## 1. What problem does this solve?

In cryptography, people study **how small changes in the input** to a cipher **show up as changes inside** the cipher. That idea is called **differential cryptanalysis** (at a high level).

This project is a **small laboratory** for one common cipher shape: an **SPN** (Substitution–Permutation Network). You can:

- Describe a toy (or real-style) SPN: how many rounds, how many S-boxes, which S-box tables, and how bits are mixed between rounds.
- Ask: “If the **difference** at the input looks like *this*, what **differences** can appear after the S-boxes and after the linear layer?”
- Add **constraints** (fixed differences, “something nonzero but unknown”, or “these two places must match”).
- In some cases, **list possible differential trails** and rank them by probability.

It is meant for **learning and experimentation**, not for attacking real systems by itself.

---

## 2. A few words you need

**S-box (substitution box)**  
A lookup table that scrambles a small block of bits (often 4 bits → 4 bits). It must be a **permutation** in this code (each output value appears exactly once).

**Round**  
One repetition of: apply S-boxes in parallel on slices of the state, then apply a **linear mixing** step on all those bits together.

**Difference**  
Here, “difference” almost always means **XOR**: two values differ in the bits where XOR is 1. We write something like \(\Delta x = x \oplus x'\).

**DDT (Difference Distribution Table)**  
For one S-box \(S\), the table answers:  
“If the **input** XOR-difference is \(a\), how often does the **output** XOR-difference equal \(b\)?”  
That count (for all pairs \((a,b)\)) is the DDT. Large counts mean “this propagation is **common**,” which matters in attacks and in design.

**P-layer (linear layer)**  
After the S-boxes, all bits are mixed with a **fixed, invertible linear map over GF(2)**—in practice, multiply the bit-vector by a **binary matrix** (each row is XOR of selected input bits). “Invertible” means every output pattern comes from exactly one input pattern, so no information is lost at that step.

---

## 3. What the program actually models

Rough picture of **one round** (keys are ignored for difference tracking in the usual way):

1. **Before S-boxes:** you have one small XOR-difference per S-box “slice.”
2. **Through each S-box:** each slice follows the **DDT rules** (many output differences may be possible for one input difference).
3. **Through P:** the **whole** block of bits is transformed by the matrix; differences follow the **same** linear map.

The code repeats that for as many **rounds** as you configured.

---

## 4. How the code is organized (simple map)

| Area | Role |
|------|------|
| `spn_dc/sbox.py` | Stores an S-box table; builds the **DDT** and related lookups. |
| `spn_dc/linear.py` | **Binary matrix** over GF(2): apply to a bit-vector, check invertibility, inverse. |
| `spn_dc/spn.py` | Describes **one round**: list of S-boxes + one P matrix; and **full cipher** = repeat that round shape. |
| `spn_dc/difference.py` | **Kinds of constraints** on one slice: “any value,” “fixed value,” “nonzero but unknown,” or a **small set** of values after narrowing. |
| `spn_dc/propagation.py` | Pushes those constraints **forward** through S-boxes and P; can apply **equality** between positions; chains rounds by turning output sets into inputs for the next round. |
| `spn_dc/paths.py` | **Enumerates trails** (branches over S-box outputs) and assigns a **trail probability** from DDT counts. |
| `spn_dc/session.py` | **Working session**: remembers your cipher, constraints, optional saved paths; can **save/load** a JSON file for the CLI. |
| `spn_dc/cli.py` | **Command-line** interface (`spn-dc …`) matching the lab workflow. |
| `spn_dc/streamlit_app.py` | **Web UI** (Streamlit) for the same ideas with forms and tables. |
| `tests/` | Short automated checks that core math and session behavior work. |

---

## 5. How you can use it

**Command line (`spn-dc`)**  
Create a cipher, set S-boxes and P, print DDTs, propagate a difference, check constraints, sometimes list paths. State can be stored in `.spn_dc_state.json` so the next command remembers your setup (unless you turn that off).

**Python import**  
You can build the same objects (`SBox`, `BinaryMatrix`, `SPNRoundSpec`, …) or call the **session helpers** from `spn_dc.session` / `spn_dc` package exports.

**Web UI (`spn-dc-ui` or `streamlit run …`)**  
Same concepts with tabs: edit boxes, buttons, and tables. By default the UI avoids writing the CLI state file.

---

## 6. Important limitations (honest list)

- **State size:** when many values remain possible at each S-box, the number of combinations can grow **exponentially**. The code is honest about that: path search and some propagation steps are only meant for **small** examples (educational sizes).
- **Keys:** subkeys are not modeled in depth; the focus is on **difference propagation** through the nonlinear and linear structure.
- **Other ciphers:** Feistel networks and others are **not** implemented yet; the structure is SPN-shaped, though the ideas (DDT, linear layer) transfer partly to other designs.

---

## 7. One-sentence summary

**This project is a hands-on toolkit to see how XOR-differences flow through a configurable SPN—using DDTs, a linear bit-mixer, constraints, and optional trail search—through a CLI, Python API, and a simple web UI.**

If you want this report turned into slides or a shorter handout, say which format and length you prefer.
