"""Configurable schemas and synthetic records; never import production data."""

import hashlib
import math
import re
import secrets
import sqlite3
import string
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta

from physalia.i18n import translate
from physalia.japanese_names import (
    FAMILY_PAIRS as DATA_FAMILY_PAIRS,
)
from physalia.japanese_names import (
    GIVEN_PAIRS as DATA_GIVEN_PAIRS,
)
from physalia.validation import (
    canary_url,
    identifier,
    integer,
    synthetic_candidate,
    vault_decoy_domain,
)

MAX_ROWS = 100000
MAX_DATABASE_BYTES = 32 * 1024 * 1024
VAULT_LOGIN_PATHS = {
    "mail-console": "/auth/login",
    "billing-workspace": "/account/signin",
    "source-archive": "/signin",
    "vendor-portal": "/login",
    "analytics-dashboard": "/sso/login",
}
API_SERVICE_SLUGS_JA = {
    "\u8ab2\u91d1API": "billing-api",
    "\u30bd\u30fc\u30b9\u7ba1\u7406": "source-control",
    "\u30aa\u30d6\u30b8\u30a7\u30af\u30c8\u4fdd\u7ba1": "object-storage",
    "\u5206\u6790\u30b2\u30fc\u30c8\u30a6\u30a7\u30a4": "analytics-gateway",
    "\u30e1\u30fc\u30eb\u4e2d\u7d99": "mail-relay",
}
VAULT_SERVICE_ALIASES = {
    "メール管理": "mail-console",
    "請求ワークスペース": "billing-workspace",
    "ソース保管庫": "source-archive",
    "取引先ポータル": "vendor-portal",
    "分析ダッシュボード": "analytics-dashboard",
}


def _vault_service_slug(service):
    service = str(service)
    service = VAULT_SERVICE_ALIASES.get(service.casefold(), service)
    return (
        re.sub(r"[^a-z0-9]+", "-", service.casefold()).strip("-")[:48].strip("-")
        or "vault"
    )


