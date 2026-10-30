import json
from pathlib import Path
import unittest

from aideceptionguard.cloud_review import MAX_RECORDS, analyze


class CloudReviewTests(unittest.TestCase):
    def test_sample_covers_all_rules_without_exposing_graph_query(self):
        rows = json.loads(Path("examples/cloud-review-sample.json").read_text(encoding="utf-8"))
        graph_row = next(row for row in rows if row.get("Type") == "MicrosoftGraphActivityLogs")
        graph_row["RequestUri"] += "?access_token=private-value"
        result = analyze(rows)
        self.assertEqual({item["rule"] for item in result["findings"]},
                         {"decoy_contact", "credential_change", "role_assignment", "signin_burst",
                          "distributed_signin_spray", "targeted_signin_failures", "agentic_signin",
                          "app_signin_then_graph", "signin_after_failures"})
        self.assertEqual(result["finding_count"], len(result["findings"]))
        self.assertNotIn("private-value", json.dumps(result))
        self.assertEqual(sum(result["incomplete"].values()), 0)

    def test_join_requires_success_and_same_tenant_app_and_service_principal(self):
        sign_in = {"Type": "AADServicePrincipalSignInLogs", "AADTenantId": "tenant-a", "AppId": "app", "ServicePrincipalId": "sp", "ResultType": "Success", "CreatedDateTime": "2026-10-21T10:00:00Z"}
        graph = {"Type": "MicrosoftGraphActivityLogs", "AadTenantId": "tenant-a", "AppId": "app", "ServicePrincipalId": "sp", "TimeGenerated": "2026-10-21T10:02:00Z", "RequestUri": "https://graph.microsoft.com/v1.0/sites/site", "ResponseStatusCode": 200}
        for changed in ({"AadTenantId": "tenant-b"}, {"AppId": "other"}, {"ServicePrincipalId": "other"}, {"ResponseStatusCode": 403}, {"TimeGenerated": "2026-10-21T11:01:00Z"}):
            with self.subTest(changed=changed):
                self.assertFalse(analyze([sign_in, {**graph, **changed}])["findings"])
        self.assertFalse(analyze([{**sign_in, "ResultType": "Failure"}, graph])["findings"])
        self.assertEqual(analyze([sign_in, graph])["findings"][0]["rule"], "app_signin_then_graph")

    def test_workspace_tenant_is_not_used_as_identity_tenant(self):
        row = {"Type": "SigninLogs", "TenantId": "workspace", "IPAddress": "192.0.2.1", "UserId": "user", "ResultType": "50126", "CreatedDateTime": "2026-10-21T10:00:00Z"}
        result = analyze([row] * 10)
        self.assertEqual(result["incomplete"]["SigninLogs"], 10)
        self.assertFalse(result["findings"])

    def test_missing_or_failed_audit_result_does_not_alert_as_success(self):
        base = {"Type": "AuditLogs", "ActivityDateTime": "2026-10-21T10:00:00Z", "ActivityDisplayName": "Add member to role"}
        self.assertFalse(analyze([base, {**base, "Result": "failure"}])["findings"])
        self.assertEqual(analyze([base])["incomplete"]["AuditLogs"], 1)

    def test_duplicate_signins_with_event_id_do_not_inflate_counts(self):
        rows = [{"Type": "SigninLogs", "AADTenantId": "tenant-a", "Id": str(i), "IPAddress": "192.0.2.1", "UserId": f"user{i}", "ResultType": "50126", "CreatedDateTime": "2026-10-21T10:00:00Z"} for i in range(5)]
        result = analyze(rows + rows)
        self.assertEqual(result["duplicates"], 5)
        self.assertFalse(result["findings"])

    def test_invalid_and_oversize_input(self):
        for value in (None, {}, [None] * (MAX_RECORDS + 1)):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                analyze(value)


if __name__ == "__main__":
    unittest.main()
