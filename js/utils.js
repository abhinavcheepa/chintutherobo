/* ========================================
   CHINTU — Utility Functions
   Shared helpers used across all modules
   ======================================== */

function $(id) {
    return document.getElementById(id);
}

function getTime() {
    const d = new Date();
    return d.toTimeString().split(' ')[0];
}

function clamp(val, min, max) {
    return Math.min(max, Math.max(min, val));
}

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function randomInRange(min, max) {
    return Math.random() * (max - min) + min;
}

/**
 * Log a message to the on-screen console.
 * @param {string} msg  - Message text (may include HTML)
 * @param {'info'|'success'|'warning'|'error'|'command'} type
 */
function logToConsole(msg, type = 'info') {
    const output = $('consoleOutput');
    if (!output) return;
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    line.innerHTML = `<span class="console-time">${getTime()}</span><span class="console-msg">${msg}</span>`;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
    while (output.children.length > 200) {
        output.removeChild(output.firstChild);
    }
}
