"""Configurable schemas and synthetic records; never import production data."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import math
import re
import secrets
import sqlite3
import string
import uuid

from aideceptionguard.i18n import translate
from aideceptionguard.validation import canary_url, identifier, integer, synthetic_candidate, text, vault_decoy_domain

MAX_ROWS = 10000
MAX_DATABASE_BYTES = 32 * 1024 * 1024
VAULT_LOGIN_PATHS = {
    "mail-console": "/auth/login", "billing-workspace": "/account/signin",
    "source-archive": "/signin", "vendor-portal": "/login",
    "analytics-dashboard": "/sso/login",
}
DEFAULT_COLUMNS = [
    {"name": "id", "kind": "id"}, {"name": "name", "kind": "name"},
    {"name": "email", "kind": "email"}, {"name": "status", "kind": "status"},
]
KINDS = {
    "id": "INTEGER", "name": "TEXT", "email": "TEXT", "company": "TEXT",
    "department": "TEXT", "integer": "INTEGER", "decimal": "REAL", "date": "TEXT",
    "datetime": "TEXT", "status": "TEXT", "uuid": "TEXT", "text": "TEXT", "phone": "TEXT",
    "domain": "TEXT", "card_reference": "TEXT", "card_expiry": "TEXT", "test_postal": "TEXT",
    "credential_preview": "TEXT", "currency": "TEXT", "documentation_ip": "TEXT",
}
GIVEN_PAIRS = (
    ("Haruto", "悠真"), ("Yui", "結衣"), ("Ren", "蓮"), ("Aoi", "葵"), ("Sota", "颯太"), ("Mio", "美緒"),
    ("Riku", "陸"), ("Hana", "花"), ("Akira", "明"), ("Ema", "恵麻"), ("Nao", "直"), ("Maya", "真彩"),
    ("Daichi", "大地"), ("Kaito", "海斗"), ("Hinata", "陽向"), ("Haruki", "陽希"), ("Rina", "莉奈"), ("Sakura", "咲良"),
    ("Hikaru", "晃"), ("Mei", "芽依"), ("Kenta", "健太"), ("Yuto", "悠斗"), ("Koharu", "心春"), ("Shota", "翔太"),
    ("Naoe", "奈緒"), ("Hikari", "光"), ("Yuna", "結菜"), ("Takumi", "拓海"), ("Saki", "咲"), ("Tsubasa", "翼"),
    ("Koki", "光希"), ("Nanami", "七海"), ("Ayaka", "彩花"), ("Shun", "駿"), ("Itsuki", "樹"), ("Kaede", "楓"),
)
FAMILY_PAIRS = (
    ("Sato", "佐藤"), ("Suzuki", "鈴木"), ("Takahashi", "高橋"), ("Tanaka", "田中"), ("Ito", "伊藤"),
    ("Watanabe", "渡辺"), ("Yamamoto", "山本"), ("Nakamura", "中村"), ("Kato", "加藤"), ("Kobayashi", "小林"),
    ("Hayashi", "林"), ("Shimizu", "清水"), ("Mori", "森"), ("Abe", "阿部"), ("Ikeda", "池田"),
    ("Hashimoto", "橋本"), ("Ishikawa", "石川"), ("Yamashita", "山下"), ("Ogawa", "小川"), ("Ishii", "石井"),
    ("Hasegawa", "長谷川"), ("Goto", "後藤"), ("Okada", "岡田"), ("Fujita", "藤田"), ("Maeda", "前田"),
    ("Nakajima", "中島"), ("Murakami", "村上"), ("Kondo", "近藤"), ("Saito", "斎藤"), ("Sakamoto", "坂本"),
    ("Endo", "遠藤"), ("Aoki", "青木"), ("Fujii", "藤井"), ("Nishimura", "西村"),
)
GIVEN = tuple(pair[0] for pair in GIVEN_PAIRS)
GIVEN_JA = tuple(pair[1] for pair in GIVEN_PAIRS)
FAMILY = tuple(pair[0] for pair in FAMILY_PAIRS)
FAMILY_JA = tuple(pair[1] for pair in FAMILY_PAIRS)
COMPANIES = ("Northbridge Systems", "Cedar Analytics", "Blueleaf Trading", "Westport Logistics", "Aster Works", "Oakline Labs")
DEPARTMENTS = ("Sales", "Engineering", "Operations", "Finance", "Customer Success", "Administration")
COMPANIES_JA = ("青葉システムズ株式会社", "北辰データサービス株式会社", "東都ロジスティクス株式会社", "みなと商事株式会社", "桜井ソリューションズ株式会社", "新都アナリティクス株式会社")
DEPARTMENTS_JA = ("営業", "開発", "運用", "経理", "カスタマーサポート", "総務")
ORG_STEMS = ("Northbridge", "Cedar", "Blueleaf", "Westport", "Aster", "Oakline", "Silverpine", "Harborview", "Summit", "Clearwater", "Redwood", "Meadowbrook", "Evergreen", "Stonehaven", "Brightwell", "Lakeshore", "Windward", "Pioneer", "Maplewood", "Granite", "Rivermark", "Eastfield", "Fairview", "Kingswell")
ORG_SUFFIXES = ("Systems", "Analytics", "Trading", "Logistics", "Works", "Labs", "Services", "Networks", "Consulting", "Supply", "Partners", "Digital")
ORG_STEMS_JA = ("青葉", "北辰", "東雲", "光洋", "三峰", "水明", "新港", "白峰", "大樹", "旭", "星海", "森泉", "山河", "日向", "千代田", "明星", "青空", "潮見", "桜川", "橘", "緑川", "高原", "清流", "東光")
ORG_SUFFIXES_JA = ("システムズ", "アナリティクス", "商事", "物流", "研究所", "テクノロジー", "サービス", "ネットワーク", "コンサルティング", "産業", "パートナーズ", "デジタル")
DATABASE_TEMPLATES = {
    "customers": {"table":"customers","ja":("顧客管理","連絡先・会社・担当状況"),"en":("Customer management","Contacts, organizations and account status"),"columns":[
        {"name":"id","kind":"id"},{"name":"name","kind":"name"},{"name":"email","kind":"email"},{"name":"company","kind":"company"},{"name":"phone","kind":"phone"},{"name":"department","kind":"department"},{"name":"status","kind":"status"},{"name":"last_contact","kind":"date"}]},
    "cards": {"table":"card_accounts","ja":("カード台帳（番号なし）","ブランド・名義・期限。カード番号やCVVは生成しません"),"en":("Card inventory (no card numbers)","Brand, holder and expiry; no PAN or CVV is generated"),"columns":[
        {"name":"id","kind":"id"},{"name":"holder_name","kind":"name"},{"name":"holder_email","kind":"email"},{"name":"card_brand","kind":"text","values":["Visa","Mastercard","JCB","American Express"]},{"name":"card_reference","kind":"card_reference"},{"name":"expiry","kind":"card_expiry"},{"name":"billing_postal","kind":"test_postal"},{"name":"account_status","kind":"status","values":["active","suspended","expired"]},{"name":"updated_at","kind":"date"}]},
    "companies": {"table":"companies","ja":("企業管理","企業・業界・従業員数・取引状況"),"en":("Company directory","Organizations, industries, size and relationship status"),"columns":[
        {"name":"id","kind":"id"},{"name":"company_name","kind":"company"},{"name":"domain","kind":"domain"},{"name":"industry","kind":"text","values":["Manufacturing","Retail","Software","Logistics","Professional services"]},{"name":"employee_count","kind":"integer","min":5,"max":25000},{"name":"contact_name","kind":"name"},{"name":"contact_email","kind":"email"},{"name":"phone","kind":"phone"},{"name":"account_status","kind":"status"}]},
    "passwords": {"table":"saved_logins","ja":("パスワード管理（無効な見本値）","利用不能なダミー文字列のみ。実際の認証情報・ハッシュは生成しません"),"en":("Password vault (nonfunctional samples)","Nonfunctional placeholders only; no real credentials or hashes"),"columns":[
        {"name":"id","kind":"id"},{"name":"owner_name","kind":"name"},{"name":"service_name","kind":"text","values":["Mail Console","Billing Workspace","Source Archive","Vendor Portal","Analytics Dashboard"]},{"name":"login_url","kind":"domain"},{"name":"username","kind":"email"},{"name":"password","kind":"credential_preview"},{"name":"vault_group","kind":"text","values":["Work","Finance","Infrastructure","Vendors"]},{"name":"last_rotated","kind":"date"},{"name":"record_status","kind":"status"}]},
    "orders": {"table":"orders","ja":("注文・販売","顧客・商品・金額・配送状態"),"en":("Orders and sales","Customers, items, amounts and fulfillment"),"columns":[
        {"name":"id","kind":"id"},{"name":"order_ref","kind":"uuid"},{"name":"customer_name","kind":"name"},{"name":"customer_email","kind":"email"},{"name":"item","kind":"text","values":["Annual Support","Field Kit","Data Migration","Service Renewal","Hardware Bundle"]},{"name":"quantity","kind":"integer","min":1,"max":12},{"name":"total","kind":"decimal","min":25,"max":25000},{"name":"currency","kind":"currency"},{"name":"order_status","kind":"status","values":["pending","processing","shipped","complete","cancelled"]},{"name":"ordered_at","kind":"date"}]},
    "invoices": {"table":"invoices","ja":("請求・支払","請求先・金額・期限・入金状態"),"en":("Invoices and payments","Bill-to contacts, amounts, due dates and status"),"columns":[
        {"name":"id","kind":"id"},{"name":"invoice_ref","kind":"text"},{"name":"company","kind":"company"},{"name":"billing_email","kind":"email"},{"name":"subtotal","kind":"decimal","min":100,"max":5000000},{"name":"currency","kind":"currency"},{"name":"issued_at","kind":"date"},{"name":"due_at","kind":"date"},{"name":"payment_status","kind":"status","values":["open","pending","paid","overdue","void"]}]},
    "employees": {"table":"employees","ja":("従業員・組織","社員番号・部署・役職・在籍状況"),"en":("Employees and teams","Staff identifiers, departments, roles and status"),"columns":[
        {"name":"id","kind":"id"},{"name":"employee_ref","kind":"uuid"},{"name":"name","kind":"name"},{"name":"work_email","kind":"email"},{"name":"department","kind":"department"},{"name":"role","kind":"text","values":["Analyst","Engineer","Account Manager","Operations Lead","Administrator"]},{"name":"office","kind":"text","values":["Tokyo","Osaka","Remote","Yokohama","Nagoya"]},{"name":"started_at","kind":"date"},{"name":"employment_status","kind":"status","values":["onboarding","active","on_leave","offboarded"]}]},
    "vendors": {"table":"vendors","ja":("取引先・委託先","会社・窓口・契約・リスク区分"),"en":("Vendors and partners","Organizations, contacts, contracts and review status"),"columns":[
        {"name":"id","kind":"id"},{"name":"vendor_name","kind":"company"},{"name":"domain","kind":"domain"},{"name":"contact_name","kind":"name"},{"name":"contact_email","kind":"email"},{"name":"service","kind":"text","values":["Cloud hosting","Payroll","Customer support","Analytics","Logistics"]},{"name":"annual_cost","kind":"decimal","min":1000,"max":2000000},{"name":"risk_tier","kind":"text","values":["low","standard","elevated"]},{"name":"reviewed_at","kind":"date"}]},
    "tickets": {"table":"support_tickets","ja":("問い合わせ・サポート","受付内容・担当・優先度・解決状況"),"en":("Support tickets","Issue summaries, assignment, priority and resolution"),"columns":[
        {"name":"id","kind":"id"},{"name":"ticket_ref","kind":"uuid"},{"name":"requester_name","kind":"name"},{"name":"requester_email","kind":"email"},{"name":"subject","kind":"text","values":["Account access review","Invoice correction","Export request","Service availability","Profile update"]},{"name":"priority","kind":"text","values":["low","normal","high"]},{"name":"assigned_team","kind":"department"},{"name":"ticket_status","kind":"status","values":["open","pending","in_progress","resolved","closed"]},{"name":"opened_at","kind":"datetime"}]},
    "assets": {"table":"assets","ja":("在庫・資産","資産番号・分類・保管場所・状態"),"en":("Inventory and assets","Asset references, categories, locations and status"),"columns":[
        {"name":"id","kind":"id"},{"name":"asset_ref","kind":"uuid"},{"name":"asset_name","kind":"text","values":["Workstation","Network Switch","Test Device","Office Display","Storage Node"]},{"name":"category","kind":"text","values":["IT","Facilities","Network","Lab"]},{"name":"location","kind":"text","values":["Tokyo-3F","Osaka-2F","Remote","Nagoya-1F"]},{"name":"purchase_cost","kind":"decimal","min":50,"max":800000},{"name":"assigned_to","kind":"name"},{"name":"asset_status","kind":"status"},{"name":"checked_at","kind":"date"}]},
    "cloud": {"table":"cloud_resources","ja":("クラウド・システム資産","サービス・環境・文書用IP・運用状態"),"en":("Cloud and system inventory","Services, environments, documentation IPs and status"),"columns":[
        {"name":"id","kind":"id"},{"name":"resource_ref","kind":"uuid"},{"name":"service_name","kind":"text","values":["Archive API","Reporting Worker","Object Store","Billing Queue","Identity Gateway"]},{"name":"environment","kind":"text","values":["production","staging","recovery","legacy"]},{"name":"endpoint","kind":"domain"},{"name":"documentation_ip","kind":"documentation_ip"},{"name":"owner_email","kind":"email"},{"name":"region","kind":"text","values":["ap-northeast-1","ap-northeast-3","us-west-2","eu-central-1"]},{"name":"resource_status","kind":"status"}]},
}


def public_templates(language="ja"):
    language = language if language in ("ja", "en") else "ja"
    return [{"id": key, "table": spec["table"], "label": spec[language][0], "description": spec[language][1],
             "columns": deepcopy(spec["columns"])}
            for key, spec in DATABASE_TEMPLATES.items()]


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
            low, high = item.get("min", 0), item.get("max", 100000)
            if (any(isinstance(v, bool) or not isinstance(v, (float, int)) or abs(v) > 1e12
                    or (isinstance(v, float) and not math.isfinite(v)) for v in (low, high)) or low > high
                    or (kind == "integer" and any(int(v) != v for v in (low, high)))):
                raise ValueError(translate("range_error", language))
            column.update(min=low, max=high)
        if "values" in item:
            values = item["values"]
            if not isinstance(values, list) or not 1 <= len(values) <= 50 or kind not in ("status", "text", "company", "department"):
                raise ValueError(translate("values_error", language))
            column["values"] = [synthetic_candidate(v, language) for v in values]
            if not all(column["values"]):
                raise ValueError(translate("values_error", language))
        columns.append(column)
    return table, columns


def records(columns, rows, language="en"):
    rng = secrets.SystemRandom()
    japanese = language == "ja"
    today = date.today()
    now = datetime.now().replace(microsecond=0)
    name_pairs = [(given_index, family_index)
                  for given_index in range(len(GIVEN)) for family_index in range(len(FAMILY))]
    rng.shuffle(name_pairs)
    organization_pool = [f"{stem} {suffix}" for stem in ORG_STEMS for suffix in ORG_SUFFIXES]
    if japanese:
        organization_pool = [f"{stem}{suffix}株式会社" for stem in ORG_STEMS_JA for suffix in ORG_SUFFIXES_JA]
    rng.shuffle(organization_pool)
    organization_index = 0
    company_columns = [column for column in columns if column["kind"] == "company"]
    columns_by_name = {column["name"].lower(): column for column in columns}
    issued_column = columns_by_name.get("issued_at")
    due_column = columns_by_name.get("due_at")
    invoice_status_column = columns_by_name.get("payment_status")
    card_expiry_column = columns_by_name.get("expiry")
    card_status_column = columns_by_name.get("account_status")
    order_status_column = columns_by_name.get("order_status")
    ordered_at_column = columns_by_name.get("ordered_at")
    order_item_column = columns_by_name.get("item")
    order_quantity_column = columns_by_name.get("quantity")
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
    currency_column = next((column for column in columns
                            if column["name"].casefold() == "currency"
                            and (column["kind"] == "currency" or "values" in column)), None)
    for i in range(1, rows + 1):
        if currency_column:
            currency_values = currency_column.get("values", ("JPY", "USD", "EUR"))
            row_currency = rng.choice(currency_values)
        else:
            row_currency = None
        if i <= len(name_pairs):
            given_index, family_index = name_pairs[i - 1]
        else:
            given_index, family_index = rng.randrange(len(GIVEN)), rng.randrange(len(FAMILY))
        given = GIVEN_JA[given_index] if japanese else GIVEN[given_index]
        family = FAMILY_JA[family_index] if japanese else FAMILY[family_index]
        email_given, email_family = GIVEN[given_index], FAMILY[family_index]
        company_values = {}
        for column in company_columns:
            if "values" in column:
                company_values[column["name"]] = rng.choice(column["values"])
            elif column["name"].casefold() in ("company_name", "vendor_name", "organization_name", "legal_name"):
                if organization_index < len(organization_pool):
                    company_values[column["name"]] = organization_pool[organization_index]
                else:
                    base_name = organization_pool[organization_index % len(organization_pool)]
                    variant = organization_index // len(organization_pool) + 1
                    suffix = f"第{variant}事業所" if japanese else f"Group {variant}"
                    company_values[column["name"]] = f"{base_name} {suffix}"
                organization_index += 1
            else:
                company_values[column["name"]] = rng.choice(COMPANIES_JA if japanese else COMPANIES)
        associated_company = next(iter(company_values.values()), None)
        invoice_dates, invoice_status = {}, None
        if (issued_column and due_column and issued_column["kind"] == due_column["kind"] == "date"
                and invoice_status_column and invoice_status_column["kind"] == "status"):
            status_values = invoice_status_column.get("values", ("open", "pending", "paid", "overdue", "void"))
            invoice_status = rng.choice(status_values)
            status_key = str(invoice_status).casefold()
            if status_key == "overdue":
                due_date = today - timedelta(days=rng.randint(1, 120))
                issued_date = due_date - timedelta(days=rng.randint(15, 60))
            elif status_key in ("open", "pending"):
                issued_date = today - timedelta(days=rng.randint(0, 21))
                due_date = max(today + timedelta(days=1), issued_date + timedelta(days=rng.randint(14, 45)))
            elif status_key == "paid":
                issued_date = today - timedelta(days=rng.randint(45, 730))
                due_date = issued_date + timedelta(days=30)
            else:
                issued_date = today - timedelta(days=rng.randint(0, 730))
                due_date = issued_date + timedelta(days=30)
            invoice_dates = {"issued_at": issued_date.isoformat(), "due_at": due_date.isoformat()}
        card_values = {}
        if (card_expiry_column and card_expiry_column["kind"] == "card_expiry"
                and card_status_column and card_status_column["kind"] == "status"):
            status_values = card_status_column.get("values", ("active", "suspended", "expired"))
            card_status = rng.choice(status_values)
            month_offset = rng.randint(1, 36) * (-1 if str(card_status).casefold() == "expired" else 1)
            absolute_month = today.year * 12 + today.month - 1 + month_offset
            expiry_month = absolute_month % 12 + 1
            expiry_year = (absolute_month // 12) % 100
            card_values = {"account_status": card_status,
                           "expiry": f"{expiry_month:02d}/{expiry_year:02d}"}
        order_values = {}
        vendor_values = {}
        if (vendor_risk_column and vendor_risk_column.get("kind") == "text"
                and vendor_risk_column.get("values")
                and vendor_cost_column and vendor_cost_column.get("kind") == "decimal"):
            risk_tier = rng.choice(vendor_risk_column["values"])
            risk_key = str(risk_tier).casefold()
            risk_cost_ranges = {
                "low": (1000, 100000), "standard": (10000, 500000),
                "elevated": (50000, 2000000),
            }
            cost_min, cost_max = float(vendor_cost_column["min"]), float(vendor_cost_column["max"])
            tier_min, tier_max = risk_cost_ranges.get(risk_key, (cost_min, cost_max))
            bounded_min, bounded_max = max(cost_min, tier_min), min(cost_max, tier_max)
            if 0 < bounded_min <= bounded_max:
                annual_cost = round(math.exp(rng.uniform(math.log(bounded_min), math.log(bounded_max))), 2)
                vendor_values["annual_cost"] = min(bounded_max, max(bounded_min, annual_cost))
            vendor_values["risk_tier"] = risk_tier
            if vendor_review_column and vendor_review_column.get("kind") == "date":
                review_age = {"low": (90, 730), "standard": (30, 365),
                              "elevated": (0, 90)}.get(risk_key, (0, 730))
                vendor_values["reviewed_at"] = (today - timedelta(days=rng.randint(*review_age))).isoformat()
        if (order_item_column and order_item_column.get("kind") == "text"
                and order_item_column.get("values")
                and order_quantity_column and order_quantity_column.get("kind") == "integer"
                and order_total_column and order_total_column.get("kind") == "decimal"):
            item = rng.choice(order_item_column["values"])
            quantity = rng.randint(int(order_quantity_column["min"]), int(order_quantity_column["max"]))
            price_ranges = {
                "annual support": (120, 600), "field kit": (75, 450),
                "data migration": (300, 2500), "service renewal": (150, 1200),
                "hardware bundle": (250, 1800),
            }
            unit_low, unit_high = price_ranges.get(str(item).casefold(), (25, 2000))
            total_low, total_high = float(order_total_column["min"]), float(order_total_column["max"])
            unit_price = rng.uniform(unit_low, unit_high)
            total = min(total_high, max(total_low, unit_price * quantity))
            zero_decimal_currency = str(row_currency).strip().casefold() in ("jpy", "yen", "円")
            total = round(total, 0 if zero_decimal_currency else 2)
            order_values.update({"item": item, "quantity": quantity, "total": total})
        if (order_status_column and order_status_column["kind"] == "status"
                and ordered_at_column and ordered_at_column["kind"] == "date"):
            order_status = rng.choice(order_status_column.get(
                "values", ("pending", "processing", "shipped", "complete", "cancelled")))
            age_ranges = {
                "pending": (0, 14), "processing": (0, 30), "shipped": (1, 90),
                "complete": (5, 730), "cancelled": (0, 365),
            }
            minimum_age, maximum_age = age_ranges.get(str(order_status).casefold(), (0, 730))
            order_values = {"order_status": order_status,
                            "ordered_at": (today - timedelta(days=rng.randint(minimum_age, maximum_age))).isoformat()}
        ticket_values = {}
        if (ticket_status_column and ticket_status_column["kind"] == "status"
                and ticket_opened_column and ticket_opened_column["kind"] == "datetime"):
            ticket_status = rng.choice(ticket_status_column.get(
                "values", ("open", "pending", "in_progress", "resolved", "closed")))
            age_ranges = {
                "open": (0, 14), "pending": (0, 30), "in_progress": (0, 60),
                "resolved": (1, 180), "closed": (15, 730),
            }
            minimum_age, maximum_age = age_ranges.get(str(ticket_status).casefold(), (0, 730))
            opened_at = now - timedelta(days=rng.randint(minimum_age, maximum_age),
                                        seconds=rng.randrange(86400))
            ticket_values = {"ticket_status": ticket_status,
                             "opened_at": opened_at.isoformat(timespec="seconds")}
        employee_values = {}
        if (employee_status_column and employee_status_column["kind"] == "status"
                and employee_started_column and employee_started_column["kind"] == "date"):
            employee_status = rng.choice(employee_status_column.get(
                "values", ("onboarding", "active", "on_leave", "offboarded")))
            age_ranges = {
                "onboarding": (0, 45), "active": (30, 3650),
                "on_leave": (90, 3650), "offboarded": (30, 3650),
            }
            minimum_age, maximum_age = age_ranges.get(str(employee_status).casefold(), (0, 3650))
            employee_values = {"employment_status": employee_status,
                               "started_at": (today - timedelta(days=rng.randint(minimum_age, maximum_age))).isoformat()}
        asset_values = {}
        if (asset_name_column and asset_name_column.get("kind") == "text"
                and asset_name_column.get("values")
                and asset_category_column and asset_category_column.get("kind") == "text"
                and asset_category_column.get("values")):
            asset_name = rng.choice(asset_name_column["values"])
            category_map = {
                "workstation": ("it",), "network switch": ("network",),
                "test device": ("lab",), "office display": ("facilities",),
                "storage node": ("it", "network"),
            }
            valid_categories = {str(value).casefold(): value for value in asset_category_column["values"]}
            matches = [valid_categories[value] for value in category_map.get(str(asset_name).casefold(), ())
                       if value in valid_categories]
            category = rng.choice(matches or asset_category_column["values"])
            asset_values.update({"asset_name": asset_name, "category": category})
        if (asset_status_column and asset_status_column["kind"] == "status"
                and asset_checked_column and asset_checked_column["kind"] == "date"):
            asset_status = rng.choice(asset_status_column.get("values", ("active", "active", "pending", "archived")))
            age_ranges = {"active": (0, 180), "pending": (30, 365), "archived": (90, 730)}
            minimum_age, maximum_age = age_ranges.get(str(asset_status).casefold(), (0, 730))
            asset_values.update({"asset_status": asset_status,
                                 "checked_at": (today - timedelta(days=rng.randint(minimum_age, maximum_age))).isoformat()})
        cloud_values = {}
        if (cloud_service_column and cloud_service_column.get("kind") == "text"
                and cloud_service_column.get("values")
                and cloud_environment_column and cloud_environment_column.get("kind") == "text"
                and cloud_environment_column.get("values")
                and cloud_endpoint_column and cloud_endpoint_column.get("kind") == "domain"):
            service_name = rng.choice(cloud_service_column["values"])
            environment = rng.choice(cloud_environment_column["values"])
            service_slug = re.sub(r"[^a-z0-9]+", "-", str(service_name).casefold()).strip("-")[:40].rstrip("-")
            environment_slug = re.sub(r"[^a-z0-9]+", "-", str(environment).casefold()).strip("-")[:16].rstrip("-")
            if not service_slug:
                service_slug = "service-" + hashlib.sha256(str(service_name).encode("utf-8")).hexdigest()[:8]
            if not environment_slug:
                environment_slug = "env-" + hashlib.sha256(str(environment).encode("utf-8")).hexdigest()[:8]
            cloud_values = {"service_name": service_name, "environment": environment,
                            "endpoint": f"{service_slug}-{environment_slug}.example.invalid"}
        row = []
        for column in columns:
            kind = column["kind"]
            if kind == "company": value = company_values[column["name"]]
            elif column["name"].lower() in invoice_dates: value = invoice_dates[column["name"].lower()]
            elif column["name"].lower() in card_values: value = card_values[column["name"].lower()]
            elif column["name"].lower() in vendor_values: value = vendor_values[column["name"].lower()]
            elif column["name"].lower() in order_values: value = order_values[column["name"].lower()]
            elif column["name"].lower() in ticket_values: value = ticket_values[column["name"].lower()]
            elif column["name"].lower() in employee_values: value = employee_values[column["name"].lower()]
            elif column["name"].lower() in asset_values: value = asset_values[column["name"].lower()]
            elif column["name"].lower() in cloud_values: value = cloud_values[column["name"].lower()]
            elif column["name"].lower() == "payment_status" and invoice_status is not None: value = invoice_status
            elif column["name"].casefold() == "currency" and row_currency is not None: value = row_currency
            elif "values" in column:
                value = rng.choice(column["values"])
            elif kind == "id": value = i
            elif kind == "name": value = f"{given} {family}"
            elif kind == "email":
                email_domain = column.get("synthetic_email_domain", "example.invalid")
                value = f"{email_given.lower()}.{email_family.lower()}.{i}@{email_domain}"
            elif kind == "department": value = rng.choice(DEPARTMENTS_JA if japanese else DEPARTMENTS)
            elif kind == "integer": value = rng.randint(int(column["min"]), int(column["max"]))
            elif kind == "decimal":
                low, high = float(column["min"]), float(column["max"])
                if (column["name"].casefold() in {
                        "total", "subtotal", "amount", "annual_cost", "price", "balance", "revenue"
                } and 0 < low <= high):
                    # Financial amounts usually cluster toward smaller values;
                    # log-uniform sampling avoids the conspicuous high-value
                    # concentration produced by a linear uniform distribution.
                    value = math.exp(rng.uniform(math.log(low), math.log(high)))
                    zero_decimal_currency = str(row_currency).strip().casefold() in ("jpy", "yen", "円")
                    value = round(value, 0 if zero_decimal_currency else 2)
                    value = min(high, max(low, value))
                else:
                    value = min(high, max(low, round(rng.uniform(low, high), 2)))
            elif kind == "date": value = (today - timedelta(days=rng.randrange(731))).isoformat()
            elif kind == "datetime": value = (now - timedelta(seconds=rng.randrange(731 * 86400))).isoformat()
            elif kind == "status": value = rng.choice(("active", "active", "pending", "archived"))
            elif kind == "uuid": value = str(uuid.uuid4())
            elif kind == "phone": value = f"+1-202-555-01{rng.randrange(100):02d}"
            elif kind == "domain":
                if associated_company:
                    normalized = re.sub(r"[\W_]+", "-", associated_company.casefold(), flags=re.UNICODE).strip("-")
                    try:
                        stem = normalized.encode("idna").decode("ascii").lower()
                    except UnicodeError:
                        stem = ""
                    if not stem:
                        stem = "org-" + hashlib.sha256(associated_company.encode("utf-8")).hexdigest()[:8]
                    elif len(stem) > 39:
                        digest = hashlib.sha256(associated_company.encode("utf-8")).hexdigest()[:8]
                        stem = stem[:30].rstrip("-") + "-" + digest
                    value = f"{stem}-{i}.example.invalid"
                else:
                    value = f"{rng.choice(('archive','billing','portal','service','vault'))}-{i}.example.invalid"
                if column["name"].casefold() == "login_url":
                    domain = column.get("vault_decoy_domain")
                    if domain:
                        service_index = next((index for index, previous in enumerate(columns[:len(row)])
                                              if previous["name"].casefold() == "service_name"), None)
                        service = str(row[service_index]) if service_index is not None else "vault"
                        stem = re.sub(r"[^a-z0-9]+", "-", service.casefold()).strip("-")[:48].strip("-") or "vault"
                        path = VAULT_LOGIN_PATHS.get(stem, "/login")
                        value = f"https://{stem}.{domain}{path}"
                    else:
                        service_index = next((index for index, previous in enumerate(columns[:len(row)])
                                              if previous["name"].casefold() == "service_name"), None)
                        service = str(row[service_index]) if service_index is not None else "Vault"
                        stem = re.sub(r"[^a-z0-9]+", "-", service.casefold()).strip("-")[:48].strip("-") or "vault"
                        value = f"https://{stem}.example.invalid{VAULT_LOGIN_PATHS.get(stem, '/login')}"
            # Keep references visibly nonfunctional, while making collisions
            # negligible even for the 10,000-row maximum database template.
            elif kind == "card_reference": value = "TEST-NOT-A-PAN-" + secrets.token_hex(6).upper()
            elif kind == "card_expiry": value = f"{rng.randint(1,12):02d}/{(today.year + rng.randint(1,5)) % 100:02d}"
            elif kind == "test_postal": value = f"TEST-{rng.randrange(10000,99999)}"
            elif kind == "credential_preview":
                alphabet = string.ascii_lowercase + string.ascii_uppercase + string.digits + "!@#$%+-_"
                value_chars = [secrets.choice(string.ascii_lowercase), secrets.choice(string.ascii_uppercase),
                               secrets.choice(string.digits), secrets.choice("!@#$%+-_")]
                value_chars.extend(secrets.choice(alphabet) for _ in range(14))
                secrets.SystemRandom().shuffle(value_chars)
                value = "".join(value_chars)
            elif kind == "currency": value = rng.choice(("JPY", "USD", "EUR"))
            elif kind == "documentation_ip": value = f"192.0.2.{rng.randint(1,254)}"
            elif kind == "text":
                topics = ("年次確認", "アカウント更新", "契約更新", "サービス移行") if japanese else (
                    "Annual review", "Account renewal", "Contract update", "Service migration")
                departments = DEPARTMENTS_JA if japanese else DEPARTMENTS
                value = f"{rng.choice(topics)} / {rng.choice(departments)}"
            else: value = f"{rng.choice(('Annual review', 'Account renewal', 'Contract update', 'Service migration'))} / {rng.choice(DEPARTMENTS)}"
            row.append(value)
        yield row


def sqlite_bytes(table, columns, data, url="", connection_table=None, connection_name="archive", language="ja"):
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
        if name.casefold() in column_names or not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(translate("columns_error", language))
        column_names.add(name.casefold())
    connection = sqlite3.connect(":memory:")
    try:
        # Identifiers were allow-listed above; values are always parameters.
        definitions = ", ".join(
            f'"{column["name"]}" {KINDS[column["kind"]]}'
            + (" NOT NULL PRIMARY KEY" if column["name"].casefold() == "id" and column["kind"] == "id"
               else " NOT NULL")
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
        indexed_names = {"email", "domain", "status", "account_status", "record_status",
                         "payment_status", "order_status", "ticket_status", "employment_status"}
        for position, column in enumerate(columns):
            if column["name"].casefold() in indexed_names:
                index_name = f'idx_{table[:20]}_{position:02d}_{column["name"][:20]}'
                connection.execute(f'CREATE INDEX "{index_name}" ON "{table}" ("{column["name"]}")')
                enforce_size_limit()
        if url:
            if connection_table is not None:
                connection_table = identifier(connection_table, language)
            metadata_table = connection_table or "service_connections"
            if metadata_table.casefold() == table.casefold():
                metadata_table = next(
                    candidate for candidate in ("archive_connections", "connection_registry", "external_connections")
                    if candidate.casefold() != table.casefold()
                )
            connection.execute(f'CREATE TABLE "{metadata_table}" (name TEXT PRIMARY KEY, endpoint TEXT NOT NULL)')
            connection.execute(f'INSERT INTO "{metadata_table}" VALUES (?, ?)', (connection_name, url))
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
    if not isinstance(template_id, str) or template_id not in (*DATABASE_TEMPLATES, "custom"):
        raise ValueError(translate("columns_error", language))
    template = DATABASE_TEMPLATES.get(template_id, DATABASE_TEMPLATES["customers"])
    configured = dict(settings)
    configured.setdefault("table", template["table"])
    configured.setdefault("columns", template["columns"])
    table, columns = validate_schema(configured, language)
    email_domain = vault_decoy_domain(settings.get("email_domain", ""),
                                      settings.get("email_domain_authorized", False), language)
    if email_domain:
        email_columns = [column for column in columns if column["kind"] == "email"]
        if not email_columns:
            raise ValueError(translate("email_domain_schema", language))
        for column in email_columns:
            column["synthetic_email_domain"] = email_domain
    if template_id == "passwords":
        domain = vault_decoy_domain(settings.get("vault_domain", ""),
                                    settings.get("vault_domain_authorized", False), language)
        if domain:
            login_column = next((column for column in columns
                                 if column["name"].casefold() == "login_url"), None)
            if login_column is None or login_column["kind"] != "domain":
                raise ValueError(translate("vault_domain_schema", language))
            login_column["vault_decoy_domain"] = domain
    return table, columns, rows
