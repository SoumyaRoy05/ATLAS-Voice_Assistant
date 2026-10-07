const statusElement = document.querySelector("#status");
const logElement = document.querySelector("#logs");
const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const clearButton = document.querySelector("#clear");

function setStatus(status) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  statusElement.textContent = label;
  statusElement.className = `status ${status}`;
}

function appendLog(message) {
  logElement.textContent += `${message}\n`;
  logElement.scrollTop = logElement.scrollHeight;
}

function updateControls(running) {
  startButton.disabled = running;
  stopButton.disabled = !running;
}

async function request(path, method) {
  const response = await fetch(path, { method });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function refreshStatus() {
  const state = await request("/api/status", "GET");
  setStatus(state.status);
  updateControls(state.running);
  if (!logElement.textContent && state.logs.length) {
    logElement.textContent = `${state.logs.join("\n")}\n`;
  }
}

function connectLogs() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/logs`);
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.status) setStatus(data.status);
    if (data.type === "snapshot") {
      logElement.textContent = `${data.logs.join("\n")}\n`;
      updateControls(data.running);
    } else if (data.message) {
      appendLog(data.message);
      refreshStatus().catch(console.error);
    }
  };
  socket.onclose = () => setTimeout(connectLogs, 1000);
}

startButton.addEventListener("click", async () => {
  try {
    const state = await request("/api/start", "POST");
    setStatus(state.status);
    updateControls(state.running);
  } catch (error) {
    setStatus("error");
    appendLog(`[APP] ${error.message}`);
  }
});

stopButton.addEventListener("click", async () => {
  try {
    const state = await request("/api/stop", "POST");
    setStatus(state.status);
    updateControls(state.running);
  } catch (error) {
    setStatus("error");
    appendLog(`[APP] ${error.message}`);
  }
});

clearButton.addEventListener("click", () => {
  logElement.textContent = "";
});

refreshStatus().catch(console.error);
connectLogs();
