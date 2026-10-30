"""Consistent synthetic business scenarios for archive and directory decoys."""
import secrets

from aideceptionguard.database import DATABASE_TEMPLATES
from aideceptionguard.i18n import translate
from aideceptionguard.validation import vault_decoy_domain


SCENARIOS = {
    "crm": {
        "title_ja": "顧客アカウント台帳", "title_en": "Customer account register",
        "schema": "customers", "context": "service", "env_key": "CRM_API_URL",
        "file_stems": ("customer_accounts", "account_register", "contact_directory", "service_accounts",
                       "customer_status", "account_review", "regional_accounts", "billing_contacts",
                       "customer_export", "support_accounts"),
        "archive_stems": ("crm_snapshot", "account_archive", "customer_backup", "customer_export",
                          "billing_records", "account_history", "customer_data", "service_accounts"),
    },
    "migration": {
        "title_ja": "顧客データ移行一覧", "title_en": "Customer migration export",
        "schema": "customers", "context": "support", "env_key": "MIGRATION_API_URL",
        "file_stems": ("customer_migration", "source_accounts", "import_manifest", "account_mapping",
                       "migration_review", "customer_delta", "source_contacts", "migration_batch",
                       "legacy_accounts", "import_status"),
        "archive_stems": ("migration_export", "import_archive", "legacy_accounts", "migration_batch",
                          "source_backup", "import_manifest", "account_mapping", "customer_delta"),
    },
    "archive": {
        "title_ja": "顧客データ保管台帳", "title_en": "Customer archive index",
        "schema": "customers", "context": "reports", "env_key": "ARCHIVE_API_URL",
        "file_stems": ("customer_archive", "account_snapshot", "records_backup", "customer_ledger",
                       "service_export", "archive_index", "account_history", "customer_backup",
                       "billing_records", "retention_review"),
        "archive_stems": ("customer_backup", "retention_archive", "account_history", "customer_records",
                          "monthly_archive", "customer_ledger", "service_export", "archive_index"),
    },
    "cards": {
        "title_ja": "支払カード台帳", "title_en": "Payment card inventory",
        "schema": "cards", "context": "billing", "env_key": "PAYMENT_API_URL",
        "file_stems": ("card_accounts", "payment_methods", "billing_profiles", "card_renewals",
                       "holder_directory", "payment_status", "cardholder_export", "expiry_review"),
        "archive_stems": ("card_inventory", "payment_archive", "billing_backup", "cardholder_records",
                          "payment_history", "account_methods", "expiry_review", "billing_snapshot"),
    },
    "companies": {
        "title_ja": "取引先企業一覧", "title_en": "Company directory",
        "schema": "companies", "context": "service", "env_key": "ORGANIZATION_API_URL",
        "file_stems": ("company_directory", "organization_register", "account_owners", "company_contacts",
                       "industry_mapping", "organization_export", "relationship_status", "company_review"),
        "archive_stems": ("company_records", "organization_backup", "account_directory", "company_archive",
                          "industry_register", "organization_snapshot", "account_owners", "company_history"),
    },
    "passwords": {
        "title_ja": "認証情報保管庫", "title_en": "Credential vault export",
        "schema": "passwords", "context": "service", "env_key": "VAULT_API_URL", "canary_field": "login_url",
        "file_stems": ("saved_logins", "vault_export", "credential_register", "service_access",
                       "account_recovery", "vault_migration", "login_inventory", "credential_review"),
        "archive_stems": ("vault_backup", "credential_archive", "saved_logins", "recovery_records",
                          "service_access", "vault_migration", "account_credentials", "login_history"),
    },
    "invoices": {
        "title_ja": "請求書・入金一覧", "title_en": "Invoice and payment register",
        "schema": "invoices", "context": "billing", "env_key": "BILLING_API_URL",
        "file_stems": ("invoice_register", "payment_status", "accounts_receivable", "billing_export",
                       "overdue_review", "invoice_history", "payment_reconciliation", "billing_contacts"),
        "archive_stems": ("invoice_archive", "billing_snapshot", "payment_history", "receivables_export",
                          "invoice_backup", "monthly_billing", "payment_records", "billing_reconciliation"),
    },
    "employees": {
        "title_ja": "従業員・部署一覧", "title_en": "Employee and department register",
        "schema": "employees", "context": "reports", "env_key": "HR_API_URL",
        "file_stems": ("employee_directory", "staff_roster", "department_assignments", "role_register",
                       "onboarding_status", "workforce_export", "employee_review", "team_contacts"),
        "archive_stems": ("employee_archive", "staff_records", "workforce_backup", "department_history",
                          "role_assignments", "onboarding_export", "employee_snapshot", "team_roster"),
    },
    "vendors": {
        "title_ja": "仕入先・委託先台帳", "title_en": "Vendor and partner register",
        "schema": "vendors", "context": "service", "env_key": "VENDOR_API_URL",
        "file_stems": ("vendor_directory", "supplier_register", "partner_contacts", "vendor_reviews",
                       "contract_owners", "vendor_services", "supplier_export", "partner_status"),
        "archive_stems": ("vendor_archive", "supplier_backup", "partner_records", "contract_register",
                          "vendor_history", "supplier_review", "partner_export", "service_providers"),
    },
    "orders": {
        "title_ja": "受注・販売台帳", "title_en": "Order and sales ledger",
        "schema": "orders", "context": "billing", "env_key": "SALES_API_URL",
        "file_stems": ("order_history", "sales_register", "fulfillment_status", "customer_orders",
                       "shipment_queue", "order_reconciliation", "sales_export", "returns_review"),
        "archive_stems": ("order_archive", "sales_backup", "fulfillment_records", "shipment_history",
                          "customer_orders", "returns_archive", "sales_snapshot", "order_reconciliation"),
    },
    "tickets": {
        "title_ja": "サポートチケット一覧", "title_en": "Support ticket queue",
        "schema": "tickets", "context": "support", "env_key": "SUPPORT_API_URL",
        "file_stems": ("support_queue", "ticket_register", "customer_issues", "case_assignments",
                       "service_requests", "resolution_status", "support_export", "escalation_review"),
        "archive_stems": ("ticket_archive", "support_backup", "case_history", "service_requests",
                          "resolution_records", "escalation_queue", "support_snapshot", "customer_cases"),
    },
    "assets": {
        "title_ja": "IT資産台帳", "title_en": "IT asset inventory",
        "schema": "assets", "context": "service", "env_key": "ASSET_API_URL",
        "file_stems": ("asset_register", "device_inventory", "hardware_assignments", "software_licenses",
                       "endpoint_status", "asset_export", "lifecycle_review", "equipment_roster"),
        "archive_stems": ("asset_archive", "device_backup", "equipment_history", "license_register",
                          "endpoint_snapshot", "hardware_records", "asset_reconciliation", "inventory_export"),
    },
    "cloud": {
        "title_ja": "クラウド資産一覧", "title_en": "Cloud resource inventory",
        "schema": "cloud", "context": "service", "env_key": "CLOUD_API_URL",
        "file_stems": ("cloud_resources", "subscription_inventory", "service_principals", "role_assignments",
                       "storage_accounts", "resource_review", "tenant_export", "deployment_inventory"),
        "archive_stems": ("cloud_archive", "tenant_backup", "resource_history", "subscription_export",
                          "identity_inventory", "storage_snapshot", "deployment_records", "cloud_reconciliation"),
    },
}


