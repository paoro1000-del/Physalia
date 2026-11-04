"""Plausible, varied default names for generated decoy artifacts."""
from datetime import datetime
import secrets


FORMAT_NAMES = {
    "env": (
        "application_settings", "service_config", "database_connection", "production_settings",
        "backend_environment", "integration_settings", "runtime_config", "worker_settings",
        "service_endpoints", "deployment_config", "database_pool", "app_environment",
        "queue_settings", "storage_config", "auth_provider_settings", "reporting_service",
        "billing_gateway", "customer_api", "notification_service", "cache_config",
    ),
    "txt": (
        "service_notes", "operations_runbook", "access_review", "migration_plan", "customer_summary",
        "quarterly_reconciliation", "vendor_onboarding", "recovery_checklist", "deployment_handoff",
        "account_review", "retention_schedule", "support_rotation", "incident_followup",
        "data_quality_notes", "integration_status", "regional_operations", "export_procedure",
        "billing_exceptions", "service_transition", "renewal_tracker",
    ),
    "json": (
        "application_settings", "service_accounts", "user_directory", "project_manifest", "system_snapshot",
        "tenant_configuration", "integration_registry", "deployment_state", "account_mapping",
        "service_catalog", "access_policies", "export_manifest", "runtime_options",
        "billing_profile", "workflow_state", "organization_snapshot", "retention_policy",
        "api_registry", "migration_status", "regional_settings",
    ),
    "csv": (
        "customer_export", "invoice_register", "vendor_contacts", "order_history", "staff_roster",
        "account_activity", "payment_reconciliation", "service_requests", "contract_renewals",
        "asset_register", "subscription_usage", "support_queue", "regional_accounts",
        "shipment_status", "access_audit", "billing_exceptions", "product_catalog",
        "employee_directory", "monthly_revenue", "integration_inventory",
    ),
    "html": (
        "account_portal", "operations_dashboard", "archive_index", "report_center",
        "service_catalog", "billing_overview", "customer_workspace", "project_status",
        "vendor_portal", "support_dashboard", "regional_summary", "export_history",
        "access_review", "contract_tracker", "system_status", "operations_home",
    ),
    "pdf": (
        "quarterly_report", "regional_sales", "invoice_register", "compliance_review",
        "service_summary", "account_review", "renewal_forecast", "operations_update",
        "vendor_assessment", "customer_retention", "budget_revision", "project_closeout",
        "risk_register", "support_metrics", "billing_summary", "access_review",
    ),
    "xlsx": (
        "account_register", "quarterly_finance", "customer_ledger", "sales_pipeline", "vendor_directory",
        "invoice_reconciliation", "subscription_forecast", "asset_inventory", "staffing_plan",
        "regional_performance", "support_metrics", "renewal_schedule", "service_capacity",
        "project_costs", "payment_status", "contract_tracker", "usage_summary",
        "customer_segments", "budget_variance", "data_quality_review",
    ),
    "pptx": (
        "quarterly_review", "sales_forecast", "operations_briefing", "project_update",
        "service_transition", "regional_performance", "customer_retention", "budget_review",
        "vendor_assessment", "capacity_planning", "account_strategy", "delivery_status",
        "risk_summary", "support_review", "renewal_outlook", "program_checkpoint",
    ),
    "sqlite": (
        "customer_archive", "billing_snapshot", "inventory_data", "service_records", "account_ledger",
        "account_history", "support_archive", "vendor_register", "subscription_store",
        "order_records", "project_catalog", "usage_snapshot", "contract_index",
        "operations_cache", "migration_stage", "reporting_store", "customer_history",
        "payment_records", "asset_catalog", "service_archive",
    ),
    "db": (
        "customer_archive", "billing_snapshot", "inventory_data", "service_records", "account_ledger",
        "account_history", "support_archive", "vendor_register", "subscription_store",
        "order_records", "project_catalog", "usage_snapshot", "contract_index",
        "operations_cache", "migration_stage", "reporting_store", "customer_history",
        "payment_records", "asset_catalog", "service_archive",
    ),
}
PURPOSE_NAMES = {
    "database": ("customer_register", "account_archive", "crm_snapshot", "customer_records", "service_ledger", "billing_store", "vendor_data", "operations_cache", "subscription_records", "support_history", "customer_snapshot", "invoice_archive"),
    "nest": ("customer_export", "service_backup", "billing_archive", "contract_records", "operations_snapshot", "account_history", "migration_bundle", "vendor_archive", "regional_backup", "support_records", "data_retention", "project_documents"),
    "directory_maze": ("shared_documents", "department_archive", "project_files", "portal_documents", "operations_workspace", "regional_reports", "customer_materials", "team_resources", "service_archive", "business_records", "support_library", "account_documents"),
    "encoding_maze": ("customer_export", "monthly_report", "service_snapshot", "legacy_archive", "account_history", "billing_extract", "regional_summary", "migration_records", "support_export", "usage_report", "vendor_register", "data_reconciliation"),
    "stream": ("archive_stream", "report_stream", "document_service", "export_service", "account_export", "billing_feed", "operations_feed", "records_download", "service_archive", "data_transfer", "reporting_endpoint", "customer_export"),
    "fake_trap": ("auth_status", "session_callback", "request_status", "access_result", "identity_check", "portal_response", "sso_return", "account_validation", "user_session", "service_access", "signin_response", "verification_result", "token_exchange", "login_complete", "workspace_status", "profile_sync", "access_review", "session_refresh"),
}
DATABASE_PROFILE_NAMES = {
    "customers": ("customer_archive", "account_ledger", "client_directory", "customer_export", "account_snapshot", "customer_history"),
    "cards": ("payment_methods", "card_inventory", "billing_profiles", "cardholder_export", "payment_status", "card_accounts"),
    "companies": ("organization_directory", "company_register", "business_accounts", "enterprise_roster", "company_snapshot", "company_archive"),
    "passwords": ("vault_backup", "saved_logins", "credential_archive", "password_vault", "access_register", "vault_export"),
    "orders": ("order_history", "sales_records", "fulfillment_queue", "order_archive", "shipment_register", "order_snapshot"),
    "sales": ("sales_transactions", "quarterly_sales", "revenue_ledger", "transaction_export", "sales_archive", "sales_snapshot"),
    "invoices": ("invoice_register", "billing_ledger", "accounts_receivable", "monthly_billing", "payment_reconciliation", "invoice_archive"),
    "employees": ("staff_roster", "employee_directory", "workforce_snapshot", "personnel_register", "hr_records", "employee_archive"),
    "users": ("user_accounts", "account_directory", "identity_roster", "access_register", "user_archive", "account_snapshot"),
    "api_credentials": ("service_tokens", "integration_keys", "api_access_registry", "application_credentials", "service_accounts", "credential_inventory"),
    "vendors": ("vendor_register", "supplier_directory", "partner_roster", "vendor_archive", "contract_register", "supplier_snapshot"),
    "tickets": ("support_queue", "service_requests", "case_history", "ticket_archive", "customer_cases", "support_snapshot"),
    "assets": ("asset_register", "hardware_inventory", "endpoint_inventory", "device_roster", "asset_snapshot", "equipment_archive"),
    "cloud": ("cloud_inventory", "resource_register", "service_accounts", "deployment_inventory", "cloud_snapshot", "platform_resources"),
}
CONTEXT_FILENAME_NAMES = {
    "service": ("service_accounts", "service_config", "service_catalog", "service_records",
                "operations_runbook", "system_snapshot", "integration_status", "runtime_config"),
    "billing": ("billing_overview", "invoice_register", "payment_reconciliation", "invoice_history",
                "payment_status", "billing_summary", "accounts_receivable", "invoice_archive"),
    "support": ("support_queue", "service_requests", "support_rotation", "case_history",
                "support_metrics", "support_dashboard", "incident_followup", "ticket_archive"),
    "reports": ("quarterly_report", "regional_summary", "report_center", "export_history",
                "usage_summary", "operations_update", "regional_performance", "reporting_store"),
    "operations": ("operations_portal", "service_archive", "operations_records", "recovery_library",
                   "service_inventory", "operations_workspace"),
    "shared": ("shared_documents", "document_workspace", "team_files", "project_library",
               "shared_archive", "document_index"),
    "archive": ("business_archive", "archive_index", "records_archive", "document_archive",
                "business_records", "retention_archive"),
    "records": ("records_center", "access_review", "vendor_register", "export_history",
                "business_records", "records_snapshot"),
}
CONTEXT_PREFIXES = (
    "", "", "", "finance", "operations", "customer", "regional", "service", "vendor",
    "support", "legacy", "shared", "migration", "internal", "platform", "billing",
)
WORKFLOW_SUFFIXES = (
    "", "", "", "current", "previous", "archive", "backup", "review", "snapshot",
    "export", "reconciled", "recovery", "handoff", "stage", "v2",
)


