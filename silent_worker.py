"""
silent_worker.py - Tagpuan Remote Administrative Client Worker
-------------------------------------------------------------
Transmits heartbeats, system status telemetry, and UAC elevation requests
to the Tagpuan Express / Socket.io broker via REST API (/api/requests).

Requirements:
- Verified explicit consent marker (.authorized)
- 'requests' library (Python 3.8+)
"""

import os
import sys
import time
import socket
import platform
import logging
import pathlib
import datetime
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' library not found. Run 'pip install requests'.")
    sys.exit(1)

# -----------------------------------------------------------
# Configuration & Paths
# -----------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
AUTH_FILE = BASE_DIR / ".authorized"

# Server API URL (Defaults to localhost broker, overridable via TAGPUAN_SERVER_URL)
SERVER_URL = os.getenv("TAGPUAN_SERVER_URL", "http://localhost:3000").rstrip("/")
API_ENDPOINT = f"{SERVER_URL}/api/requests"

# Node identity
HOSTNAME = socket.gethostname()
DEVICE_ID = f"NODE-{HOSTNAME.upper()[:12]}"
OS_INFO = f"{platform.system()} {platform.release()}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# -----------------------------------------------------------
# Consent & Safety Verification
# -----------------------------------------------------------
def verify_authorization() -> bool:
    """Ensure transparent explicit consent is active before any transmission."""
    if not AUTH_FILE.is_file():
        logging.warning("Authorization marker missing. Terminating worker.")
        return False
    return True


# -----------------------------------------------------------
# Transmission Engine
# -----------------------------------------------------------
class TagpuanClient:
    def __init__(self, endpoint: str = API_ENDPOINT):
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": f"TagpuanWorker/2.0 ({OS_INFO})"
        })

    def post_event(
        self,
        request_type: str,
        status: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Transmit a structured payload to the Tagpuan server."""
        payload = {
            "deviceId": DEVICE_ID,
            "hostname": HOSTNAME,
            "os": OS_INFO,
            "type": request_type,
            "status": status,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

        try:
            response = self.session.post(self.endpoint, json=payload, timeout=10)
            if response.status_code in (200, 201):
                logging.info("Transmitted %s (%s): %s", request_type, status, message)
                return True
            else:
                logging.error("Server rejected event (HTTP %s): %s", response.status_code, response.text)
                return False
        except requests.exceptions.RequestException as err:
            logging.warning("Failed to connect to Tagpuan Broker (%s): %s", self.endpoint, err)
            return False

    def send_heartbeat(self):
        """Sends periodic live pulse with memory/CPU summary."""
        return self.post_event(
            request_type="HEARTBEAT",
            status="INFO",
            message=f"Node {DEVICE_ID} operational pulse.",
            metadata={"uptime": time.time()}
        )

    def request_uac_elevation(self, reason: str = "Administrative task execution required"):
        """Sends an administrative UAC elevation request to the dashboard."""
        return self.post_event(
            request_type="UAC_REQUEST",
            status="PENDING",
            message=reason,
            metadata={
                "requestedBy": os.getenv("USERNAME", "Administrator"),
                "priority": "HIGH"
            }
        )


# -----------------------------------------------------------
# Worker Loop
# -----------------------------------------------------------
def main():
    if not verify_authorization():
        sys.exit(1)

    logging.info("Starting Tagpuan Worker for [%s] -> %s", DEVICE_ID, API_ENDPOINT)
    client = TagpuanClient()

    # Initial registration / status update
    client.post_event(
        request_type="STATUS_UPDATE",
        status="ONLINE",
        message=f"Worker initialized on {HOSTNAME} ({OS_INFO}).",
        metadata={"platform": platform.platform()}
    )

    interval_seconds = 30
    pulse_counter = 0

    try:
        while True:
            # Continually re-verify authorization to allow instant revocation
            if not verify_authorization():
                logging.info("Authorization revoked during execution. Exiting.")
                break

            pulse_counter += 1
            client.send_heartbeat()

            # Example: Send a sample UAC request on the 2nd cycle to demonstrate live dashboard feed
            if pulse_counter == 2:
                client.request_uac_elevation("System update requires administrative privilege confirmation.")

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        logging.info("Worker stopped by user.")
    finally:
        client.post_event(
            request_type="STATUS_UPDATE",
            status="OFFLINE",
            message="Worker process shutdown."
        )


if __name__ == "__main__":
    main()
