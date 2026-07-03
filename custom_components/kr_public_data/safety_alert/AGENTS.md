# `safety_alert` (안전알림 - 행정안전부)

Regions live flatly in `entry.data["regions"]` (`[{"code", "name"}, ...]`) — no subentries, same style `pharmacy` moved to in 4.9. One `SafetyAlertCoordinator` per region, keyed by region `code` in `store["coordinators"]`. Legacy fallback: a pre-list single-region shape (`entry.data["area_code"]`/`["area_name"]`) — don't remove it.

Region names/codes come from the safekorea region API (`safety_alert/region_api.py`), the same lookup `disaster` and (pre-4.9) `pharmacy` use for their 시군구 pickers.
