import json
import logging
import os
import platform
import socket
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


class ControllerClient:

    def __init__(self):
        self.base_url = os.environ.get(
            "EDGE_CONTROLLER_URL",
            ""
        ).rstrip("/")

        self.timeout = int(
            os.environ.get(
                "EDGE_CONTROLLER_TIMEOUT",
                "5"
            )
        )

        self.node_id = os.environ.get(
            "EDGE_NODE_ID",
            socket.gethostname()
        )

        self.service_id = os.environ.get(
            "EDGE_SERVICE_ID",
            "edge-audio"
        )

        self.service_name = os.environ.get(
            "EDGE_SERVICE_NAME",
            "edge-audio"
        )

        self.service_version = os.environ.get(
            "EDGE_SERVICE_VERSION",
            "unknown"
        )

    def _request(
        self,
        method,
        path,
        payload=None
    ):
        url = f"{self.base_url}{path}"

        data = None

        if payload is not None:
            data = json.dumps(
                payload
            ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout
        ) as response:
            response_data = response.read()

            if not response_data:
                return None

            return json.loads(
                response_data.decode("utf-8")
            )

    def register(self):
        if not self.base_url:
            logger.info(
                "EDGE_CONTROLLER_URL is not configured; "
                "controller registration disabled"
            )
            return False

        try:
            self._register_node()
            self._register_service()

            logger.info(
                "Registered %s with edge-controller",
                self.service_id
            )

            return True

        except Exception as exc:
            logger.warning(
                "Controller registration failed: %s",
                exc
            )

            return False

    def _register_node(self):
        try:
            self._request(
                "GET",
                f"/api/v1/nodes/{self.node_id}"
            )

            logger.debug(
                "Node already registered: %s",
                self.node_id
            )

            return

        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

        payload = {
            "node_id": self.node_id,
            "hostname": socket.gethostname(),
            "platform": (
                f"{platform.system().lower()}-"
                f"{platform.machine()}"
            )
        }

        self._request(
            "POST",
            "/api/v1/nodes",
            payload
        )

        logger.info(
            "Registered node: %s",
            self.node_id
        )

    def _register_service(self):
        response = self._request(
            "GET",
            f"/api/v1/nodes/{self.node_id}/services"
        )

        services = response or []

        for service in services:
            if service.get("service_id") == self.service_id:
                logger.debug(
                    "Service already registered: %s",
                    self.service_id
                )

                return

        payload = {
            "service_id": self.service_id,
            "name": self.service_name,
            "version": self.service_version
        }

        self._request(
            "POST",
            f"/api/v1/nodes/{self.node_id}/services",
            payload
        )

        logger.info(
            "Registered service: %s version=%s",
            self.service_id,
            self.service_version
        )

    def get_pending_calibration(self):
        try:
            response = self._request(
                "GET",
                f"/api/v1/nodes/{self.node_id}/calibration/pending"
                f"?service_id={self.service_id}"
            )

            return response

        except Exception as exc:
            logger.warning(
                "Unable to check for pending calibration: %s",
                exc
            )

            return None

    def complete_calibration(
        self,
        calibration_id,
        status="complete",
        result=None,
        error=None,
    ):
        payload = {
            "status": status,
            "result": result,
            "error": error,
        }

        return self._request(
            "POST",
            f"/api/v1/nodes/{self.node_id}/calibration/{calibration_id}/result",
            payload,
        )


    def get_configuration(self):
        try:
            response = self._request(
                "GET",
                f"/api/v1/nodes/{self.node_id}/services/"
                f"{self.service_id}/configuration",
            )

            if not response:
                return {}

            return response.get("configuration", {})

        except Exception as exc:
            logger.warning(
                "Controller configuration unavailable: %s",
                exc
            )

            return {}