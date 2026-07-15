let clicks = 0; // counter for clicks
let openClicksCount = 5; // counter for clicks
let log_text = '';
let logContent;

window.onload = function () {
    // Create div for log container
    let logDiv = document.createElement("div");
    logDiv.id = "log";
    logDiv.style.position = "absolute";
    logDiv.style.top = "20px";
    logDiv.style.left = "0";
    logDiv.style.color = "white";
    logDiv.style.width = "100%";
    logDiv.style.height = "450px";
    logDiv.style.background = "rgba(0, 0, 0, 0.35)";
    logDiv.style.padding = "10px";
    logDiv.style.boxSizing = "border-box";
    logDiv.style.fontFamily = "'Courier New', monospace";
    logDiv.style.display = 'none';

    // Create div for buttons
    let buttonsDiv = document.createElement("div");
    buttonsDiv.style.position = "sticky";
    buttonsDiv.style.top = "0";
    buttonsDiv.style.background = "rgba(0, 0, 0, 0.1)";
    buttonsDiv.style.zIndex = "1000"; // Ensure buttons stay on top

    // Create div for logs
    logContent = document.createElement("div");
    logContent.id = "logContent";
    logContent.style.maxHeight = "380px";
    logContent.style.overflowY = "scroll";
    logContent.style.paddingTop = "10px"; // Space between buttons and log text

    // Create buttons
    let shareScoreButton = document.createElement("button");
    shareScoreButton.onclick = function () {
        sendScore(43);
    };
    shareScoreButton.textContent = "Share Score";

    let hideLogButton = document.createElement("button");
    hideLogButton.onclick = function () {
        hideLog();
    };
    hideLogButton.textContent = "X";

    // Append buttons to buttonsDiv
    buttonsDiv.appendChild(shareScoreButton);
    buttonsDiv.appendChild(hideLogButton);

    // Append buttonsDiv and logContent to logDiv
    logDiv.appendChild(buttonsDiv);
    logDiv.appendChild(logContent);

    document.body.appendChild(logDiv);

    function handleClick(event) {
        const x = event.clientX || event.touches[0].clientX;
        const y = event.clientY || event.touches[0].clientY;

        if (x < 35 && y < 35) {
            clicks++;
            if (clicks >= openClicksCount) {
                logDiv.style.display = 'block';
                clicks = openClicksCount;
                if (log_text.length > 0) {
                    logContent.innerHTML += log_text;
                    log_text = '';
                }
            }
        }
    }

    window.addEventListener('click', handleClick);
    window.addEventListener('touchstart', handleClick);
};

function hideLog() {
    document.getElementById("log").style.display = "none";
}

console_log = function (message) {
    console.log(message);
    if (logContent != null) {
        logContent.innerHTML += message + '<br>';
        logContent.scrollTop = logContent.scrollHeight; // Автоматическая прокрутка к низу
    } else {
        log_text += message + '<br>';
    }
};

console_log("init debug console");