DEFAULT_COLUMNS = [
    {"name": "id", "kind": "id"},
    {"name": "name", "kind": "name"},
    {"name": "email", "kind": "email"},
    {"name": "phone", "kind": "phone"},
    {"name": "birth_date", "kind": "date"},
    {"name": "postal_code", "kind": "test_postal"},
    {"name": "prefecture", "kind": "text"},
    {"name": "city", "kind": "text"},
    {"name": "street_address", "kind": "address"},
    {"name": "created_at", "kind": "date"},
    {"name": "last_login", "kind": "datetime"},
    {"name": "is_deleted", "kind": "boolean"},
]
KINDS = {
    "id": "INTEGER",
    "boolean": "BOOLEAN",
    "name": "TEXT",
    "username": "TEXT",
    "email": "TEXT",
    "company": "TEXT",
    "department": "TEXT",
    "invoice_reference": "TEXT",
    "order_reference": "TEXT",
    "sale_reference": "TEXT",
    "integer": "INTEGER",
    "decimal": "REAL",
    "date": "TEXT",
    "datetime": "TEXT",
    "status": "TEXT",
    "uuid": "TEXT",
    "text": "TEXT",
    "phone": "TEXT",
    "domain": "TEXT",
    "card_reference": "TEXT",
    "card_expiry": "TEXT",
    "test_postal": "TEXT",
    "address": "TEXT",
    "credential_preview": "TEXT",
    "currency": "TEXT",
    "documentation_ip": "TEXT",
}
GIVEN_PAIRS = (
    ("Haruto", "悠真"),
    ("Yui", "結衣"),
    ("Ren", "蓮"),
    ("Aoi", "葵"),
    ("Sota", "颯太"),
    ("Mio", "美緒"),
    ("Riku", "陸"),
    ("Hana", "花"),
    ("Akira", "明"),
    ("Ema", "恵麻"),
    ("Nao", "直"),
    ("Maya", "真彩"),
    ("Daichi", "大地"),
    ("Kaito", "海斗"),
    ("Hinata", "陽向"),
    ("Haruki", "陽希"),
    ("Rina", "莉奈"),
    ("Sakura", "咲良"),
    ("Hikaru", "晃"),
    ("Mei", "芽依"),
    ("Kenta", "健太"),
    ("Yuto", "悠斗"),
    ("Koharu", "心春"),
    ("Shota", "翔太"),
    ("Naoe", "奈緒"),
    ("Hikari", "光"),
    ("Yuna", "結菜"),
    ("Takumi", "拓海"),
    ("Saki", "咲"),
    ("Tsubasa", "翼"),
    ("Koki", "光希"),
    ("Nanami", "七海"),
    ("Ayaka", "彩花"),
    ("Shun", "駿"),
    ("Itsuki", "樹"),
    ("Kaede", "楓"),
)
FAMILY_PAIRS = (
    ("Sato", "佐藤"),
    ("Suzuki", "鈴木"),
    ("Takahashi", "高橋"),
    ("Tanaka", "田中"),
    ("Ito", "伊藤"),
    ("Watanabe", "渡辺"),
    ("Yamamoto", "山本"),
    ("Nakamura", "中村"),
    ("Kato", "加藤"),
    ("Kobayashi", "小林"),
    ("Hayashi", "林"),
    ("Shimizu", "清水"),
    ("Mori", "森"),
    ("Abe", "阿部"),
    ("Ikeda", "池田"),
    ("Hashimoto", "橋本"),
    ("Ishikawa", "石川"),
    ("Yamashita", "山下"),
    ("Ogawa", "小川"),
    ("Ishii", "石井"),
    ("Hasegawa", "長谷川"),
    ("Goto", "後藤"),
    ("Okada", "岡田"),
    ("Fujita", "藤田"),
    ("Maeda", "前田"),
    ("Nakajima", "中島"),
    ("Murakami", "村上"),
    ("Kondo", "近藤"),
    ("Saito", "斎藤"),
    ("Sakamoto", "坂本"),
    ("Endo", "遠藤"),
    ("Aoki", "青木"),
    ("Fujii", "藤井"),
    ("Nishimura", "西村"),
)
GIVEN = tuple(pair[0] for pair in GIVEN_PAIRS)
GIVEN_JA = tuple(pair[1] for pair in GIVEN_PAIRS)
FAMILY = tuple(pair[0] for pair in FAMILY_PAIRS)
FAMILY_JA = tuple(pair[1] for pair in FAMILY_PAIRS)
GIVEN_PAIRS = DATA_GIVEN_PAIRS
GIVEN = tuple(pair[0] for pair in GIVEN_PAIRS)
GIVEN_JA = tuple(pair[1] for pair in GIVEN_PAIRS)
FAMILY_PAIRS = DATA_FAMILY_PAIRS
FAMILY = tuple(pair[0] for pair in FAMILY_PAIRS)
FAMILY_JA = tuple(pair[1] for pair in FAMILY_PAIRS)
DEPARTMENTS = (
    "Sales",
    "Engineering",
    "Operations",
    "Finance",
    "Customer Success",
    "Administration",
)
DEPARTMENTS_JA = ("営業", "開発", "運用", "経理", "カスタマーサポート", "総務")
ORG_STEMS = (
    "Northbridge",
    "Cedar",
    "Blueleaf",
    "Westport",
    "Aster",
    "Oakline",
    "Silverpine",
    "Harborview",
    "Summit",
    "Clearwater",
    "Redwood",
    "Meadowbrook",
    "Evergreen",
    "Stonehaven",
    "Brightwell",
    "Lakeshore",
    "Windward",
    "Pioneer",
    "Maplewood",
    "Granite",
    "Rivermark",
    "Eastfield",
    "Fairview",
    "Kingswell",
)
ORG_SUFFIXES = (
    "Systems",
    "Analytics",
    "Trading",
    "Logistics",
    "Works",
    "Labs",
    "Services",
    "Networks",
    "Consulting",
    "Supply",
    "Partners",
    "Digital",
)
ORG_STEMS_JA = (
    "青葉",
    "北辰",
    "東雲",
    "光洋",
    "三峰",
    "水明",
    "新港",
    "白峰",
    "大樹",
    "旭",
    "星海",
    "森泉",
    "山河",
    "日向",
    "千代田",
    "明星",
    "青空",
    "潮見",
    "桜川",
    "橘",
    "緑川",
    "高原",
    "清流",
    "東光",
)
ORG_SUFFIXES_JA = (
    "システムズ",
    "アナリティクス",
    "商事",
    "物流",
    "研究所",
    "テクノロジー",
    "サービス",
    "ネットワーク",
    "コンサルティング",
    "産業",
    "パートナーズ",
    "デジタル",
)
ORG_STEM_SLUGS_JA = dict(
    zip(
        ORG_STEMS_JA,
        (
            "aoba",
            "hokushin",
            "shinonome",
            "koyo",
            "mitsumine",
            "suimei",
            "shinko",
            "shiramine",
            "taiju",
            "asahi",
            "seikai",
            "moriizumi",
            "sanga",
            "hyuga",
            "chiyoda",
            "myojo",
            "aozora",
            "shiomi",
            "sakuragawa",
            "tachibana",
            "midorikawa",
            "takahara",
            "seiryu",
            "toko",
        ),
    )
)
ORG_SUFFIX_SLUGS_JA = dict(
    zip(
        ORG_SUFFIXES_JA,
        (
            "systems",
            "analytics",
            "trading",
            "logistics",
            "labs",
            "technologies",
            "services",
            "networks",
            "consulting",
            "industries",
            "partners",
            "digital",
        ),
    )
)
DATABASE_TEMPLATES = {
    "customers": {
        "table": "customers",
        "ja": ("BtoC顧客管理", "連絡先、地域に合う住所、登録日、ログイン履歴を含む架空データ"),
        "en": (
            "Consumer customer records",
            "Synthetic consumer contact, locality-matched address, registration and login details",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "name", "kind": "name"},
            {"name": "email", "kind": "email"},
            {"name": "phone", "kind": "phone"},
            {"name": "birth_date", "kind": "date"},
            {"name": "postal_code", "kind": "test_postal"},
            {"name": "prefecture", "kind": "text"},
            {"name": "city", "kind": "text"},
            {"name": "street_address", "kind": "address"},
            {"name": "created_at", "kind": "date"},
            {"name": "last_login", "kind": "datetime"},
            {"name": "is_deleted", "kind": "boolean"},
        ],
    },
    "cards": {
        "table": "card_accounts",
        "ja": (
            "カード台帳（番号なし）",
            "ブランド・名義・期限。カード番号やCVVは生成しません",
        ),
        "en": (
            "Card inventory",
            "Brand, holder and expiry; no PAN or CVV is generated",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "holder_name", "kind": "name"},
            {"name": "holder_email", "kind": "email"},
            {
                "name": "card_brand",
                "kind": "text",
                "values": ["Visa", "Mastercard", "JCB", "American Express"],
            },
            {"name": "card_reference", "kind": "card_reference"},
            {"name": "expiry", "kind": "card_expiry"},
            {"name": "billing_postal", "kind": "test_postal"},
            {
                "name": "account_status",
                "kind": "status",
                "values": ["active", "suspended", "expired"],
            },
            {"name": "updated_at", "kind": "date"},
        ],
    },
    "companies": {
        "table": "companies",
        "ja": ("企業管理", "企業・業界・従業員数・取引状況"),
        "en": (
            "Company directory",
            "Organizations, industries, size and relationship status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "company_name", "kind": "company"},
            {"name": "domain", "kind": "domain"},
            {
                "name": "industry",
                "kind": "text",
                "values": [
                    "Manufacturing",
                    "Retail",
                    "Software",
                    "Logistics",
                    "Professional services",
                ],
            },
            {"name": "employee_count", "kind": "integer", "min": 5, "max": 25000},
            {"name": "contact_name", "kind": "name"},
            {"name": "contact_email", "kind": "email"},
            {"name": "phone", "kind": "phone"},
            {"name": "account_status", "kind": "status"},
        ],
    },
    "passwords": {
        "table": "saved_logins",
        "ja": (
            "パスワード管理（無効な見本値）",
            "利用不能なダミー文字列のみ。実際の認証情報・ハッシュは生成しません",
        ),
        "en": (
            "Password vault samples",
            "Nonfunctional placeholders only; no real credentials or hashes",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "owner_name", "kind": "name"},
            {
                "name": "service_name",
                "kind": "text",
                "values": [
                    "Mail Console",
                    "Billing Workspace",
                    "Source Archive",
                    "Vendor Portal",
                    "Analytics Dashboard",
                ],
            },
            {"name": "login_url", "kind": "domain"},
            {"name": "username", "kind": "email"},
            {"name": "password", "kind": "credential_preview"},
            {
                "name": "vault_group",
                "kind": "text",
                "values": ["Work", "Finance", "Infrastructure", "Vendors"],
            },
            {"name": "last_rotated", "kind": "date"},
            {"name": "record_status", "kind": "status"},
        ],
    },
    "orders": {
        "table": "orders",
        "ja": ("注文管理", "顧客・商品・金額・配送状態"),
        "en": ("Order management", "Customers, items, amounts and fulfillment"),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "order_ref", "kind": "order_reference"},
            {"name": "customer_name", "kind": "name"},
            {"name": "customer_email", "kind": "email"},
            {
                "name": "item",
                "kind": "text",
                "values": [
                    "Annual Support",
                    "Field Kit",
                    "Data Migration",
                    "Service Renewal",
                    "Hardware Bundle",
                ],
            },
            {"name": "quantity", "kind": "integer", "min": 1, "max": 12},
            {"name": "unit_price", "kind": "decimal", "min": 25, "max": 2500},
            {"name": "total", "kind": "decimal", "min": 25, "max": 25000},
            {"name": "currency", "kind": "currency"},
            {
                "name": "order_status",
                "kind": "status",
                "values": ["pending", "processing", "shipped", "complete", "cancelled"],
            },
            {"name": "ordered_at", "kind": "date"},
        ],
    },
    "sales": {
        "table": "sales_transactions",
        "ja": (
            "\u58f2\u4e0a\u660e\u7d30",
            "\u9867\u5ba2\u30fb\u5546\u54c1\u30fb\u6570\u91cf\u30fb\u91d1\u984d\u30fb\u901a\u8ca8\u30fb\u8ca9\u58f2\u72b6\u6cc1\u306e\u67b6\u7a7a\u8a18\u9332",
        ),
        "en": (
            "Sales transactions",
            "Fictional customers, products, amounts, currency and sales status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "sale_ref", "kind": "sale_reference"},
            {"name": "customer_name", "kind": "name"},
            {"name": "customer_email", "kind": "email"},
            {
                "name": "product",
                "kind": "text",
                "values": [
                    "Annual Support",
                    "Field Kit",
                    "Data Migration",
                    "Service Renewal",
                    "Hardware Bundle",
                ],
            },
            {"name": "quantity", "kind": "integer", "min": 1, "max": 20},
            {"name": "unit_price", "kind": "decimal", "min": 25, "max": 2500},
            {"name": "total", "kind": "decimal", "min": 25, "max": 500000},
            {"name": "currency", "kind": "currency"},
            {
                "name": "sales_channel",
                "kind": "text",
                "values": ["Direct", "Partner", "Online", "Renewal"],
            },
            {
                "name": "sale_status",
                "kind": "status",
                "values": ["pending", "processing", "complete", "refunded"],
            },
            {"name": "sold_at", "kind": "date"},
        ],
    },
    "users": {
        "table": "user_accounts",
        "ja": (
            "\u30e6\u30fc\u30b6\u30fc\u7ba1\u7406",
            "\u8868\u793a\u540d\u30fb\u30ed\u30b0\u30a4\u30f3\u540d\u3092\u5206\u3051\u3001\u30ed\u30b0\u30a4\u30f3\u540d\u306f\u91cd\u8907\u3057\u306a\u3044\u67b6\u7a7a\u5024\u3092\u751f\u6210\u3057\u307e\u3059\u3002\u5b9f\u969b\u306b\u4f7f\u3048\u308b\u8a8d\u8a3c\u60c5\u5831\u306f\u542b\u307f\u307e\u305b\u3093",
        ),
        "en": (
            "User management",
            "Separate display names and unique synthetic login names, roles, account state, MFA and activity dates; no usable credentials",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "user_ref", "kind": "uuid"},
            {"name": "display_name", "kind": "name"},
            {"name": "username", "kind": "username"},
            {"name": "email", "kind": "email"},
            {
                "name": "role",
                "kind": "text",
                "values": [
                    "Administrator",
                    "Finance",
                    "Support",
                    "Developer",
                    "Read only",
                ],
            },
            {"name": "department", "kind": "department"},
            {
                "name": "account_status",
                "kind": "status",
                "values": ["active", "locked", "disabled", "invited"],
            },
            {
                "name": "mfa_status",
                "kind": "status",
                "values": ["enabled", "required", "pending"],
            },
            {"name": "created_at", "kind": "date"},
            {"name": "last_login", "kind": "datetime"},
        ],
    },
    "api_credentials": {
        "table": "api_credentials",
        "ja": (
            "\u0041\u0050\u0049\u8a8d\u8a3c\u60c5\u5831\u53f0\u5e33",
            "\u30b5\u30fc\u30d3\u30b9\u540d\u30fb\u62c5\u5f53\u8005\u30fb\u74b0\u5883\u30fb\u6a29\u9650\u7bc4\u56f2\u30fb\u30ed\u30fc\u30c6\u30fc\u30b7\u30e7\u30f3\u72b6\u6cc1\u3092\u8a18\u9332\u3059\u308b\u67b6\u7a7a\u30c7\u30fc\u30bf\u3002\u8a8d\u8a3c\u306b\u4f7f\u3048\u308b\u30ad\u30fc\u306f\u751f\u6210\u3057\u307e\u305b\u3093",
        ),
        "en": (
            "API credential inventory",
            "Fictional service credentials, owners, scopes and rotation metadata. Key previews are nonfunctional and cannot authenticate.",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "credential_ref", "kind": "uuid"},
            {
                "name": "service_name",
                "kind": "text",
                "values": [
                    "Billing API",
                    "Source Control",
                    "Object Storage",
                    "Analytics Gateway",
                    "Mail Relay",
                ],
            },
            {"name": "api_endpoint", "kind": "domain"},
            {"name": "owner_name", "kind": "name"},
            {"name": "owner_email", "kind": "email"},
            {
                "name": "environment",
                "kind": "text",
                "values": ["production", "staging", "recovery", "legacy"],
            },
            {
                "name": "access_scope",
                "kind": "text",
                "values": [
                    "read:reports",
                    "write:billing",
                    "read:objects",
                    "deploy:staging",
                    "admin:limited",
                ],
            },
            {"name": "key_preview", "kind": "credential_preview"},
            {"name": "created_at", "kind": "date"},
            {"name": "last_rotated", "kind": "date"},
            {"name": "last_used", "kind": "datetime"},
            {
                "name": "credential_status",
                "kind": "status",
                "values": ["active", "rotation_due", "revoked", "pending"],
            },
        ],
    },
    "invoices": {
        "table": "invoices",
        "ja": ("請求・支払", "請求先・小計・通貨・期限・入金状態"),
        "en": (
            "Invoices and payments",
            "Bill-to contacts, subtotal, currency, due dates and payment status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "invoice_ref", "kind": "invoice_reference"},
            {"name": "company", "kind": "company"},
            {"name": "billing_email", "kind": "email"},
            {"name": "subtotal", "kind": "decimal", "min": 100, "max": 5000000},
            {"name": "currency", "kind": "currency"},
            {"name": "issued_at", "kind": "date"},
            {"name": "due_at", "kind": "date"},
            {
                "name": "payment_status",
                "kind": "status",
                "values": ["open", "pending", "paid", "overdue", "void"],
            },
        ],
    },
    "employees": {
        "table": "employees",
        "ja": ("従業員・組織", "社員番号・部署・役職・在籍状況"),
        "en": (
            "Employees and teams",
            "Staff identifiers, departments, roles and status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "employee_ref", "kind": "uuid"},
            {"name": "name", "kind": "name"},
            {"name": "work_email", "kind": "email"},
            {"name": "department", "kind": "department"},
            {
                "name": "role",
                "kind": "text",
                "values": [
                    "Analyst",
                    "Engineer",
                    "Account Manager",
                    "Operations Lead",
                    "Administrator",
                ],
            },
            {
                "name": "office",
                "kind": "text",
                "values": ["Tokyo", "Osaka", "Remote", "Yokohama", "Nagoya"],
            },
            {"name": "started_at", "kind": "date"},
            {
                "name": "employment_status",
                "kind": "status",
                "values": ["onboarding", "active", "on_leave", "offboarded"],
            },
        ],
    },
    "vendors": {
        "table": "vendors",
        "ja": ("取引先・委託先", "会社・窓口・契約・リスク区分"),
        "en": (
            "Vendors and partners",
            "Organizations, contacts, contracts and review status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "vendor_name", "kind": "company"},
            {"name": "domain", "kind": "domain"},
            {"name": "contact_name", "kind": "name"},
            {"name": "contact_email", "kind": "email"},
            {
                "name": "service",
                "kind": "text",
                "values": [
                    "Cloud hosting",
                    "Payroll",
                    "Customer support",
                    "Analytics",
                    "Logistics",
                ],
            },
            {"name": "annual_cost", "kind": "decimal", "min": 1000, "max": 2000000},
            {
                "name": "risk_tier",
                "kind": "text",
                "values": ["low", "standard", "elevated"],
            },
            {"name": "reviewed_at", "kind": "date"},
        ],
    },
    "tickets": {
        "table": "support_tickets",
        "ja": ("問い合わせ・サポート", "受付内容・担当・優先度・解決状況"),
        "en": (
            "Support tickets",
            "Issue summaries, assignment, priority and resolution",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "ticket_ref", "kind": "uuid"},
            {"name": "requester_name", "kind": "name"},
            {"name": "requester_email", "kind": "email"},
            {
                "name": "subject",
                "kind": "text",
                "values": [
                    "Account access review",
                    "Invoice correction",
                    "Export request",
                    "Service availability",
                    "Profile update",
                ],
            },
            {"name": "priority", "kind": "text", "values": ["low", "normal", "high"]},
            {"name": "assigned_team", "kind": "department"},
            {
                "name": "ticket_status",
                "kind": "status",
                "values": ["open", "pending", "in_progress", "resolved", "closed"],
            },
            {"name": "opened_at", "kind": "datetime"},
        ],
    },
    "assets": {
        "table": "assets",
        "ja": ("在庫・資産", "資産番号・分類・保管場所・状態"),
        "en": (
            "Inventory and assets",
            "Asset references, categories, locations and status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "asset_ref", "kind": "uuid"},
            {
                "name": "asset_name",
                "kind": "text",
                "values": [
                    "Workstation",
                    "Network Switch",
                    "Test Device",
                    "Office Display",
                    "Storage Node",
                ],
            },
            {
                "name": "category",
                "kind": "text",
                "values": ["IT", "Facilities", "Network", "Lab"],
            },
            {
                "name": "location",
                "kind": "text",
                "values": ["Tokyo-3F", "Osaka-2F", "Remote", "Nagoya-1F"],
            },
            {"name": "purchase_cost", "kind": "decimal", "min": 50, "max": 800000},
            {"name": "assigned_to", "kind": "name"},
            {"name": "asset_status", "kind": "status"},
            {"name": "checked_at", "kind": "date"},
        ],
    },
    "cloud": {
        "table": "cloud_resources",
        "ja": ("クラウド・システム資産", "サービス・環境・文書用IP・運用状態"),
        "en": (
            "Cloud and system inventory",
            "Services, environments, documentation IPs and status",
        ),
        "columns": [
            {"name": "id", "kind": "id"},
            {"name": "resource_ref", "kind": "uuid"},
            {
                "name": "service_name",
                "kind": "text",
                "values": [
                    "Archive API",
                    "Reporting Worker",
                    "Object Store",
                    "Billing Queue",
                    "Identity Gateway",
                ],
            },
            {
                "name": "environment",
                "kind": "text",
                "values": ["production", "staging", "recovery", "legacy"],
            },
            {"name": "endpoint", "kind": "domain"},
            {"name": "documentation_ip", "kind": "documentation_ip"},
            {"name": "owner_email", "kind": "email"},
            {
                "name": "region",
                "kind": "text",
                "values": [
                    "ap-northeast-1",
                    "ap-northeast-3",
                    "us-west-2",
                    "eu-central-1",
                ],
            },
            {"name": "resource_status", "kind": "status"},
        ],
    },
}

