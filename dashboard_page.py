# dashboard_page.py (laptop)

HTML_PAGE = r"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIoT Guardian Logger</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #101018;
            color: white;
        }

        .container {
            padding: 18px;
            max-width: 540px;
            margin: auto;
        }

        h1 {
            font-size: 24px;
            margin-bottom: 6px;
        }

        .subtitle {
            color: #aaa;
            font-size: 14px;
            margin-bottom: 18px;
        }

        .status-card {
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 18px;
            background: #222230;
            border: 3px solid #888;
        }

        .status {
            font-size: 40px;
            font-weight: bold;
            margin-top: 8px;
        }

        .message {
            font-size: 16px;
            color: #ddd;
            margin-top: 8px;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .card {
            background: #222230;
            padding: 16px;
            border-radius: 16px;
        }

        .label {
            color: #aaa;
            font-size: 14px;
        }

        .value {
            font-size: 28px;
            font-weight: bold;
            margin-top: 6px;
            overflow-wrap: anywhere;
        }

        .button-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 16px;
        }

        button {
            border: none;
            border-radius: 14px;
            padding: 16px;
            font-size: 17px;
            font-weight: bold;
            color: white;
        }

        .btn-safe {
            background: #168a3a;
        }

        .btn-tilt {
            background: #d99a00;
        }

        .btn-vib {
            background: #6d5bd9;
        }

        .btn-shock {
            background: #d94a32;
        }

        .btn-stop {
            background: #555;
            grid-column: span 2;
        }

        .events {
            background: #222230;
            padding: 16px;
            border-radius: 16px;
            margin-top: 16px;
        }

        .event {
            color: #ddd;
            font-size: 14px;
            padding-top: 6px;
        }

        .safe {
            color: #5CFF8A;
            border-color: #5CFF8A;
        }

        .warning {
            color: #FFD54A;
            border-color: #FFD54A;
        }

        .danger {
            color: #FF5A5A;
            border-color: #FF5A5A;
        }

        .neutral {
            color: #CCCCCC;
            border-color: #888888;
        }

        .event-safe {
            color: #5CFF8A;
        }

        .event-tilt {
            color: #FFD54A;
        }

        .event-vibration {
            color: #C77DFF;
        }

        .event-shock {
            color: #FF5A5A;
        }

        .event-neutral {
            color: #CCCCCC;
        }

        .small {
            font-size: 13px;
            color: #aaa;
            margin-top: 12px;
        }

        .recording {
            background: #29293a;
            padding: 14px;
            border-radius: 14px;
            margin-top: 14px;
            border: 2px solid #777;
        }

        .hint {
            font-size: 13px;
            color: #bbb;
            margin-top: 8px;
            line-height: 1.4;
        }
    </style>
</head>

