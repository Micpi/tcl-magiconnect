"""Allowlisted diagnostics: never export identifiers, text or screenshots."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    info = coordinator.data
    return {
        "integration_version": "0.1.0",
        "last_update_success": coordinator.last_update_success,
        "model": info.model,
        "software_version": info.software_version,
        "service_version": info.app_version,
        "algorithm": info.algorithm,
        "functions": info.functions,
        "applications_loaded": coordinator.apps_loaded,
        "application_count": len(coordinator.apps),
        "hardware_validated": False,
    }