TEMPLATE_VALUE_TRANSLATIONS = {
    "ja": {
        ("customers", "prefecture"): ["東京都", "神奈川県", "大阪府", "愛知県", "福岡県", "北海道", "埼玉県", "千葉県"],
        ("customers", "city"): ["新宿区", "世田谷区", "横浜市西区", "川崎市川崎区", "大阪市北区", "名古屋市中区", "福岡市中央区", "札幌市中央区", "さいたま市浦和区", "千葉市中央区"],
        ("api_credentials", "service_name"): [
            "\u8ab2\u91d1API",
            "\u30bd\u30fc\u30b9\u7ba1\u7406",
            "\u30aa\u30d6\u30b8\u30a7\u30af\u30c8\u4fdd\u7ba1",
            "\u5206\u6790\u30b2\u30fc\u30c8\u30a6\u30a7\u30a4",
            "\u30e1\u30fc\u30eb\u4e2d\u7d99",
        ],
        ("api_credentials", "environment"): [
            "\u672c\u756a",
            "\u691c\u8a3c",
            "\u707d\u5bb3\u5fa9\u65e7",
            "\u65e7\u74b0\u5883",
        ],
        ("companies", "industry"): [
            "製造",
            "小売",
            "ソフトウェア",
            "物流",
            "専門サービス",
        ],
        ("passwords", "service_name"): [
            "メール管理",
            "請求ワークスペース",
            "ソース保管庫",
            "取引先ポータル",
            "分析ダッシュボード",
        ],
        ("passwords", "vault_group"): ["業務", "経理", "インフラ", "取引先"],
        ("orders", "item"): [
            "年間サポート",
            "現地設置キット",
            "データ移行",
            "サービス更新",
            "ハードウェア一式",
        ],
        ("sales", "product"): [
            "年間サポート",
            "現地設置キット",
            "データ移行",
            "サービス更新",
            "ハードウェア一式",
        ],
        ("sales", "sales_channel"): ["直販", "販売代理店", "オンライン", "更新契約"],
        ("users", "role"): ["管理者", "経理", "サポート", "開発", "閲覧のみ"],
        ("employees", "role"): [
            "アナリスト",
            "エンジニア",
            "営業担当",
            "運用リーダー",
            "管理者",
        ],
        ("employees", "office"): ["東京", "大阪", "リモート", "横浜", "名古屋"],
        ("vendors", "service"): [
            "クラウド基盤",
            "給与計算",
            "顧客サポート",
            "分析",
            "物流",
        ],
        ("vendors", "risk_tier"): ["低", "標準", "高"],
        ("tickets", "subject"): [
            "アカウントアクセスの確認",
            "請求内容の修正",
            "データ出力の依頼",
            "サービス稼働状況",
            "プロフィールの更新",
        ],
        ("tickets", "priority"): ["低", "通常", "高"],
        ("assets", "asset_name"): [
            "業務用端末",
            "ネットワークスイッチ",
            "試験用機器",
            "オフィスディスプレイ",
            "ストレージノード",
        ],
        ("assets", "category"): ["IT機器", "施設", "ネットワーク", "検証環境"],
        ("assets", "location"): ["東京・3階", "大阪・2階", "リモート", "名古屋・1階"],
        ("cloud", "service_name"): [
            "保管API",
            "レポート処理基盤",
            "オブジェクト保管庫",
            "請求キュー",
            "認証ゲートウェイ",
        ],
        ("cloud", "environment"): ["本番", "検証", "災害復旧", "旧環境"],
    },
    "en": {
        ("customers", "prefecture"): ["Tokyo", "Kanagawa", "Osaka", "Aichi", "Fukuoka", "Hokkaido", "Saitama", "Chiba"],
        ("customers", "city"): ["Shinjuku-ku", "Setagaya-ku", "Yokohama Nishi-ku", "Kawasaki-ku", "Osaka Kita-ku", "Nagoya Naka-ku", "Fukuoka Chuo-ku", "Sapporo Chuo-ku", "Saitama Urawa-ku", "Chiba Chuo-ku"],
    },
}

# Real postal-code/locality pairs checked against Japan Post's published data.
# The locality is public geographic data; street numbers are generated separately and are synthetic.
CUSTOMER_ADDRESS_PROFILES = (
    ("東京都", "新宿区", "Tokyo", "Shinjuku-ku", "160-0022", "新宿", "Shinjuku", 7),
    ("東京都", "世田谷区", "Tokyo", "Setagaya-ku", "154-0017", "世田谷", "Setagaya", 4),
    ("神奈川県", "横浜市西区", "Kanagawa", "Yokohama Nishi-ku", "220-0012", "みなとみらい", "Minato Mirai", 7),
    ("神奈川県", "川崎市川崎区", "Kanagawa", "Kawasaki-ku", "210-0006", "砂子", "Isago", 3),
    ("大阪府", "大阪市北区", "Osaka", "Osaka Kita-ku", "530-0001", "梅田", "Umeda", 3),
    ("愛知県", "名古屋市中区", "Aichi", "Nagoya Naka-ku", "460-0008", "栄", "Sakae", 5),
    ("福岡県", "福岡市中央区", "Fukuoka", "Fukuoka Chuo-ku", "810-0001", "天神", "Tenjin", 6),
    ("北海道", "札幌市中央区", "Hokkaido", "Sapporo Chuo-ku", "060-0042", "大通西", "Odori Nishi", 19),
    ("埼玉県", "さいたま市浦和区", "Saitama", "Saitama Urawa-ku", "330-0061", "常盤", "Tokiwa", 10),
    ("千葉県", "千葉市中央区", "Chiba", "Chiba Chuo-ku", "260-0013", "中央", "Chuo", 4),
)

CLOUD_SERVICE_SLUGS_JA = {
    "保管API": "archive-api",
    "レポート処理基盤": "reporting-worker",
    "オブジェクト保管庫": "object-store",
    "請求キュー": "billing-queue",
    "認証ゲートウェイ": "identity-gateway",
}
CLOUD_ENVIRONMENT_SLUGS_JA = {
    "本番": "production",
    "検証": "staging",
    "災害復旧": "recovery",
    "旧環境": "legacy",
}


def _template_columns(template_id, language):
    columns = deepcopy(DATABASE_TEMPLATES[template_id]["columns"])
    translations = TEMPLATE_VALUE_TRANSLATIONS.get(language, {})
    for column in columns:
        values = translations.get((template_id, column["name"]))
        if values:
            column["values"] = list(values)
    return columns