<body>
    <div class="container">
        <h1>Edge AIoT Smart Asset Guardian</h1>
        <div class="subtitle">Phone dashboard + 3-second ML window logger</div>

        <div id="statusCard" class="status-card neutral">
            <div class="label">Current Asset Condition</div>
            <div id="status" class="status neutral">SEARCHING</div>
            <div id="message" class="message">Waiting for ESP32 data...</div>
            <div id="ble" class="small">BLE: Searching</div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">Tilt</div>
                <div id="tilt" class="value">0°</div>
            </div>

            <div class="card">
                <div class="label">Vibration</div>
                <div id="vib" class="value">0</div>
            </div>

            <div class="card">
                <div class="label">Shock</div>
                <div id="shock" class="value">0.00g</div>
            </div>

            <div class="card">
                <div class="label">Sensitivity</div>
                <div id="sens" class="value">0</div>
            </div>

            <div class="card">
                <div class="label">Detected Event</div>
                <div id="eventType" class="value event-neutral">--</div>
            </div>

            <div class="card">
                <div class="label">Decision Mode</div>
                <div id="modeType" class="value">--</div>
            </div>
        </div>

        <div class="recording">
            <div class="label">Current Training Label</div>
            <div id="currentLabel" class="value">STOPPED</div>
            <div id="sampleCount" class="small">Saved 3-second windows: 0</div>
            <div class="hint">Each saved sample is a 3-second summary, not one instant reading.</div>
        </div>

        <div class="button-grid">
            <button class="btn-safe" onclick="setLabel('SAFE')">Record SAFE</button>
            <button class="btn-tilt" onclick="setLabel('TILT')">Record TILT</button>
            <button class="btn-vib" onclick="setLabel('VIBRATION')">Record VIBRATION</button>
            <button class="btn-shock" onclick="setLabel('SHOCK')">Record SHOCK</button>
            <button class="btn-stop" onclick="setLabel('STOPPED')">STOP Recording</button>
        </div>

        <div class="events">
            <div class="label">Event Log</div>
            <div id="events"></div>
        </div>

        <div id="time" class="small">Last update: --:--:--</div>
    </div>

    <script>
        function statusClass(status) {
            if (status === "SAFE") return "safe";
            if (status === "WARNING") return "warning";
            if (status === "DANGER") return "danger";
            return "neutral";
        }

        function eventClass(eventName) {
            if (eventName === "SAFE") return "event-safe";
            if (eventName === "TILT") return "event-tilt";
            if (eventName === "VIBRATION") return "event-vibration";
            if (eventName === "SHOCK") return "event-shock";
            return "event-neutral";
        }

        function statusMessage(status, eventName) {
            if (status === "SAFE") return "Asset is stable and safe.";
            if (eventName === "VIBRATION") return "Vibration detected. Asset may be shaking.";
            if (eventName === "TILT") return "Unsafe tilt detected.";
            if (eventName === "SHOCK") return "Shock or impact detected. Check asset now.";
            if (status === "WARNING") return "Possible unsafe handling detected.";
            if (status === "DANGER") return "High-risk event detected. Check asset now.";
            if (status === "NOT FOUND") return "ESP32 device not found.";
            return "Waiting for ESP32 data...";
        }

        function setLabel(label) {
            fetch("/set_label?value=" + label)
                .then(response => response.json())
                .then(data => {
                    console.log("Label set:", data.label);
                });
        }

        const ws = new WebSocket(`ws://${location.host}/ws`);

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);

            const cls = statusClass(data.status);

            const statusCard = document.getElementById("statusCard");
            const statusText = document.getElementById("status");
            const eventText = document.getElementById("eventType");

            statusCard.className = "status-card " + cls;
            statusText.className = "status " + cls;

            eventText.className = "value " + eventClass(data.event);

            document.getElementById("status").innerText = data.status;
            document.getElementById("message").innerText = statusMessage(data.status, data.event);
            document.getElementById("ble").innerText = "BLE: " + data.ble;

            document.getElementById("tilt").innerText = Math.round(data.tilt) + "°";
            document.getElementById("vib").innerText = Math.round(data.vib);
            document.getElementById("shock").innerText = Number(data.shock).toFixed(2) + "g";
            document.getElementById("sens").innerText = data.sens;

            document.getElementById("eventType").innerText = data.event;
            document.getElementById("modeType").innerText = data.mode;

            document.getElementById("currentLabel").innerText = data.label;
            document.getElementById("sampleCount").innerText =
                "Saved 3-second windows: " + data.samples;

            document.getElementById("time").innerText = "Last update: " + data.time;

            const eventsDiv = document.getElementById("events");
            eventsDiv.innerHTML = "";

            if (data.events && data.events.length > 0) {
                data.events.forEach(function(item) {
                    const div = document.createElement("div");
                    div.className = "event";
                    div.innerText = item;
                    eventsDiv.appendChild(div);
                });
            } else {
                eventsDiv.innerHTML = "<div class='event'>No events yet.</div>";
            }
        };

        ws.onclose = function() {
            document.getElementById("message").innerText = "Dashboard connection lost.";
        };
    </script>
</body>
</html>
"""
