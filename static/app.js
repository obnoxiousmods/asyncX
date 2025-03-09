document.getElementById("startButton").addEventListener("click", function() {
    const username = document.getElementById("username").value.trim();
    if (!username) {
        alert("Please enter a Twitter username.");
        return;
    }

    const progressLog = document.getElementById("progressLog");
    const followersList = document.getElementById("followersList");
    const downloadButton = document.getElementById("downloadButton");

    progressLog.value = "";  // Clear previous logs
    followersList.value = "";  // Clear previous followers

    // ✅ Store the username for the download filename
    downloadButton.dataset.username = username;

    const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(`${wsProtocol}${window.location.host}/ws`);
    

    ws.onopen = () => {
        console.log("Connected to WebSocket");
        progressLog.value += "✅ Connected to server...\n";
        ws.send(username);
    };

    ws.onmessage = (event) => {
        if (event.data.startsWith("⏳") || event.data.startsWith("❌")) {
            progressLog.value += event.data + "\n";
            progressLog.scrollTop = progressLog.scrollHeight;
        } else {
            followersList.value += event.data + "\n";
            followersList.scrollTop = followersList.scrollHeight;
        }
    };

    ws.onclose = () => {
        console.log("WebSocket disconnected");
        progressLog.value += "🔴 Disconnected from server.\n";
        downloadButton.disabled = false;  // Enable download after completion
    };

    ws.onerror = (error) => {
        console.log("WebSocket error:", error);
        progressLog.value += "❌ WebSocket error occurred!\n";
    };
});

// ✅ "Download Followers" button with dynamic filename
document.getElementById("downloadButton").addEventListener("click", function() {
    const followersText = document.getElementById("followersList").value.trim();
    const username = this.dataset.username || "unknown";  // Get stored username

    if (!followersText) {
        alert("No followers to download.");
        return;
    }

    const blob = new Blob([followersText], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `followers_${username}.txt`;  // ✅ Dynamic filename
    a.click();
    URL.revokeObjectURL(a.href);
});


document.getElementById("importButton").addEventListener("click", async function() {
    const inputText = document.getElementById("accountInput").value.trim();
    if (!inputText) {
        alert("Please enter account details.");
        return;
    }

    const accounts = inputText.split("\n").map(line => {
        const [auth_token, kdt, ct0] = line.trim().split("|");
        return { auth_token, kdt, ct0 };
    });

    const response = await fetch("/import_accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accounts })
    });

    const result = await response.json();
    alert(result.message);
});
