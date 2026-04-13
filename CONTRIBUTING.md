# Contributing Guide

## Workflow

This project uses a simple **feature-branch** workflow:

```
main          ← stable, instructor-reviewed code only
develop       ← integration branch
feature/xxx   ← one branch per student task
```

### Step-by-step

```bash
# 1. Clone the repo
git clone https://github.com/<org>/filter-toolbox.git
cd filter-toolbox

# 2. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Create your feature branch from develop
git checkout develop
git pull
git checkout -b feature/your-name-task
# e.g. feature/alice-butterworth-tf

# 4. Implement your entry point(s) in filter_design.py
# See the docstrings for the exact signature and return types

# 5. Run the app to test manually
python main.py

# 6. Commit and push
git add filter_design.py
git commit -m "feat: implement compute_transfer_function for Butterworth"
git push origin feature/your-name-task

# 7. Open a Pull Request → develop on GitHub
```

## Commit message convention

```
feat:  new functionality
fix:   bug fix
test:  adding or updating tests
docs:  documentation only
style: formatting, no logic change
```

## Student entry points

All student code goes in **`filter_design.py`** only.  
Do **not** modify `mainwindow.py`, `main.py`, or any file in `resources/`.

| Function | Owner (assign in GitHub) |
|---|---|
| `compute_minimum_order` | |
| `compute_transfer_function` | |
| `factored_biquads` | |
| `compute_frequency_response` | |
| `synthesise_sallen_key` | |
| `synthesise_tow_thomas` | |
| `synthesise_deliyannis` | |
| `generate_spice_netlist` | |
| `run_spice_simulation` | |

## Pull Request checklist

Before opening a PR, make sure:

- [ ] The GUI launches without errors (`python main.py`)
- [ ] Your function returns the documented type (check the docstring)
- [ ] No new imports added outside the standard library / `requirements.txt`
- [ ] No changes to files outside `filter_design.py`
- [ ] Branch is up to date with `develop` (`git pull origin develop`)
