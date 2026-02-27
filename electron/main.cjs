/* electron/main.cjs */
const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const fs = require("fs");

let mainWindow;
let apiProc = null;
let runnerProc = null;

const DEV_URL = "http://localhost:5173";

// Packaged app:
// main.cjs => <resources>/app.asar/electron/main.cjs
// UI => <resources>/app.asar/frontend/dist/index.html  (because build.files includes frontend/dist/**)
const PROD_INDEX = path.join(__dirname, "..", "frontend", "dist", "index.html");

// -------------------------
// Backend (API) config
// -------------------------
function getApiPort() {
  const raw = String(process.env.SALESTROOPZ_API_PORT ?? "8715").trim();
  const digits = raw.replace(/[^\d]/g, "");
  return digits || "8715";
}

const API_PORT = getApiPort();
const API_HEALTH_URL = `http://127.0.0.1:${API_PORT}/health`;

// -------------------------
// userData paths (CRITICAL)
// -------------------------
function ensureDir(p) {
  try {
    fs.mkdirSync(p, { recursive: true });
  } catch {}
}

function getUserDataEnv() {
  // Electron userData is writable. Program Files is not.
  const ud = app.getPath("userData"); // e.g. C:\Users\X\AppData\Roaming\Salestroopz Desktop
  const root = path.join(ud, "salestroopz");
  ensureDir(root);

  return {
    SALESTROOPZ_USERDATA_DIR: root,
    SQLITE_DB_FILE: path.join(root, "salestroopz.db"),
    TOKEN_CACHE_PATH: path.join(root, "token_cache.json"),
    SALESTROOPZ_API_PORT: API_PORT,
    VITE_AGENT_URL: `http://127.0.0.1:${API_PORT}`,
  };
}

// -------------------------
// Helpers
// -------------------------
function waitForHttpOk(url, timeoutMs = 20000) {
  const start = Date.now();

  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      http
        .get(url, (res) => {
          const ok = res.statusCode && res.statusCode >= 200 && res.statusCode < 400;
          res.resume();
          if (ok) return resolve(true);
          retry();
        })
        .on("error", retry);
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

function isHttpOk(url) {
  return new Promise((resolve) => {
    http
      .get(url, (res) => {
        const ok = res.statusCode && res.statusCode >= 200 && res.statusCode < 400;
        res.resume();
        resolve(ok);
      })
      .on("error", () => resolve(false));
  });
}

function getRepoRoot() {
  // dev: __dirname = <repo>/electron => repo root is ..
  // packaged: __dirname = <resources>/app.asar/electron => app.asar is ..
  return path.join(__dirname, "..");
}

function pythonScriptPath(scriptName) {
  // ✅ dev scripts live at <repo>/agent/<scriptName>
  return path.join(getRepoRoot(), "agent", scriptName);
}

function binPath(relPath) {
  // In packaged mode, process.resourcesPath points to <InstallDir>\resources
  return path.join(process.resourcesPath, "bin", relPath);
}

function spawnProcess(command, args, name, extraEnv = {}) {
  const child = spawn(command, args, {
    windowsHide: true,
    stdio: "inherit",
    env: {
      ...process.env,
      ...extraEnv,
    },
  });

  child.on("exit", (code) => {
    if (app.isQuiting) return;
    console.log(`[${name}] exited (${code}).`);

    if (name.includes("API")) apiProc = null;
    if (name.includes("RUNNER")) runnerProc = null;

    setTimeout(() => startBackendProcesses(), 1200);
  });

  return child;
}

async function startBackendProcesses() {
  const apiAlreadyUp = await isHttpOk(API_HEALTH_URL);
  const isDev = !app.isPackaged;
  const userEnv = getUserDataEnv();

  if (isDev) {
    const py = process.env.SALESTROOPZ_PYTHON || "python";

    if (!apiAlreadyUp && !apiProc) {
      console.log(`[API_DEV] starting on port ${API_PORT}...`);
      apiProc = spawnProcess(py, ["-u", pythonScriptPath("api_main.py")], "API_DEV", userEnv);
    }

    if (!runnerProc) {
      console.log("[RUNNER_DEV] starting...");
      runnerProc = spawnProcess(py, ["-u", pythonScriptPath("worker_main.py")], "RUNNER_DEV", userEnv);
    }
  } else {
    // ✅ packaged mode uses foldered PyInstaller outputs copied by extraResources:
    // resources/bin/salestroopz_api/salestroopz_api.exe
    // resources/bin/salestroopz_runner/salestroopz_runner.exe
    if (!apiAlreadyUp && !apiProc) {
      console.log(`[API] starting embedded salestroopz_api on port ${API_PORT}...`);
      apiProc = spawnProcess(
        binPath(path.join("salestroopz_api", "salestroopz_api.exe")),
        [],
        "API",
        userEnv
      );
    }

    if (!runnerProc) {
      console.log("[RUNNER] starting embedded salestroopz_runner...");
      runnerProc = spawnProcess(
        binPath(path.join("salestroopz_runner", "salestroopz_runner.exe")),
        [],
        "RUNNER",
        userEnv
      );
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

// -------------------------
// Window
// -------------------------
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

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  await startBackendProcesses();

  try {
    await waitForHttpOk(API_HEALTH_URL, 25000);
  } catch (err) {
    await mainWindow.loadURL(
      `data:text/html,
       <h2>Backend not ready</h2>
       <p>Salestroopz API did not start on <code>${API_HEALTH_URL}</code></p>
       <pre>${String(err).replace(/</g, "&lt;")}</pre>`
    );
    return;
  }

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
         <p>Start it with: <code>npm run dev:electron</code></p>
         <pre>${String(err).replace(/</g, "&lt;")}</pre>`
      );
    }
  } else {
    await mainWindow.loadFile(PROD_INDEX);
  }
}

// -------------------------
// App lifecycle
// -------------------------
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
  if (process.platform !== "darwin") {
    app.isQuiting = true;
    stopBackendProcesses();
    app.quit();
  }
});
