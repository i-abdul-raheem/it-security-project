# SPN Differential Lab

This project is an interactive tool for studying differential cryptanalysis in Substitution–Permutation Networks (SPNs). Users can configure cipher rounds, S-boxes, and invertible XOR-based P-layers, inspect difference distribution tables (DDTs), propagate input differences, and explore differential trails and their probabilities.

The Streamlit interface provides animated propagation, bit-level wiring diagrams, a complete vertical network view, constraint checking, and configuration and diagram exports.

## Supervisors

- Prof. Dr. Elmar Tischhauser [https://www.uni-marburg.de/en/fb12/research-groups/itsecurity/elmar-tischhauser]
- Alexander Bille [https://www.uni-marburg.de/en/fb12/research-groups/itsecurity/alexander-bille]

## Running the Project Locally

You can run the updated project on your laptop by following these steps from the project's root directory:

### Step 1: Create a Python virtual environment

```bash
python -m venv .venv
```

This creates an isolated Python environment for the project, preventing conflicts with other installed packages.

### Step 2: Activate the virtual environment

On Windows (PowerShell):
```bash
.venv\Scripts\Activate.ps1
```

On Linux/macOS:
```bash
source .venv/bin/activate
```

This ensures that the project's dependencies are installed and executed within the virtual environment.

### Step 3: Install the project dependencies

```bash
pip install -e ".[ui]"
```

This installs the project in editable mode, including the dependencies required for the user interface.

### Step 4: Launch the Streamlit application

```bash
streamlit run spn_dc/streamlit_app.py
```

This starts the application locally. You can then access the interface through the URL displayed in your terminal (typically `http://localhost:8501`).