def scenario_for(settings, language="ja"):
    name = settings.get("scenario", "crm")
    if not isinstance(name, str) or name not in SCENARIOS:
        raise ValueError(translate("invalid_input", language))
    scenario = dict(SCENARIOS[name])
    template = DATABASE_TEMPLATES[scenario["schema"]]
    scenario["table"] = template["table"]
    scenario["columns"] = [
        {**column, **({"values": list(column["values"])} if "values" in column else {})}
        for column in template["columns"]
    ]
    if name == "passwords":
        domain = vault_decoy_domain(settings.get("vault_domain", ""),
                                    settings.get("vault_domain_authorized", False), language)
        if domain:
            login_column = next((column for column in scenario["columns"]
                                 if column["name"].casefold() == "login_url"), None)
            if login_column is not None and "values" not in login_column:
                login_column["vault_decoy_domain"] = domain
    scenario["title"] = scenario["title_en" if language == "en" else "title_ja"]
    return name, scenario


def place_canary(scenario, data, url):
    """Place a canary in a plausible synthetic field when the scenario defines one."""
    field = scenario.get("canary_field")
    if not url or not field or not data:
        return None
    column = next((index for index, item in enumerate(scenario["columns"])
                   if item["name"].casefold() == field.casefold()), None)
    if column is None:
        raise ValueError("Scenario canary field is missing from its schema")
    row = secrets.randbelow(len(data))
    data[row][column] = url
    return row, column
