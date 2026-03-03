# Contributing to Salestroopz Desktop

First off — thank you! 🎉 Whether you're fixing a bug, improving docs, or proposing a new feature, every contribution makes Salestroopz better for everyone.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Coding Guidelines](#coding-guidelines)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## Code of Conduct

This project follows a simple rule: **be kind**. Treat everyone with respect. Harassment, discrimination, or toxic behaviour of any kind will not be tolerated.

---

## How Can I Contribute?

### 🐛 Fix a Bug
Browse [open issues](https://github.com/salestroopz/salestroopz-desktop/issues) tagged `bug`. Comment on the issue to let others know you're working on it.

### ✨ Add a Feature
Check the [roadmap in README.md](README.md#roadmap) or open a new issue tagged `enhancement` to discuss your idea before building it. This avoids duplicate work.

### 📝 Improve Documentation
Spotted something unclear in the README or inline comments? PRs for docs are always welcome and quick to merge.

### 🧪 Write Tests
The project needs more test coverage. If you enjoy writing tests, this is a great way to contribute.

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/salestroopz-desktop.git
cd salestroopz-desktop

# 2. Install Node dependencies
npm install

# 3. Install Python dependencies
cd agent && pip install -r requirements.txt && cd ..

# 4. Start Ollama
ollama serve

# 5. Run in dev mode
npm run dev:electron
```

> **Note:** You'll need Microsoft 365 or SMTP credentials configured in Settings to test email sending.

---

## Submitting a Pull Request

1. **Fork** the repo and create your branch from `main`:
   ```bash
   git checkout -b fix/your-bug-name
   # or
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** — keep commits focused and atomic.

3. **Test your changes** locally with `npm run dev:electron`.

4. **Commit** with a clear message:
   ```bash
   git commit -m "fix: correct email sender field validation"
   git commit -m "feat: add campaign pause/resume support"
   ```
   We loosely follow [Conventional Commits](https://www.conventionalcommits.org/).

5. **Push** your branch and open a Pull Request against `main`.

6. Fill in the PR template — describe what changed and why.

A maintainer will review your PR within a few days. We may request changes or ask questions before merging.

---

## Coding Guidelines

### Frontend (Electron + Vite + React)
- Use functional React components with hooks
- Keep components small and single-purpose
- Avoid inline styles — use Tailwind or existing CSS classes

### Backend (Python Agent)
- Follow PEP 8
- Add docstrings to new functions and classes
- Avoid adding new dependencies unless necessary — discuss in the issue first

### General
- Do not commit `.env` files, secrets, or credentials — ever
- Keep `node_modules/`, `dist/`, and `release/` out of commits (already in `.gitignore`)
- Comment your code where intent isn't obvious

---

## Reporting Bugs

Open an issue using the **Bug Report** template and include:

- Your OS and version
- Salestroopz Desktop version
- Steps to reproduce
- What you expected vs what happened
- Any relevant logs from the Electron console (`View → Toggle Developer Tools`)

---

## Requesting Features

Open an issue using the **Feature Request** template. Describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

---

## Questions?

Open a [GitHub Discussion](https://github.com/salestroopz/salestroopz-desktop/discussions) or reach out via [salestroopz.com](https://salestroopz.com).

---

*Thanks again for contributing. You're helping build the future of local-first sales automation.* 🚀
