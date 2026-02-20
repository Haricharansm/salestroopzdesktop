/* electron/main.cjs */
const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

let mainWindow;
let apiProc = null;
let runnerProc = null;

const DEV_URL = "http://localhost:5173";
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
  return path.join(__dirname, "..");
}

function pythonScriptPath(scriptName) {
  return path.join(getRepoRoot(), "agent", scriptName);
}

function binPath(exeName) {
  return path.join(process.resourcesPath, "bin", exeName);
}

function spawnProcess(command, args, name) {
  const child = spawn(command, args, {
    windowsHide: true,
    stdio: "inherit", // important: lets you SEE real errors (like missing dotenv)
    env: {
      ...process.env,
      SALESTROOPZ_API_PORT: API_PORT,
    },
  });

  child.on("exit", (code) => {
    if (app.isQuiting) return;
    console.log(`[${name}] exited (${code}).`);

    // Mark the right proc as dead
    if (name.includes("API")) apiProc = null;
    if (name.includes("RUNNER")) runnerProc = null;

    // Do NOT restart aggressively in dev if the port is occupied by another instance.
    // We let startBackendProcesses() decide if it needs to spawn.
    setTimeout(() => startBackendProcesses(), 1200);
  });

  return child;
}

async function startBackendProcesses() {
  // If API already responding, do NOT start another instance (prevents 10048 bind loop)
  const apiAlreadyUp = await isHttpOk(API_HEALTH_URL);

  const isDev = !app.isPackaged;

  if (isDev) {
    const py = process.env.SALESTROOPZ_PYTHON || "python";

    // Only spawn API if not already up
    if (!apiAlreadyUp && !apiProc) {
      console.log(`[API_DEV] starting on port ${API_PORT}...`);
      apiProc = spawnProcess(py, ["-u", pythonScriptPath("api_main.py")], "API_DEV");
    }

    // Runner can run even if API is already up (but avoid duplicates)
    if (!runnerProc) {
      console.log("[RUNNER_DEV] starting...");
      runnerProc = spawnProcess(py, ["-u", pythonScriptPath("worker_main.py")], "RUNNER_DEV");
    }
  } else {
    // Packaged mode uses embedded exe(s) in resources/bin
    if (!apiProc) apiProc = spawnProcess(binPath("salestroopz_api.exe"), [], "API");
    if (!runnerProc) runnerProc = spawnProcess(binPath("salestroopz_runner.exe"), [], "RUNNER");
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

  // start backend (or detect already running)
  await startBackendProcesses();

  // Wait until API is reachable (whether we spawned it or it was already running)
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
         <p>Start it with: <code>npm run dev:ui</code></p>
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
