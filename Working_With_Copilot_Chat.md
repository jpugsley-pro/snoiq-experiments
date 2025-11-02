## 🧩 Working With Copilot Chat After Handoff

### 1. Repo Context Setup

When you open your `snoiq-experiments` folder in VS Code:

1. Ensure **Copilot Chat** is enabled (bottom-right “Copilot” icon → “Enable Chat”).
2. Run:

   ```bash
   pixi install
   ```

   This ensures Copilot’s LSP sees all dependencies.
3. In VS Code, select the Pixi environment as your interpreter:

   ```
   .pixi/envs/default/bin/python
   ```

### 2. Activate Project Context

Start Copilot Chat with:

```
@workspace load context
```

Then type:

```
/explain current project
```

This helps Copilot cache the structure (`src/`, `tests/`, `data/`, etc.).

You can also prime it by referencing:

* `Decision_Sheet.md` → for architecture, milestones, and contracts
* `README.md` → for workflows and folder roles

---

### 3. Daily Commands

| Goal                     | Command / Prompt for Copilot Chat |
| ------------------------ | --------------------------------- |
| **Run all checks**       | `make verify`                     |
| **Run tests**            | `pixi run tests`                  |
| **Open lab**             | `pixi run lab`                    |
| **Start MinIO + MLflow** | `make up`                         |
| **Shut down services**   | `make down`                       |

---

### 4. Working With Copilot Chat

You can issue natural language prompts like:

```
/test explain src/ingestion/mrms.py
/add unit test for open_uscrn_hourly similar to test_ingestion_mrms
/refactor src/physics/snow.py for clarity, keep all tests green
/explain Decision_Sheet.md section 3
/write docstring for open_mrms_qpe following repo conventions
```

or task-driven sequences:

```
@workspace plan “implement adaptive event segmentation v0”
```

Copilot will propose files and edits. Accept or reject inline.

---

### 5. Adding New Experiments

Use:

```bash
pixi run lab
```

Then prototype in `notebooks/`.
When ready, ask Copilot:

```
/promote notebook src/ingestion/hrrr.py
```

and reference `Decision_Sheet.md` section 1-D (“Promotion Policy”).

---

### 6. Before Committing

Use Copilot to check:

```
/lint project
/typecheck src/
```

Then run:

```bash
git add .
git commit -m "feat: promote MRMS and USCRN ingestion per Decision_Sheet"
```