(function () {
    "use strict";

    function setupLocationButton() {
        const latitudeInput = document.getElementById("id_latitude");
        const longitudeInput = document.getElementById("id_longitude");
        if (!latitudeInput || !longitudeInput || document.getElementById("use-device-location")) {
            return;
        }

        const wrapper = document.createElement("span");
        wrapper.className = "gps-location-wrapper";

        const button = document.createElement("button");
        button.type = "button";
        button.id = "use-device-location";
        button.className = "gps-location-button";
        button.title = "Use this device's current GPS location";
        button.setAttribute("aria-label", "Use this device's current GPS location");
        button.innerHTML = [
            '<svg viewBox="0 0 24 24" aria-hidden="true">',
            '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm8.94 2.5A9.01 9.01 0 0 0 13 3.06V1h-2v2.06A9.01 9.01 0 0 0 3.06 11H1v2h2.06A9.01 9.01 0 0 0 11 20.94V23h2v-2.06A9.01 9.01 0 0 0 20.94 13H23v-2h-2.06ZM12 19a7 7 0 1 1 0-14 7 7 0 0 1 0 14Z"/>',
            '</svg>'
        ].join("");

        const status = document.createElement("span");
        status.className = "gps-location-status";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");

        wrapper.appendChild(button);
        wrapper.appendChild(status);
        longitudeInput.insertAdjacentElement("afterend", wrapper);

        button.addEventListener("click", function () {
            if (!window.isSecureContext && window.location.hostname !== "localhost") {
                status.textContent = "GPS requires HTTPS.";
                status.className = "gps-location-status gps-location-error";
                return;
            }
            if (!("geolocation" in navigator)) {
                status.textContent = "Location is not available on this device.";
                status.className = "gps-location-status gps-location-error";
                return;
            }

            button.disabled = true;
            button.classList.add("gps-location-loading");
            status.textContent = "Getting location…";
            status.className = "gps-location-status";

            navigator.geolocation.getCurrentPosition(
                function (position) {
                    latitudeInput.value = position.coords.latitude.toFixed(7);
                    longitudeInput.value = position.coords.longitude.toFixed(7);
                    latitudeInput.dispatchEvent(new Event("input", { bubbles: true }));
                    longitudeInput.dispatchEvent(new Event("input", { bubbles: true }));
                    latitudeInput.dispatchEvent(new Event("change", { bubbles: true }));
                    longitudeInput.dispatchEvent(new Event("change", { bubbles: true }));

                    const accuracy = Math.round(position.coords.accuracy);
                    status.textContent = "GPS filled (accuracy about " + accuracy + " m).";
                    status.className = "gps-location-status gps-location-success";
                    button.disabled = false;
                    button.classList.remove("gps-location-loading");
                },
                function (error) {
                    const messages = {
                        1: "Location permission was denied.",
                        2: "The device could not determine its location.",
                        3: "Location request timed out. Try again."
                    };
                    status.textContent = messages[error.code] || "Could not get the current location.";
                    status.className = "gps-location-status gps-location-error";
                    button.disabled = false;
                    button.classList.remove("gps-location-loading");
                },
                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                }
            );
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupLocationButton);
    } else {
        setupLocationButton();
    }
})();
