let clicks = 0;
let openClicksCount = 5;
let logText = "";
let logContent;

window.addEventListener("load", function () {
    const logDiv = document.createElement("div");
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
    logDiv.style.display = "none";
    logDiv.style.zIndex = "100";

    const buttonsDiv = document.createElement("div");
    buttonsDiv.style.position = "sticky";
    buttonsDiv.style.top = "0";
    buttonsDiv.style.background = "rgba(0, 0, 0, 0.1)";
    buttonsDiv.style.zIndex = "1000";

    logContent = document.createElement("div");
    logContent.id = "logContent";
    logContent.style.maxHeight = "380px";
    logContent.style.overflowY = "scroll";
    logContent.style.paddingTop = "10px";

    const shareScoreButton = document.createElement("button");
    shareScoreButton.onclick = function () {
        sendScore(43);
    };
    shareScoreButton.textContent = "Share Score";

    const hideLogButton = document.createElement("button");
    hideLogButton.onclick = function () {
        hideLog();
    };
    hideLogButton.textContent = "X";

    buttonsDiv.appendChild(shareScoreButton);
    buttonsDiv.appendChild(hideLogButton);
    logDiv.appendChild(buttonsDiv);
    logDiv.appendChild(logContent);
    document.body.appendChild(logDiv);

    function handleClick(event) {
        const point = event.touches ? event.touches[0] : event;
        const x = point.clientX;
        const y = point.clientY;

        if (x < 35 && y < 35) {
            clicks++;
            if (clicks >= openClicksCount) {
                logDiv.style.display = "block";
                clicks = openClicksCount;
                if (logText.length > 0) {
                    logContent.innerHTML += logText;
                    logText = "";
                }
            }
        }
    }

    window.addEventListener("click", handleClick);
    window.addEventListener("touchstart", handleClick);
});

function hideLog() {
    document.getElementById("log").style.display = "none";
}

console_log = function (message) {
    console.log(message);
    if (logContent != null) {
        logContent.innerHTML += message + "<br>";
        logContent.scrollTop = logContent.scrollHeight;
    } else {
        logText += message + "<br>";
    }
};

console_log("init debug console");
