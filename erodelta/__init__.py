doc = """EROFS and xdelta3 sync plugin for Portage"""
__doc__ = doc[:]

from portage.sync.config_checks import CheckSyncConfig

module_spec = {
    "name": "erodelta",
    "description": doc,
    "provides": {
        "erodelta-module": {
            "name": "erodelta",
            "sourcefile": "erodelta",
            "class": "ErodeltaSync",
            "description": doc,
            "functions": ["sync", "new", "exists"],
            "func_desc": {
                "sync": "Syncs the repository via EROFS and xdelta3",
                "new": "Initializes and mounts the repository for the first time",
                "exists": "Checks if repository directory exists and has files",
            },
            "validate_config": CheckSyncConfig,
        }
    },
}
