⬇️ Download
The easiest way to get started is to download the latest installer from the website:
→ Download at salestroopz.com
Or grab the latest release directly from GitHub Releases.

What is Salestroopz?
Salestroopz Desktop is an autonomous Sales Development Representative (SDR) agent that runs 100% locally on your machine. It uses a local LLM via Ollama to research prospects, craft personalised outreach campaigns, and send emails — all without your data ever touching a third-party server.
Key principles:

🔒 Local-first — your leads, emails, and AI model stay on your machine
⚡ Autonomous — set your ICP and let the agent run campaigns end-to-end
🔌 Your email — connects to Microsoft 365 or any SMTP provider, nothing in between
🆓 Free & open source — MIT licensed, forever


Features

🎯 Define your Ideal Customer Profile (ICP) and offering once
🤖 AI-generated, personalised outreach sequences
📧 Send via Microsoft 365 or SMTP — no middleman
📊 Campaign orchestrator to track and manage outreach
🧠 Powered by Ollama — runs local LLMs like Llama 3, Mistral, and more
🖥️ Clean desktop UI built with Electron + Vite + React


Prerequisites
Before running from source, make sure you have:
RequirementVersionNotesNode.jsv18+For the Electron frontendPython3.10+For the agent backendOllamaLatestMust be running locallyMicrosoft 365 or SMTP—For sending emails

Getting Started (from source)
bash# 1. Clone the repo
git clone https://github.com/salestroopz/salestroopz-desktop.git
cd salestroopz-desktop

# 2. Install Node dependencies
npm install

# 3. Install Python dependencies
cd agent && pip install -r requirements.txt && cd ..

# 4. Make sure Ollama is running
ollama serve

# 5. Start the app in dev mode
npm run dev:electron

Building for Windows
bash# Build the full Windows installer
npm run dist:win
Output will be in the release/ folder as an .exe NSIS installer.

Project Structure
salestroopz-desktop/
├── electron/        # Electron main process
├── frontend/        # Vite + React UI
├── agent/           # Python SDR agent & API
├── build/           # App icons & electron-builder assets
└── release/         # Built installers (gitignored)

Contributing
Contributions are welcome! Please read CONTRIBUTING.md before submitting a PR.

Fork the repo
Create a feature branch: git checkout -b feature/my-feature
Commit your changes: git commit -m 'Add my feature'
Push and open a Pull Request

For bugs and feature requests, please open an issue.

Roadmap

 macOS support
 Linux support
 Multi-account email support
 CRM integrations (HubSpot, Salesforce)
 Campaign analytics dashboard
 Custom LLM model selection UI


License
MIT © Haricharan Mylaraiah