def plausible_filename(purpose, extension=None, profile=None, context=None):
    """Return a Physalia-prefixed, context-matched stem for a generated download."""
    pool = DATABASE_PROFILE_NAMES.get(profile, ()) if profile else ()
    if not pool:
        pool = CONTEXT_FILENAME_NAMES.get(context, ()) if context else ()
    if not pool:
        pool = FORMAT_NAMES.get(extension, ()) if extension else ()
    if not pool:
        pool = PURPOSE_NAMES[purpose]
    now = datetime.now().astimezone()
    quarter = (now.month - 1) // 3 + 1
    stem = secrets.choice(pool)
    prefix = "" if context in CONTEXT_FILENAME_NAMES else secrets.choice(CONTEXT_PREFIXES)
    suffix = secrets.choice(WORKFLOW_SUFFIXES)
    tokens = set(stem.split("_"))
    if prefix and prefix not in tokens:
        stem = prefix + "_" + stem
        tokens.add(prefix)
    if suffix and suffix not in tokens:
        stem += "_" + suffix
        tokens.add(suffix)
    dated_suffixes = (
        "", "", "", "_" + now.strftime("%Y_%m"),
        f"_{now.year}Q{quarter}", f"_{now.year}",
    )
    date_suffix = secrets.choice(dated_suffixes)
    if date_suffix:
        date_tokens = set(date_suffix.strip("_").split("_"))
        if not tokens.intersection(date_tokens):
            stem += date_suffix
    return "Physalia_" + stem
