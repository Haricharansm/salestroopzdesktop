// electron/main.js
// Clean replacement file: fixes Windows port whitespace, defaults to venv python in dev,
// and shows backend logs in dev (so you can see why API/Runner exits).

const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

let mainWindow;

// -------------------------
// Frontend dev/prod
// -------------------------
const DEV_URL = "http://localhost:5173";
const PROD_INDEX = path.join(__dirname, "..", "frontend", "dist", "index.html");

// -------------------------
// Backend (API) config
// -------------------------
function getApiPort() {
  // sanitize because Windows env vars can include weird whitespace
  const raw = String(process.env.SALESTROOPZ_API_PORT ?? "8715").trim();

  // allow only digits
  const digits = raw.replace(/[^\d]/g, "");
  return digits || "8715";
}

const API_PORT = getApiPort();
const API_HEALTH_URL = `http://127.0.0.1:${API_PORT}/health`;

// Child processes
let apiProc = null;
let runnerProc = null;

function waitForHttpOk(url, timeoutMs = 20000) {
  const start = Date.now();

  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      try {
        http
          .get(url, (res) => {
            if (res.statusCode && res.statusCode >= 200 && res.statusCode < 400) {
              res.resume();
              return resolve(true);
            }
            res.resume();
            retry();
          })
          .on("error", retry);
      } catch (e) {
        // catches TypeError: Invalid URL (bad url string)
        return reject(e);
      }
    };

    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error(`Server not ready at ${url} within ${timeoutMs}ms`));
      }
      setTimeout(tryOnce, 300);
    };

    tryOnce();
  });
}

function getRepoRoot() {
  // electron/ is one level below repo root
  return path.join(__dirname, "..");
}

function binPath(exeName) {
  // Packaged: resources/bin/<exeName>
  return path.join(process.resourcesPath, "bin", exeName);
}

function pythonScriptPath(scriptName) {
  return path.join(getRepoRoot(), "agent", scriptName);
}

function getDevPythonPath() {
  // Prefer explicit override, else default to repo venv python (Windows)
  if (process.env.SALESTROOPZ_PYTHON && String(process.env.SALESTROOPZ_PYTHON).trim()) {
    return String(process.env.SALESTROOPZ_PYTHON).trim();
  }

  // Most common path for your setup:
  // <repoRoot>/agent/venv/Scripts/python.exe
  const venvPy = path.join(getRepoRoot(), "agent", "venv", "Scripts", "python.exe");
  return venvPy;
}

function spawnProcess(command, args, name) {
  const isDev = !app.isPackaged;

  const child = spawn(command, args, {
    windowsHide: true,
    // In dev: show logs so you can see real errors.
    // In prod: keep quiet (or change to "inherit" if you want logs in packaged too).
    stdio: isDev ? "inherit" : "ignore",
    env: {
      ...process.env,
      SALESTROOPZ_API_PORT: API_PORT,
    },
  });

  child.on("exit", (code) => {
    if (!app.isQuiting) {
      console.log(`[${name}] exited (${code}). restarting...`);
      apiProc = null;
      runnerProc = null;
      setTimeout(() => startBackendProcesses(), 1200);
    }
  });

  return child;
}

function startBackendProcesses() {
  // prevent double-spawns
  if (apiProc && runnerProc) return;

  const isDev = !app.isPackaged;

  if (isDev) {
    const py = getDevPythonPath();

    if (!apiProc) {
      apiProc = spawnProcess(py, ["-u", pythonScriptPath("api_main.py")], "API_DEV");
    }
    if (!runnerProc) {
      runnerProc = spawnProcess(py, ["-u", pythonScriptPath("worker_main.py")], "RUNNER_DEV");
    }
  } else {
    if (!apiProc) {
      apiProc = spawnProcess(binPath("salestroopz_api.exe"), [], "API");
    }
    if (!runnerProc) {
      runnerProc = spawnProcess(binPath("salestroopz_runner.exe"), [], "RUNNER");
    }
  }
}

function stopBackendProcesses() {
  try {
    apiProc && apiProc.kill();
  } catch {}
  try {
    runnerProc && runnerProc.kill();
  } catch {}
  apiProc = null;
  runnerProc = null;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "Salestroopz Desktop",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Open external links in default browser, not inside Electron window
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  // Start backend processes first (API + Runner)
 await startBackendProcesses();

  // Wait for API to be ready
  try {
    await waitForHttpOk(API_HEALTH_URL, 25000);
  } catch (err) {
    await mainWindow.loadURL(
      `data:text/html,
       <h2>Backend not ready</h2>
       <p>Salestroopz API did not start on <code>${API_HEALTH_URL}</code></p>
       <p>Try restarting the app. If in dev mode, ensure python deps are installed.</p>
       <pre>${String(err).replace(/</g, "&lt;")}</pre>`
    );
    return;
  }

  // Now load frontend
  const isDev = !app.isPackaged;

  if (isDev) {
    try {
      await waitForHttpOk(DEV_URL, 15000);
      await mainWindow.loadURL(DEV_URL);
      mainWindow.webContents.openDevTools({ mode: "detach" });
    } catch (err) {
      await mainWindow.loadURL(
        `data:text/html,
         <h2>Vite dev server not running</h2>
         <p>Start it with: <code>npm run dev</code></p>
         <pre>${String(err).replace(/</g, "&lt;")}</pre>`
      );
    }
  } else {
    await mainWindow.loadFile(PROD_INDEX);
  }
}

app.whenReady().then(async () => {
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on("before-quit", () => {
  app.isQuiting = true;
  stopBackendProcesses();
});

app.on("window-all-closed", () => {
  // On Windows/Linux we quit and stop child processes
  if (process.platform !== "darwin") {
    app.isQuiting = true;
    stopBackendProcesses();
    app.quit();
  }
});
