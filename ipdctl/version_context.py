"""Read-only inventory of independently versioned project inputs."""

from .documents import digest, load_pack
from .version import PACKAGE_VERSION, PUBLIC_VERSION


def inventory(root, registry, *, process_schema, runtime_schema):
    manifest, _ = load_pack(root)
    shipped = {key: manifest[key] for key in ("id", "version", "contract", "layer")}
    shipped["sha256"] = digest(manifest)
    templates = {(item["document_type"], item["locale"]): item for item in manifest["templates"]}
    active = next((i for i in (registry or {}).get("increments", [])
                   if i["id"] == registry["active_increment"]), None)
    pinned = registry["template_pack"] if registry else None
    instances = []
    if registry:
        from .template_publications import live_instances

        live_ids = {item["id"] for item in live_instances(registry)}
        for item in registry["instances"]:
            target = templates.get((item["document_type"], item["locale"]))
            instances.append({
                "id": item["id"], "path": item["path"], "increment": item["increment"],
                "template_id": item["template_id"], "template_version": item["template_version"],
                "template_sha256": item["template_sha256"], "pack": item["pack"],
                "live": item["id"] in live_ids,
                "shipped_template_version": target["version"] if target else None,
                "shipped_template_comparison": ("unavailable" if not target else
                    "same" if (target["id"], target["version"], target["sha256"]) ==
                    (item["template_id"], item["template_version"], item["template_sha256"]) else "different"),
            })
    return {
        "cli": {"package": PACKAGE_VERSION, "release": PUBLIC_VERSION},
        "contracts": {"process": process_schema, "runtime": runtime_schema,
                      "requirements": registry["contract"] if registry else None,
                      "registry": registry["schema_version"] if registry else None},
        "templates": {
            "shipped": shipped, "project_pin": pinned, "active_increment_pin": active["pack"] if active else None,
            "publications": (registry or {}).get("template_records", []), "instances": instances,
        },
        "upgrade_preview": {
            "tool_install_changes_project_facts": False,
            "project_pin_differs_from_shipped": pinned["sha256"] != shipped["sha256"] if pinned else None,
            "active_pin_differs_from_shipped": active["pack"]["sha256"] != shipped["sha256"] if active else None,
            "live_instances_for_explicit_review": [item["id"] for item in instances if item["live"]
                                                  and item["shipped_template_comparison"] != "same"],
        },
    }