DATABASE_COLUMN_LABELS_JA = {
    "is_deleted": "\u8ad6\u7406\u524a\u9664\u30d5\u30e9\u30b0",
    "birth_date": "生年月日",
    "postal_code": "郵便番号",
    "street_address": "番地",
    "prefecture": "都道府県",
    "city": "市区町村",
    "last_login": "最終ログイン日時",
    "credential_ref": "\u8a8d\u8a3c\u60c5\u5831\u53c2\u7167ID",
    "key_preview": "\u8a8d\u8a3c\u306b\u4f7f\u3048\u306a\u3044\u5408\u6210\u30ad\u30fc\u898b\u672c",
    "access_scope": "\u6a29\u9650\u7bc4\u56f2",
    "last_used": "\u6700\u7d42\u4f7f\u7528\u65e5\u6642",
    "credential_status": "\u8a8d\u8a3c\u60c5\u5831\u306e\u72b6\u614b",
    "api_endpoint": "API\u63a5\u7d9a\u5148URL\uff08example.invalid\uff09",
    "account_status": "アカウント状態",
    "annual_cost": "年間費用",
    "asset_name": "資産名",
    "asset_ref": "資産参照番号",
    "asset_status": "資産状態",
    "assigned_team": "担当チーム",
    "assigned_to": "利用者",
    "billing_email": "請求先メールアドレス",
    "billing_postal": "請求先郵便番号",
    "card_brand": "カードブランド",
    "card_reference": "決済方法参照ID",
    "category": "分類",
    "checked_at": "確認日",
    "company": "会社",
    "company_name": "企業名",
    "contact_email": "担当者メールアドレス",
    "contact_name": "担当者名",
    "created_at": "作成日時",
    "currency": "通貨",
    "customer_email": "顧客メールアドレス",
    "customer_name": "顧客名",
    "department": "部署",
    "display_name": "表示名",
    "documentation_ip": "文書用IPアドレス",
    "domain": "ドメイン",
    "due_at": "支払期限",
    "email": "メールアドレス",
    "employee_count": "従業員数",
    "employee_ref": "従業員参照番号",
    "employment_status": "在籍状況",
    "endpoint": "接続先ドメイン",
    "environment": "環境",
    "expiry": "有効期限",
    "holder_email": "名義人メールアドレス",
    "holder_name": "名義人",
    "id": "ID",
    "industry": "業種",
    "invoice_ref": "請求書番号",
    "issued_at": "発行日",
    "item": "商品",
    "last_contact": "最終連絡日",
    "last_login": "最終ログイン日時",
    "last_rotated": "最終更新日",
    "location": "保管場所",
    "login_url": "ログインページ",
    "mfa_status": "多要素認証の状態",
    "name": "氏名",
    "office": "拠点",
    "opened_at": "受付日時",
    "order_ref": "注文番号",
    "order_status": "注文状況",
    "ordered_at": "注文日",
    "owner_email": "管理者メールアドレス",
    "owner_name": "利用者名",
    "password": "パスワード例（使用不可）",
    "payment_status": "支払状況",
    "phone": "電話番号",
    "priority": "優先度",
    "product": "商品",
    "purchase_cost": "購入費用",
    "quantity": "数量",
    "record_status": "レコード状態",
    "region": "リージョン",
    "requester_email": "問い合わせ者メールアドレス",
    "requester_name": "問い合わせ者名",
    "resource_ref": "リソース参照番号",
    "resource_status": "リソース状態",
    "reviewed_at": "確認日",
    "risk_tier": "リスク区分",
    "role": "役割",
    "sale_ref": "売上番号",
    "sale_status": "販売状況",
    "sales_channel": "販売経路",
    "service": "サービス",
    "service_name": "サービス名",
    "sold_at": "販売日",
    "started_at": "開始日",
    "status": "状態",
    "subject": "件名",
    "subtotal": "小計",
    "ticket_ref": "問い合わせ番号",
    "ticket_status": "問い合わせ対応状況",
    "total": "合計金額",
    "unit_price": "単価",
    "updated_at": "更新日時",
    "user_ref": "ユーザー参照番号",
    "username": "ログイン名",
    "vault_group": "保管グループ",
    "vendor_name": "取引先名",
    "work_email": "会社メールアドレス",
}
DATABASE_COLUMN_LABELS_EN = {
    "is_deleted": "Soft-delete flag",
    "birth_date": "Date of birth",
    "postal_code": "Postal code",
    "street_address": "Street address",
    "prefecture": "Prefecture",
    "city": "City / ward",
    "created_at": "Registration date",
    "last_login": "Last login date and time",
    "id": "ID",
    "credential_ref": "Credential reference",
    "key_preview": "Nonfunctional credential preview",
    "access_scope": "Access scope",
    "last_rotated": "Last rotated",
    "last_used": "Last used",
    "credential_status": "Credential status",
    "api_endpoint": "API endpoint URL (example.invalid)",
    "phone": "Phone number",
    "mfa_status": "MFA status",
    "documentation_ip": "Documentation IP address",
    "login_url": "Login URL",
    "card_reference": "Payment method reference",
    "billing_postal": "Billing postal code",
    "employee_ref": "Employee reference",
    "resource_ref": "Resource reference",
    "user_ref": "User reference",
    "asset_ref": "Asset reference",
    "order_ref": "Order reference",
    "sale_ref": "Sale reference",
    "ticket_ref": "Ticket reference",
    "invoice_ref": "Invoice reference",
    "unit_price": "Unit price",
}
DATABASE_COLUMN_LABEL_OVERRIDES = {
    "ja": {
        "customers": {"postal_code": "郵便番号（地域対応）", "created_at": "会員登録日"},
        "passwords": {"username": "ログイン名", "last_rotated": "パスワード最終更新日"},
        "users": {"username": "ユーザー名", "role": "アクセス権限"},
        "employees": {"role": "役職", "started_at": "入社日"},
        "invoices": {"company": "請求先企業"},
        "vendors": {"service": "委託サービス", "reviewed_at": "取引先審査日"},
        "assets": {"checked_at": "棚卸確認日"},
    },
    "en": {
        "customers": {"postal_code": "Postal code (locality-matched)", "created_at": "Registration date"},
        "passwords": {
            "username": "Login name",
            "last_rotated": "Password last updated",
        },
        "users": {"username": "Username", "role": "Access role"},
        "employees": {"role": "Job title", "started_at": "Hire date"},
        "invoices": {"company": "Bill-to company"},
        "vendors": {
            "service": "Contracted service",
            "reviewed_at": "Vendor review date",
        },
        "assets": {"checked_at": "Inventory check date"},
    },
}

DATABASE_TEMPLATE_PRIORITY = ("customers", "sales", "users", "api_credentials")
TEMPLATE_DESCRIPTION_SUFFIXES = {
    "orders": {
        "ja": " 顧客名とメールは複数の注文で再利用されることがあります。単価と合計額は商品・数量に合わせ、JPYは整数、その他の通貨は小数2桁で生成します。",
        "en": " Fictional customer names and email addresses can recur across orders. Unit prices and totals match the item and quantity; JPY uses whole numbers and other currencies use two decimal places.",
    },
    "sales": {
        "ja": " 顧客名とメールは複数の取引で再利用されることがあります。単価と合計額は商品・数量に合わせ、JPYは整数、その他の通貨は小数2桁で生成します。",
        "en": " Fictional customer names and email addresses can recur across transactions. Unit prices and totals match the product and quantity; JPY uses whole numbers and other currencies use two decimal places.",
    },
    "invoices": {
        "ja": " 発行日・支払期限・入金状況を対応させます。未払いは期限前、期限超過は過去の支払期限になります。",
        "en": " Issue dates, due dates and payment status are related. Open items have future due dates; overdue items have past due dates.",
    },
    "companies": {
        "ja": " 会社名とドメインは対応し、ドメインは通信できない予約済み`.invalid`配下になります。",
        "en": " Company names map to matching domains under the reserved, non-routable `.invalid` namespace.",
    },
    "api_credentials": {
        "ja": " \u63a5\u7d9a\u5148\u306f\u4e88\u7d04\u6e08\u307f\u306e\u4f7f\u7528\u4e0d\u53ef\u306a.example.invalid\u3067\u3001\u751f\u6210\u5668\u306f\u63a5\u7d9a\u3057\u307e\u305b\u3093\u3002\u76e3\u8996URL\u3092\u6307\u5b9a\u3057\u305f\u5834\u5408\u306f\u63a5\u7d9a\u5148\u6b04\u306e\u3044\u305a\u308c\u304b1\u4ef6\u3092\u7f6e\u304d\u63db\u3048\u307e\u3059\u3002\u30ad\u30fc\u898b\u672c\u306f\u67b6\u7a7a\u306e\u8868\u793a\u7528\u6587\u5b57\u5217\u3067\u3042\u308a\u3001\u5b9f\u969b\u306e\u30b5\u30fc\u30d3\u30b9\u3078\u306e\u8a8d\u8a3c\u3084\u63a5\u7d9a\u306b\u306f\u4f7f\u3048\u307e\u305b\u3093\u3002\u66f4\u65b0\u671f\u9650\u304c\u8fd1\u3044\u72b6\u614b\u3067\u306f\u6700\u7d42\u66f4\u65b0\u65e5\u3092\u53e4\u304f\u3057\u3001\u6700\u7d42\u4f7f\u7528\u65e5\u306f\u66f4\u65b0\u65e5\u3088\u308a\u5f8c\u306b\u8a2d\u5b9a\u3057\u307e\u3059\u3002",
        "en": " Endpoints use reserved, non-routable `.invalid` hosts and are never requested by the generator; a supplied canary URL replaces one endpoint value. Key previews cannot authenticate to any service. Rotation-due records have older rotation dates; last-used timestamps follow the recorded rotation date.",
    },
    "users": {
        "ja": " 招待中アカウントの最終ログインは空欄です。その他のログイン日時は作成日以降で、MFA状態もアカウント状態に合わせます。",
        "en": " Invited accounts have no last-login time. Other login times follow account creation, and MFA status is matched to the account state.",
    },
    "employees": {
        "ja": " 雇用状態に応じて入社日の範囲を変え、社員番号はUUID形式で生成します。",
        "en": " Hire-date ranges reflect employment status, and employee references use UUIDs.",
    },
    "cards": {
        "ja": " 名義人が複数のカード記録に現れることがあります。名前とメールは対応します。",
        "en": " A cardholder can recur across records with a consistent name and email address.",
    },
    "passwords": {
        "ja": " 同じ所有者が複数の保管項目に現れることがあります。所有者名とログイン名は対応します。",
        "en": " An owner can recur across entries with a consistent owner name and login name.",
    },
    "tickets": {
        "ja": " 同じ問い合わせ元が複数のチケットに現れることがあります。名前とメールは対応し、受付日時は対応状況に合わせます。",
        "en": " Requesters can recur across tickets with matching names and email addresses; opened times reflect ticket status.",
    },
    "vendors": {
        "ja": " リスク区分に応じて年間費用の範囲と審査日の新しさを変えます。会社名とドメインも対応します。",
        "en": " Risk tiers affect annual-cost ranges and review recency. Vendor names and domains also match.",
    },
    "assets": {
        "ja": " 資産名に合う分類があれば組み合わせ、状態に応じて最終棚卸日の古さを変えます。",
        "en": " Asset names are paired with matching categories when available; status affects inventory-check recency.",
    },
    "cloud": {
        "ja": " 接続先はサービス名と環境名に対応した`.invalid`ドメインです。名前解決・通信はしません。",
        "en": " Endpoints reflect the selected service and environment under `.invalid`; the generator never resolves or contacts them.",
    },
}


def _template_columns_with_labels(template_id, language):
    language = language if language in ("ja", "en") else "ja"
    columns = _template_columns(template_id, language)
    for column in columns:
        column_name = column["name"]
        base_label = (
            DATABASE_COLUMN_LABELS_JA.get(column_name, column_name)
            if language == "ja"
            else DATABASE_COLUMN_LABELS_EN.get(
                column_name, column_name.replace("_", " ").title()
            )
        )
        column["label"] = (
            DATABASE_COLUMN_LABEL_OVERRIDES[language]
            .get(template_id, {})
            .get(column_name, base_label)
        )
    return columns


def ensure_canary_endpoint_column(columns, field, label, preferred=()):
    """Return a natural URL field, reusing a matching endpoint where available."""
    for candidate in (*preferred, field):
        index = next(
            (
                i
                for i, column in enumerate(columns)
                if column["name"].casefold() == candidate.casefold()
                and column["kind"] == "domain"
            ),
            None,
        )
        if index is not None:
            columns[index]["label"] = label
            return index, columns[index]["name"]
    columns.append({"name": field, "kind": "domain", "label": label})
    return len(columns) - 1, field


def public_templates(language="ja"):
    language = language if language in ("ja", "en") else "ja"
    templates = []
    # Keep the common CRM, sales and user-management presets easy to find in
    # both the quick-create and detailed selectors. Preserve declaration order
    # for all remaining templates, including any future additions.
    ordered_keys = (
        *(key for key in DATABASE_TEMPLATE_PRIORITY if key in DATABASE_TEMPLATES),
        *(key for key in DATABASE_TEMPLATES if key not in DATABASE_TEMPLATE_PRIORITY),
    )
    for key in ordered_keys:
        spec = DATABASE_TEMPLATES[key]
        columns = _template_columns_with_labels(key, language)
        example_row = next(records(columns, 1, language))
        templates.append(
            {
                "id": key,
                "table": spec["table"],
                "label": spec[language][0],
                "description": spec[language][1]
                + TEMPLATE_DESCRIPTION_SUFFIXES.get(key, {}).get(language, ""),
                "columns": columns,
                "example_row": example_row,
            }
        )
    return templates


