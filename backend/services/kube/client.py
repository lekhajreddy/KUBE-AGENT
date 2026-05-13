"""
KubeMind — Kubernetes Client Factory
Supports: Minikube, K3s, EKS, GKE, AKS, MicroK8s
"""
import logging
from typing import Optional

from kubernetes import client, config

logger = logging.getLogger("kubemind.kube.client")

_client_cache: dict = {}
_incluster_tried = False


def get_core_v1() -> Optional[client.CoreV1Api]:
    if "core_v1" not in _client_cache:
        _init()
        _client_cache["core_v1"] = client.CoreV1Api()
    return _client_cache["core_v1"]


def get_apps_v1() -> Optional[client.AppsV1Api]:
    if "apps_v1" not in _client_cache:
        _init()
        _client_cache["apps_v1"] = client.AppsV1Api()
    return _client_cache["apps_v1"]


def get_custom_objects() -> Optional[client.CustomObjectsApi]:
    if "custom" not in _client_cache:
        _init()
        _client_cache["custom"] = client.CustomObjectsApi()
    return _client_cache["custom"]


def get_networking_v1() -> Optional[client.NetworkingV1Api]:
    if "net_v1" not in _client_cache:
        _init()
        _client_cache["net_v1"] = client.NetworkingV1Api()
    return _client_cache["net_v1"]


def get_batch_v1() -> Optional[client.BatchV1Api]:
    if "batch_v1" not in _client_cache:
        _init()
        _client_cache["batch_v1"] = client.BatchV1Api()
    return _client_cache["batch_v1"]


def get_storage_v1() -> Optional[client.StorageV1Api]:
    if "storage_v1" not in _client_cache:
        _init()
        _client_cache["storage_v1"] = client.StorageV1Api()
    return _client_cache["storage_v1"]


def _init():
    global _incluster_tried
    if _client_cache.get("_initialized"):
        return
    try:
        if _incluster_tried:
            raise Exception("incluster already failed")
        config.load_incluster_config()
        logger.info("K8s: loaded in-cluster config")
    except Exception:
        _incluster_tried = True
        try:
            config.load_kube_config()
            logger.info("K8s: loaded kubeconfig")
        except Exception as e:
            logger.error(f"K8s config failed: {e}")
            return
    _client_cache["_initialized"] = True


def reset_clients():
    _client_cache.clear()
    logger.info("K8s clients reset")


def cluster_info() -> dict:
    v1 = get_core_v1()
    if not v1:
        return {"connected": False}
    try:
        version = v1.get_code()
        nodes = v1.list_node()
        return {
            "connected": True,
            "version": version.git_version,
            "platform": version.platform,
            "node_count": len(nodes.items),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
