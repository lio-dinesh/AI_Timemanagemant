# Contributing to AI Time Management (AI TimeSync)

First off, thank you for considering contributing to AI Time Management! It's people like you that make this an exceptional, community-driven tool.

---

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## How Can I Contribute?

### Reporting Bugs
- Ensure the bug was not already reported by searching on GitHub under [Issues](https://github.com/lio-dinesh/AI_Timemanagemant/issues).
- If you're unable to find an open issue addressing the problem, open a new one using the **Bug report** template.
- Include a clear title and description, step-by-step reproduction instructions, and system information.

### Suggesting Enhancements
- Open an issue using the **Feature request** template.
- Provide a clear and detailed explanation of the proposed feature and why it would be beneficial.

### Pull Requests
1. **Fork the repository** and clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/AI_Timemanagemant.git
   cd AI_Timemanagemant
   ```
2. **Create a topic branch** from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
3. **Set up the virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Make your changes** and write tests for any new functionality.
5. **Run the test suite**:
   ```bash
   python manage.py test apps --settings=config.settings.development
   ```
6. **Ensure migration integrity**:
   ```bash
   python manage.py makemigrations --check --dry-run
   ```
7. **Commit with conventional messages**:
   - `feat: add new feature`
   - `fix: resolve bug`
   - `docs: update documentation`
   - `style: formatting and css tweaks`
8. **Push to your fork** and submit a Pull Request targeting `main`.

---

## Code Style Guidelines
- **Python**: Follow PEP 8 guidelines. Keep code clean, explicit, and well-typed where appropriate.
- **Django**: Follow standard Django conventions (apps structure, services pattern, fat models / lean views).
- **CSS / UI**: Use modern vanilla CSS and Bootstrap 5 tokens. Avoid inline styles wherever possible.