def validate_schema(settings, language="ja"):
    table = identifier(settings.get("table", "customers"), language)
    raw = settings.get("columns", DEFAULT_COLUMNS)
    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
        raise ValueError(translate("columns_error", language))
    columns, names = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(translate("columns_error", language))
        name = identifier(item.get("name"), language)
        kind = item.get("kind")
        if name.lower() in names or not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(translate("columns_error", language))
        allowed = {"name", "kind"}
        if kind in ("integer", "decimal"):
            allowed.update(("min", "max"))
        if kind in ("status", "text", "company", "department"):
            allowed.add("values")
        if any(not isinstance(key, str) for key in item) or item.keys() - allowed:
            raise ValueError(translate("columns_error", language))
        names.add(name.lower())
        column = {"name": name, "kind": kind}
        if kind in ("integer", "decimal"):
            defaults = {"quantity": (1, 100), "unit_price": (25, 2500)}
            default_low, default_high = defaults.get(name.casefold(), (0, 100000))
            low, high = item.get("min", default_low), item.get("max", default_high)
            if (
                any(
                    isinstance(v, bool)
                    or not isinstance(v, (float, int))
                    or abs(v) > 1e12
                    or (isinstance(v, float) and not math.isfinite(v))
                    for v in (low, high)
                )
                or low > high
                or (kind == "integer" and any(int(v) != v for v in (low, high)))
            ):
                raise ValueError(translate("range_error", language))
            column.update(min=low, max=high)
        if "values" in item:
            values = item["values"]
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 50
                or kind not in ("status", "text", "company", "department")
            ):
                raise ValueError(translate("values_error", language))
            column["values"] = [synthetic_candidate(v, language) for v in values]
            if not all(column["values"]):
                raise ValueError(translate("values_error", language))
        columns.append(column)
    quantity_column = next(
        (column for column in columns if column["name"].casefold() == "quantity"), None
    )
    if (
        quantity_column
        and quantity_column["kind"] == "integer"
        and quantity_column["min"] < 1
    ):
        raise ValueError(translate("quantity_error", language))
    return table, columns


def synthetic_company_domain(company):
    normalized = re.sub(r"[\W_]+", "-", company.casefold(), flags=re.UNICODE).strip("-")
    digest = hashlib.sha256(company.encode("utf-8")).hexdigest()[:8]
    builtin_slug = ""
    if company.endswith("株式会社"):
        body = company[: -len("株式会社")]
        for japanese_stem in sorted(ORG_STEM_SLUGS_JA, key=len, reverse=True):
            if body.startswith(japanese_stem):
                japanese_suffix = body[len(japanese_stem) :]
                if japanese_suffix in ORG_SUFFIX_SLUGS_JA:
                    builtin_slug = f"{ORG_STEM_SLUGS_JA[japanese_stem]}-{ORG_SUFFIX_SLUGS_JA[japanese_suffix]}"
                    break
    if builtin_slug:
        stem = builtin_slug
    else:
        try:
            stem = normalized.encode("idna").decode("ascii").lower()
        except UnicodeError:
            stem = ""
    if not stem:
        stem = "org-" + digest
    elif len(stem) > 54:
        # Keep the organization mapping stable while respecting the 63-byte
        # DNS label limit. The digest distinguishes truncated names.
        stem = stem[:54].rstrip("-") + "-" + digest
    return f"{stem}.example.invalid"


