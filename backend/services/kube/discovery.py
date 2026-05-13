"""
KubeMind — Kubernetes Resource Discovery
Discovers all resources across clusters with metadata.
"""
import logging
from typing import Dict, List, Any, Optional

from kubernetes.client.rest import ApiException

from backend.services.kube.client import (
    get_core_v1, get_apps_v1, get_custom_objects,
    get_networking_v1, get_batch_v1, get_storage_v1,
)

logger = logging.getLogger("kubemind.kube.discovery")


class ResourceDiscovery:
    def discover_all(self, namespace: str = "") -> Dict[str, List[dict]]:
        ns_filter = namespace or None
        return {
            "pods": self.discover_pods(ns_filter),
            "services": self.discover_services(ns_filter),
            "deployments": self.discover_deployments(ns_filter),
            "statefulsets": self.discover_statefulsets(ns_filter),
            "daemonsets": self.discover_daemonsets(ns_filter),
            "configmaps": self.discover_configmaps(ns_filter),
            "secrets": self.discover_secrets(ns_filter),
            "pvcs": self.discover_pvcs(ns_filter),
            "pvs": self.discover_pvs(),
            "nodes": self.discover_nodes(),
            "namespaces": self.discover_namespaces(),
            "ingresses": self.discover_ingresses(ns_filter),
            "cronjobs": self.discover_cronjobs(ns_filter),
            "storage_classes": self.discover_storage_classes(),
        }

    def discover_pods(self, namespace: Optional[str] = None) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            if namespace:
                items = v1.list_namespaced_pod(namespace).items
            else:
                items = v1.list_pod_for_all_namespaces().items
            return [self._pod_to_dict(p) for p in items]
        except ApiException as e:
            logger.warning(f"Pod discovery error: {e}")
            return []

    def discover_services(self, namespace: Optional[str] = None) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            if namespace:
                items = v1.list_namespaced_service(namespace).items
            else:
                items = v1.list_service_for_all_namespaces().items
            return [self._service_to_dict(s) for s in items]
        except ApiException as e:
            logger.warning(f"Service discovery error: {e}")
            return []

    def discover_deployments(self, namespace: Optional[str] = None) -> List[dict]:
        apps = get_apps_v1()
        if not apps:
            return []
        try:
            if namespace:
                items = apps.list_namespaced_deployment(namespace).items
            else:
                items = apps.list_deployment_for_all_namespaces().items
            return [self._deployment_to_dict(d) for d in items]
        except ApiException as e:
            logger.warning(f"Deployment discovery error: {e}")
            return []

    def discover_statefulsets(self, namespace: Optional[str] = None) -> List[dict]:
        apps = get_apps_v1()
        if not apps:
            return []
        try:
            if namespace:
                items = apps.list_namespaced_stateful_set(namespace).items
            else:
                items = apps.list_stateful_set_for_all_namespaces().items
            return [{"name": s.metadata.name, "namespace": s.metadata.namespace,
                     "replicas": s.spec.replicas or 0, "ready": s.status.ready_replicas or 0,
                     "service": s.spec.service_name or "", "labels": s.metadata.labels or {}} for s in items]
        except ApiException as e:
            logger.warning(f"StatefulSet discovery error: {e}")
            return []

    def discover_daemonsets(self, namespace: Optional[str] = None) -> List[dict]:
        apps = get_apps_v1()
        if not apps:
            return []
        try:
            if namespace:
                items = apps.list_namespaced_daemon_set(namespace).items
            else:
                items = apps.list_daemon_set_for_all_namespaces().items
            return [{"name": d.metadata.name, "namespace": d.metadata.namespace,
                     "desired": d.status.desired_number_scheduled or 0,
                     "ready": d.status.number_ready or 0,
                     "labels": d.metadata.labels or {}} for d in items]
        except ApiException as e:
            logger.warning(f"DaemonSet discovery error: {e}")
            return []

    def discover_configmaps(self, namespace: Optional[str] = None) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            if namespace:
                items = v1.list_namespaced_config_map(namespace).items
            else:
                items = v1.list_config_map_for_all_namespaces().items
            return [{"name": c.metadata.name, "namespace": c.metadata.namespace,
                     "keys": list(c.data.keys()) if c.data else [], "labels": c.metadata.labels or {}} for c in items]
        except ApiException as e:
            logger.warning(f"ConfigMap discovery error: {e}")
            return []

    def discover_secrets(self, namespace: Optional[str] = None) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            if namespace:
                items = v1.list_namespaced_secret(namespace).items
            else:
                items = v1.list_secret_for_all_namespaces().items
            return [{"name": s.metadata.name, "namespace": s.metadata.namespace,
                     "type": s.type or "", "keys": list(s.data.keys()) if s.data else []} for s in items]
        except ApiException as e:
            logger.warning(f"Secret discovery error: {e}")
            return []

    def discover_pvcs(self, namespace: Optional[str] = None) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            if namespace:
                items = v1.list_namespaced_persistent_volume_claim(namespace).items
            else:
                items = v1.list_persistent_volume_claim_for_all_namespaces().items
            return [{"name": p.metadata.name, "namespace": p.metadata.namespace,
                     "phase": p.status.phase or "Pending",
                     "storage": str(p.spec.resources.requests.get("storage", "")) if p.spec.resources else "",
                     "access_modes": p.spec.access_modes or [],
                     "storage_class": p.spec.storage_class_name or "",
                     "labels": p.metadata.labels or {}} for p in items]
        except ApiException as e:
            logger.warning(f"PVC discovery error: {e}")
            return []

    def discover_pvs(self) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            items = v1.list_persistent_volume().items
            return [{"name": p.metadata.name, "phase": p.status.phase or "",
                     "capacity": str(p.spec.capacity.get("storage", "")) if p.spec.capacity else "",
                     "access_modes": p.spec.access_modes or [],
                     "storage_class": p.spec.storage_class_name or "",
                     "claim": p.spec.claim_ref.name if p.spec.claim_ref else "",
                     "claim_namespace": p.spec.claim_ref.namespace if p.spec.claim_ref else ""} for p in items]
        except ApiException as e:
            logger.warning(f"PV discovery error: {e}")
            return []

    def discover_nodes(self) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            items = v1.list_node().items
            nodes = []
            for n in items:
                conditions = {c.type: c.status for c in (n.status.conditions or [])}
                capacity = n.status.capacity or {}
                allocatable = n.status.allocatable or {}
                nodes.append({
                    "name": n.metadata.name,
                    "status": conditions.get("Ready", "Unknown"),
                    "capacity": {k: str(v) for k, v in capacity.items()},
                    "allocatable": {k: str(v) for k, v in allocatable.items()},
                    "roles": [k.split("/")[-1] for k in (n.metadata.labels or {}) if "node-role" in k],
                    "labels": n.metadata.labels or {},
                    "taints": [{"key": t.key, "effect": t.effect} for t in (n.spec.taints or [])],
                })
            return nodes
        except ApiException as e:
            logger.warning(f"Node discovery error: {e}")
            return []

    def discover_namespaces(self) -> List[dict]:
        v1 = get_core_v1()
        if not v1:
            return []
        try:
            items = v1.list_namespace().items
            return [{"name": ns.metadata.name, "status": ns.status.phase or "Active",
                     "labels": ns.metadata.labels or {}} for ns in items]
        except ApiException as e:
            logger.warning(f"Namespace discovery error: {e}")
            return []

    def discover_ingresses(self, namespace: Optional[str] = None) -> List[dict]:
        net = get_networking_v1()
        if not net:
            return []
        try:
            if namespace:
                items = net.list_namespaced_ingress(namespace).items
            else:
                items = net.list_ingress_for_all_namespaces().items
            ingresses = []
            for ing in items:
                rules = []
                for rule in (ing.spec.rules or []):
                    for path in (rule.http.paths or []):
                        rules.append({
                            "host": rule.host or "",
                            "path": path.path or "/",
                            "service": path.backend.service.name if path.backend.service else "",
                            "port": path.backend.service.port.number if path.backend.service and path.backend.service.port else 0,
                        })
                ingresses.append({
                    "name": ing.metadata.name,
                    "namespace": ing.metadata.namespace,
                    "rules": rules,
                    "labels": ing.metadata.labels or {},
                })
            return ingresses
        except ApiException as e:
            logger.warning(f"Ingress discovery error: {e}")
            return []

    def discover_cronjobs(self, namespace: Optional[str] = None) -> List[dict]:
        batch = get_batch_v1()
        if not batch:
            return []
        try:
            if namespace:
                items = batch.list_namespaced_cron_job(namespace).items
            else:
                items = batch.list_cron_job_for_all_namespaces().items
            return [{"name": c.metadata.name, "namespace": c.metadata.namespace,
                     "schedule": c.spec.schedule, "suspend": c.spec.suspend or False,
                     "labels": c.metadata.labels or {}} for c in items]
        except ApiException as e:
            logger.warning(f"CronJob discovery error: {e}")
            return []

    def discover_storage_classes(self) -> List[dict]:
        storage = get_storage_v1()
        if not storage:
            return []
        try:
            items = storage.list_storage_class().items
            return [{"name": sc.metadata.name, "provisioner": sc.provisioner,
                     "reclaim_policy": sc.reclaim_policy or "Delete",
                     "volume_binding_mode": sc.volume_binding_mode or "Immediate",
                     "labels": sc.metadata.labels or {}} for sc in items]
        except ApiException as e:
            logger.warning(f"StorageClass discovery error: {e}")
            return []

    @staticmethod
    def _pod_to_dict(pod) -> dict:
        container_statuses = pod.status.container_statuses or []
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "node": pod.spec.node_name or "",
            "status": pod.status.phase or "",
            "pod_ip": pod.status.pod_ip or "",
            "host_ip": pod.status.host_ip or "",
            "restart_count": sum(cs.restart_count or 0 for cs in container_statuses),
            "ready_containers": sum(1 for cs in container_statuses if cs.ready),
            "total_containers": len(pod.spec.containers) if pod.spec.containers else 0,
            "creation_timestamp": str(pod.metadata.creation_timestamp),
            "labels": pod.metadata.labels or {},
            "annotations": pod.metadata.annotations or {},
            "owner": (pod.metadata.owner_references or [{}])[0].kind if pod.metadata.owner_references else "",
            "owner_name": (pod.metadata.owner_references or [{}])[0].name if pod.metadata.owner_references else "",
        }

    @staticmethod
    def _service_to_dict(svc) -> dict:
        return {
            "name": svc.metadata.name,
            "namespace": svc.metadata.namespace,
            "type": svc.spec.type or "ClusterIP",
            "cluster_ip": svc.spec.cluster_ip or "",
            "ports": [{"port": p.port, "target_port": str(p.target_port or ""), "protocol": p.protocol or ""}
                      for p in (svc.spec.ports or [])],
            "selector": svc.spec.selector or {},
            "labels": svc.metadata.labels or {},
        }

    @staticmethod
    def _deployment_to_dict(dep) -> dict:
        return {
            "name": dep.metadata.name,
            "namespace": dep.metadata.namespace,
            "replicas": dep.spec.replicas or 0,
            "ready_replicas": dep.status.ready_replicas or 0,
            "available_replicas": dep.status.available_replicas or 0,
            "strategy": dep.spec.strategy.type if dep.spec.strategy else "RollingUpdate",
            "selector": dep.spec.selector.match_labels if dep.spec.selector else {},
            "labels": dep.metadata.labels or {},
            "creation_timestamp": str(dep.metadata.creation_timestamp),
        }


resource_discovery = ResourceDiscovery()