def records(columns, rows, language="en"):
    rng = secrets.SystemRandom()
    japanese = language == "ja"
    today = date.today()
    now = datetime.now().replace(microsecond=0)
    total_name_combinations = len(GIVEN) * len(FAMILY)
    name_pair_count = min(rows, total_name_combinations)
    name_pairs = [
        divmod(index, len(FAMILY))
        for index in rng.sample(range(total_name_combinations), k=name_pair_count)
    ]
    organization_pool = [
        f"{stem} {suffix}" for stem in ORG_STEMS for suffix in ORG_SUFFIXES
    ]
    if japanese:
        organization_pool = [
            f"{stem}{suffix}株式会社"
            for stem in ORG_STEMS_JA
            for suffix in ORG_SUFFIXES_JA
        ]
    rng.shuffle(organization_pool)
    # Contact-oriented tables usually contain several people from the same
    # organizations. Reuse a bounded pool for generic organization columns,
    # while directory-style name columns below remain unique per row.
    contact_organization_count = min(
        len(organization_pool), max(5, min(40, (rows + 4) // 5))
    )
    contact_organization_pool = organization_pool[:contact_organization_count]
    organization_index = 0
    used_usernames = set()
    used_phone_numbers = set()

    def japanese_phone_number():
        area_codes = (
            ("03", 4), ("06", 4), ("011", 3), ("022", 3), ("045", 3),
            ("052", 3), ("075", 3), ("078", 3), ("082", 3), ("092", 3),
        )
        while True:
            if rng.random() < 0.8:
                number = (
                    f"{rng.choice(('070', '080', '090'))}-"
                    f"{rng.randrange(10000):04d}-{rng.randrange(10000):04d}"
                )
            else:
                area_code, exchange_digits = rng.choice(area_codes)
                subscriber_digits = 10 - len(area_code) - exchange_digits
                exchange_minimum = 2 * 10 ** (exchange_digits - 1)
                number = (
                    f"{area_code}-{rng.randint(exchange_minimum, 10 ** exchange_digits - 1):0{exchange_digits}d}-"
                    f"{rng.randrange(10 ** subscriber_digits):0{subscriber_digits}d}"
                )
            if number not in used_phone_numbers:
                used_phone_numbers.add(number)
                return number
    company_columns = [column for column in columns if column["kind"] == "company"]
    columns_by_name = {column["name"].lower(): column for column in columns}
    reusable_identity_pairs = (
        ("customer_name", "customer_email"),
        ("requester_name", "requester_email"),
        ("holder_name", "holder_email"),
        ("owner_name", "username"),
        ("owner_name", "owner_email"),
    )
    reuse_person_profiles = any(
        columns_by_name.get(name) is not None
        and columns_by_name[name]["kind"] == "name"
        and columns_by_name.get(email) is not None
        and columns_by_name[email]["kind"] == "email"
        for name, email in reusable_identity_pairs
    )
    person_profile_count = (
        min(500, len(name_pairs), max(5, rows // 3)) if reuse_person_profiles else 0
    )
    person_organization_profiles = {}
    issued_column = columns_by_name.get("issued_at")
    due_column = columns_by_name.get("due_at")
    invoice_status_column = columns_by_name.get("payment_status")
    card_expiry_column = columns_by_name.get("expiry")
    card_status_column = columns_by_name.get("account_status")
    order_status_column = columns_by_name.get("order_status") or columns_by_name.get(
        "sale_status"
    )
    ordered_at_column = columns_by_name.get("ordered_at") or columns_by_name.get(
        "sold_at"
    )
    order_item_column = columns_by_name.get("item") or columns_by_name.get("product")
    order_quantity_column = columns_by_name.get("quantity")
    order_unit_price_column = columns_by_name.get("unit_price")
    order_total_column = columns_by_name.get("total")
    vendor_risk_column = columns_by_name.get("risk_tier")
    vendor_cost_column = columns_by_name.get("annual_cost")
    vendor_review_column = columns_by_name.get("reviewed_at")
    ticket_status_column = columns_by_name.get("ticket_status")
    ticket_opened_column = columns_by_name.get("opened_at")
    asset_status_column = columns_by_name.get("asset_status")
    asset_checked_column = columns_by_name.get("checked_at")
    asset_name_column = columns_by_name.get("asset_name")
    asset_category_column = columns_by_name.get("category")
    cloud_service_column = columns_by_name.get("service_name")
    cloud_environment_column = columns_by_name.get("environment")
    cloud_endpoint_column = columns_by_name.get("endpoint")
    employee_status_column = columns_by_name.get("employment_status")
    employee_started_column = columns_by_name.get("started_at")
    user_status_column = columns_by_name.get("account_status")
    user_created_column = columns_by_name.get("created_at")
    user_last_login_column = columns_by_name.get("last_login")
    user_mfa_column = columns_by_name.get("mfa_status")
    credential_status_column = columns_by_name.get("credential_status")
    credential_created_column = columns_by_name.get("created_at")
    credential_rotated_column = columns_by_name.get("last_rotated")
    credential_last_used_column = columns_by_name.get("last_used")
    customer_created_column = columns_by_name.get("created_at")
    customer_deleted_column = columns_by_name.get("is_deleted")
    currency_column = next(
        (
            column
            for column in columns
            if column["name"].casefold() == "currency"
            and (column["kind"] == "currency" or "values" in column)
        ),
        None,
    )
    order_feasibility_cache = {}
    for i in range(1, rows + 1):
        customer_lifecycle_values = {}
        if (
            customer_created_column
            and customer_created_column.get("kind") == "date"
            and customer_deleted_column
            and customer_deleted_column.get("kind") == "boolean"
        ):
            account_age_days = rng.randint(0, 3650)
            customer_lifecycle_values = {
                "created_at": (today - timedelta(days=account_age_days)).isoformat(),
                # Soft deletion stays uncommon, with older accounts more likely
                # to be deleted: about 0.1% for new accounts up to 5% at 10 years.
                "is_deleted": rng.random() < (0.001 + 0.049 * account_age_days / 3650),
            }
            last_login_column = columns_by_name.get("last_login")
            if last_login_column and last_login_column.get("kind") == "datetime":
                customer_lifecycle_values["last_login"] = (
                    now - timedelta(days=rng.randint(0, account_age_days),
                                    seconds=rng.randrange(86400))
                ).isoformat()
        customer_address_values = {}
        prefecture_column = columns_by_name.get("prefecture")
        city_column = columns_by_name.get("city")
        postal_column = columns_by_name.get("postal_code")
        if prefecture_column and city_column and postal_column:
            prefecture_candidates = prefecture_column.get("values")
            city_candidates = city_column.get("values")
            eligible_profiles = [
                profile
                for profile in CUSTOMER_ADDRESS_PROFILES
                if (not prefecture_candidates or profile[0 if japanese else 2] in prefecture_candidates)
                and (not city_candidates or profile[1 if japanese else 3] in city_candidates)
            ]
            if eligible_profiles:
                profile = rng.choice(eligible_profiles)
                chome = rng.randint(1, profile[7])
                block = rng.randint(1, 30)
                building = rng.randint(1, 25)
                customer_address_values = {
                    "prefecture": profile[0 if japanese else 2],
                    "city": profile[1 if japanese else 3],
                    "postal_code": profile[4],
                    "street_address": (
                        f"{profile[5]}{chome}丁目{block}-{building}"
                        if japanese
                        else f"{profile[6]} {chome}-{block}-{building}"
                    ),
                }
        if currency_column:
            currency_values = currency_column.get("values", ("JPY", "USD", "EUR"))
            row_currency = rng.choice(currency_values)
        else:
            row_currency = None
        if reuse_person_profiles:
            # Related records reuse plausible fictional identities instead
            # of inventing a new person for every transaction or ticket.
            person_profile_index = rng.randrange(person_profile_count)
            given_index, family_index = name_pairs[person_profile_index]
        elif i <= len(name_pairs):
            given_index, family_index = name_pairs[i - 1]
        else:
            given_index, family_index = (
                rng.randrange(len(GIVEN)),
                rng.randrange(len(FAMILY)),
            )
        given = GIVEN_JA[given_index] if japanese else GIVEN[given_index]
        family = FAMILY_JA[family_index] if japanese else FAMILY[family_index]
        email_given, email_family = GIVEN[given_index], FAMILY[family_index]
        company_values = {}
        for column in company_columns:
            column_key = column["name"].casefold()
            if (
                reuse_person_profiles
                and "values" not in column
                and column_key
                in ("company", "organization", "employer", "customer_company")
            ):
                # Keep a recurring fictional contact attached to the same
                # organization so their email domain remains consistent too.
                if person_profile_index not in person_organization_profiles:
                    person_organization_profiles[person_profile_index] = rng.choice(
                        contact_organization_pool
                    )
                company_values[column["name"]] = person_organization_profiles[
                    person_profile_index
                ]
            elif "values" in column:
                company_values[column["name"]] = rng.choice(column["values"])
            elif column_key in (
                "company",
                "organization",
                "employer",
                "customer_company",
            ):
                company_values[column["name"]] = rng.choice(contact_organization_pool)
            elif column["name"].casefold() in (
                "company_name",
                "vendor_name",
                "organization_name",
                "legal_name",
            ):
                if organization_index < len(organization_pool):
                    company_values[column["name"]] = organization_pool[
                        organization_index
                    ]
                else:
                    base_name = organization_pool[
                        organization_index % len(organization_pool)
                    ]
                    variant = organization_index // len(organization_pool) + 1
                    suffix = f"第{variant}事業所" if japanese else f"Group {variant}"
                    company_values[column["name"]] = f"{base_name} {suffix}"
                organization_index += 1
            else:
                company_values[column["name"]] = rng.choice(organization_pool)
        associated_company = next(iter(company_values.values()), None)
        invoice_dates, invoice_status = {}, None
        if (
            issued_column
            and due_column
            and issued_column["kind"] == due_column["kind"] == "date"
            and invoice_status_column
            and invoice_status_column["kind"] == "status"
        ):
            status_values = invoice_status_column.get(
                "values", ("open", "pending", "paid", "overdue", "void")
            )
            invoice_status = rng.choice(status_values)
            status_key = str(invoice_status).casefold()
            if status_key == "overdue":
                due_date = today - timedelta(days=rng.randint(1, 120))
                issued_date = due_date - timedelta(days=rng.randint(15, 60))
            elif status_key in ("open", "pending"):
                issued_date = today - timedelta(days=rng.randint(0, 21))
                due_date = max(
                    today + timedelta(days=1),
                    issued_date + timedelta(days=rng.randint(14, 45)),
                )
            elif status_key == "paid":
                issued_date = today - timedelta(days=rng.randint(45, 730))
                due_date = issued_date + timedelta(days=30)
            else:
                issued_date = today - timedelta(days=rng.randint(0, 730))
                due_date = issued_date + timedelta(days=30)
            invoice_dates = {
                "issued_at": issued_date.isoformat(),
                "due_at": due_date.isoformat(),
            }
        card_values = {}
        if (
            card_expiry_column
            and card_expiry_column["kind"] == "card_expiry"
            and card_status_column
            and card_status_column["kind"] == "status"
        ):
            status_values = card_status_column.get(
                "values", ("active", "suspended", "expired")
            )
            card_status = rng.choice(status_values)
            month_offset = rng.randint(1, 36) * (
                -1 if str(card_status).casefold() == "expired" else 1
            )
            absolute_month = today.year * 12 + today.month - 1 + month_offset
            expiry_month = absolute_month % 12 + 1
            expiry_year = (absolute_month // 12) % 100
            card_values = {
                "account_status": card_status,
                "expiry": f"{expiry_month:02d}/{expiry_year:02d}",
            }
        order_values = {}
        vendor_values = {}
        if (
            vendor_risk_column
            and vendor_risk_column.get("kind") == "text"
            and vendor_risk_column.get("values")
            and vendor_cost_column
            and vendor_cost_column.get("kind") == "decimal"
        ):
            risk_tier = rng.choice(vendor_risk_column["values"])
            risk_key = {
                "low": "low",
                "standard": "standard",
                "elevated": "elevated",
                "低": "low",
                "標準": "standard",
                "高": "elevated",
            }.get(str(risk_tier).casefold(), str(risk_tier).casefold())
            risk_cost_ranges = {
                "low": (1000, 100000),
                "standard": (10000, 500000),
                "elevated": (50000, 2000000),
            }
            cost_min, cost_max = (
                float(vendor_cost_column["min"]),
                float(vendor_cost_column["max"]),
            )
            tier_min, tier_max = risk_cost_ranges.get(risk_key, (cost_min, cost_max))
            bounded_min, bounded_max = max(cost_min, tier_min), min(cost_max, tier_max)
            if 0 < bounded_min <= bounded_max:
                annual_cost = round(
                    math.exp(rng.uniform(math.log(bounded_min), math.log(bounded_max))),
                    2,
                )
                vendor_values["annual_cost"] = min(
                    bounded_max, max(bounded_min, annual_cost)
                )
            vendor_values["risk_tier"] = risk_tier
            if vendor_review_column and vendor_review_column.get("kind") == "date":
                review_age = {
                    "low": (90, 730),
                    "standard": (30, 365),
                    "elevated": (0, 90),
                }.get(risk_key, (0, 730))
                vendor_values["reviewed_at"] = (
                    today - timedelta(days=rng.randint(*review_age))
                ).isoformat()
        if (
            order_item_column
            and order_item_column.get("kind") == "text"
            and order_item_column.get("values")
            and order_quantity_column
            and order_quantity_column.get("kind") == "integer"
            and order_total_column
            and order_total_column.get("kind") == "decimal"
        ):
            price_ranges = {
                "annual support": (120, 600),
                "field kit": (75, 450),
                "data migration": (300, 2500),
                "service renewal": (150, 1200),
                "hardware bundle": (250, 1800),
                "年間サポート": (120, 600),
                "現地設置キット": (75, 450),
                "データ移行": (300, 2500),
                "サービス更新": (150, 1200),
                "ハードウェア一式": (250, 1800),
            }
            total_low, total_high = (
                float(order_total_column["min"]),
                float(order_total_column["max"]),
            )
            quantity_min = int(order_quantity_column["min"])
            quantity_max = int(order_quantity_column["max"])
            zero_decimal_currency = str(row_currency).strip().casefold() in (
                "jpy",
                "yen",
                "円",
                "¥",
            )
            precision = 1 if zero_decimal_currency else 100
            total_min_tick = math.ceil(total_low * precision - 1e-9)
            total_max_tick = math.floor(total_high * precision + 1e-9)

            def item_price_bounds(candidate):
                low, high = price_ranges.get(str(candidate).casefold(), (25, 2000))
                if (
                    order_unit_price_column
                    and order_unit_price_column.get("kind") == "decimal"
                ):
                    low = max(low, float(order_unit_price_column["min"]))
                    high = min(high, float(order_unit_price_column["max"]))
                return float(low), float(high)

            def feasible_quantities(low, high, minimum, maximum):
                cache_key = (
                    precision,
                    low,
                    high,
                    minimum,
                    maximum,
                    total_low,
                    total_high,
                )
                if cache_key in order_feasibility_cache:
                    return order_feasibility_cache[cache_key]
                if low < 0 or high <= 0 or total_min_tick > total_max_tick:
                    order_feasibility_cache[cache_key] = []
                    return order_feasibility_cache[cache_key]
                low_tick = math.ceil(low * precision - 1e-9)
                high_tick = math.floor(high * precision + 1e-9)
                if low_tick > high_tick or high_tick <= 0:
                    order_feasibility_cache[cache_key] = []
                    return order_feasibility_cache[cache_key]

                def has_representable_price(quantity):
                    first = max(low_tick, math.ceil(total_min_tick / quantity - 1e-9))
                    last = min(high_tick, math.floor(total_max_tick / quantity + 1e-9))
                    return first <= last

                span = maximum - minimum + 1
                if span <= 10000:
                    result = [
                        quantity
                        for quantity in range(minimum, maximum + 1)
                        if has_representable_price(quantity)
                    ]
                else:
                    probes = {
                        minimum,
                        maximum,
                        max(
                            minimum,
                            min(
                                maximum,
                                round(
                                    ((total_low + total_high) / 2) / ((low + high) / 2)
                                ),
                            ),
                        ),
                    }
                    probes.update(rng.randint(minimum, maximum) for _ in range(64))
                    result = [
                        quantity
                        for quantity in probes
                        if has_representable_price(quantity)
                    ]
                order_feasibility_cache[cache_key] = result
                return result

            # Pick only item/quantity combinations that have at least one
            # representable unit price inside the configured total range. This
            # avoids random failures from impossible quantities.
            feasible = []
            if total_low >= 0 and total_high >= 0:
                for candidate in order_item_column["values"]:
                    candidate_low, candidate_high = item_price_bounds(candidate)
                    continuous_min = (
                        max(quantity_min, math.ceil(total_low / candidate_high - 1e-9))
                        if candidate_high > 0
                        else quantity_max + 1
                    )
                    continuous_max = (
                        min(quantity_max, math.floor(total_high / candidate_low + 1e-9))
                        if candidate_low > 0
                        else quantity_max
                    )
                    if continuous_min <= continuous_max:
                        quantities = feasible_quantities(
                            candidate_low,
                            candidate_high,
                            continuous_min,
                            continuous_max,
                        )
                        if quantities:
                            feasible.append(
                                (candidate, candidate_low, candidate_high, quantities)
                            )

            if feasible:
                item, unit_low, unit_high, quantities = rng.choice(feasible)
                quantity = rng.choice(quantities)
            else:
                item = rng.choice(order_item_column["values"])
                unit_low, unit_high = item_price_bounds(item)
                quantity = rng.randint(quantity_min, quantity_max)
            unit_low = max(unit_low, total_low / quantity)
            unit_high = min(unit_high, total_high / quantity)
            first_tick = math.ceil(unit_low * precision - 1e-9)
            last_tick = math.floor(unit_high * precision + 1e-9)
            if first_tick > last_tick:
                raise ValueError(translate("order_ranges_error", language))
            unit_price = rng.randint(first_tick, last_tick) / precision
            total = round(unit_price * quantity, 0 if zero_decimal_currency else 2)
            order_values.update(
                {
                    order_item_column["name"].casefold(): item,
                    "quantity": quantity,
                    "total": total,
                }
            )
            if (
                order_unit_price_column
                and order_unit_price_column.get("kind") == "decimal"
            ):
                order_values[order_unit_price_column["name"].casefold()] = unit_price
        if (
            order_status_column
            and order_status_column["kind"] == "status"
            and ordered_at_column
            and ordered_at_column["kind"] == "date"
        ):
            order_status = rng.choice(
                order_status_column.get(
                    "values",
                    ("pending", "processing", "shipped", "complete", "cancelled"),
                )
            )
            age_ranges = {
                "pending": (0, 14),
                "processing": (0, 30),
                "shipped": (1, 90),
                "complete": (5, 730),
                "cancelled": (0, 365),
                "refunded": (5, 365),
            }
            minimum_age, maximum_age = age_ranges.get(
                str(order_status).casefold(), (0, 730)
            )
            order_values.update(
                {
                    order_status_column["name"].casefold(): order_status,
                    ordered_at_column["name"].casefold(): (
                        today - timedelta(days=rng.randint(minimum_age, maximum_age))
                    ).isoformat(),
                }
            )
        ticket_values = {}
        if (
            ticket_status_column
            and ticket_status_column["kind"] == "status"
            and ticket_opened_column
            and ticket_opened_column["kind"] == "datetime"
        ):
            ticket_status = rng.choice(
                ticket_status_column.get(
                    "values", ("open", "pending", "in_progress", "resolved", "closed")
                )
            )
            age_ranges = {
                "open": (0, 14),
                "pending": (0, 30),
                "in_progress": (0, 60),
                "resolved": (1, 180),
                "closed": (15, 730),
            }
            minimum_age, maximum_age = age_ranges.get(
                str(ticket_status).casefold(), (0, 730)
            )
            opened_at = now - timedelta(
                days=rng.randint(minimum_age, maximum_age), seconds=rng.randrange(86400)
            )
            ticket_values = {
                "ticket_status": ticket_status,
                "opened_at": opened_at.isoformat(timespec="seconds"),
            }
        employee_values = {}
        if (
            employee_status_column
            and employee_status_column["kind"] == "status"
            and employee_started_column
            and employee_started_column["kind"] == "date"
        ):
            employee_status = rng.choice(
                employee_status_column.get(
                    "values", ("onboarding", "active", "on_leave", "offboarded")
                )
            )
            age_ranges = {
                "onboarding": (0, 45),
                "active": (30, 3650),
                "on_leave": (90, 3650),
                "offboarded": (30, 3650),
            }
            minimum_age, maximum_age = age_ranges.get(
                str(employee_status).casefold(), (0, 3650)
            )
            employee_values = {
                "employment_status": employee_status,
                "started_at": (
                    today - timedelta(days=rng.randint(minimum_age, maximum_age))
                ).isoformat(),
            }
        user_values = {}
        if (
            user_status_column
            and user_status_column.get("kind") == "status"
            and user_created_column
            and user_created_column.get("kind") == "date"
            and user_last_login_column
            and user_last_login_column.get("kind") == "datetime"
        ):
            account_status = rng.choice(
                user_status_column.get(
                    "values", ("active", "locked", "disabled", "invited")
                )
            )
            status_key = str(account_status).casefold()
            if status_key == "invited":
                created_at = today - timedelta(days=rng.randint(0, 14))
                last_login = ""
            else:
                minimum_age = 180 if status_key == "disabled" else 30
                created_at = today - timedelta(days=rng.randint(minimum_age, 730))
                if status_key == "disabled":
                    login_age = rng.randint(90, min(365, (today - created_at).days))
                elif status_key == "locked":
                    login_age = rng.randint(0, min(14, (today - created_at).days))
                else:
                    login_age = rng.randint(0, min(30, (today - created_at).days))
                last_login_at = now - timedelta(
                    days=login_age, seconds=rng.randrange(86400)
                )
                account_created_at = datetime.combine(created_at, datetime.min.time())
                if last_login_at < account_created_at:
                    last_login_at = account_created_at + timedelta(
                        seconds=rng.randrange(86400)
                    )
                last_login = last_login_at.isoformat()
            user_values = {
                "account_status": account_status,
                "created_at": created_at.isoformat(),
                "last_login": last_login,
            }
            if user_mfa_column and user_mfa_column.get("kind") in ("status", "text"):
                mfa_values = user_mfa_column.get(
                    "values", ("enabled", "required", "pending")
                )
                compatible_mfa = {
                    "invited": {"pending", "required"},
                    "active": {"enabled", "required"},
                    "locked": {"enabled", "required"},
                    "disabled": {"enabled", "required", "pending"},
                }.get(status_key, {str(value).casefold() for value in mfa_values})
                matching_mfa = [
                    value
                    for value in mfa_values
                    if str(value).casefold() in compatible_mfa
                ]
                if matching_mfa:
                    user_values[user_mfa_column["name"].casefold()] = rng.choice(
                        matching_mfa
                    )
        credential_values = {}
        if (
            credential_status_column
            and credential_status_column.get("kind") == "status"
            and credential_created_column
            and credential_created_column.get("kind") == "date"
            and credential_rotated_column
            and credential_rotated_column.get("kind") == "date"
            and credential_last_used_column
            and credential_last_used_column.get("kind") == "datetime"
        ):
            status_choices = credential_status_column.get(
                "values",
                ("active", "active", "active", "rotation_due", "revoked", "pending"),
            )
            weighted_status_choices = [
                status
                for status in status_choices
                for _ in range(3 if str(status).casefold() == "active" else 1)
            ]
            credential_status = rng.choice(weighted_status_choices)
            status_key = str(credential_status).casefold()
            created_age = rng.randint(365, 1800)
            rotated_age_ranges = {
                "active": (1, 180),
                "rotation_due": (180, 365),
                "revoked": (1, 365),
                "pending": (90, 180),
            }
            minimum_age, maximum_age = rotated_age_ranges.get(status_key, (1, 180))
            rotated_age = rng.randint(
                min(minimum_age, created_age), min(maximum_age, created_age)
            )
            rotated_at = datetime.combine(
                today - timedelta(days=rotated_age), datetime.min.time()
            )
            last_used_at = rotated_at + timedelta(
                seconds=rng.randint(0, max(0, int((now - rotated_at).total_seconds())))
            )
            credential_values = {
                "credential_status": credential_status,
                "created_at": (today - timedelta(days=created_age)).isoformat(),
                "last_rotated": (today - timedelta(days=rotated_age)).isoformat(),
                "last_used": last_used_at.isoformat(),
            }
        asset_values = {}
        if (
            asset_name_column
            and asset_name_column.get("kind") == "text"
            and asset_name_column.get("values")
            and asset_category_column
            and asset_category_column.get("kind") == "text"
            and asset_category_column.get("values")
        ):
            asset_name = rng.choice(asset_name_column["values"])
            category_map = {
                "workstation": ("it",),
                "network switch": ("network",),
                "test device": ("lab",),
                "office display": ("facilities",),
                "storage node": ("it", "network"),
                "業務用端末": ("it機器",),
                "ネットワークスイッチ": ("ネットワーク",),
                "試験用機器": ("検証環境",),
                "オフィスディスプレイ": ("施設",),
                "ストレージノード": ("it機器", "ネットワーク"),
            }
            valid_categories = {
                str(value).casefold(): value
                for value in asset_category_column["values"]
            }
            matches = [
                valid_categories[value]
                for value in category_map.get(str(asset_name).casefold(), ())
                if value in valid_categories
            ]
            category = rng.choice(matches or asset_category_column["values"])
            asset_values.update({"asset_name": asset_name, "category": category})
        if (
            asset_status_column
            and asset_status_column["kind"] == "status"
            and asset_checked_column
            and asset_checked_column["kind"] == "date"
        ):
            asset_status = rng.choice(
                asset_status_column.get(
                    "values", ("active", "active", "pending", "archived")
                )
            )
            age_ranges = {
                "active": (0, 180),
                "pending": (30, 365),
                "archived": (90, 730),
            }
            minimum_age, maximum_age = age_ranges.get(
                str(asset_status).casefold(), (0, 730)
            )
            asset_values.update(
                {
                    "asset_status": asset_status,
                    "checked_at": (
                        today - timedelta(days=rng.randint(minimum_age, maximum_age))
                    ).isoformat(),
                }
            )
        cloud_values = {}
        if (
            cloud_service_column
            and cloud_service_column.get("kind") == "text"
            and cloud_service_column.get("values")
            and cloud_environment_column
            and cloud_environment_column.get("kind") == "text"
            and cloud_environment_column.get("values")
            and cloud_endpoint_column
            and cloud_endpoint_column.get("kind") == "domain"
        ):
            service_name = rng.choice(cloud_service_column["values"])
            environment = rng.choice(cloud_environment_column["values"])
            service_slug = CLOUD_SERVICE_SLUGS_JA.get(service_name) or re.sub(
                r"[^a-z0-9]+", "-", str(service_name).casefold()
            ).strip("-")[:40].rstrip("-")
            environment_slug = CLOUD_ENVIRONMENT_SLUGS_JA.get(environment) or re.sub(
                r"[^a-z0-9]+", "-", str(environment).casefold()
            ).strip("-")[:16].rstrip("-")
            if not service_slug:
                service_slug = (
                    "service-"
                    + hashlib.sha256(str(service_name).encode("utf-8")).hexdigest()[:8]
                )
            if not environment_slug:
                environment_slug = (
                    "env-"
                    + hashlib.sha256(str(environment).encode("utf-8")).hexdigest()[:8]
                )
            cloud_values = {
                "service_name": service_name,
                "environment": environment,
                "endpoint": f"{service_slug}-{environment_slug}.example.invalid",
            }
        row = []
        for column in columns:
            kind = column["kind"]
            if column["name"].casefold() in customer_address_values:
                value = customer_address_values[column["name"].casefold()]
            elif column["name"].casefold() in customer_lifecycle_values:
                value = customer_lifecycle_values[column["name"].casefold()]
            elif kind == "company":
                value = company_values[column["name"]]
            elif column["name"].lower() in invoice_dates:
                value = invoice_dates[column["name"].lower()]
            elif column["name"].lower() in card_values:
                value = card_values[column["name"].lower()]
            elif column["name"].lower() in vendor_values:
                value = vendor_values[column["name"].lower()]
            elif column["name"].lower() in order_values:
                value = order_values[column["name"].lower()]
            elif column["name"].lower() in ticket_values:
                value = ticket_values[column["name"].lower()]
            elif column["name"].lower() in employee_values:
                value = employee_values[column["name"].lower()]
            elif column["name"].lower() in user_values:
                value = user_values[column["name"].lower()]
            elif column["name"].lower() in credential_values:
                value = credential_values[column["name"].lower()]
            elif column["name"].lower() in asset_values:
                value = asset_values[column["name"].lower()]
            elif column["name"].lower() in cloud_values:
                value = cloud_values[column["name"].lower()]
            elif (
                column["name"].lower() == "payment_status"
                and invoice_status is not None
            ):
                value = invoice_status
            elif column["name"].casefold() == "currency" and row_currency is not None:
                value = row_currency
            elif "values" in column:
                value = rng.choice(column["values"])
            elif kind == "username":
                base_username = f"{email_given.lower()}.{email_family.lower()}"
                value = base_username
                suffix = 2
                while value.casefold() in used_usernames:
                    value = f"{base_username}{suffix}"
                    suffix += 1
                used_usernames.add(value.casefold())
            elif kind == "invoice_reference":
                invoice_year = invoice_dates.get("issued_at", today.isoformat())[:4]
                value = f"INV-{invoice_year}-{i:06d}"
            elif kind in ("order_reference", "sale_reference"):
                prefix = "ORD" if kind == "order_reference" else "SAL"
                date_key = (
                    ordered_at_column["name"].casefold() if ordered_at_column else ""
                )
                reference_date = order_values.get(date_key, today.isoformat())
                value = f"{prefix}-{reference_date[:4]}-{i:06d}"
            elif kind == "id":
                value = i
            elif kind == "name":
                value = f"{family} {given}" if japanese else f"{given} {family}"
            elif kind == "email":
                email_domain = column.get("synthetic_email_domain")
                if not email_domain and associated_company:
                    email_domain = synthetic_company_domain(associated_company)
                email_domain = email_domain or "example.invalid"
                email_reference = (
                    person_profile_index + 1 if reuse_person_profiles else i
                )
                value = f"{email_given.lower()}.{email_family.lower()}.{email_reference}@{email_domain}"
            elif kind == "department":
                value = rng.choice(DEPARTMENTS_JA if japanese else DEPARTMENTS)
            elif kind == "integer":
                value = rng.randint(int(column["min"]), int(column["max"]))
            elif kind == "boolean":
                value = False
            elif kind == "decimal":
                low, high = float(column["min"]), float(column["max"])
                if (
                    column["name"].casefold()
                    in {
                        "total",
                        "subtotal",
                        "amount",
                        "annual_cost",
                        "price",
                        "balance",
                        "revenue",
                    }
                    and 0 < low <= high
                ):
                    # Financial amounts usually cluster toward smaller values;
                    # log-uniform sampling avoids the conspicuous high-value
                    # concentration produced by a linear uniform distribution.
                    value = math.exp(rng.uniform(math.log(low), math.log(high)))
                    zero_decimal_currency = str(row_currency).strip().casefold() in (
                        "jpy",
                        "yen",
                        "円",
                    )
                    value = round(value, 0 if zero_decimal_currency else 2)
                    value = min(high, max(low, value))
                else:
                    value = min(high, max(low, round(rng.uniform(low, high), 2)))
            elif kind == "date":
                value = (today - timedelta(days=rng.randrange(731))).isoformat()
            elif kind == "datetime":
                value = (
                    now - timedelta(seconds=rng.randrange(730 * 86400))
                ).isoformat()
            elif kind == "status":
                value = rng.choice(("active", "active", "pending", "archived"))
            elif kind == "uuid":
                value = str(uuid.uuid4())
            elif kind == "phone":
                value = (
                    japanese_phone_number()
                    if japanese
                    else f"+1-202-555-01{rng.randrange(100):02d}"
                )
            elif kind == "domain":
                endpoint_fields = {
                    "endpoint": ("/api/v1", "service"),
                    "service_portal_url": ("/portal", "service"),
                    "billing_portal_url": ("/billing/invoices", "billing"),
                    "support_portal_url": ("/support/cases", "support"),
                    "report_portal_url": ("/reports", "reports"),
                }
                endpoint = endpoint_fields.get(column["name"].casefold())
                if endpoint:
                    path, fallback_slug = endpoint
                    service_index = next(
                        (
                            index
                            for index, previous in enumerate(columns[: len(row)])
                            if previous["name"].casefold() == "service_name"
                        ),
                        None,
                    )
                    environment_index = next(
                        (
                            index
                            for index, previous in enumerate(columns[: len(row)])
                            if previous["name"].casefold() == "environment"
                        ),
                        None,
                    )
                    service = (
                        str(row[service_index])
                        if service_index is not None
                        else fallback_slug
                    )
                    environment = (
                        str(row[environment_index]).casefold()
                        if environment_index is not None
                        else "development"
                    )
                    service_aliases = {
                        "archive api": "archive",
                        "保管api": "archive",
                        "reporting worker": "reports",
                        "レポート処理基盤": "reports",
                        "object store": "objects",
                        "オブジェクト保管庫": "objects",
                        "billing queue": "billing",
                        "請求キュー": "billing",
                        "identity gateway": "identity",
                        "認証ゲートウェイ": "identity",
                    }
                    stem = service_aliases.get(
                        service.casefold()
                    ) or API_SERVICE_SLUGS_JA.get(service)
                    if not stem:
                        stem = re.sub(r"[^a-z0-9]+", "-", service.casefold()).strip("-")
                    if not stem:
                        stem = (
                            fallback_slug
                            + "-"
                            + hashlib.sha256(service.encode("utf-8")).hexdigest()[:8]
                        )
                    environment_aliases = {
                        "本番": "production",
                        "検証": "staging",
                        "災害復旧": "recovery",
                        "旧環境": "legacy",
                    }
                    environment_slug = environment_aliases.get(
                        environment,
                        re.sub(r"[^a-z0-9-]+", "-", environment).strip("-")
                        or "development",
                    )
                    value = f"https://{stem}-{environment_slug}.example.invalid{path}"
                elif associated_company:
                    value = synthetic_company_domain(associated_company)
                else:
                    value = f"{rng.choice(('archive', 'billing', 'portal', 'service', 'vault'))}-{i}.example.invalid"
                if column["name"].casefold() == "api_endpoint":
                    service_index = next(
                        (
                            index
                            for index, previous in enumerate(columns[: len(row)])
                            if previous["name"].casefold() == "service_name"
                        ),
                        None,
                    )
                    service = (
                        str(row[service_index])
                        if service_index is not None
                        else "service"
                    )
                    stem = API_SERVICE_SLUGS_JA.get(service) or re.sub(
                        r"[^a-z0-9]+", "-", service.casefold()
                    ).strip("-")[:40].rstrip("-")
                    if not stem:
                        stem = (
                            "service-"
                            + hashlib.sha256(service.encode("utf-8")).hexdigest()[:8]
                        )
                    value = f"https://{stem}.example.invalid/v1"
                elif column["name"].casefold() == "login_url":
                    domain = column.get("vault_decoy_domain")
                    if domain:
                        service_index = next(
                            (
                                index
                                for index, previous in enumerate(columns[: len(row)])
                                if previous["name"].casefold() == "service_name"
                            ),
                            None,
                        )
                        service = (
                            str(row[service_index])
                            if service_index is not None
                            else "vault"
                        )
                        stem = _vault_service_slug(service)
                        path = VAULT_LOGIN_PATHS.get(stem, "/login")
                        value = f"https://{stem}.{domain}{path}"
                    else:
                        service_index = next(
                            (
                                index
                                for index, previous in enumerate(columns[: len(row)])
                                if previous["name"].casefold() == "service_name"
                            ),
                            None,
                        )
                        service = (
                            str(row[service_index])
                            if service_index is not None
                            else "Vault"
                        )
                        stem = _vault_service_slug(service)
                        value = f"https://{stem}.example.invalid{VAULT_LOGIN_PATHS.get(stem, '/login')}"
            # Use a reference identifier, never a payment-card number.
            elif kind == "card_reference":
                value = "PM-" + secrets.token_hex(6).upper()
            elif kind == "card_expiry":
                value = f"{rng.randint(1, 12):02d}/{(today.year + rng.randint(1, 5)) % 100:02d}"
            elif kind == "test_postal":
                value = str(rng.randrange(10000, 100000))
            elif kind == "address":
                value = f"{rng.randint(1, 8)}-{rng.randint(1, 30)}-{rng.randint(1, 25)}"
            elif kind == "credential_preview":
                alphabet = (
                    string.ascii_lowercase
                    + string.ascii_uppercase
                    + string.digits
                    + "!@#$%+-_"
                )
                value_chars = [
                    secrets.choice(string.ascii_lowercase),
                    secrets.choice(string.ascii_uppercase),
                    secrets.choice(string.digits),
                    secrets.choice("!@#$%+-_"),
                ]
                value_chars.extend(secrets.choice(alphabet) for _ in range(14))
                secrets.SystemRandom().shuffle(value_chars)
                value = "".join(value_chars)
            elif kind == "currency":
                value = rng.choice(("JPY", "USD", "EUR"))
            elif kind == "documentation_ip":
                value = f"192.0.2.{rng.randint(1, 254)}"
            elif kind == "text":
                topics = (
                    ("年次確認", "アカウント更新", "契約更新", "サービス移行")
                    if japanese
                    else (
                        "Annual review",
                        "Account renewal",
                        "Contract update",
                        "Service migration",
                    )
                )
                departments = DEPARTMENTS_JA if japanese else DEPARTMENTS
                value = f"{rng.choice(topics)} / {rng.choice(departments)}"
            else:
                value = f"{rng.choice(('Annual review', 'Account renewal', 'Contract update', 'Service migration'))} / {rng.choice(DEPARTMENTS)}"
            row.append(value)
        yield row


def sqlite_bytes(
    table,
    columns,
    data,
    url="",
    connection_table=None,
    connection_name="archive",
    language="ja",
):
    table = identifier(table, language)
    url = canary_url(url, language)
    connection_name = identifier(connection_name, language)
    if not isinstance(columns, list) or not 1 <= len(columns) <= 30:
        raise ValueError(translate("columns_error", language))
    column_names = set()
    for column in columns:
        if not isinstance(column, dict):
            raise ValueError(translate("columns_error", language))
        name = identifier(column.get("name"), language)
        kind = column.get("kind")
        if (
            name.casefold() in column_names
            or not isinstance(kind, str)
            or kind not in KINDS
        ):
            raise ValueError(translate("columns_error", language))
        column_names.add(name.casefold())
    connection = sqlite3.connect(":memory:")
    try:
        # Identifiers were allow-listed above; values are always parameters.
        definitions = ", ".join(
            f'"{column["name"]}" {KINDS[column["kind"]]}'
            + (
                " NOT NULL PRIMARY KEY"
                if column["name"].casefold() == "id" and column["kind"] == "id"
                else " NOT NULL"
            )
            for column in columns
        )
        connection.execute(f'CREATE TABLE "{table}" ({definitions})')
        placeholders = ",".join("?" for _ in columns)
        insert = f'INSERT INTO "{table}" VALUES ({placeholders})'
        batch = []

        def enforce_size_limit():
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            if page_size * page_count > MAX_DATABASE_BYTES:
                raise ValueError(translate("database_size_limit", language))

        for row in data:
            batch.append(tuple(row))
            if len(batch) >= 128:
                connection.executemany(insert, batch)
                batch.clear()
                enforce_size_limit()
        if batch:
            connection.executemany(insert, batch)
        enforce_size_limit()
        indexed_names = {
            "email",
            "domain",
            "status",
            "account_status",
            "record_status",
            "payment_status",
            "order_status",
            "ticket_status",
            "employment_status",
        }
        for position, column in enumerate(columns):
            if column["name"].casefold() in indexed_names:
                index_name = f"idx_{table[:20]}_{position:02d}_{column['name'][:20]}"
                connection.execute(
                    f'CREATE INDEX "{index_name}" ON "{table}" ("{column["name"]}")'
                )
                enforce_size_limit()
        if url:
            if connection_table is not None:
                connection_table = identifier(connection_table, language)
            metadata_table = connection_table or "service_connections"
            if metadata_table.casefold() == table.casefold():
                metadata_table = next(
                    candidate
                    for candidate in (
                        "archive_connections",
                        "connection_registry",
                        "external_connections",
                    )
                    if candidate.casefold() != table.casefold()
                )
            connection.execute(
                f'CREATE TABLE "{metadata_table}" (name TEXT PRIMARY KEY, endpoint TEXT NOT NULL)'
            )
            connection.execute(
                f'INSERT INTO "{metadata_table}" VALUES (?, ?)', (connection_name, url)
            )
            enforce_size_limit()
        connection.commit()
        result = connection.serialize()
        if len(result) > MAX_DATABASE_BYTES:
            raise ValueError(translate("database_size_limit", language))
        return result
    finally:
        connection.close()


def database_settings(settings, language="ja"):
    rows = integer(settings.get("rows", 25), "rows", 1, MAX_ROWS, language)
    template_id = settings.get("template", "customers")
    if not isinstance(template_id, str) or template_id not in (
        *DATABASE_TEMPLATES,
        "custom",
    ):
        raise ValueError(translate("columns_error", language))
    template = DATABASE_TEMPLATES.get(template_id, DATABASE_TEMPLATES["customers"])
    configured = dict(settings)
    configured.setdefault("table", template["table"])
    configured.setdefault("columns", _template_columns(template_id, language))
    table, columns = validate_schema(configured, language)
    email_domain = vault_decoy_domain(
        settings.get("email_domain", ""),
        settings.get("email_domain_authorized", False),
        language,
    )
    if email_domain:
        email_columns = [column for column in columns if column["kind"] == "email"]
        if not email_columns:
            raise ValueError(translate("email_domain_schema", language))
        for column in email_columns:
            column["synthetic_email_domain"] = email_domain
    if template_id == "passwords":
        domain = vault_decoy_domain(
            settings.get("vault_domain", ""),
            settings.get("vault_domain_authorized", False),
            language,
        )
        if domain:
            login_column = next(
                (
                    column
                    for column in columns
                    if column["name"].casefold() == "login_url"
                ),
                None,
            )
            if login_column is None or login_column["kind"] != "domain":
                raise ValueError(translate("vault_domain_schema", language))
            login_column["vault_decoy_domain"] = domain
    return table, columns, rows
